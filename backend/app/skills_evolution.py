"""Skill evolution gate: propose → approve → install → (rollback | reject).

Ported from Hermas (MIT). Nothing lands in the live skills directory
without an explicit approval, and every install snapshots the previous
state for one-click rollback. The ledger lives in
``data/skills-evolution.json``; live skills stay in ``data/skills/<name>/``.
"""

from __future__ import annotations

import datetime
import json
import shutil
import threading
import uuid

from .config import DATA_DIR
from .diagnostics import agentdesk_log
from .skills import SKILLS_DIR

_LOCK = threading.Lock()
_PATH = DATA_DIR / "skills-evolution.json"


def _load() -> list:
    if _PATH.exists():
        try:
            data = json.loads(_PATH.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception:
            pass
    return []


def _save(items: list) -> None:
    tmp = _PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(items, indent=1), encoding="utf-8")
    tmp.replace(_PATH)


def list_proposals() -> list:
    with _LOCK:
        return _load()


def propose(name: str, description: str, files: dict, score: float = 0.5) -> dict:
    sk = {
        "id": "s" + uuid.uuid4().hex[:6],
        "name": (name or "unnamed-skill").strip()[:60],
        "description": (description or "").strip(),
        "files": {str(k)[:60]: str(v)[:200000] for k, v in (files or {}).items()},
        "score": max(0.0, min(1.0, float(score))),
        "status": "proposed",
        "created": datetime.datetime.now().isoformat(timespec="seconds"),
        "installed_at": None,
        "backup": None,
    }
    with _LOCK:
        db = _load()
        db.append(sk)
        _save(db)
    agentdesk_log("info", "skill_proposed", name=sk["name"], score=sk["score"])
    return sk


def approve(skill_id: str) -> dict | None:
    with _LOCK:
        db = _load()
        for s in db:
            if s["id"] == skill_id and s["status"] == "proposed":
                d = SKILLS_DIR / s["name"]
                backup = None
                if d.exists():
                    backup = SKILLS_DIR / f".backup-{s['name']}-{uuid.uuid4().hex[:4]}"
                    shutil.move(str(d), str(backup))
                    s["backup"] = backup.name
                d.mkdir(parents=True, exist_ok=True)
                for fname, content in (s.get("files") or {}).items():
                    p = (d / fname).resolve()
                    if not str(p).startswith(str(SKILLS_DIR.resolve())):
                        continue
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text(str(content), encoding="utf-8")
                s["status"] = "installed"
                s["installed_at"] = datetime.datetime.now().isoformat(timespec="seconds")
                _save(db)
                agentdesk_log("info", "skill_installed", name=s["name"], backup=backup.name if backup else "")
                return s
    return None


def reject(skill_id: str, reason: str = "") -> dict | None:
    with _LOCK:
        db = _load()
        for s in db:
            if s["id"] == skill_id and s["status"] == "proposed":
                s["status"] = "rejected"
                s["reject_reason"] = (reason or "rejected by operator")[:200]
                _save(db)
                agentdesk_log("info", "skill_rejected", name=s["name"])
                return s
    return None


def rollback(skill_id: str) -> dict | None:
    with _LOCK:
        db = _load()
        for s in db:
            if s["id"] == skill_id and s["status"] == "installed":
                d = SKILLS_DIR / s["name"]
                if d.exists():
                    shutil.rmtree(d)
                if s.get("backup"):
                    b = SKILLS_DIR / s["backup"]
                    if b.exists():
                        shutil.move(str(b), str(d))
                        s["backup"] = None
                s["status"] = "rolled_back"
                _save(db)
                agentdesk_log("info", "skill_rolled_back", name=s["name"])
                return s
    return None


def installed_names() -> list:
    with _LOCK:
        return [s["name"] for s in _load() if s["status"] == "installed"]
