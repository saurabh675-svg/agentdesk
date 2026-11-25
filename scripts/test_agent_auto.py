"""End-to-end smoke test for the default (saved model) agent loop."""

import asyncio
import json
import time
from pathlib import Path

import httpx
import websockets

BASE = "http://127.0.0.1:8756"
TARGET = Path.home() / "AgentDeskProjects" / "hello-agentdesk.txt"


async def main() -> None:
    async with httpx.AsyncClient(timeout=30) as client:
        session = (
            await client.post(
                f"{BASE}/api/sessions", json={"title": "Agent smoke test", "workspace": str(TARGET.parent)}
            )
        ).json()
    session_id = session["id"]
    print("session", session_id)

    ok = False
    try:
        async with websockets.connect(
            f"ws://127.0.0.1:8756/ws/chat/{session_id}", max_size=20_000_000
        ) as socket:
            await socket.send(
                json.dumps(
                    {
                        "type": "chat",
                        "text": (
                            "Create a file named hello-agentdesk.txt in the workspace root. "
                            "Its exact content should be: AgentDesk is ready"
                        ),
                        "mode": "auto",
                    }
                )
            )
            deadline = time.monotonic() + 240
            while time.monotonic() < deadline:
                try:
                    event = json.loads(await asyncio.wait_for(socket.recv(), timeout=20))
                except asyncio.TimeoutError:
                    print("waiting…")
                    continue
                kind = event.get("type")
                if kind == "tool_call":
                    print("tool_call:", event["name"], json.dumps(event.get("args"))[:160])
                elif kind == "tool_result":
                    print("tool_result:", event["name"], "ok" if event["ok"] else "FAILED")
                elif kind == "message_end":
                    print("reply:", event["message"]["content"][:300])
                    ok = True
                    break
                elif kind == "error":
                    print("error:", event["message"])
                    break
                elif kind == "stopped":
                    print("stopped")
                    break
    finally:
        exists = TARGET.exists()
        print("file exists:", exists)
        if exists:
            print("file content:", repr(TARGET.read_text(encoding="utf-8")))
            TARGET.unlink()
            print("removed test file")
        async with httpx.AsyncClient(timeout=30) as client:
            await client.delete(f"{BASE}/api/sessions/{session_id}")
            print("deleted test session")
    if not ok:
        raise SystemExit(1)


asyncio.run(main())
