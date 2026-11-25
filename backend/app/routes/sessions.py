from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import db
from ..config import load_settings
from ..subagents import subagent_pool

router = APIRouter()


class SessionCreate(BaseModel):
    title: str = "New chat"
    workspace: str | None = None


class SessionUpdate(BaseModel):
    title: str | None = None
    workspace: str | None = None


@router.get("")
def list_sessions() -> list[dict]:
    return db.list_sessions()


@router.post("")
def create_session(body: SessionCreate) -> dict:
    workspace = body.workspace or load_settings().get("workspace")
    return db.create_session(title=body.title or "New chat", workspace=workspace)


@router.get("/{session_id}")
def get_session(session_id: int) -> dict:
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.patch("/{session_id}")
def update_session(session_id: int, body: SessionUpdate) -> dict:
    session = db.update_session(session_id, **body.model_dump(exclude_none=True))
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.delete("/{session_id}")
def delete_session(session_id: int) -> dict:
    db.delete_session(session_id)
    return {"ok": True}


@router.get("/{session_id}/messages")
def get_messages(session_id: int) -> list[dict]:
    return db.list_messages(session_id)


@router.get("/{session_id}/export")
def export_session(session_id: int) -> dict:
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session": session, "messages": db.list_messages(session_id), "archives": db.list_transcript_archives(session_id)}


class CompactBody(BaseModel):
    summary: str = ""


@router.post("/{session_id}/compact")
async def compact_session_route(session_id: int, body: CompactBody) -> dict:
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    summary = body.summary.strip()
    if not summary:
        raise HTTPException(status_code=422, detail="A summary is required to compact this conversation.")
    msg = db.compact_session(session_id, summary)
    return {"ok": True, "message": msg}


@router.post("/{session_id}/rewind-to/{message_id}")
def rewind_session_route(session_id: int, message_id: int) -> dict:
    msgs = db.list_messages(session_id)
    if not any(m["id"] == message_id for m in msgs):
        raise HTTPException(status_code=404, detail="Message not found in session")
    deleted = db.rewind_session(session_id, message_id)
    return {"ok": True, "deleted": deleted, "kept_up_to": message_id}


@router.post("/subagents")
async def spawn_subagent(body: SessionCreate) -> dict:
    return await subagent_pool.spawn(body.title or "Subagent", body.title)


@router.get("/subagents/{session_id}")
def get_subagent(session_id: int) -> dict:
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session": session, "busy": subagent_pool.get(session_id).busy if subagent_pool.get(session_id) else False}
