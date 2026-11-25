"""Call the model directly with the same messages AgentDesk sends for attachments."""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agent import TOOL_SCHEMAS, AgentRunner, build_system_prompt
from app.config import UPLOADS_DIR, load_settings
from app.engine.openai_compat import stream_completion
from app.mcp_manager import mcp_manager


async def main() -> None:
    settings = load_settings()
    workspace = settings["workspace"]
    files = sorted(UPLOADS_DIR.glob("*"), key=lambda p: p.stat().st_mtime)
    text_files = [p for p in files if p.is_file() and p.suffix == ".txt"]
    print("upload files:", [p.name for p in text_files])
    messages = [
        {"role": "system", "content": build_system_prompt(workspace)},
        {"role": "user", "content": "Repeat the contents of the two attached text files, one per line."},
    ]
    for path in text_files[-2:]:
        messages.append({"role": "user", "content": f"[Attached file {path.name} at {path}.]\n{path.read_text()}"})

    tokens = 0
    started = time.monotonic()

    async def on_token(piece: str) -> None:
        nonlocal tokens
        tokens += 1
        if tokens == 1:
            print("first token", round(time.monotonic() - started, 1))
        if tokens % 20 == 0:
            print("tokens", tokens, round(time.monotonic() - started, 1))

    try:
        result = await stream_completion(
            settings, messages, TOOL_SCHEMAS + mcp_manager.tool_schemas(), on_token
        )
        print("done in", round(time.monotonic() - started, 1), "content:", repr(result["content"][:500]))
        print("tool calls:", len(result["tool_calls"]))
    except Exception as exc:
        print("failed after", round(time.monotonic() - started, 1), type(exc).__name__, str(exc)[:500])


asyncio.run(main())
