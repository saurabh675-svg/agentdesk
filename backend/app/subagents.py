"""Agent subagent pools: lightweight background agents spawned by an orchestrator.

Two different things live in the sub-agent area of AgentDesk:

- this module: the *pool* of long-running background agents (each one its own
  session, reachable from the sessions API);
- ``subagent_profiles``: the *specialists* the main agent can delegate to
  synchronously with the ``spawn_agent`` tool.

Both are re-exported here so callers can import from one place.
"""

from typing import Callable, Awaitable

from .agent import AgentRunner
from . import db
from .config import load_settings
from .engine.openai_compat import stream_completion


class SubagentPool:
    def __init__(self) -> None:
        self._sessions: dict[str, AgentRunner] = {}

    async def spawn(self, prompt: str, title: str = "Subagent") -> dict:
        session = db.create_session(title=title)
        runner = AgentRunner(session["id"], self._broadcast)
        self._sessions[str(session["id"])] = runner
        await runner.start(prompt, "auto")
        return {"id": session["id"], "title": title, "session_id": session["id"], "busy": runner.busy}

    def get(self, session_id: int) -> AgentRunner | None:
        return self._sessions.get(str(session_id))

    async def _broadcast(self, payload: dict) -> None:
        # Intentionally local-only for now; OpenBot-style AG-UI streaming can hook here later.
        pass


subagent_pool = SubagentPool()


from .subagent_profiles import (  # noqa: E402  (re-export)
    PROFILES,
    SubAgentProfile,
    SubAgentResult,
    get_profile,
    profile_listing,
    run_subagent,
    tool_allowed,
)
