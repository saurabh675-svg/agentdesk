"""Downloads ingestion API (Phase 4)."""

from __future__ import annotations

from fastapi import APIRouter

from .. import downloads_ingest

router = APIRouter()


@router.post("/scan")
def scan(force: bool = False) -> dict:
    return {"ok": True, **downloads_ingest.scan(force=force)}
