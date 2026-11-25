"""Free.ai GPU compute and LLM gateway integration for AgentDesk.

Allows AgentDesk to offload heavy Python, PyTorch, and CUDA workloads to
remote NVIDIA A100 (20GB VRAM) instances using Free.ai tokens (including the
30,000 free tokens provided daily without credit cards).
"""

from __future__ import annotations

import httpx
import json
from typing import Any

from ..config import load_settings

FREEAI_API_BASE = "https://api.free.ai/v1"


def get_freeai_api_key(settings_override: dict[str, Any] | None = None) -> str:
    """Retrieve saved Free.ai API key from settings or environment."""
    settings = settings_override or load_settings()
    keys = settings.get("keys") or {}
    return str(keys.get("freeai") or settings.get("freeai_api_key") or "").strip()


async def check_freeai_quota(api_key: str = "") -> dict[str, Any]:
    """Check remaining Free.ai daily token balance and GPU compute quota."""
    key = api_key or get_freeai_api_key()
    if not key:
        return {
            "has_key": False,
            "daily_free_allowance": 30_000,
            "gpu_rate_per_min": 10_000,
            "cpu_rate_per_min": 10,
            "free_gpu_minutes_daily": 3.0,
            "free_cpu_hours_daily": 50.0,
            "message": "No API key configured. Sign up at https://free.ai for 30,000 free tokens/day (no credit card). Use `/freeai key sk-free-...` to save.",
        }

    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(f"{FREEAI_API_BASE}/user/tokens", headers=headers)
            if res.status_code == 200:
                data = res.json()
                tokens = int(data.get("tokens") or data.get("balance") or 30000)
                return {
                    "has_key": True,
                    "tokens_available": tokens,
                    "gpu_minutes_remaining": round(tokens / 10000, 1),
                    "cpu_hours_remaining": round(tokens / 600, 1),
                    "raw": data,
                }
            return {
                "has_key": True,
                "status_code": res.status_code,
                "message": f"Connected to Free.ai API (HTTP {res.status_code}): {res.text[:300]}",
            }
    except Exception as exc:
        return {"has_key": True, "error": str(exc)}


async def run_freeai_gpu_code(script: str, api_key: str = "", timeout: int = 120) -> tuple[bool, str]:
    """Execute a Python/PyTorch/CUDA script on Free.ai NVIDIA A100 GPU compute."""
    key = api_key or get_freeai_api_key()
    if not key:
        return False, (
            "Free.ai API key is required to dispatch GPU tasks. "
            "Get your free key at https://free.ai (30K free tokens daily, no credit card needed). "
            "Then set it via `/freeai key sk-free-YOUR_KEY` or in Settings."
        )

    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {
        "code": script,
        "runtime": "gpu-a100-20gb",
        "cuda_version": "12.4",
        "timeout": min(timeout, 300),
    }

    try:
        async with httpx.AsyncClient(timeout=float(timeout + 15)) as client:
            # Dispatch to Free.ai Coder / Execution endpoint
            res = await client.post(f"{FREEAI_API_BASE}/coder/execute", json=payload, headers=headers)
            if res.status_code in (200, 201):
                data = res.json()
                out = data.get("stdout") or data.get("output") or data.get("result") or ""
                err = data.get("stderr") or ""
                tokens_used = data.get("tokens_used", 0)
                msg = f"🚀 **NVIDIA A100 GPU Execution Result** (Used ~{tokens_used} tokens):\n```\n{out}\n```"
                if err:
                    msg += f"\n*Stderr:*\n```\n{err[:1000]}\n```"
                return True, msg
            elif res.status_code == 402:
                return False, "Free.ai token quota exceeded for today. Tokens reset every 24 hours (30K daily)."
            return False, f"Free.ai execution returned HTTP {res.status_code}: {res.text[:600]}"
    except Exception as exc:
        return False, f"Failed to execute on Free.ai GPU: {exc}"
