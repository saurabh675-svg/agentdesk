"""OpenRouter free-model discovery and selection.

Free model IDs rotate, so Hard mode asks OpenRouter for the current catalog and picks a
strong tool-capable model instead of hard-coding a model that may disappear.
"""

import time

import httpx

FALLBACK_MODEL = "nvidia/nemotron-3-ultra-550b-a55b:free"
PREFERRED_MODELS = [
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "nvidia/nemotron-3.5-super-vl:free",
    "inclusionai/ling-3.2-flash:free",
    "google/gemma-4-31b-it:free",
    "google/gemma-4-26b-a4b-it:free",
    "nvidia/nemotron-3.5-lightning:free",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "baidu/ernie-5.5-flash-preview:free",
    "particle-ai/particle-1:free",
]

_cache: tuple[float, list[dict]] | None = None
CACHE_SECONDS = 1800


def _rank(model: dict) -> float:
    model_id = model["id"].lower()
    score = 0.0
    for index, preferred in enumerate(PREFERRED_MODELS):
        if model_id == preferred:
            score += 5000 - index * 100
    if "coder" in model_id or "code" in model_id:
        score += 1200
    if "ultra" in model_id:
        score += 700
    if "nemotron" in model_id:
        score += 300
    if "reasoning" in model_id:
        score += 100
    if model.get("tools"):
        score += 80
    context = model.get("context_length") or 0
    return score + min(context / 100_000, 30)


async def free_models(force: bool = False) -> list[dict]:
    global _cache
    now = time.time()
    if not force and _cache and now - _cache[0] < CACHE_SECONDS:
        return _cache[1]

    models: list[dict] = []
    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            response = await client.get("https://openrouter.ai/api/v1/models")
            response.raise_for_status()
            raw = response.json().get("data", [])
        for item in raw:
            model_id = str(item.get("id", ""))
            if not model_id.endswith(":free"):
                continue
            pricing = item.get("pricing") or {}
            if str(pricing.get("prompt")) not in ("0", "0.0", "0.00"):
                continue
            supported = item.get("supported_parameters") or []
            architecture = item.get("architecture") or {}
            models.append(
                {
                    "id": model_id,
                    "name": item.get("name") or model_id,
                    "context_length": item.get("context_length") or 0,
                    "tools": "tools" in supported,
                    "vision": "image" in (architecture.get("input_modalities") or []),
                }
            )
        models.sort(key=_rank, reverse=True)
        for index, model in enumerate(models):
            model["recommended"] = index == 0
    except Exception:
        models = []

    if not models:
        models = [
            {
                "id": FALLBACK_MODEL,
                "name": "Nemotron 3 Ultra (free, fallback)",
                "context_length": 1_000_000,
                "tools": True,
                "vision": False,
                "recommended": True,
            }
        ]
    _cache = (now, models)
    return models


async def resolve_free_model(preferred: str = "auto") -> str:
    preferred = (preferred or "").strip()
    if preferred and preferred.lower() != "auto":
        return preferred
    models = await free_models()
    return next((model["id"] for model in models if model["tools"]), FALLBACK_MODEL)
