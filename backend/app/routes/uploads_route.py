import uuid
import re
from pathlib import Path

from fastapi import APIRouter, File, UploadFile

from ..config import UPLOADS_DIR

router = APIRouter()


@router.post("/files")
async def upload_files(files: list[UploadFile] = File(...)):
    """Store chat attachments so the agent can read them with read_file."""
    out = []
    for upload in files:
        filename = Path(upload.filename or "file").name or "file"
        suffix = Path(filename).suffix
        if not re.fullmatch(r"[.][a-zA-Z0-9_-]{1,32}", suffix):
            suffix = ""
        upload_id = f"{uuid.uuid4().hex}{suffix}"
        target = UPLOADS_DIR / upload_id
        with target.open("wb") as out_file:
            while chunk := await upload.read(1 << 20):
                out_file.write(chunk)
        out.append({"id": upload_id, "name": filename, "size": target.stat().st_size})
    return out
