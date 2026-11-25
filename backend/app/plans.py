"""Lightweight plan-then-act tracker: structured plans with per-step status.

Plans are persisted in data/plans.json and injected into the system prompt so the agent
can keep long tasks on track across turns.
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from .config import DATA_DIR

PLANS_FILE = DATA_DIR / "plans.json"
MAX_PLANS = 30


def _load() -> list[dict[str, Any]]:
    if not PLANS_FILE.exists():
        return []
    try:
        data = json.loads(PLANS_FILE.read_text(encoding="utf-8"))
        return data.get("plans", [])
    except Exception:
        return []


def _save(plans: list[dict[str, Any]]) -> None:
    PLANS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PLANS_FILE.write_text(json.dumps({"plans": plans, "updated_at": time.time()}, indent=2), encoding="utf-8")


def _normalize_steps(steps: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for index, step in enumerate(steps or []):
        if isinstance(step, str):
            title = step
            detail = ""
        elif isinstance(step, dict):
            title = str(step.get("title") or step.get("step") or f"Step {index + 1}")
            detail = str(step.get("detail") or step.get("description") or "")
        else:
            title = str(step)
            detail = ""
        out.append({"index": index, "title": title[:200], "detail": detail[:1000], "status": "pending", "result": ""})
    return out


def create_plan(name: str, steps: list[Any], session_id: int | None = None) -> dict[str, Any]:
    plans = _load()
    plan = {
        "id": uuid.uuid4().hex[:12],
        "name": (name or "Plan").strip() or "Plan",
        "session_id": session_id,
        "status": "active",
        "steps": _normalize_steps(steps),
        "created_at": time.time(),
        "updated_at": time.time(),
    }
    plans = [p for p in plans if p.get("status") == "active"][: MAX_PLANS - 1] + [plan]
    _save(plans)
    return plan


def list_plans(status: str | None = None) -> list[dict[str, Any]]:
    plans = _load()
    if status:
        plans = [p for p in plans if p.get("status") == status]
    return plans


def get_plan(plan_id: str) -> dict[str, Any] | None:
    for plan in _load():
        if str(plan.get("id")) == str(plan_id):
            return plan
    return None


def update_step(plan_id: str, step: int, status: str = "done", result: str = "") -> dict[str, Any] | None:
    plans = _load()
    for plan in plans:
        if str(plan.get("id")) != str(plan_id):
            continue
        steps = plan.get("steps") or []
        if step < 0 or step >= len(steps):
            return None
        steps[step]["status"] = status if status in {"pending", "in_progress", "done", "blocked"} else "done"
        if result:
            steps[step]["result"] = result[:2000]
        if all(s.get("status") == "done" for s in steps):
            plan["status"] = "complete"
        plan["updated_at"] = time.time()
        _save(plans)
        return plan
    return None


def plan_diff(plan_id: str) -> dict[str, Any] | None:
    """Diff current plan steps against the persisted revision history."""
    plan = get_plan(plan_id)
    if not plan:
        return None
    history = plan.get("history") or []
    current = plan.get("steps") or []
    previous = (history[-1].get("steps") if history else []) or []
    changed = []
    for idx, step in enumerate(current):
        prev = previous[idx] if idx < len(previous) else None
        if prev is None:
            changed.append({"index": idx, "change": "added", "title": step.get("title")})
        elif prev.get("status") != step.get("status") or prev.get("result") != step.get("result"):
            changed.append({"index": idx, "change": "modified", "title": step.get("title"), "from": prev.get("status"), "to": step.get("status")})
    return {"plan_id": plan_id, "changed": changed, "total": len(current)}


def context_block() -> str:
    active = [p for p in list_plans("active")]
    if not active:
        return ""
    lines = ["## Active plans"]
    for plan in active[:3]:
        done = sum(1 for s in plan.get("steps", []) if s.get("status") == "done")
        total = len(plan.get("steps", []))
        lines.append(f"- Plan '{plan['name']}' ({plan['id']}): {done}/{total} steps done")
        for step in plan.get("steps", []):
            if step.get("status") != "done":
                lines.append(f"  next: {step['title']}")
                break
    lines.append("Use plan_create / plan_update_step to keep long tasks structured.")
    return "\n".join(lines)[:1500]