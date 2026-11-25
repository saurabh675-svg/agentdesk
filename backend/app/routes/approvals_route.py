from fastapi import APIRouter

from .. import db

router = APIRouter()


@router.get("")
def list_approvals(limit: int = 100, session_id: int | None = None) -> list[dict]:
    return db.list_approvals(limit=limit, session_id=session_id)