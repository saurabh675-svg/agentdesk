"""Local sandbox command execution.

Provides a safe, local-only sandbox for running untrusted commands with
resource limits and process isolation. Cloud execution is not implemented;
this module runs commands locally under a Windows Job Object with bounded
lifetime and restricted environment.
"""

import os
import time
import uuid

from .tools.shell import run_command

_MAX_SESSIONS = 32
_SESSIONS: dict[str, dict] = {}


def _prune_sessions() -> None:
    if len(_SESSIONS) <= _MAX_SESSIONS:
        return
    oldest = sorted(_SESSIONS.items(), key=lambda item: item[1]["created_at"])
    for session_id, _descriptor in oldest[: len(_SESSIONS) - _MAX_SESSIONS]:
        _SESSIONS.pop(session_id, None)


async def create_sandbox(name: str = "agentdesk") -> dict:
    """Create a local sandbox session. Returns a session descriptor."""
    session_id = f"sandbox-{uuid.uuid4().hex[:12]}"
    descriptor = {
        "session_id": session_id,
        "name": name,
        "created_at": time.time(),
        "local": True,
    }
    _SESSIONS[session_id] = descriptor
    _prune_sessions()
    return descriptor


async def run_sandbox(session_id: str, command: str) -> dict:
    """Run a command in the local sandbox with a bounded timeout and minimal environment."""
    if session_id not in _SESSIONS:
        raise KeyError("Unknown or expired sandbox session")
    try:
        result = await run_command(command, cwd=os.getcwd(), timeout=120)
        return {
            "session_id": session_id,
            "command": command,
            "exit_code": result["exit_code"],
            "output": result["output"],
            "timed_out": result["timed_out"],
            "local": True,
        }
    except Exception as exc:
        return {
            "session_id": session_id,
            "command": command,
            "exit_code": -1,
            "output": str(exc),
            "timed_out": False,
            "local": True,
            "error": str(exc),
        }
