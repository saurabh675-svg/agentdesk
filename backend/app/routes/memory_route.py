from fastapi import APIRouter
from pydantic import BaseModel

from .. import db

router = APIRouter()


class MemoryIn(BaseModel):
    key: str
    value: str
    project_id: int | None = None
    scope: str = "project"


@router.get("")
def get_memories() -> list[dict]:
    return db.list_memories()


@router.post("")
def save_memory(body: MemoryIn) -> dict:
    return db.save_memory(body.key, body.value, body.project_id, body.scope)


@router.get("/projects")
def get_projects() -> list[dict]:
    return db.list_projects()


@router.post("/projects")
def create_project(body: MemoryIn) -> dict:
    return db.create_project(body.key, body.value, body.scope)
