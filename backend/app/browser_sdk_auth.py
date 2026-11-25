"""Capability token for the browser control plane.

The desktop token in ``AGENTDESK_API_TOKEN`` rotates on every app launch, which
is right for the UI but awkward for an external C++/C#/JS program that wants to
drive the browser. This module keeps a stable, per-user token on disk so those
clients can authenticate without restarting AgentDesk.

The token grants control of the *local* browser only (same privilege as the
account running AgentDesk). It is stored in the user's AgentDesk data folder
and is only accepted on the ``/api/browser/sdk`` and ``/api/browser/bidi``
routes.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path

from .config import DATA_DIR

TOKEN_FILE = DATA_DIR / "browser-sdk.token"


def _read() -> str:
    try:
        value = TOKEN_FILE.read_text(encoding="utf-8").strip()
        if value:
            return value
    except OSError:
        pass
    return ""


def ensure_token() -> str:
    """Return the browser SDK token, creating it on first use."""
    token = _read()
    if token:
        return token
    token = secrets.token_hex(24)
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        TOKEN_FILE.write_text(token, encoding="utf-8")
        try:
            os.chmod(TOKEN_FILE, 0o600)
        except OSError:
            pass
    except OSError:
        pass
    return token


def token() -> str:
    return _read() or ensure_token()
