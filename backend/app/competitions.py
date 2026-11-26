"""Global Competitions store (Phase 5): catalog + rules + team workflow.

Local JSON store at DATA_DIR/competitions.json. Rules are hand-checked
then automated (browser structured_extract fills `rules`). The
multi-agent workflow composes existing sub-agent profiles:

  researcher -> doc-writer -> code-reviewer -> formatter -> submission-pack

No auto-submit: the pack stops at a human Submit step.
"""

from __future__ import annotations

import json
from pathlib import Path

from .config import DATA_DIR

_FILE = DATA_DIR / "competitions.json"

SEED: list[dict] = [
    {"name": "FOSS4G Community Challenge", "url": "https://foss4g.org", "sector": "geoinformatics",
     "prize": "Travel grants", "deadline": "2026-09-01", "eligibility": ["Professional", "Researcher", "Student"]},
    {"name": "Global Geospatial Challenge (GIS)", "url": "https://www.geospatialworld.org/challenge", "sector": "geoinformatics",
     "prize": "Research prize", "deadline": "2026-10-15", "eligibility": ["Researcher", "Professional"]},
    {"name": "Dr. Wu Impact Challenge", "url": "https://drwu.com/impact", "sector": "engineering",
     "prize": "100k USD", "deadline": "2026-11-01", "eligibility": ["Professional", "Startup"]},
    {"name": "Nvidia Indegree Awards (AI)", "url": "https://developer.nvidia.com/indegree", "sector": "engineering",
     "prize": "GPU grants", "deadline": "2026-08-20", "eligibility": ["Researcher", "Startup"]},
    {"name": "Earth Day Code Sprints", "url": "https://earthday.org", "sector": "environment",
     "prize": "Micro-grants", "deadline": "2026-06-01", "eligibility": ["Student", "NGO"]},
]

TEAM = ["researcher", "doc-writer", "code-reviewer", "formatter", "submission-pack"]


def _load() -> dict:
    try:
        return json.loads(_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"items": [], "checklists": {}}


def _save(data: dict) -> None:
    _FILE.parent.mkdir(parents=True, exist_ok=True)
    _FILE.write_text(json.dumps(data, indent=1), encoding="utf-8")


def list_competitions() -> list[dict]:
    data = _load()
    if not data["items"]:
        data["items"] = SEED
        _save(data)
    return data["items"]


def get(name: str) -> dict | None:
    for c in list_competitions():
        if c["name"] == name:
            return c
    return None


def add(comp: dict) -> dict:
    data = _load()
    data["items"].append(comp)
    _save(data)
    return comp


def set_checklist(name: str, stage: str, done: bool) -> dict:
    data = _load()
    data["checklists"].setdefault(name, {})[stage] = bool(done)
    _save(data)
    return data["checklists"][name]


def checklist(name: str) -> dict:
    return _load()["checklists"].get(name, {})


def team_plan(name: str) -> list[dict]:
    """Multi-agent steps for a competition (grand-master workflow)."""
    steps = [
        ("researcher", f"Extract rules, past winners and eligibility for {name}"),
        ("doc-writer", f"Draft solution structured to the competition sections"),
        ("code-reviewer", "Review draft against rubric (verify_work); revise once if needed"),
        ("formatter", "Format submission pack (cover, TOC, references, PDF)"),
        ("submission-pack", "Halt at human Submit; never auto-submit"),
    ]
    return [{"role": r, "task": t} for r, t in steps]


__all__ = ["list_competitions", "get", "add", "set_checklist", "checklist", "team_plan"]
