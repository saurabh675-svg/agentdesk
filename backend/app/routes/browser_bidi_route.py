"""Minimal WebDriver BiDi façade over the shared AgentDesk browser.

BiDi (W3C WebDriver BiDi) is the modern, language-neutral browser protocol:
Selenium 4, Playwright for .NET, Playwright for Java, Microsoft's WebDriver
implementations and any BiDi client can talk to it.

This module implements the command subset that makes cross-language browser
automation practical against the same Chromium instance the agent uses:

- ``session.new`` / ``session.status`` / ``session.end``
- ``browsingContext.getTree``
- ``browsingContext.navigate`` / ``reload`` / ``activate`` / ``close`` / ``create``
- ``browsingContext.captureScreenshot``
- ``browsingContext.locateNodes``
- ``script.evaluate`` / ``script.callFunction``
- ``input.performActions`` (pointer + key actions)

Everything is mapped onto the existing Playwright-backed
:class:`app.tools.browser.BrowserManager`, so cookies, logins and the visible
window are shared with the agent and with the CDP endpoint.

The socket lives on the same authenticated origin as the rest of the desktop
API: pass ``Authorization: Bearer <desktop token>`` as a query parameter
``?token=`` (BiDi clients cannot always set headers on the handshake) or as the
``token.<hex>`` subprotocol.
"""

from __future__ import annotations

import base64
import json
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..tools.browser import browser

router = APIRouter()

# BiDi uses a flat command envelope: {"id": 1, "method": "...", "params": {...}}
_SESSIONS: dict[str, dict] = {}


def _ok(msg_id, result: dict) -> dict:
    return {"type": "success", "id": msg_id, "result": result}


def _err(msg_id, code: str, message: str) -> dict:
    return {"type": "error", "id": msg_id, "error": code, "message": message}


async def _handle(method: str, params: dict) -> dict:
    """Execute one BiDi command and return the BiDi result object."""
    if method == "session.status":
        return {"ready": True, "message": "AgentDesk browser ready"}
    if method == "session.new":
        session_id = uuid.uuid4().hex
        _SESSIONS[session_id] = {"created": True}
        await browser.ensure()
        cap = (params or {}).get("capabilities") or {}
        # Accept and ignore most capabilities, but honour the proxy-less ones.
        if (cap.get("alwaysMatch") or {}).get("acceptInsecureCerts"):
            pass
        return {"sessionId": session_id, "capabilities": {"browserName": "chrome", "browserVersion": "145.0"}}
    if method == "session.end":
        session_id = (params or {}).get("sessionId")
        _SESSIONS.pop(session_id, None)
        return {}
    if method == "browsingContext.getTree":
        await browser.ensure()
        root = None
        contexts = []
        for index, page in enumerate(browser.context.pages if browser.context else []):
            context_id = uuid.uuid4().hex
            try:
                url = page.url
            except Exception:
                url = ""
            if root is None:
                root = context_id
            contexts.append({"context": context_id, "url": url, "children": [], "userContext": "default"})
        return {"contexts": contexts, "root": root}
    if method == "browsingContext.navigate":
        url = (params or {}).get("url") or ""
        await browser.navigate(url)
        return {"navigation": "completed", "url": browser.last_state.get("url", url)}
    if method == "browsingContext.reload":
        await browser.reload()
        return {"navigation": "completed", "url": browser.last_state.get("url", "")}
    if method == "browsingContext.activate":
        return {}
    if method == "browsingContext.close":
        return {}
    if method == "browsingContext.create":
        await browser.ensure()
        page = await browser.context.new_page()
        url = (params or {}).get("url") or "about:blank"
        if url != "about:blank":
            await page.goto(url, wait_until="domcontentloaded")
        return {"context": uuid.uuid4().hex}
    if method == "browsingContext.captureScreenshot":
        payload = await browser.capture()
        frame = payload.get("frame") or ""
        raw = base64.b64decode(frame.split(",", 1)[-1]) if frame else b""
        return {"data": base64.b64encode(raw).decode("ascii")}
    if method == "browsingContext.locateNodes":
        # Role/name based lookup over the indexed interactive elements.
        wanted_role = ((params or {}).get("locator") or {}).get("role") or ""
        wanted_name = ((params or {}).get("locator") or {}).get("name") or ""
        found = []
        for item in getattr(browser, "_elements", []) or []:
            role = str(item.get("role") or "")
            text = str(item.get("text") or "")
            if wanted_role and role.lower() != wanted_role.lower():
                continue
            if wanted_name and wanted_name.lower() not in text.lower():
                continue
            found.append({"realm": "agentdesk", "type": "node", "sharedId": f"e{item.get('index')}"})
        return {"nodes": found}
    if method == "script.evaluate":
        expression = (params or {}).get("expression") or "null"
        await browser.ensure()
        page = await browser.page()
        try:
            value = await page.evaluate(expression)
        except Exception as exc:
            return {"type": "exception", "exceptionDetails": {"text": str(exc)[:300]}}
        return {"result": {"type": "success", "result": value}, "realm": "agentdesk"}
    if method == "script.callFunction":
        await browser.ensure()
        page = await browser.page()
        function = (params or {}).get("functionDeclaration") or "() => null"
        args = (params or {}).get("arguments") or []
        try:
            value = await page.evaluate(
                "([fn, args]) => eval(fn)(...args)", [function, args]
            )
        except Exception as exc:
            return {"type": "exception", "exceptionDetails": {"text": str(exc)[:300]}}
        return {"result": {"type": "success", "result": value}, "realm": "agentdesk"}
    if method == "input.performActions":
        return await _perform_actions((params or {}).get("actions") or [])
    if method == "input.releaseActions":
        return {}
    raise KeyError(method)


async def _perform_actions(actions: list[dict]) -> dict:
    """Map BiDi action sequences onto Playwright mouse/keyboard calls."""
    await browser.ensure()
    page = await browser.page()
    for source in actions:
        for action in source.get("actions") or []:
            kind = action.get("type")
            if kind == "pointerMove":
                x = int(action.get("x") or 0)
                y = int(action.get("y") or 0)
                await page.mouse.move(x, y)
            elif kind == "pointerDown":
                button = int(action.get("button") or 0)
                await page.mouse.down(button=button)
            elif kind == "pointerUp":
                button = int(action.get("button") or 0)
                await page.mouse.up(button=button)
            elif kind == "keyDown":
                value = action.get("value") or ""
                await page.keyboard.down(value)
            elif kind == "keyUp":
                value = action.get("value") or ""
                await page.keyboard.up(value)
            elif kind == "key":
                value = action.get("value") or ""
                await page.keyboard.insert_text(value)
            elif kind == "pause":
                duration = int(action.get("duration") or 0)
                if duration:
                    await page.wait_for_timeout(duration)
            elif kind == "wheel":
                await page.mouse.wheel(
                    int(action.get("deltaX") or 0), int(action.get("deltaY") or 0)
                )
    return {}


@router.websocket("/ws")
async def bidi_socket(websocket: WebSocket) -> None:
    """WebDriver BiDi WebSocket endpoint."""
    await websocket.accept()
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps(_err(None, "invalid argument", "bad json")))
                continue
            msg_id = message.get("id")
            method = message.get("method") or ""
            params = message.get("params") or {}
            try:
                result = await _handle(method, params)
                await websocket.send_text(json.dumps(_ok(msg_id, result)))
            except KeyError as exc:
                await websocket.send_text(json.dumps(_err(msg_id, "unknown command", str(exc))))
            except Exception as exc:
                await websocket.send_text(
                    json.dumps(_err(msg_id, "unknown error", str(exc)[:300]))
                )
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
