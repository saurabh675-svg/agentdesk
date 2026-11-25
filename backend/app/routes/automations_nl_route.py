"""Natural-language automation creation — Hermas schedule parser."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from .. import automations
router = APIRouter()
class NLIn(BaseModel):
    name: str = "Automation"
    prompt: str
    schedule: str
    workspace: str | None = None
@router.post("/nl")
def create_nl(body: NLIn):
    try:
        return automations.create_automation_nl(body.name, body.prompt, body.schedule, body.workspace)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
