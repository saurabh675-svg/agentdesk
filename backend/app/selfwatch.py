"""Self-observation and watchdog: agents read health logs, fix crashes, retry with backoff."""

import asyncio
import json
import os
import time
import urllib.request
from pathlib import Path
from typing import Any, Awaitable, Callable

from .config import DATA_DIR

HEALTH_LOG = DATA_DIR / "health.log"


def read_recent_errors(limit: int = 50) -> list[str]:
    if not HEALTH_LOG.exists():
        return []
    try:
        text = HEALTH_LOG.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []
    return [line for line in text.splitlines() if "ERROR" in line or "Error" in line][-limit:]


def run_health() -> bool:
    """Direct, proxy-free loopback health check (no PowerShell spawn per tick)."""
    try:
        token = str(os.environ.get("AGENTDESK_API_TOKEN") or "")
        request = urllib.request.Request(
            "http://127.0.0.1:8756/api/health",
            headers={"Authorization": f"Bearer {token}"},
        )
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=10) as response:
            return response.status == 200
    except Exception:
        return False


async def retry(target: Any, attempts: int = 5, delay_base: float = 1.0):
    """Retry an async callable or coroutine with exponential backoff."""
    for i in range(attempts):
        try:
            if callable(target):
                res = target()
                return await res if asyncio.iscoroutine(res) else res
            return await target
        except Exception:
            if i == attempts - 1:
                raise
            await asyncio.sleep(min(delay_base * (2 ** i), 16))
    return None


async def circuit_breaker(target: Any, threshold: int = 3, cooldown: float = 30):
    for _ in range(threshold):
        try:
            if callable(target):
                res = target()
                return await res if asyncio.iscoroutine(res) else res
            return await target
        except Exception:
            await asyncio.sleep(cooldown)
    raise RuntimeError("circuit open: persistent failure")


def log_error(error: str) -> None:
    HEALTH_LOG.parent.mkdir(parents=True, exist_ok=True)
    with HEALTH_LOG.open("a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {error}\n")
