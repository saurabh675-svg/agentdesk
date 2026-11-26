"""Auto-discovery (Phase 2): MCP servers + skill packs from Downloads."""

from __future__ import annotations

import json
import shutil
from pathlib import Path


def _downloads() -> Path:
    return Path.home() / "Downloads"


def discover_mcp_servers() -> list[dict]:
    """Return MCP configs referenced by Downloads files (does not execute)."""
    root = _downloads()
    found: list[dict] = []
    if not root.exists():
        return found
    for cand in sorted(root.glob("mcp-*.json")) + sorted(root.glob("*mcp*.json")):
        try:
            data = json.loads(cand.read_text(encoding="utf-8"))
            if isinstance(data, dict) and ("command" in data or "url" in data):
                found.append({"source": str(cand), **data})
        except Exception:
            continue
    return found


def apply_mcp_servers() -> dict:
    """Merge discovered servers into the live MCP config (idempotent)."""
    from .mcp_manager import load_config, save_config

    servers = load_config()
    known = {s.get("id") for s in servers}
    added: list[str] = []
    for disc in discover_mcp_servers():
        sid = str(disc.get("id") or Path(disc["source"]).stem)
        if sid in known:
            continue
        servers.append({
            "id": sid,
            "name": str(disc.get("name") or sid),
            "command": str(disc.get("command") or ""),
            "args": disc.get("args") or [],
            "env": disc.get("env") or {},
            "url": str(disc.get("url") or ""),
            "headers": disc.get("headers") or {},
            "enabled": True,
        })
        added.append(sid)
    if added:
        save_config(servers)
    return {"discovered": len(discover_mcp_servers()), "added": added}


def discover_skill_packs() -> list[Path]:
    """Candidate skill-pack folders/zips in Downloads."""
    root = _downloads()
    if not root.exists():
        return []
    cands = list(root.glob("*.zip"))
    for d in root.iterdir():
        if d.is_dir() and (d / "SKILL.md").exists():
            cands.append(d)
    return cands


def apply_skill_packs() -> dict:
    """Rescan Downloads for new skill packs (preview only; install stays gated)."""
    from . import skills_import

    preview: list[dict] = []
    for cand in discover_skill_packs():
        try:
            preview.extend(skills_import.scan(cand))
        except Exception:
            continue
    return {"packs": [str(p) for p in discover_skill_packs()], "preview": preview[:20]}


__all__ = ["discover_mcp_servers", "apply_mcp_servers", "discover_skill_packs", "apply_skill_packs"]
