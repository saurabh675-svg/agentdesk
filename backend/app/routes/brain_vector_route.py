"""Hybrid brain search route — 0.6."""
from fastapi import APIRouter
from ..brain_vector import hybrid_search
router = APIRouter()
@router.get("/search/hybrid")
def hybrid(q: str, limit: int = 8):
    return {"query": q, "hits": hybrid_search(q, limit)}
