"""Smoke test chat file attachments: upload two text files and ask the agent about them."""

import asyncio
import json
import time
from pathlib import Path

import httpx
import websockets

BASE = "http://127.0.0.1:8756"
UPLOADS_DIR = Path(r"C:\Users\saura\agentdesk\data\uploads")


async def main() -> None:
    async with httpx.AsyncClient(timeout=60) as client:
        session = (
            await client.post(f"{BASE}/api/sessions", json={"title": "Attachment smoke test"})
        ).json()
        uploads = await client.post(
            f"{BASE}/api/uploads/files",
            files=[
                ("files", ("alpha.txt", b"Alpha file contents.", "text/plain")),
                ("files", ("beta.txt", b"Beta file contents.", "text/plain")),
            ],
        )
        if uploads.status_code != 200:
            print("upload failed", uploads.status_code, uploads.text)
            await client.delete(f"{BASE}/api/sessions/{session['id']}")
            return
        attached = uploads.json()
        print("uploaded", [(a["name"], a["size"]) for a in attached])
        if any(not (UPLOADS_DIR / a["id"]).is_file() for a in attached):
            print("missing upload file on disk")
            return

        try:
            async with websockets.connect(
                f"ws://127.0.0.1:8756/ws/chat/{session['id']}", max_size=20_000_000
            ) as socket:
                await socket.send(
                    json.dumps(
                        {
                            "type": "chat",
                            "text": "Repeat the contents of the two attached text files, one per line.",
                            "mode": "auto",
                            "attachments": attached,
                        }
                    )
                )
                deadline = time.monotonic() + 180
                while time.monotonic() < deadline:
                    try:
                        event = json.loads(await asyncio.wait_for(socket.recv(), timeout=20))
                    except asyncio.TimeoutError:
                        print("waiting...")
                        continue
                    if event["type"] in ("message_start", "tool_call", "tool_result", "file_changed", "approval_request"):
                        print(event["type"], {k: v for k, v in event.items() if k not in ("id",)})
                    if event["type"] == "error":
                        print("error:", event["message"])
                        return
                    if event["type"] == "message_end":
                        print("reply:", event["message"]["content"])
                        return
                    if event["type"] == "token":
                        print("token:", event["text"][:100])
                print("timed out")
        finally:
            await client.delete(f"{BASE}/api/sessions/{session['id']}")
            print("deleted attachment smoke-test session")


asyncio.run(main())
