"""Funds + Consultancy store (Phase 6): live opportunities + owner guidance.

Local JSON at DATA_DIR/funds.json. Owner types: Student / Professional /
Researcher / NGO / Startup. Google Docs automation degrades to a local
docx export (python-docx when available, else plain .docx passthrough
of formatted text) so the flow never hard-depends on OAuth.
"""

from __future__ import annotations

import json
from pathlib import Path

from .config import DATA_DIR
from . import missions

_FILE = DATA_DIR / "funds.json"

SEED_FUNDS: list[dict] = [
    {"name": "NSF Earth Sciences (EAR)", "url": "https://www.nsf.gov/funding/opportunities/ear",
     "sector": "earth", "ticket": "1M+", "deadline": "2026-12-01", "eligible": ["Researcher", "Professional"]},
    {"name": "ESA Open-Space Grant (GIS)", "url": "https://www.esa.int", "sector": "geoinformatics",
     "ticket": "100k", "deadline": "2026-09-15", "eligible": ["Researcher"]},
    {"name": "UNDP GEF Small Grants (Env)", "url": "https://sgp.undp.org", "sector": "environment",
     "ticket": "50k", "deadline": "2026-08-01", "eligible": ["NGO", "Student"]},
    {"name": "Civil Engineering Resilience Fund", "url": "https://www.asce.org", "sector": "engineering",
     "ticket": "25k", "deadline": "2026-10-01", "eligible": ["Professional", "Startup"]},
    {"name": "Remote-Sensing Fellowship (GIS)", "url": "https://www.maxar.com", "sector": "geoinformatics",
     "ticket": "10k", "deadline": "2026-07-01", "eligible": ["Student", "Researcher"]},
]


def _load() -> dict:
    try:
        return json.loads(_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"funds": [], "projects": []}


def _save(data: dict) -> None:
    _FILE.parent.mkdir(parents=True, exist_ok=True)
    _FILE.write_text(json.dumps(data, indent=1), encoding="utf-8")


def list_funds(owner: str = "") -> list[dict]:
    data = _load()
    if not data["funds"]:
        data["funds"] = SEED_FUNDS
        _save(data)
    if not owner:
        return data["funds"]
    out = []
    for f in data["funds"]:
        eligible = owner in (f.get("eligible") or [])
        out.append({**f, "fit": "eligible" if eligible else "not eligible", "owner": owner})
    return out


def owner_guidance(owner: str, fund_name: str) -> dict:
    """Next-step guidance for a given owner type + fund."""
    for f in list_funds():
        if f["name"] == fund_name:
            ok = owner in (f.get("eligible") or [])
            nxt = [
                "Confirm eligibility window & hard deadline",
                "File LOI / concept note",
                "Draft proposal to the funder template",
                "Rubric-review (verify_work), then submit",
            ] if ok else ["Not eligible as " + owner, "Check similar fund for this owner type"]
            return {"fund": f, "owner": owner, "eligible": ok, "next_steps": nxt}
    return {"error": "fund not found"}


def list_projects() -> list[dict]:
    return _load().get("projects", [])


def add_project(project: dict) -> dict:
    """Consultancy project (Estimate -> Contract -> Deliver -> Invoice)."""
    data = _load()
    project = {"stage": "Estimate", **project}
    data["projects"].append(project)
    _save(data)
    return project


def export_checklist_doc(title: str, sections: dict[str, str]) -> Path:
    """Write a formatted .docx (Google Docs automation fallback).

    Prefers python-docx; falls back to a plain-text .docx substitute
    so the flow is testable without the optional dependency.
    """
    out = DATA_DIR / "exports" / (title.replace("/", "-")[:60] + ".docx")
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        from docx import Document  # type: ignore

        doc = Document()
        doc.add_heading(title, level=0)
        for h, body in sections.items():
            doc.add_heading(h, level=1)
            doc.add_paragraph(body)
        doc.save(str(out))
    except ImportError:
        out.write_text(f"{title}\n\n" + "\n\n".join(f"## {k}\n{v}" for k, v in sections.items()), encoding="utf-8")
    return out


__all__ = ["list_funds", "owner_guidance", "list_projects", "add_project", "export_checklist_doc"]
