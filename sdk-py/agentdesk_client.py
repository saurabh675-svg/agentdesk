"""Small standard-library client for the AgentDesk integration API.

Version: 0.4.0
NOTE: `/v1/*` requires the `AGENTDESK_GATEWAY_TOKEN` env value, which is
DIFFERENT from the desktop bearer token used for `/api/*`.
"""
import json
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

__version__ = "0.4.0"


class AgentDeskError(RuntimeError):
    pass


class AgentDeskClient:
    def __init__(self, token: str, base_url: str = "http://127.0.0.1:8756/v1", timeout: float = 180, retries: int = 2):
        self.token = token
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.retries = retries

    def _request(self, path: str, body: dict | None = None):
        data = json.dumps(body).encode() if body is not None else None
        last_exc = None
        for attempt in range(self.retries + 1):
            try:
                return urlopen(Request(self.base_url + path, data=data, headers={
                    "Authorization": f"Bearer {self.token}", "Content-Type": "application/json",
                }), timeout=self.timeout)
            except HTTPError as exc:
                detail = exc.read().decode("utf-8", "replace")[:500]
                raise AgentDeskError(f"AgentDesk HTTP {exc.code}: {detail}") from exc
            except (URLError, TimeoutError, OSError) as exc:
                last_exc = exc
                if attempt < self.retries:
                    time.sleep(0.5 * (2 ** attempt))
                    continue
                raise AgentDeskError(f"AgentDesk unreachable: {exc}") from exc
        assert last_exc is not None
        raise AgentDeskError(str(last_exc))

    def models(self):
        with self._request("/models") as response:
            return json.load(response)

    def complete(self, messages: list[dict], model: str = "agentdesk-local", **options):
        with self._request("/chat/completions", {**options, "messages": messages, "model": model, "stream": False}) as response:
            return json.load(response)

    def stream(self, messages: list[dict], model: str = "agentdesk-local", **options):
        with self._request("/chat/completions", {**options, "messages": messages, "model": model, "stream": True}) as response:
            for line in response:
                if not line.startswith(b"data: "):
                    continue
                payload = line[6:].strip()
                if payload == b"[DONE]":
                    return
                event = json.loads(payload)
                if "error" in event:
                    raise RuntimeError(event["error"]["message"])
                yield event
        raise RuntimeError("The AgentDesk stream ended unexpectedly.")
