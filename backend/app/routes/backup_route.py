import time
import zipfile
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

from ..config import DATA_DIR

router = APIRouter()


@router.post("/create")
def create_backup() -> dict:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    out = DATA_DIR / f"agentdesk-backup-{stamp}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in DATA_DIR.rglob("*"):
            if path == out or path.suffix == ".zip":
                continue
            if "browser-profile" in path.parts:
                continue
            if path.name in {"settings.json", "mcp.json", "workspace.key"} or path.suffix == ".tmp":
                continue
            if path.is_file():
                zf.write(path, path.relative_to(DATA_DIR).as_posix())
    return {"path": str(out), "name": out.name, "size": out.stat().st_size}


@router.get("/download/{name}")
def download_backup(name: str) -> FileResponse:
    target = (DATA_DIR / name).resolve()
    if not target.is_file() or target.suffix != ".zip" or DATA_DIR.resolve() not in target.parents:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Backup not found")
    return FileResponse(target, filename=target.name, media_type="application/zip")
