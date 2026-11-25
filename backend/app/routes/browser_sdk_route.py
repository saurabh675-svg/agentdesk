"""Language-neutral browser control plane.

One real browser (the very one the agent drives, with the user's signed-in
profile) exposed through three façades so any language can use it:

1. **AgentDesk REST + WebSocket** (this module) — trivially callable from
   C++, C#, Java/JS/Python/Go/Rust with just an HTTP client.
2. **Chrome DevTools Protocol** — enabled on ``127.0.0.1:<browser_cdp_port>``.
   Attach with Puppeteer (`puppeteer.connect`), Selenium 4
   (`options.AdditionalOption("debuggerAddress", ...)`), ChromeDriver,
   libcurl + a websocket lib, or anything speaking raw CDP.
3. **WebDriver BiDi** (see :mod:`app.routes.browser_bidi_route`) — the W3C
   standard, supported natively by Selenium 4, Playwright for .NET and Java,
   and Microsoft.Playwright.

All three drive the same Chromium instance, so cookies, logins and the visible
window are shared.
"""

from __future__ import annotations

import base64
import json
from typing import Any

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from ..tools.browser import browser

router = APIRouter()


class NavigateBody(BaseModel):
    url: str


class ActBody(BaseModel):
    action: str
    selector: str | None = None
    text: str | None = None
    key: str | None = None
    value: str | None = None
    x: int | None = None
    y: int | None = None
    button: str = "left"
    clicks: int = 1
    modifiers: list[str] | None = None
    delta_y: int = 600
    delta_x: int = 0
    to_x: int | None = None
    to_y: int | None = None
    steps: int = 20
    path: str | None = None
    timeout: int = 15000


@router.get("/info")
async def sdk_info() -> dict:
    """Endpoint discovery: how to reach this browser from any language."""
    state = await browser.state()
    return {
        "service": "AgentDesk Browser Control Plane",
        "version": "0.7.0",
        "transports": {
            "rest": "/api/browser/sdk",
            "websocket_events": "/api/browser/sdk/events",
            "cdp_http": f"http://127.0.0.1:{browser.cdp_port}/json/version" if browser.cdp_enabled else None,
            "webdriver_bidi": "ws://127.0.0.1:8756/api/browser/bidi",
            "websocket_bidi": "ws://127.0.0.1:8756/api/browser/bidi/ws",
        },
        "cdp": {
            "enabled": browser.cdp_enabled,
            "port": browser.cdp_port,
            "note": "Attach with puppeteer.connect / Selenium debuggerAddress / raw CDP",
        },
        "state": state.get("state", {}),
    }


@router.get("/tabs")
async def sdk_tabs() -> dict:
    """List open pages (targets) of the shared browser."""
    await browser.ensure()
    pages = []
    active_page = browser.page
    for index, page in enumerate(browser.context.pages if browser.context else []):
        try:
            pages.append({
                "index": index,
                "url": page.url,
                "title": await page.title(),
                "active": page == active_page,
            })
        except Exception:
            pages.append({"index": index, "url": page.url, "title": "", "active": False})
    return {"tabs": pages, "active_index": next(
        (p["index"] for p in pages if p.get("active")), 0
    )}


@router.post("/navigate")
async def sdk_navigate(body: NavigateBody) -> dict:
    if not body.url:
        raise HTTPException(status_code=400, detail="url is required")
    try:
        await browser.navigate(body.url)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return await browser.state()


@router.post("/act")
async def sdk_act(body: ActBody) -> dict:
    """Perform one input action. Mirrors the agent's browser tool surface."""
    action = (body.action or "").strip().lower()
    try:
        if action == "click":
            if not body.selector:
                raise ValueError("selector is required")
            await browser.click(body.selector)
        elif action == "click_at":
            if body.x is None or body.y is None:
                raise ValueError("x and y are required")
            await browser.click_at(body.x, body.y)
        elif action == "double_click_at":
            if body.x is None or body.y is None:
                raise ValueError("x and y are required")
            await browser.mouse_double_click(body.x, body.y)
        elif action == "type":
            if body.selector and body.text is not None:
                await browser.type_text(body.selector, body.text, False)
            elif body.text is not None:
                await browser.keyboard_type(body.text)
        elif action == "key":
            await browser.press(body.key or body.text or "Enter")
        elif action == "hover":
            if body.x is None or body.y is None:
                raise ValueError("x and y are required")
            await browser.hover_at(body.x, body.y)
        elif action == "drag":
            if None in (body.x, body.y, body.to_x, body.to_y):
                raise ValueError("x, y, to_x and to_y are required")
            await browser.drag(body.x, body.y, body.to_x, body.to_y, body.steps)
        elif action == "scroll":
            await browser.scroll(body.delta_y, body.delta_x)
        elif action == "scroll_to":
            if not body.selector:
                raise ValueError("selector is required")
            await browser.scroll_to(body.selector)
        elif action == "select":
            if not body.selector:
                raise ValueError("selector is required")
            await browser.select(body.selector, body.value or "")
        elif action == "wait_for":
            await browser.wait_for(body.selector, body.text, body.timeout)
        elif action == "upload":
            if not body.selector or not body.path:
                raise ValueError("selector and path are required")
            await browser.upload_file(body.selector, body.path)
        elif action == "back":
            await browser.back()
        elif action == "forward":
            await browser.forward()
        elif action == "reload":
            await browser.reload()
        else:
            raise ValueError(f"unknown action: {action}")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "action": action, "state": (await browser.state()).get("state", {})}


@router.get("/snapshot")
async def sdk_snapshot(limit: int = 20000) -> dict:
    """Readable content of the active page (URL, title, text)."""
    await browser.ensure()
    text = await browser.read_text(limit=limit)
    links = await browser.links()
    elements = getattr(browser, "_elements", []) or []
    return {
        "url": browser.last_state.get("url", ""),
        "title": browser.last_state.get("title", ""),
        "text": text,
        "links": links.splitlines() if links else [],
        "indexed_elements": elements,
    }


@router.get("/screenshot")
async def sdk_screenshot(fmt: str = "jpeg", quality: int = 70) -> dict:
    """Base64 screenshot of the active page."""
    payload = await browser.capture()
    frame = payload.get("frame") or ""
    if not frame:
        raise HTTPException(status_code=503, detail="no frame available")
    return {"format": fmt, "data_uri": frame, "state": payload.get("state", {})}


@router.websocket("/events")
async def sdk_events(websocket: WebSocket) -> None:
    """Stream frames + state changes to any language client."""
    await websocket.accept()
    queue: list[dict] = []

    async def on_payload(payload: dict) -> None:
        queue.append(payload)
        if len(queue) > 4:
            queue.pop(0)

    browser.subscribe(on_payload)
    try:
        while True:
            state = await browser.state()
            await websocket.send_json({"type": "state", "state": state.get("state", {})})
            if queue:
                await websocket.send_json(queue.pop(0))
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        browser.unsubscribe(on_payload)
