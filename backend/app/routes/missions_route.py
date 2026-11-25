from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import db, missions
from ..agent import AgentRunner
from ..config import load_settings
from .settings_route import SettingsPatch
from ..config import save_settings

router = APIRouter()


class MissionIn(BaseModel):
    name: str
    prompt: str = ""
    session_id: int | None = None


@router.get("")
def get_missions() -> list[dict]:
    return missions.list_missions()


@router.post("")
def pin_mission(body: MissionIn) -> dict:
    mission = missions.add_mission(body.name, body.prompt, body.session_id)
    return mission


@router.delete("/{mission_id}")
def unpin_mission(mission_id: str) -> dict:
    return missions.remove_mission(mission_id)


@router.post("/{mission_id}/run")
async def run_mission(mission_id: str) -> dict:
    mission = missions.get_mission(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")
    session_id = missions.mission_session(mission)
    if not session_id:
        raise HTTPException(status_code=400, detail="Mission has no attached session; run it from chat")
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    async def send(_payload: dict) -> None:
        return None

    runner = AgentRunner(session_id, send)
    await runner.start(mission["prompt"], "auto")
    if runner._task:
        await runner._task
    return {"ok": True, "session_id": session_id}
