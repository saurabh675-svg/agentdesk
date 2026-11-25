"""Structured logging + diagnostics snapshots for AgentDesk.

This module is **additive** — it doesn't replace the existing log files
(`data/backend.log`, `data/health.log`) created by Electron / uvicorn. It
appends JSON lines to `data/diagnostics.jsonl` and exposes a redacted
snapshot for the `/api/diagnostics` endpoint.

Use `agentdesk_log(level, event, **fields)` from anywhere in the backend to
record a structured event. Use `agentdesk_snapshot()` from a route handler.
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from contextlib import suppress
from pathlib import Path
from typing import Any, Callable

from .config import DATA_DIR

DIAG_FILE = DATA_DIR / "diagnostics.jsonl"
MAX_FILE_BYTES = 2_000_000  # rotate after ~2 MB


def _safe_json_default(value: Any) -> Any:
    """Fallback for objects that don't serialize by default."""
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return repr(value)


def _rotate_if_needed() -> None:
    try:
        if DIAG_FILE.exists() and DIAG_FILE.stat().st_size > MAX_FILE_BYTES:
            rotated = DIAG_FILE.with_suffix(".jsonl.1")
            if rotated.exists():
                rotated.unlink()
            DIAG_FILE.rename(rotated)
    except Exception:
        pass


def agentdesk_log(level: str, event: str, **fields: Any) -> None:
    """Append a structured JSON line to `data/diagnostics.jsonl`.

    Best-effort only — never raises. Safe to call from any code path.
    """
    try:
        DIAG_FILE.parent.mkdir(parents=True, exist_ok=True)
        _rotate_if_needed()
        record = {
            "ts": round(time.time(), 3),
            "level": str(level).lower(),
            "event": str(event),
            "fields": {k: _safe_json_default(v) for k, v in fields.items()},
        }
        with DIAG_FILE.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except Exception:
        # Last-ditch: print to stderr but don't raise.
        print("[agentdesk_log failed]", file=sys.stderr, flush=True)


def _redact(value: Any) -> Any:
    """Redact secrets detected by their key/field name."""
    if isinstance(value, dict):
        return {k: ("***" if _looks_secret(k) else _redact(v)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact(v) for v in value]
    return value


import uuid as _uuid


def new_trace_id() -> str:
    """Lightweight trace id (no OpenTelemetry dependency)."""
    return _uuid.uuid4().hex[:16]


_SECRET_FRAGMENTS = (
    "api_key", "apikey", "secret", "token", "password", "auth", "credential",
)


def _looks_secret(field: str) -> bool:
    f = (field or "").lower()
    return any(part in f for part in _SECRET_FRAGMENTS)


def _status_or_error(fn: Callable[[], Any], default: Any = None) -> Any:
    """Run a status probe; never raise."""
    try:
        return fn()
    except Exception as exc:
        return {"error": str(exc)[:200]}


def agentdesk_snapshot() -> dict:
    """Build a redacted diagnostics snapshot for `/api/diagnostics`.

    The snapshot purposely avoids any code path that could dump a real
    API key into the response.
    """
    from . import automations, brain as _brain, provider_health
    from .config import load_settings
    from .engine import llama_local
    from .mcp_manager import mcp_manager
    from .selfwatch import read_recent_errors
    from .tools.browser import browser

    settings = load_settings()
    provider_state = _status_or_error(provider_health.summary, {})
    # Never spawn the local model from a diagnostics probe: report what is
    # already running plus the configured backend instead.
    local_state = _status_or_error(
        lambda: {**llama_local.backend_status(), "available": llama_local.is_available()},
        {},
    )

    browser_state = _status_or_error(lambda: browser.last_state or {})
    mcp_state = _status_or_error(lambda: mcp_manager.status())
    watchdog = _status_or_error(lambda: read_recent_errors(20))
    backlog = _status_or_error(lambda: automations.due_automations(limit=5))
    brain_stats = _status_or_error(_brain.get_brain_stats, {})

    return _redact({
        "generated_at": round(time.time(), 3),
        "version": os.environ.get("AGENTDESK_VERSION", "0.7.0"),
        "providers": provider_state,
        "local_model": local_state,
        "browser": browser_state,
        "mcp": mcp_state,
        "watchdog_recent": watchdog,
        "automations_due": backlog,
        "brain": brain_stats,
        "settings_keys_known": sorted(settings.get("keys", {}).keys())
        if isinstance(settings.get("keys"), dict)
        else [],
    })


__all__ = ["agentdesk_log", "agentdesk_snapshot", "new_trace_id"]
