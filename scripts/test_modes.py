"""Exercise Hard mode and browser-chat routing without needing a signed-in account.

Shows notices/frames for a limited time, then stops the run. The ChatGPT/Gemini window is
left open on purpose so the user can finish a sign-in or human check.
"""

import asyncio
import json
import sys
import time

import httpx
import websockets

BASE = "http://127.0.0.1:8756"


async def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "hard"
    seconds = int(sys.argv[2]) if len(sys.argv) > 2 else 45

    async with httpx.AsyncClient(timeout=30) as client:
        session = (await client.post(f"{BASE}/api/sessions", json={"title": f"{mode} test"})).json()
    session_id = session["id"]
    print("session", session_id, "mode", mode)

    last_url = None
    finished = False
    try:
        async with websockets.connect(
            f"ws://127.0.0.1:8756/ws/chat/{session_id}", max_size=20_000_000
        ) as socket:
            await socket.send(
                json.dumps(
                    {
                        "type": "chat",
                        "text": "Reply with exactly one short sentence: the browser route works.",
                        "mode": mode,
                    }
                )
            )
            deadline = time.monotonic() + seconds
            while time.monotonic() < deadline:
                try:
                    event = json.loads(await asyncio.wait_for(socket.recv(), timeout=4))
                except asyncio.TimeoutError:
                    continue
                kind = event.get("type")
                if kind == "notice":
                    print(f"[{time.strftime('%H:%M:%S')}] notice:", event["message"])
                elif kind == "browser_frame":
                    state = event.get("state") or {}
                    if state.get("url") != last_url:
                        last_url = state.get("url")
                        print("  browser:", last_url, "|", state.get("title"), "| headless",
                              state.get("headless"))
                elif kind == "error":
                    print("  error:", event["message"])
                    finished = True
                    break
                elif kind == "token":
                    print("  token:", event["text"][:100])
                elif kind == "message_end":
                    print("  message_end:", event["message"]["content"][:200])
                    finished = True
                    break
                elif kind in ("ready", "message_start", "done", "stopped"):
                    print(" ", kind)
            if not finished:
                await socket.send(json.dumps({"type": "stop"}))
                print("sent stop; browser window stays open for sign-in")
    finally:
        async with httpx.AsyncClient(timeout=30) as client:
            await client.delete(f"{BASE}/api/sessions/{session_id}")
            print("deleted test session")


asyncio.run(main())
