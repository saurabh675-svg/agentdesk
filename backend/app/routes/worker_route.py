from fastapi import APIRouter
from pydantic import BaseModel

from ..workers.manager import create_cline, create_kiro, create_opencode, list_workers, output_worker, stop_worker

router = APIRouter()


class WorkerStart(BaseModel):
    task: str | None = None


@router.post("/cline")
def start_cline(body: WorkerStart | None = None) -> dict:
    return create_cline((body.task if body else None))


@router.post("/kiro")
def start_kiro(body: WorkerStart | None = None) -> dict:
    return create_kiro((body.task if body else None))


@router.post("/opencode")
def start_opencode(body: WorkerStart | None = None) -> dict:
    return create_opencode((body.task if body else None))


@router.get("")
def get_workers() -> list[dict]:
    return list_workers()


@router.post("/{worker_type}/stop")
def stop_worker_route(worker_type: str) -> dict:
    return stop_worker(worker_type)


@router.get("/{worker_type}/output")
def get_worker_output(worker_type: str) -> list[str]:
    return output_worker(worker_type)


@router.get("/catalog")
def get_catalog() -> list[dict]:
    from ..cline_catalog import CATALOG

    return CATALOG
