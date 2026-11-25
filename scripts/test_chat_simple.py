"""Measure a plain model reply through the chat websocket (no tools needed)."""

import asyncio
import json
import time

import httpx
import websockets

BASE = "http://127.0.0.1:8756"


async def main() -> None:
    async with httpx.AsyncClient(timeout=30) as client:
        session = (await client.post(f"{BASE}/api/sessions", json={"title": "Model timing"})).json()
    session_id = session["id"]
    started = time.monotonic()
    try:
        async with websockets.connect(
            f"ws://127.0.0.1:8756/ws/chat/{session_id}", max_size=20_000_000
        ) as socket:
            await socket.send(
                json.dumps(
                    {"type": "chat", "text": "Reply with the single word READY.", "mode": "auto"}
                )
            )
            first = None
            while True:
                event = json.loads(await asyncio.wait_for(socket.recv(), timeout=420))
                kind = event.get("type")
                elapsed = round(time.monotonic() - started, 1)
                if kind == "token" and first is None:
                    first = elapsed
                    print(f"first token after {elapsed}s:", repr(event["text"][:80]))
                elif kind == "message_end":
                    print(f"message_end after {elapsed}s:", repr(event["message"]["content"][:200]))
                    break
                elif kind == "error":
                    print(f"error after {elapsed}s:", event["message"][:300])
                    break
                elif kind in ("done", "stopped"):
                    print(kind, "after", elapsed)
                    break
    finally:
        async with httpx.AsyncClient(timeout=30) as client:
            await client.delete(f"{BASE}/api/sessions/{session_id}")
        print("deleted test session")


asyncio.run(main())
