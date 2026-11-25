from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..config import save_settings
from ..engine import llama_local, models

router = APIRouter()


class DownloadRequest(BaseModel):
    url: str = ""
    filename: str | None = None
    model_id: str | None = None


class ActivateRequest(BaseModel):
    path: str


class BackendRequest(BaseModel):
    backend: str


@router.get("")
def list_models() -> dict:
    return {
        "local": models.list_local(),
        "catalog": models.catalog_with_status(),
        "download": models.download_status(),
        "models_dir": str(models.MODELS_DIR),
        "backend": llama_local.backend_status(),
    }


@router.get("/status")
def download_status() -> dict:
    return models.download_status()


@router.get("/backend")
def backend_status() -> dict:
    return llama_local.backend_status()


@router.post("/backend")
async def set_backend(body: BackendRequest) -> dict:
    choice = body.backend.strip().lower()
    if choice not in ("auto", "vulkan", "cpu"):
        raise HTTPException(status_code=400, detail="backend must be auto, vulkan, or cpu")
    status = llama_local.backend_status()
    if choice == "vulkan" and not status["available"]:
        raise HTTPException(status_code=400, detail="Vulkan llama.cpp binary is not bundled")
    save_settings({"local_backend": choice})
    await llama_local.stop()
    await llama_local.ensure()
    return llama_local.backend_status()


@router.post("/download")
async def download_model(body: DownloadRequest) -> dict:
    try:
        return await models.download(body.url, body.filename, body.model_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/activate")
async def activate_model(body: ActivateRequest) -> dict:
    try:
        return await models.activate(body.path)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{name}")
def delete_model(name: str) -> dict:
    # Accept either a bare filename (resolved in the models dir) or a full path.
    path = name if (":" in name or name.startswith("/")) else str(models.MODELS_DIR / name)
    try:
        return models.delete_model(path)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
