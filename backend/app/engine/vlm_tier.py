"""Local VLM tier for computer-use — 0.7.

Vision-language models (Qwen2.5-VL and friends) ground the screen:
“where is the Settings button?”. When a VLM model file is present the
caller gets ``describe_screen(frame_b64)``; otherwise the tier reports
``{"available": False}`` and the Set-of-Marks path (DOM boxes) is used.
No download happens automatically (8 GB+).
"""

from __future__ import annotations

from pathlib import Path

from ..config import load_settings
from . import llama_local

VLM_HINTS = ("qwen2.5-vl", "qwen2vl", "llava", "minicpm-v", "moondream")


def available_models() -> list[str]:
    """Local GGUF basenames that look like VLMs."""
    try:
        names = [Path(m.get("path", "")).name.lower() for m in llama_local.list_models()] if hasattr(llama_local, "list_models") else []
    except Exception:
        names = []
    # Fall back to the configured model name.
    try:
        settings = load_settings() or {}
        cfg = str(settings.get("local_model_path") or settings.get("model") or "")
        if cfg:
            names.append(Path(cfg).name.lower())
    except Exception:
        pass
    return [n for n in names if any(h in n for h in VLM_HINTS)]


def is_available() -> bool:
    return bool(available_models()) and llama_local.is_available() if hasattr(llama_local, "is_available") else bool(available_models())


async def describe_screen(frame_b64: str, prompt: str = "List visible UI elements with approximate coordinates for automation.") -> dict:
    """Ask the local VLM to describe a HiDPI screenshot frame.

    ``frame_b64`` is ``data:image/jpeg;base64,...``. Returns
    ``{"available": False, ...}`` when no VLM model is installed — the
    caller should fall back to Set-of-Marks.
    """
    models = available_models()
    if not models:
        return {"available": False, "reason": "No vision model installed (Qwen2.5-VL / LLaVA). Drop a GGUF named *vl* into the models folder."}
    try:
        settings = load_settings() or {}
        text = await llama_local.generate_vision(
            settings, frame_b64, prompt
        ) if hasattr(llama_local, "generate_vision") else ""
        if not text:
            return {"available": False, "reason": "VLM present but vision endpoint returned empty; use Set-of-Marks."}
        return {"available": True, "model": models[0], "description": text[:3000]}
    except Exception as exc:
        return {"available": False, "reason": str(exc)[:300]}
