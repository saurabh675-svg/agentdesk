"""Verify the Hard-mode fallback: invalid OpenRouter key -> browser web chat.

Restores the original saved key even if the run fails or is interrupted.
"""

import asyncio
import json
import time

import httpx
import websockets

BASE = "http://127.0.0.1:8756"


async def main() -> None:
    async with httpx.AsyncClient(timeout=30) as client:
        original = (await client.get(f"{BASE}/api/settings")).json()
        original_key = original.get("hard_api_key", "")
        await client.put(f"{BASE}/api/settings", json={"hard_api_key": "sk-or-v1-invalid-test-key"})
        session = (
            await client.post(f"{BASE}/api/sessions", json={"title": "Hard fallback test"})
        ).json()

    saw_fallback = False
    try:
        async with websockets.connect(
            f"ws://127.0.0.1:8756/ws/chat/{session['id']}", max_size=20_000_000
        ) as socket:
            await socket.send(
                json.dumps(
                    {
                        "type": "chat",
                        "text": "Reply with one short sentence.",
                        "mode": "hard",
                    }
                )
            )
            deadline = time.monotonic() + 50
            while time.monotonic() < deadline:
                try:
                    event = json.loads(await asyncio.wait_for(socket.recv(), timeout=5))
                except asyncio.TimeoutError:
                    continue
                kind = event.get("type")
                if kind == "notice":
                    print("notice:", event["message"])
                    if "falling back" in event["message"].lower():
                        saw_fallback = True
                elif kind == "browser_frame":
                    state = event.get("state") or {}
                    if "chatgpt.com" in (state.get("url") or ""):
                        print("browser:", state.get("url"), "headless", state.get("headless"))
                elif kind == "error":
                    print("error:", event["message"][:300])
                    break
                if saw_fallback:
                    print("hard-route fallback confirmed")
                    await socket.send(json.dumps({"type": "stop"}))
                    break
            else:
                print("timed out without an explicit fallback notice")
    finally:
        async with httpx.AsyncClient(timeout=30) as client:
            await client.put(f"{BASE}/api/settings", json={"hard_api_key": original_key})
            await client.delete(f"{BASE}/api/sessions/{session['id']}")
        print("restored key and deleted test session")
    if not saw_fallback:
        raise SystemExit(1)


asyncio.run(main())
