"""Pinned missions: historical tasks the user wants kept and can run on demand."""

import time
import uuid
from pathlib import Path

from .config import DATA_DIR

MISSIONS_FILE = DATA_DIR / "missions.json"
MAX_MISSIONS = 50


def list_missions() -> list[dict]:
    if not MISSIONS_FILE.exists():
        return []
    try:
        import json

        data = json.loads(MISSIONS_FILE.read_text(encoding="utf-8"))
        return data.get("missions", [])
    except Exception:
        return []


def _save(missions: list[dict]) -> None:
    import json

    MISSIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    MISSIONS_FILE.write_text(json.dumps({"missions": missions, "updated_at": time.time()}, indent=2), encoding="utf-8")


def add_mission(name: str, prompt: str, session_id: int | None = None, goal: str = "", acceptance_criteria: str = "", expected_outputs: str = "") -> dict:
    now = time.time()
    mission = {
        "id": uuid.uuid4().hex[:12],
        "name": (name or "Pinned task").strip() or "Pinned task",
        "prompt": (prompt or "").strip(),
        "goal": (goal or "").strip(),
        "acceptance_criteria": (acceptance_criteria or "").strip(),
        "expected_outputs": (expected_outputs or "").strip(),
        "session_id": session_id,
        "status": "pinned",
        "created_at": now,
    }
    missions = [m for m in list_missions() if m.get("status") == "pinned"][:MAX_MISSIONS - 1] + [mission]
    _save(missions)
    return mission


def remove_mission(mission_id: str) -> dict:
    missions = [m for m in list_missions() if str(m.get("id") or "") != str(mission_id)]
    _save(missions)
    return {"ok": True}


def get_mission(mission_id: str) -> dict | None:
    for mission in list_missions():
        if str(mission.get("id") or "") == str(mission_id):
            return mission
    return None


def mission_session(mission: dict) -> int | None:
    return int(mission.get("session_id") or 0) or None
