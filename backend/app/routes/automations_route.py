from fastapi import APIRouter
from pydantic import BaseModel

from ..automations import create_automation, list_automations, cancel_automation
from ..config import load_settings

router = APIRouter()


class AutomationIn(BaseModel):
    name: str
    prompt: str
    interval_minutes: int = 15
    workspace: str | None = None


@router.get("")
def get_automations() -> list[dict]:
    return list_automations()


@router.post("")
def post_automation(body: AutomationIn) -> dict:
    workspace = body.workspace or load_settings().get("workspace")
    return create_automation(body.name, body.prompt, body.interval_minutes, workspace)


@router.post("/{job_id}/cancel")
def cancel(job_id: str) -> dict:
    return cancel_automation(job_id)
