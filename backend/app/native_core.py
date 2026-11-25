"""Native accelerator bridge (Rust `agentdesk_core`) with pure-Python fallbacks.

The app must never break because a native artifact is missing, so every
function here tries the compiled extension first and falls back to an
equivalent Python implementation. `active_backend()` reports which path is
live, and `/api/diagnostics` surfaces it.

Load order for the compiled module:

1. `agentdesk_core` next to this package (the installed layout)
2. `native/agentdesk_core/target/.../release` (development build)
3. `importlib` on ``sys.path`` (a wheel installed by pip)
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

_MODULE: Any = None
_LOAD_TRIED = False
_LOAD_ERROR = ""


def _candidate_paths() -> list[Path]:
    here = Path(__file__).resolve().parent
    out = [here / "agentdesk_core.dll", here / "agentdesk_core.pyd"]
    root = here.parents[2] if len(here.parents) > 2 else here.parent
    for rel in (
        "native/agentdesk_core/target/x86_64-pc-windows-gnu/release/agentdesk_core.dll",
        "native/agentdesk_core/target/release/agentdesk_core.dll",
        "native/agentdesk_core/target/release/libagentdesk_core.so",
        "native/agentdesk_core/target/release/libagentdesk_core.dylib",
    ):
        out.append(root / rel)
    return out


def _load() -> Any:
    global _MODULE, _LOAD_TRIED, _LOAD_ERROR
    if _LOAD_TRIED:
        return _MODULE
    _LOAD_TRIED = True
    if os.environ.get("AGENTDESK_DISABLE_NATIVE", "") == "1":
        _LOAD_ERROR = "disabled by AGENTDESK_DISABLE_NATIVE"
        return None
    try:
        import agentdesk_core as module  # type: ignore

        _MODULE = module
        return _MODULE
    except Exception as exc:
        _LOAD_ERROR = f"import failed: {exc}"
    for path in _candidate_paths():
        if not path.exists():
            continue
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location("agentdesk_core", path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                sys.modules["agentdesk_core"] = module
                _MODULE = module
                _LOAD_ERROR = ""
                return _MODULE
        except Exception as exc:
            _LOAD_ERROR = f"{path.name}: {exc}"
    return None


def active_backend() -> str:
    """``"rust"`` when the compiled extension is live, otherwise ``"python"``."""
    return "rust" if _load() is not None else "python"


def backend_info() -> dict:
    module = _load()
    return {
        "backend": "rust" if module is not None else "python",
        "version": getattr(module, "__version__", "") if module else "",
        "error": _LOAD_ERROR,
        "features": ["dom_diff", "content_ref", "scrub", "count_tokens"],
    }


# --------------------------------------------------------------------------- #
# DOM diff
# --------------------------------------------------------------------------- #
def _python_diff(old_payload: str, new_payload: str) -> list[dict]:
    """Pure-Python fallback for the DOM diff."""

    def parse(payload: str) -> list[dict]:
        try:
            data = json.loads(payload)
        except Exception:
            return []
        out: list[dict] = []

        def walk(node: Any) -> None:
            if not isinstance(node, dict):
                return
            children = node.get("children") or []
            for child in children:
                walk(child)
            out.append({
                "tag": str(node.get("tag") or "node"),
                "role": str(node.get("role") or ""),
                "name": str(node.get("name") or ""),
                "value": str(node.get("value") or ""),
            })

        for item in data if isinstance(data, list) else []:
            walk(item)
        return out

    def key_of(node: dict) -> str:
        return f"{node['tag']}|{node['role']}|{node['name']}"

    def content_hash(node: dict) -> str:
        payload = json.dumps(node, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def ref_of(node: dict) -> str:
        return hashlib.sha256(key_of(node).encode("utf-8")).hexdigest()[:8]

    old_nodes = {key_of(n): n for n in parse(old_payload)}
    new_nodes = {key_of(n): n for n in parse(new_payload)}
    entries: list[dict] = []
    for key, node in new_nodes.items():
        if key not in old_nodes:
            entries.append({"kind": "added", "ref_id": ref_of(node), "name": node["name"], "tag": node["tag"]})
        elif content_hash(old_nodes[key]) != content_hash(node):
            entries.append({"kind": "changed", "ref_id": ref_of(node), "name": node["name"], "tag": node["tag"]})
    for key, node in old_nodes.items():
        if key not in new_nodes:
            entries.append({"kind": "removed", "ref_id": ref_of(node), "name": node["name"], "tag": node["tag"]})
    return entries


def dom_diff(old_payload: str, new_payload: str) -> list[dict]:
    """Return the list of DOM changes between two snapshots."""
    module = _load()
    if module is not None:
        try:
            raw = module.diff(old_payload, new_payload)
            return json.loads(raw) if isinstance(raw, str) else list(raw)
        except Exception:
            pass
    return _python_diff(old_payload, new_payload)


def content_ref(payload: str) -> str:
    """Content-addressed reference for a snapshot (``ref:ab12cd34``)."""
    module = _load()
    if module is not None:
        try:
            value = module.content_ref(payload)
            if value:
                return f"ref:{value}"
        except Exception:
            pass
    try:
        data = json.loads(payload)
    except Exception:
        data = payload
    digest = hashlib.sha256(json.dumps(data, sort_keys=True).encode("utf-8")).hexdigest()
    return f"ref:{digest[:8]}"


# --------------------------------------------------------------------------- #
# Scrubbing
# --------------------------------------------------------------------------- #
_PATTERNS: list[tuple[str, str]] = [
    (r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[email]"),
    (r"(?i)bearer\s+[A-Za-z0-9._\-]{16,}", "Bearer [redacted]"),
    (r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*[\"']?[A-Za-z0-9._\-]{8,}[\"']?", r"\1=[redacted]"),
    (r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}", "[jwt]"),
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----", "[private-key]"),
    (r"\b[0-9a-fA-F]{32,}\b", "[hex-secret]"),
    (r"sk-[A-Za-z0-9]{20,}", "[api-key]"),
]


def _python_scrub(text: str) -> tuple[str, int]:
    count = 0
    out = text
    for pattern, replacement in _PATTERNS:
        compiled = re.compile(pattern)
        hits = len(compiled.findall(out))
        if hits:
            count += hits
            out = compiled.sub(replacement, out)
    return out, count


def scrub(text: str) -> tuple[str, int]:
    """Remove secrets and PII from tool output. Returns (text, redactions)."""
    module = _load()
    if module is not None:
        try:
            result = module.scrub(text)
            if isinstance(result, (list, tuple)) and len(result) == 2:
                return str(result[0]), int(result[1])
        except Exception:
            pass
    return _python_scrub(text)


def count_tokens(text: str) -> int:
    """Cheap token estimate used for cost guards."""
    module = _load()
    if module is not None:
        try:
            return int(module.count_tokens(text))
        except Exception:
            pass
    return max(len(text) // 4, len(text.split()) or 0)
