from fastapi import APIRouter

from ..engine.openrouter import free_models, resolve_free_model

router = APIRouter()


@router.get("/models")
async def list_free_models(refresh: bool = False) -> list[dict]:
    return await free_models(force=refresh)


@router.get("/recommended")
async def recommended(preferred: str = "auto") -> dict:
    return {"model": await resolve_free_model(preferred)}
