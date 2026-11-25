"""Smoke test the terminal websocket."""

import asyncio
import json
import sys

import httpx
import websockets

BASE = "http://127.0.0.1:8756"


async def main() -> None:
    async with httpx.AsyncClient(timeout=30) as client:
        sessions = (await client.get(f"{BASE}/api/sessions")).json()
        if not sessions:
            sessions = [(await client.post(f"{BASE}/api/sessions", json={"title": "Terminal test"})).json()]
    session_id = sessions[0]["id"]
    print("session", session_id)

    async with websockets.connect(f"ws://127.0.0.1:8756/ws/terminal/{session_id}") as socket:
        ready = json.loads(await asyncio.wait_for(socket.recv(), timeout=60))
        print("ready:", {k: (v[:120] if isinstance(v, str) else v) for k, v in ready.items() if k != "buffer"})
        if ready.get("error"):
            print("terminal error:", ready["error"])
            return
        await socket.send(json.dumps({"type": "input", "data": "Write-Output AGENTDESK_TERMINAL_OK\r"}))
        buffer = ""
        try:
            while "AGENTDESK_TERMINAL_OK" not in buffer:
                event = json.loads(await asyncio.wait_for(socket.recv(), timeout=30))
                if event.get("type") == "output":
                    buffer += event["data"]
        except asyncio.TimeoutError:
            print("timeout waiting for command output")
        print("output tail:", repr(buffer[-600:]))
        await socket.send(json.dumps({"type": "restart"}))
        try:
            while True:
                event = json.loads(await asyncio.wait_for(socket.recv(), timeout=5))
                if event.get("type") == "cleared":
                    print("restart acknowledged")
                    break
        except asyncio.TimeoutError:
            print("no restart acknowledgement")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:
        print(f"FAILED: {type(exc).__name__}: {exc}")
        sys.exit(1)
