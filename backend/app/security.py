"""Authenticate the local API before any HTTP or WebSocket handler runs."""

import hmac
import os
import time
from collections import deque

from starlette.responses import JSONResponse

_RATE_LIMIT_PER_MINUTE = int(os.environ.get("AGENTDESK_RATE_LIMIT", "240"))
_rate_buckets: dict[str, deque] = {}

def _rate_limited(client: str) -> bool:
    now = time.monotonic()
    bucket = _rate_buckets.setdefault(client, deque())
    while bucket and now - bucket[0] > 60:
        bucket.popleft()
    if len(bucket) >= _RATE_LIMIT_PER_MINUTE:
        return True
    bucket.append(now)
    return False


class LocalAccessMiddleware:
    def __init__(self, app):
        self.app = app

    def _sdk_token(self) -> bytes:
        """Stable per-user token for the browser control plane (external clients)."""
        try:
            from .browser_sdk_auth import token as sdk_token
            return (sdk_token() or "").encode()
        except Exception:
            return b""

    async def __call__(self, scope, receive, send):
        kind = scope['type']
        if kind not in ('http', 'websocket'):
            return await self.app(scope, receive, send)
        headers = dict(scope['headers'])
        origin = headers.get(b'origin', b'')
        # Packaged Electron loads the UI from file:// and its WebSocket sends
        # Origin: file:// (or null). Both are local, token-authenticated contexts.
        allowed_origins = {
            b'', b'null', b'file://',
            b'http://127.0.0.1:5173', b'http://localhost:5173',
        }
        token = os.environ.get('AGENTDESK_API_TOKEN', '').encode()
        credentials = headers.get(b'authorization', b'')
        path = scope.get("path", "")
        # Browser control plane: the desktop token works, and so does the stable
        # SDK token (for C++/C#/JS clients that attach without restarting the app).
        sdk_paths = path.startswith("/api/browser/sdk") or path.startswith("/api/browser/bidi")
        sdk_token = self._sdk_token() if sdk_paths else b""
        query_token = b""
        if sdk_paths and kind == "http":
            raw_query = scope.get("query_string", b"")
            for part in raw_query.split(b"&"):
                if part.startswith(b"token="):
                    query_token = part[6:]
                    break
        if kind == "http" and path.startswith("/v1/"):
            gateway_token = os.environ.get("AGENTDESK_GATEWAY_TOKEN", "").encode()
            if origin or not gateway_token or not hmac.compare_digest(credentials, b"Bearer " + gateway_token):
                return await JSONResponse({"detail": "AgentDesk integration authorization required"}, 401)(scope, receive, send)
            return await self.app(scope, receive, send)
        if kind == 'websocket':
            protocols = scope.get('subprotocols', [])
            candidate = next((p[6:] for p in protocols if p.startswith('token.')), '')
            credentials = b'Bearer ' + candidate.encode()
            if 'agentdesk' not in protocols and not (sdk_token and candidate.encode() == sdk_token):
                credentials = b''
        client = scope.get("client")[0] if scope.get("client") else "local"
        if kind == 'http' and _rate_limited(str(client)):
            return await JSONResponse({'detail': 'Rate limit exceeded'}, 429)(scope, receive, send)
        origin_ok = origin in allowed_origins or origin.startswith(b'file://')
        # The BiDi/CDP control plane is used by local native clients that do not
        # send an Origin header, so origin is not required there — the token is.
        if sdk_paths:
            origin_ok = True
        def _matches(secret: bytes) -> bool:
            if not secret:
                return False
            if hmac.compare_digest(credentials, b"Bearer " + secret):
                return True
            if query_token and hmac.compare_digest(query_token, secret):
                return True
            return False
        authorized = False
        if token and _matches(token):
            authorized = True
        elif sdk_token and _matches(sdk_token):
            authorized = True
        if not origin_ok or not authorized:
            if kind == 'websocket':
                await send({'type': 'websocket.close', 'code': 1008})
                return
            return await JSONResponse({'detail': 'AgentDesk desktop authorization required'}, 403)(scope, receive, send)
        if kind == 'http':
            try:
                from . import telemetry as _telemetry
                _telemetry.counter('agentdesk_http_requests_total', route=path.split('?', 1)[0])
            except Exception:
                pass
        return await self.app(scope, receive, send)
