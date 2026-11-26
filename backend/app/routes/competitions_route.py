"""Global Competitions API (Phase 5)."""

from __future__ import annotations

from fastapi import APIRouter

from .. import competitions

router = APIRouter()


@router.get("")
def list_all() -> list[dict]:
    return competitions.list_competitions()


@router.get("/{name}/team")
def team(name: str) -> dict:
    return {"competition": name, "team": competitions.team_plan(name), "checklist": competitions.checklist(name)}


@router.post("/{name}/checklist")
def checklist(name: str, body: dict) -> dict:
    return {"ok": True, "checklist": competitions.set_checklist(name, body.get("stage", ""), bool(body.get("done")))}


@router.post("")
def create(body: dict) -> dict:
    return {"ok": True, "competition": competitions.add(body)}
