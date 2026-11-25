from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from ..agent import AgentRunner
from ..config import save_settings, load_settings
from ..tools.browser import browser
from ..tools.computer import computer
from ..engine.gateways import GATEWAY_MODELS, FREE_OPENROUTER_MODELS

router = APIRouter()

ACTIVE_RUNNERS: dict[int, AgentRunner] = {}


@router.websocket("/ws/chat/{session_id}")
async def chat_socket(websocket: WebSocket, session_id: int) -> None:
    await websocket.accept(subprotocol="agentdesk")

    async def send(payload: dict) -> None:
        if websocket.client_state == WebSocketState.CONNECTED:
            try:
                await websocket.send_json(payload)
            except Exception:
                pass

    if session_id in ACTIVE_RUNNERS and not ACTIVE_RUNNERS[session_id]._closed:
        runner = ACTIVE_RUNNERS[session_id]
        runner.send = send
    else:
        runner = AgentRunner(session_id, send)
        ACTIVE_RUNNERS[session_id] = runner

    async def on_browser_frame(payload: dict) -> None:
        await send({"type": "browser_frame", **payload})

    async def on_computer_frame(payload: dict) -> None:
        await send({"type": "computer_frame", **payload})

    browser.subscribe(on_browser_frame)
    computer.subscribe(on_computer_frame)
    try:
        await send({"type": "ready"})
        await send(
            {
                "type": "browser_frame",
                "state": browser.last_state,
                "frame": browser.last_frame,
            }
        )
        await send({"type": "computer_frame", "frame": computer.last_frame})
        while True:
            data = await websocket.receive_json()
            message_type = data.get("type")
            if message_type == "chat":
                text = (data.get("text") or "").strip()
                if not text:
                    continue
                mode = str(data.get("mode") or "auto")
                attachments = data.get("attachments") or []
                try:
                    await runner.start(text, mode, attachments)
                except RuntimeError as exc:
                    await send({"type": "error", "message": str(exc)})
            elif message_type == "stop":
                runner.stop()
            elif message_type == "switch_model":
                new_model = str(data.get("model") or "").strip()
                new_provider = str(data.get("provider") or "").strip()
                if new_model or new_provider:
                    patch = {}
                    if new_model:
                        patch["model"] = new_model
                    if new_provider:
                        patch["provider"] = new_provider
                    save_settings(patch)
                    label = f"{new_provider}/{new_model}" if new_provider and new_model else (new_model or new_provider)
                    await send({"type": "model_switched", "model": new_model, "provider": new_provider, "label": label})
            elif message_type == "approval":
                runner.resolve_approval(data.get("id", ""), bool(data.get("approved")))
                if data.get("persist") and data.get("approved"):
                    save_settings({"auto_approve_commands": True})
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        browser.unsubscribe(on_browser_frame)
        computer.unsubscribe(on_computer_frame)
        if not runner.busy:
            ACTIVE_RUNNERS.pop(session_id, None)
            runner.close()
