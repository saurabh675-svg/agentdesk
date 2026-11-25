from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..sandbox import create_sandbox, run_sandbox

router = APIRouter()


class SandboxRun(BaseModel):
    sandbox_id: str
    command: str


@router.get("/session")
async def sandbox_session() -> dict:
    try:
        return await create_sandbox()
    except Exception as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc


@router.post("/run")
async def sandbox_run(body: SandboxRun) -> dict:
    try:
        return await run_sandbox(body.sandbox_id, body.command)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
