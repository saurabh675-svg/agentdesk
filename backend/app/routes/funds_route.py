"""Funds & Consultancy API (Phase 6)."""

from __future__ import annotations

from fastapi import APIRouter

from .. import funds

router = APIRouter()


@router.get("/funds")
def funds_list(owner: str = "") -> list[dict]:
    return funds.list_funds(owner)


@router.get("/funds/{name}/guidance")
def guidance(name: str, owner: str = "Student") -> dict:
    return funds.owner_guidance(owner, name)


@router.get("/projects")
def projects() -> list[dict]:
    return funds.list_projects()


@router.post("/projects")
def create_project(body: dict) -> dict:
    return {"ok": True, "project": funds.add_project(body)}


@router.post("/export-doc")
def export_doc(body: dict) -> dict:
    path = funds.export_checklist_doc(str(body.get("title", "submission")), dict(body.get("sections") or {}))
    return {"ok": True, "path": str(path)}
