"""Background watchdog: retries/circuit breaker for backend, local llama.cpp, and the built-in browser."""

import asyncio
import urllib.request
from contextlib import suppress

from .engine import llama_local
from .selfwatch import log_error, read_recent_errors, run_health
from .tools.browser import browser


def _check_http_ok(url: str, headers: dict[str, str] | None = None) -> bool:
    try:
        request = urllib.request.Request(url, headers=headers or {})
        # Loopback health checks must never go through a system proxy.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=5) as response:
            return response.status == 200
    except Exception:
        return False


def ensure_services() -> dict:
    local_ok = _check_http_ok(
        llama_local.health_url(),
        {"Authorization": f"Bearer {llama_local.access_key()}"},
    )
    backend_ok = run_health()
    return {"local_ok": local_ok, "backend_ok": backend_ok}


async def watchdog_loop(stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            status = await asyncio.get_running_loop().run_in_executor(None, ensure_services)
            if status["backend_ok"] and status["local_ok"]:
                try:
                    await browser.ensure()
                except Exception:
                    pass
            else:
                log_error(f"watchdog: backend_ok={status['backend_ok']} local_ok={status['local_ok']}")
        except Exception as exc:
            log_error(f"watchdog: {exc}")
        await asyncio.sleep(30)


class Watchdog:
    def __init__(self) -> None:
        self._stop = asyncio.Event()
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        if self._task is None or self._task.done():
            self._stop.clear()
            self._task = asyncio.create_task(watchdog_loop(self._stop))

    async def stop(self) -> None:
        self._stop.set()
        if self._task and not self._task.done():
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task

    def recent_errors(self, limit: int = 50) -> list[str]:
        return read_recent_errors(limit)
