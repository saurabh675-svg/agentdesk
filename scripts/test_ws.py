"""End-to-end smoke test: create a session, run the agent, print events."""

import asyncio
import json

import httpx
import websockets

BASE = "http://127.0.0.1:8756"


async def main() -> None:
    async with httpx.AsyncClient(timeout=30) as client:
        workspace = (await client.get(f"{BASE}/api/workspace")).json()["path"]
        session = (
            await client.post(f"{BASE}/api/sessions", json={"title": "New chat"})
        ).json()
    session_id = session["id"]
    print(f"session={session_id} workspace={workspace}")

    prompt = (
        "Create a file called agentdesk-smoke.txt in the workspace with exactly the text "
        "'hello from agentdesk'. Read it back to confirm the contents, then run the command "
        "'dir agentdesk-smoke.txt' to verify the file exists. Keep the final answer short."
    )
    async with websockets.connect(
        f"ws://127.0.0.1:8756/ws/chat/{session_id}", max_size=20_000_000
    ) as socket:
        await socket.send(json.dumps({"type": "chat", "text": prompt}))
        while True:
            raw = await asyncio.wait_for(socket.recv(), timeout=300)
            event = json.loads(raw)
            kind = event.get("type")
            if kind == "token":
                print(event["text"], end="", flush=True)
            elif kind == "tool_call":
                print(f"\n[tool_call] {event['name']} {json.dumps(event['args'])[:200]}")
            elif kind == "tool_result":
                print(f"[tool_result {event['ok']}] {event['result'][:300]}")
            elif kind == "approval_request":
                print(f"\n[approval] {event['command']} -> approve")
                await socket.send(json.dumps({"type": "approval", "id": event["id"], "approved": True}))
            elif kind == "message_commit":
                print(f"\n[commit] {event['message']['content'][:300]}")
            elif kind == "message_end":
                print(f"\n[end] {event['message']['content'][:300]}")
            elif kind == "browser_frame":
                print(
                    f"[browser] {event['state']['url']} frame={len(event.get('frame') or '')}"
                )
            elif kind in ("error", "stopped", "done"):
                print(f"\n[{kind}] {event.get('message', '')}")
                if kind in ("error", "done", "stopped"):
                    break
            else:
                print(f"[{kind}]")

    async with httpx.AsyncClient(timeout=30) as client:
        messages = (await client.get(f"{BASE}/api/sessions/{session_id}/messages")).json()
    print(f"\npersisted messages: {len(messages)}")
    for message in messages:
        print(f"  {message['role']}: {message['content'][:120]!r}")


asyncio.run(main())
