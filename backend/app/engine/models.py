"""Local GGUF model manager: discover, download, activate, and remove models.

AgentDesk serves local models through the bundled llama.cpp server. This module
lets users download additional GGUF models (from Hugging Face or any direct URL)
into the data directory and activate them without touching the command line.
"""

import asyncio
import os
import re
import time
from pathlib import Path

import httpx

from ..config import DATA_DIR, load_settings, save_settings

MODELS_DIR = DATA_DIR / "models"
HOME_LLAMA = Path.home() / ".llama"

# Curated, CPU-friendly GGUF models. URLs point at Hugging Face `resolve/main`
# so they download the actual file (not an HTML page).
CATALOG = [
    {
        "id": "qwen2.5-1.5b-instruct-q4_k_m",
        "name": "Qwen2.5 1.5B Instruct (Q4_K_M)",
        "filename": "qwen2.5-1.5b-instruct-q4_k_m.gguf",
        "url": "https://huggingface.co/bartowski/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf",
        "size_bytes": 1_120_000_000,
        "context": 32768,
        "description": "Fast general chat/coding model. Bundled default; great on CPU.",
    },
    {
        "id": "qwen2.5-3b-instruct-q4_k_m",
        "name": "Qwen2.5 3B Instruct (Q4_K_M)",
        "filename": "qwen2.5-3b-instruct-q4_k_m.gguf",
        "url": "https://huggingface.co/bartowski/Qwen2.5-3B-Instruct-GGUF/resolve/main/Qwen2.5-3B-Instruct-Q4_K_M.gguf",
        "size_bytes": 2_100_000_000,
        "context": 32768,
        "description": "Better reasoning than 1.5B while still CPU-friendly.",
    },
    {
        "id": "qwen2.5-coder-3b-instruct-q4_k_m",
        "name": "Qwen2.5 Coder 3B Instruct (Q4_K_M)",
        "filename": "qwen2.5-coder-3b-instruct-q4_k_m.gguf",
        "url": "https://huggingface.co/bartowski/Qwen2.5-Coder-3B-Instruct-GGUF/resolve/main/Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf",
        "size_bytes": 2_100_000_000,
        "context": 32768,
        "description": "Code-focused local model for editing and generation.",
    },
    {
        "id": "llama-3.2-3b-instruct-q4_k_m",
        "name": "Llama 3.2 3B Instruct (Q4_K_M)",
        "filename": "llama-3.2-3b-instruct-q4_k_m.gguf",
        "url": "https://huggingface.co/bartowski/Llama-3.2-3B-Instruct-GGUF/resolve/main/Llama-3.2-3B-Instruct-Q4_K_M.gguf",
        "size_bytes": 2_020_000_000,
        "context": 131072,
        "description": "Meta Llama 3.2, strong instruction following.",
    },
    {
        "id": "phi-3.5-mini-instruct-q4_k_m",
        "name": "Phi 3.5 Mini Instruct (Q4_K_M)",
        "filename": "phi-3.5-mini-instruct-q4_k_m.gguf",
        "url": "https://huggingface.co/bartowski/Phi-3.5-mini-instruct-GGUF/resolve/main/Phi-3.5-mini-instruct-Q4_K_M.gguf",
        "size_bytes": 2_390_000_000,
        "context": 131072,
        "description": "Microsoft Phi 3.5, compact reasoning model.",
    },
    {
        "id": "qwen2.5-7b-instruct-q4_k_m",
        "name": "Qwen2.5 7B Instruct (Q4_K_M)",
        "filename": "qwen2.5-7b-instruct-q4_k_m.gguf",
        "url": "https://huggingface.co/bartowski/Qwen2.5-7B-Instruct-GGUF/resolve/main/Qwen2.5-7B-Instruct-Q4_K_M.gguf",
        "size_bytes": 4_680_000_000,
        "context": 32768,
        "description": "Higher quality local model; needs ~6 GB RAM and a faster CPU.",
    },
]

_download: dict = {"active": False}
_lock = asyncio.Lock()


def _model_dirs() -> list[Path]:
    dirs = [MODELS_DIR, HOME_LLAMA]
    # Bundled runtime models (packaged install).
    try:
        import sys

        runtime_models = Path(sys.executable).parent.parent / "models"
        if runtime_models.exists():
            dirs.append(runtime_models)
    except Exception:
        pass
    return dirs


