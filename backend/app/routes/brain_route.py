from fastapi import APIRouter
from pydantic import BaseModel

from .. import brain


router = APIRouter()


class NoteIn(BaseModel):
    title: str
    body: str
    tags: list[str] = []
    link: str | None = None


@router.get("")
def get_brain() -> dict:
    return brain.load_brain()


@router.post("")
def add_brain(body: NoteIn) -> dict:
    return brain.add_brain_note(body.title, body.body, body.tags, body.link)


@router.get("/search")
def search_brain(query: str, limit: int = 20) -> list[dict]:
    return brain.search_brain_notes(query, limit)
