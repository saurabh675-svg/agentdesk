"""In-memory provider health tracking for routing and diagnostics."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Any

_STATS: dict[str, dict[str, Any]] = defaultdict(lambda: {"ok": 0, "fail": 0, "latencies": deque(maxlen=20)})


_COOLDOWNS: dict[str, float] = {}


def cooldown(provider: str, delay: float | None) -> None:
    # Some gateways return a Retry-After of many hours. Never park a route that
    # long: a 5-minute pause is enough to avoid hammering a rate-limited service
    # while still letting the router recover automatically.
    seconds = min(300.0, max(1.0, delay)) if delay is not None else 15.0
    _COOLDOWNS[provider] = time.monotonic() + seconds


def available(provider: str) -> bool:
    return time.monotonic() >= _COOLDOWNS.get(provider, 0.0)


def record(provider: str, ok: bool, latency_ms: float = 0.0, tokens: int = 0, ttft_ms: float = 0.0, error_class: str = "") -> None:
    provider = (provider or "unknown").strip().lower()
    bucket = _STATS[provider]
    bucket.setdefault("tokens", 0)
    bucket.setdefault("ttfts", deque(maxlen=20))
    bucket.setdefault("errors", defaultdict(int))
    if ok:
        bucket["ok"] += 1
    else:
        bucket["fail"] += 1
        if error_class:
            bucket["errors"][error_class] += 1
    if latency_ms and latency_ms > 0:
        bucket["latencies"].append(latency_ms)
    if tokens:
        bucket["tokens"] += int(tokens)
    if ttft_ms and ttft_ms > 0:
        bucket["ttfts"].append(ttft_ms)


def summary() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for provider, bucket in _STATS.items():
        total = bucket["ok"] + bucket["fail"]
        latencies = list(bucket["latencies"])
        out[provider] = {
            "ok": bucket["ok"],
            "fail": bucket["fail"],
            "total": total,
            "cooldown_seconds": round(max(0, _COOLDOWNS.get(provider, 0.0) - time.monotonic())),
            "success_rate": round(bucket["ok"] / total, 3) if total else 1.0,
            "avg_latency_ms": round(sum(latencies) / len(latencies), 1) if latencies else 0.0,
            "tokens": bucket.get("tokens", 0),
            "avg_ttft_ms": round(sum(bucket.get("ttfts", [])) / len(bucket.get("ttfts", [])), 1) if bucket.get("ttfts") else 0.0,
            "errors": dict(bucket.get("errors", {})),
        }
    return out


def best_provider(candidates: list[str]) -> str | None:
    if not candidates:
        return None
    scored = []
    for provider in candidates:
        info = summary().get(provider.strip().lower(), {"success_rate": 1.0, "avg_latency_ms": 0.0})
        scored.append((provider, info["success_rate"], -info["avg_latency_ms"]))
    scored.sort(key=lambda item: (item[1], item[2]), reverse=True)
    return scored[0][0] if scored else None