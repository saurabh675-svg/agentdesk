import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from .. import db
from ..config import load_settings
from ..terminal import terminal_manager

router = APIRouter()


@router.websocket("/ws/terminal/{session_id}")
async def terminal_socket(websocket: WebSocket, session_id: int) -> None:
    await websocket.accept(subprotocol="agentdesk")
    session = db.get_session(session_id)
    if not session:
        await websocket.close(code=1008)
        return
    cwd = session.get("workspace") or load_settings().get("workspace")
    terminal = terminal_manager.get(session_id, cwd)
    queue: asyncio.Queue = asyncio.Queue()
    terminal.subscribers.add(queue)

    async def send(payload: dict) -> None:
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.send_json(payload)

    await send(
        {
            "type": "ready",
            "buffer": terminal.buffer,
            "error": terminal.error,
            "cwd": cwd,
        }
    )

    async def sender() -> None:
        while True:
            data = await queue.get()
            try:
                await send({"type": "output", "data": data})
            except Exception:
                return

    async def receiver() -> None:
        while True:
            try:
                message = await websocket.receive_json()
            except (WebSocketDisconnect, RuntimeError):
                return
            kind = message.get("type")
            if kind == "input":
                terminal.write(message.get("data", ""))
            elif kind == "resize":
                terminal.resize(int(message.get("rows", 30)), int(message.get("cols", 120)))
            elif kind == "restart":
                terminal.restart()
                await send({"type": "cleared"})

    tasks = [asyncio.create_task(sender()), asyncio.create_task(receiver())]
    try:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
    except WebSocketDisconnect:
        pass
    finally:
        terminal.subscribers.discard(queue)
        for task in tasks:
            if not task.done():
                task.cancel()
