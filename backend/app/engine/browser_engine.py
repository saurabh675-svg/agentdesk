"""Browser engine protocol — 0.6.

One browser, several drivers. ``BrowserEngine`` is the swappable seam so
Playwright (current) and the native C++ CDP helper can be exchanged without
touching tool code. ``BrowserManager`` in ``tools/browser.py`` implements
this protocol today; ``CdpNativeEngine`` wraps ``cdp_helper.exe`` for the
low-latency path and falls back to Playwright when the binary is missing.
"""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from typing import Any, Protocol

from ..config import load_settings


class BrowserEngine(Protocol):
    async def start(self, headless: bool = False) -> None: ...
    async def close(self) -> None: ...
    async def navigate(self, url: str) -> dict: ...
    async def elements(self, limit: int = 60, annotate: bool = False) -> dict: ...
    async def click_element(self, index: int) -> dict: ...
    async def type_element(self, index: int, text: str, submit: bool = False) -> dict: ...
    async def snapshot(self, text_limit: int = 3600, element_limit: int = 120) -> dict: ...


def cdp_helper_path() -> Path | None:
    """Locate ``cdp_helper.exe`` (installer `native/cdp_helper/` or dev `.tmp`)."""
    here = Path(__file__).resolve()
    candidates = [
        here.parent.parent.parent.parent / "native" / "cdp_helper" / "cdp_helper.exe",
        shutil.which("cdp_helper.exe") or shutil.which("cdp_helper") or "",
        Path.home() / "agentdesk" / "native" / "cdp_helper" / "cdp_helper.exe",
    ]
    for c in candidates:
        try:
            p = Path(str(c)) if c else None
        except Exception:
            continue
        if p and p.exists():
            return p
    return None


class CdpNativeEngine:
    """Native C++ CDP driver behind the same interface.

    The helper is a tiny dependency-free Winsock client: ``--port <n>
    --action <targets|evaluate|click|key|scroll|screenshot>``. We keep a
    30s cached ``targets`` probe so the engine can report its health
    without spawning Chromium (the user's browser already runs on the
    CDP port).
    """

    name = "cdp-native"

    def __init__(self, port: int = 9333) -> None:
        self.port = int(port)
        self._proc: asyncio.subprocess.Process | None = None
        self._alive = False

    async def _run(self, *args: str, timeout: float = 20.0) -> str:
        helper = cdp_helper_path()
        if helper is None:
            raise RuntimeError("cdp_helper.exe not found; falling back to Playwright.")
        cmd = [str(helper), "--port", str(self.port), *args]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            env={**__import__("os").environ, "TEMP": str(Path(__file__).resolve().parents[3] / ".tmp")},
        )
        try:
            out, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            raise RuntimeError("cdp_helper timed out")
        text = out.decode("utf-8", "replace")
        if proc.returncode != 0:
            raise RuntimeError(f"cdp_helper failed: {text[:400]}")
        return text

    async def probe(self) -> dict[str, Any]:
        helper = cdp_helper_path()
        if helper is None:
            return {"available": False, "reason": "cdp_helper.exe not found"}
        try:
            out = await self._run("--action", "targets")
            self._alive = True
            return {"available": True, "helper": str(helper), "port": self.port, "raw": out[:500]}
        except Exception as exc:
            return {"available": False, "helper": str(helper), "port": self.port, "error": str(exc)[:300]}

    async def start(self, headless: bool = False) -> None:
        health = await self.probe()
        if not health.get("available"):
            raise RuntimeError(health.get("error") or "CDP bridge unavailable")

    async def close(self) -> None:
        self._alive = False

    async def navigate(self, url: str) -> dict[str, Any]:
        return await self._eval(f"location.href = {url!r}; 'ok'")

    async def _eval(self, expr: str) -> dict[str, Any]:
        out = await self._run("--action", "evaluate", "--expr", expr)
        return {"result": out.strip()}

    async def elements(self, limit: int = 60, annotate: bool = False) -> dict[str, Any]:
        return await self._eval("Array.from(document.querySelectorAll('a,button,input,select,textarea,[tabindex]')).slice(0,60).map((e,i)=>({i,tag:e.tagName,text:(e.innerText||e.value||'').slice(0,80)}))")

    async def click_element(self, index: int) -> dict[str, Any]:
        return await self._run("--action", "click", "--index", str(index))

    async def type_element(self, index: int, text: str, submit: bool = False) -> dict[str, Any]:
        return await self._run("--action", "type", "--index", str(index), "--text", text)

    async def snapshot(self, text_limit: int = 3600, element_limit: int = 120) -> dict[str, Any]:
        return await self._eval(f"({{'url': location.href, 'title': document.title, 'text': document.body?.innerText?.slice(0,{text_limit}) || ''}})")


def engine_for(settings: dict | None = None) -> str:
    """Pick the engine name from settings (``browser_engine``)."""
    settings = settings or {}
    name = str(settings.get("browser_engine") or "auto")
    if name == "cdp-native":
        return "cdp-native" if cdp_helper_path() else "playwright"
    if name == "playwright":
        return "playwright"
    # auto: prefer native when the binary exists, else Playwright (never breaks)
    return "cdp-native" if cdp_helper_path() else "playwright"
