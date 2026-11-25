"""Ordered provider/gateway catalog: endpoints, keys, and fallback chains.

Auto routing uses the keyless gateway plus saved-key cloud gateways first, then
the local llama.cpp model (Vulkan when available) as an offline fallback, then
browser-based ChatGPT / Gemini web sessions as the last resort.

Model discovery and failover follow the GenAgent gatewayManager pattern:
models are resolved live from /models when possible, health/cooldown-aware
fallback skips dead routes, and failures emit sanitised retry events.
"""

from __future__ import annotations

import time
from typing import Callable

GATEWAY_ENDPOINTS = {
    # Keyless anonymous endpoint (verified live 2026-11-24). Works for chat,
    # streaming and tool calls; IP-rate-limited, no account/key required.
    "keyless": "https://api.apillmfree.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "freeai": "https://api.free.ai/v1",
    "vercel": "https://ai-gateway.vercel.app/v1",
    "unorouter": "https://api.unorouter.com/v1",
    "opencode": "https://opencode.ai/inference/openai/v1",
    "pollinations": "https://gen.pollinations.ai/v1",
    "openai": "https://api.openai.com/v1",
}

# Gateways that need a key to work (local "local" is handled separately).
GATEWAY_MODELS = {
    "keyless": "free-ai",
    "openai": "gpt-4o-mini",
    "freeai": "qwen7b",
    "vercel": "openai/gpt-5",
    "pollinations": "openai/gpt-5.4-nano",
    # OpenRouter's live free router: always points at a currently available free
    # model, so hardcoded model IDs never go stale/404.
    "openrouter": "openrouter/free",
    "unorouter": "claude-opus-4-7-thinking",
    "opencode": "mimo-v2.6-flash-free",
}

# Verified free models across open gateways:
FREE_OPENROUTER_MODELS = [
    "meta-llama/llama-3.3-70b-instruct:free",
    "qwen/qwen-2.5-coder-32b-instruct:free",
    "google/gemini-2.0-flash-exp:free",
    "deepseek/deepseek-r1:free",
]

# "free" in practice: usable without a paid key (OpenRouter/Pollinations free
# tiers, Vercel Gateway tokens, UnoRouter/OpenCode free routes).
FREE_GATEWAYS = ["keyless", "pollinations", "freeai", "openrouter", "opencode", "vercel", "unorouter"]

# Keyless gateways work without a saved credential. Keep the placeholder key
# non-empty because the OpenAI-compatible clients require an Authorization value.
KEYLESS_GATEWAYS = {"keyless"}

# Ordered gateway chain for Auto. Keyless is first because it is anonymous,
# tool-capable and currently reliable; OpenRouter is next when its daily free
# quota is available. The local model is added separately as an offline leg.
FALLBACK_CHAIN = ["keyless", "openrouter", "opencode", "vercel", "unorouter", "pollinations", "freeai", "openai"]


# --- GenAgent-style live model discovery -------------------------------
# Per-gateway model preferences (ported from GenAgent PROVIDERS.pick).
# "free" suffix means the provider marks the model as free-tier.
_PROVIDER_PREFS: dict[str, list[str]] = {
    "openrouter": [
        "deepseek/deepseek-chat-v3", "deepseek/deepseek-r1", "qwen/qwen3-235b",
        "meta-llama/llama-3.3-70b", "google/gemini-2.0-flash-exp", "mistralai/mistral-small",
    ],
    "groq": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "qwen/qwen3-32b", "gemma2"],
    "google": ["gemini-2.0-flash", "gemini-2.5-flash", "gemini-1.5-flash"],
    "cerebras": ["llama-3.3-70b", "llama3.3-70b", "qwen-3-32b", "llama3.1-8b"],
}

_MODEL_CACHE: dict[str, tuple[list[str], float]] = {}
CACHE_TTL_SECONDS = 3600


def pick_models(gateway: str, all_ids: list[str]) -> list[str]:
    """GenAgent-style pick: prefer known-good ids, then free-tier, then rest."""
    prefs = _PROVIDER_PREFS.get(gateway, [])
    lower = [(mid.lower(), mid) for mid in all_ids]
    picked: list[str] = []
    seen: set[str] = set()
    # 1) explicit preferences in order
    for pref in prefs:
        needle = pref.lower()
        for low, orig in lower:
            if needle in low and orig not in seen:
                picked.append(orig)
                seen.add(orig)
                break
    # 2) free-tier markers
    for low, orig in lower:
        if ":free" in low and orig not in seen:
            picked.append(orig)
            seen.add(orig)
    # 3) fill with remainder
    for low, orig in lower:
        if orig not in seen:
            picked.append(orig)
            seen.add(orig)
    return picked[:6]