def list_local() -> list[dict]:
    settings = load_settings()
    active = str(settings.get("local_model_path") or "").strip()
    if not active:
        try:
            from . import llama_local

            resolved = llama_local.resolve_model_path()
            active = str(resolved) if resolved else ""
        except Exception:
            active = ""
    seen: set[str] = set()
    out: list[dict] = []
    for directory in _model_dirs():
        try:
            if not directory.exists():
                continue
            for path in sorted(directory.glob("*.gguf")):
                key = str(path.resolve())
                if key in seen:
                    continue
                seen.add(key)
                stat = path.stat()
                out.append(
                    {
                        "name": path.name,
                        "path": str(path),
                        "size_bytes": stat.st_size,
                        "modified": stat.st_mtime,
                        "active": bool(active) and Path(active).resolve() == path.resolve(),
                        "builtin": directory != MODELS_DIR,
                    }
                )
        except Exception:
            continue
    out.sort(key=lambda item: (not item["active"], item["name"].lower()))
    return out


def catalog_with_status() -> list[dict]:
    local_names = {item["name"].lower() for item in list_local()}
    result = []
    for entry in CATALOG:
        result.append({**entry, "downloaded": entry["filename"].lower() in local_names})
    return result


def download_status() -> dict:
    return dict(_download)


def _safe_filename(name: str) -> str:
    name = os.path.basename(name.strip())
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    if not name.lower().endswith(".gguf"):
        name += ".gguf"
    return name


async def download(url: str, filename: str | None = None, model_id: str | None = None) -> dict:
    """Stream a GGUF file into MODELS_DIR with progress tracking."""
    async with _lock:
        if _download.get("active"):
            raise RuntimeError("A model download is already in progress.")
        entry = next((item for item in CATALOG if item["id"] == model_id), None)
        if entry:
            url = url or entry["url"]
            filename = filename or entry["filename"]
        if not url:
            raise ValueError("A download URL is required.")
        filename = _safe_filename(filename or url.split("/")[-1].split("?")[0])
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        target = MODELS_DIR / filename
        part = target.with_suffix(target.suffix + ".part")
        _download.update(
            {
                "active": True,
                "filename": filename,
                "url": url,
                "downloaded": 0,
                "total": entry["size_bytes"] if entry else 0,
                "started_at": time.time(),
                "error": None,
            }
        )
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=httpx.Timeout(30.0, read=120.0)) as client:
                async with client.stream("GET", url) as response:
                    response.raise_for_status()
                    total = int(response.headers.get("content-length") or 0)
                    if total:
                        _download["total"] = total
                    with part.open("wb") as handle:
                        async for chunk in response.aiter_bytes(chunk_size=1024 * 256):
                            handle.write(chunk)
                            _download["downloaded"] += len(chunk)
            part.replace(target)
            _download.update({"active": False, "done": True, "path": str(target)})
            return {"ok": True, "path": str(target), "filename": filename, "size_bytes": target.stat().st_size}
        except Exception as exc:
            _download.update({"active": False, "error": str(exc)})
            try:
                part.unlink(missing_ok=True)
            except Exception:
                pass
            raise


def delete_model(path: str) -> dict:
    target = Path(path)
    allowed = [directory.resolve() for directory in _model_dirs()]
    try:
        resolved = target.resolve()
    except Exception:
        raise ValueError("Invalid model path.")
    if not any(str(resolved).startswith(str(directory)) for directory in allowed):
        raise ValueError("Refusing to delete a file outside the model directories.")
    if not target.exists():
        raise FileNotFoundError("Model file not found.")
    settings = load_settings()
    if str(settings.get("local_model_path") or "").strip() == str(target):
        save_settings({"local_model_path": ""})
    target.unlink()
    return {"ok": True, "deleted": str(target)}


async def activate(path: str) -> dict:
    target = Path(path)
    if not target.exists():
        raise FileNotFoundError("Model file not found.")
    save_settings({"local_model_path": str(target), "provider": "local", "gateway": "local"})
    from . import llama_local

    await llama_local.stop()
    url = await llama_local.ensure()
    return {"ok": True, "path": str(target), "base_url": url}
