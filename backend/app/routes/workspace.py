from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..config import load_settings, save_settings
from ..tools import fs

router = APIRouter()


class WorkspaceIn(BaseModel):
    path: str


def current_tree() -> list[dict]:
    settings = load_settings()
    workspace = settings.get("workspace")
    if not workspace or not Path(workspace).is_dir():
        return []
    try:
        return fs.build_tree(workspace, ".", max_depth=3)
    except Exception:
        return []


@router.get("")
def get_workspace() -> dict:
    settings = load_settings()
    workspace = settings.get("workspace")
    exists = bool(workspace) and Path(workspace).is_dir()
    return {"path": workspace, "exists": exists, "tree": current_tree() if exists else []}


@router.post("")
def set_workspace(body: WorkspaceIn) -> dict:
    path = Path(body.path).expanduser()
    try:
        path = path.resolve()
    except OSError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not path.is_dir():
        raise HTTPException(status_code=400, detail=f"Not a folder: {path}")
    settings = save_settings({"workspace": str(path)})
    return {"path": settings["workspace"], "exists": True, "tree": current_tree()}


@router.get("/tree")
def get_tree(path: str = Query("."), depth: int = Query(3, ge=1, le=6)) -> list[dict]:
    settings = load_settings()
    try:
        return fs.build_tree(settings["workspace"], path, max_depth=depth)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/file")
def get_file(path: str = Query(...)) -> dict:
    settings = load_settings()
    try:
        file_path = fs.safe_path(settings["workspace"], path)
        if not file_path.is_file():
            raise ValueError(f"File not found: {path}")
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if len(content) > 400_000:
        content = content[:400_000] + "\n... (truncated)"
    return {"path": path, "content": content, "size": file_path.stat().st_size}