def cached_models(gateway: str) -> list[str]:
    cached = _MODEL_CACHE.get(gateway)
    if cached and (time.monotonic() - cached[1]) < CACHE_TTL_SECONDS:
        return list(cached[0])
    return []


def cache_models(gateway: str, ids: list[str]) -> None:
    _MODEL_CACHE[gateway] = (list(ids), time.monotonic())


async def discover_models(gateway: str, api_key: str, base_url: str | None = None, timeout: float = 8.0, force: bool = False) -> list[str]:
    """Live /models discovery (GenAgent models()). Cached 1h. Safe to fail.

    Returns [] when the gateway has no key, the endpoint errors, or the
    response has no usable ids. Callers always fall back to static defaults.
    """
    if gateway in KEYLESS_GATEWAYS:
        return []
    if not force:
        cached = cached_models(gateway)
        if cached:
            return cached
    if not api_key:
        return []
    endpoint = (base_url or GATEWAY_ENDPOINTS.get(gateway, "")).rstrip("/")
    if not endpoint:
        return []
    try:
        import httpx
        headers = {"Authorization": f"Bearer {api_key}"}
        if gateway == "openrouter":
            headers["HTTP-Referer"] = "https://agentdesk.local"
            headers["X-Title"] = "AgentDesk"
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(f"{endpoint}/models", headers=headers)
            if resp.status_code != 200:
                return []
            data = resp.json().get("data") or []
            ids = [str(m.get("id") or "").strip() for m in data if str(m.get("id") or "").strip()]
            # Google prefixes ids with models/
            if gateway == "google":
                ids = [i[7:] if i.startswith("models/") else i for i in ids]
                ids = [i for i in ids if "gemini" in i.lower()]
            picked = pick_models(gateway, ids)
            cache_models(gateway, picked)
            return picked
    except Exception:
        return cached_models(gateway)


def classify_error(exc: object) -> str:
    """Classify a provider failure for routing + telemetry."""
    status = getattr(exc, "status", None)
    text = str(exc).lower()
    if status == 401 or status == 403 or "auth" in text or "api key" in text or "invalid key" in text:
        return "auth_failed"
    if status == 429 or "rate limit" in text or "too many requests" in text or "quota" in text:
        return "rate_limited"
    if status == 404 or "model" in text and ("not found" in text or "no longer" in text or "does not exist" in text):
        return "model_not_found"
    if "empty" in text or "no choices" in text:
        return "empty_response"
    if "timeout" in text or "timed out" in text:
        return "timeout"
    if status in (500, 502, 503, 504):
        return "provider_5xx"
    if status is not None:
        return f"http_{status}"
    return type(exc).__name__


def is_model_level_failure(kind: str) -> bool:
    """True when the next model on the same gateway is worth trying."""
    return kind in ("model_not_found", "empty_response")


def safe_error_message(exc: object, max_len: int = 220) -> str:
    """Sanitised error text for notices — no raw bodies, no keys."""
    text = str(exc)
    lowered = text.lower()
    # Strip anything that looks like an api key / bearer token
    import re as _re
    text = _re.sub(r"(Bearer\s+)[A-Za-z0-9._\-]{10,}", r"\1***", text, flags=_re.IGNORECASE)
    text = _re.sub(r"sk-[A-Za-z0-9._\-]{10,}", "sk-***", text)
    text = _re.sub(r"https?://\S+", "<url>", text)
    return " ".join(text.split())[:max_len]


def key_for_gateway(gateway: str, settings: dict) -> str:
    """Return the key saved for a gateway. Per-gateway `keys` is authoritative, so
    activating one gateway does not inherit another gateway's key."""
    keys = settings.get("keys") or {}
    if gateway == "vercel":
        return str(
            settings.get("gateway_api_key")
            or keys.get("vercel")
            or ""
        ).strip()
    if gateway == "freeai":
        return str(settings.get("freeai_api_key") or keys.get("freeai") or "").strip()
    if gateway == "local":
        return ""
    if gateway in KEYLESS_GATEWAYS:
        return "free"
    legacy_key = settings.get("api_key") if (settings.get("gateway") or settings.get("provider")) == gateway else ""
    if gateway == "openrouter":
        # Keep the old Hard-mode key working without hardcoding OpenRouter as the route.
        legacy_key = str(settings.get("hard_api_key") or legacy_key or "")
    return str(keys.get(gateway) or legacy_key or "").strip()
