"""Skill evolution gate: propose → approve → install → rollback — Hermas."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from .. import skills_evolution
router = APIRouter()
class ProposeIn(BaseModel):
    name: str
    description: str = ""
    files: dict = {}
    score: float = 0.5
class ActIn(BaseModel):
    reason: str = ""
@router.get("")
def caps():
    return {"proposals": skills_evolution.list_proposals()}
@router.post("/propose")
def propose(body: ProposeIn):
    return skills_evolution.propose(body.name, body.description, body.files, body.score)
@router.post("/{skill_id}/approve")
def approve(skill_id: str):
    out = skills_evolution.approve(skill_id)
    if not out:
        raise HTTPException(status_code=404, detail="proposal not found or not proposed")
    return out
@router.post("/{skill_id}/reject")
def reject(skill_id: str, body: ActIn = ActIn()):
    out = skills_evolution.reject(skill_id, body.reason)
    if not out:
        raise HTTPException(status_code=404, detail="proposal not found or not proposed")
    return out
@router.post("/{skill_id}/rollback")
def rollback(skill_id: str):
    out = skills_evolution.rollback(skill_id)
    if not out:
        raise HTTPException(status_code=404, detail="installed skill not found")
    return out
