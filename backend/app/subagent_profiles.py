"""Sub-agents: small, specialised agents the main agent can delegate to.

Adapted from the sub-agent architecture of the deepagents project (MIT,
Copyright (c) LangChain, Inc.): a parent agent calls a ``spawn_agent`` tool,
the child runs its own loop with a restricted tool set and its own step
budget, and only its final report comes back to the parent. The parent's
context stays clean and the child cannot wander into unrelated work.

AgentDesk keeps its own inventions in this area: every sub-agent runs through
the same tool dispatcher as the parent, so policy checks, approvals,
telemetry and the native scrubbing all apply unchanged.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable

from . import telemetry

SUBAGENT_SYSTEM_PROMPT = """You are a sub-agent working inside AgentDesk.

The calling agent only sees your final report - not your intermediate steps,
tool results or status updates. Therefore your final message must be a
complete, self-contained answer: what you found, the evidence (file paths,
commands and their output, URLs you actually visited), and your conclusion.

Rules:
- Do not ask follow-up questions. You cannot see the user's reply.
- Never claim you did something you did not do. Report failures honestly.
- Prefer evidence over inference: quote the exact command output or line.
- Keep the report tight. No preamble, no filler, no "I hope this helps".
- If the task is out of your scope, say so in one sentence and stop.
"""

RESEARCHER_PROMPT = """You are a research sub-agent working inside AgentDesk.

You investigate and return findings. Read-only access only: you may browse,
search and read files, but you never edit, create or delete anything.

Your final report must list:
- the findings, each with its source (URL or file path);
- conflicting evidence, if any;
- a one-paragraph conclusion.
Do not pad the report with process narration.
"""

CODE_REVIEWER_PROMPT = """You are a code review sub-agent working inside AgentDesk.

You read code and report problems. You never modify files.

Look for: correctness bugs, broken edge cases, race conditions, missing error
handling, security issues (injection, secrets, path traversal), and places
where the code contradicts its own comments or the project's conventions.

For each finding give: file path, line number, the problem in one sentence,
and why it matters. Rank findings by severity. If the code is sound, say so
plainly instead of inventing issues.
"""

TEST_RUNNER_PROMPT = """You are a test and verification sub-agent working inside AgentDesk.

You run the project's real checks and report the real result.

1. Read the manifest (package.json, pyproject.toml, requirements.txt) to find
   the actual test and build commands.
2. Run the narrowest relevant check first, then the broader suite.
3. Read the real output. Quote the failing test names and the first error.
4. Never claim a test passed unless you saw it pass.

Your final report: commands run, their exit status, what passed, what failed,
and the smallest next step to fix the failures.
"""

DOC_WRITER_PROMPT = """You are a documentation sub-agent working inside AgentDesk.

You write documentation files for the project. You may create or edit
documentation, but you do not change source code.

Write for a reader who has not seen the codebase. Document what exists, not
what you wish existed. Include exact commands, paths and names taken from the
repository. Keep the structure the project already uses.
"""


@dataclass
class SubAgentProfile:
    """A specialist the parent agent can delegate to."""

    name: str
    description: str
    prompt: str
    tools: list[str] | None = None  # None = every tool
    max_steps: int = 8
    allow_parallel: bool = True


READ_ONLY_TOOLS = {
    "list_files",
    "read_file",
    "list_skills",
    "use_skill",
    "browser_navigate",
    "browser_read",
    "browser_links",
    "browser_elements",
    "browser_extract",
    "browser_search",
    "web_search",
    "brain_search",
    "memory_search",
    "list_sessions",
    "read_session",
    "list_automations",
    "provider_health",
    "credentials_check",
}

NO_WRITE_TOOLS = READ_ONLY_TOOLS | {"run_command"}

PROFILES: dict[str, SubAgentProfile] = {
    "general-purpose": SubAgentProfile(
        name="general-purpose",
        description=(
            "General-purpose agent for researching complex questions, searching files and "
            "content, and executing multi-step tasks. Use it for any complex, context-heavy "
            "work that would flood your own context."
        ),
        prompt=SUBAGENT_SYSTEM_PROMPT,
        max_steps=12,
    ),
    "researcher": SubAgentProfile(
        name="researcher",
        description=(
            "Read-only researcher. Searches the web and the local knowledge base and returns "
            "findings with sources. Never edits anything."
        ),
        prompt=RESEARCHER_PROMPT,
        tools=sorted(READ_ONLY_TOOLS),
        max_steps=8,
    ),
    "code-reviewer": SubAgentProfile(
        name="code-reviewer",
        description=(
            "Reads code and reports correctness, security and convention problems with file "
            "and line references. Never modifies files."
        ),
        prompt=CODE_REVIEWER_PROMPT,
        tools=sorted(NO_WRITE_TOOLS),
        max_steps=8,
    ),
    "test-runner": SubAgentProfile(
        name="test-runner",
        description=(
            "Runs the project's real test and build commands and reports the actual outcome. "
            "Use it whenever you change code."
        ),
        prompt=TEST_RUNNER_PROMPT,
        tools=sorted({"list_files", "read_file", "run_command", "list_skills", "use_skill"}),
        max_steps=10,
    ),
    "doc-writer": SubAgentProfile(
        name="doc-writer",
        description="Writes or updates documentation files for the project.",
        prompt=DOC_WRITER_PROMPT,
        tools=sorted({"list_files", "read_file", "write_file", "edit_file"}),
        max_steps=8,
    ),
}


def profile_listing() -> str:
    """Human readable list used in the tool description."""
    return "\n".join(f"- {p.name}: {p.description}" for p in PROFILES.values())


def get_profile(name: str) -> SubAgentProfile:
    key = (name or "").strip().lower()
    if key in PROFILES:
        return PROFILES[key]
    raise ValueError(f"Unknown sub-agent '{name}'. Available: {', '.join(PROFILES)}")


def tool_allowed(profile: SubAgentProfile, tool_name: str) -> bool:
    if profile.tools is None:
        return True
    return tool_name in profile.tools


def build_task_prompt(task: str, context: str = "") -> str:
    parts = [f"Objective:\n{task.strip()}"]
    if context.strip():
        parts.append(f"Context from the calling agent:\n{context.strip()}")
    parts.append(
        "Work autonomously. When you are done, reply with your final report only - "
        "that report is the only thing the caller receives."
    )
    return "\n\n".join(parts)


@dataclass
class SubAgentResult:
    """Outcome of one sub-agent run."""

    profile: str
    ok: bool
    report: str
    steps: int = 0
    duration_ms: float = 0.0
    error: str = ""
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "profile": self.profile,
            "ok": self.ok,
            "report": self.report,
            "steps": self.steps,
            "duration_ms": round(self.duration_ms, 1),
            "error": self.error,
            "notes": self.notes,
        }


async def run_subagent(
    profile_name: str,
    task: str,
    *,
    context: str = "",
    run_turn: Callable[[str, list[str], int], Awaitable[str]],
    max_steps: int | None = None,
) -> SubAgentResult:
    """Run one sub-agent.

    ``run_turn`` performs a single model turn with the given tool names and
    returns either the final text or a request for more steps. The AgentDesk
    agent supplies this callback so sub-agents reuse the exact same tool
    dispatcher (policy, approvals, telemetry) as the parent.
    """
    try:
        profile = get_profile(profile_name)
    except ValueError as exc:
        return SubAgentResult(profile=str(profile_name), ok=False, report="", error=str(exc)[:200])
    started = time.time()
    telemetry.counter("agentdesk_subagent_total", profile=profile.name)
    try:
        report, steps = await run_turn(
            build_task_prompt(task, context),
            profile.tools or [],
            int(max_steps or profile.max_steps),
        )
    except Exception as exc:
        telemetry.counter("agentdesk_subagent_total", profile=profile.name, outcome="error")
        return SubAgentResult(
            profile=profile.name,
            ok=False,
            report="",
            duration_ms=(time.time() - started) * 1000,
            error=str(exc)[:500],
        )
    telemetry.counter("agentdesk_subagent_total", profile=profile.name, outcome="ok")
    telemetry.observe(
        "agentdesk_subagent_duration_seconds", (time.time() - started) * 1000, profile=profile.name
    )
    return SubAgentResult(
        profile=profile.name,
        ok=bool(report.strip()),
        report=report.strip(),
        steps=steps,
        duration_ms=(time.time() - started) * 1000,
    )


async def run_many(
    jobs: list[dict],
    *,
    run_turn: Callable[[str, list[str], int], Awaitable[str]],
) -> list[SubAgentResult]:
    """Run several sub-agents in parallel (deepagents' async sub-agents)."""

    async def one(job: dict) -> SubAgentResult:
        return await run_subagent(
            str(job.get("profile") or "general-purpose"),
            str(job.get("task") or ""),
            context=str(job.get("context") or ""),
            run_turn=run_turn,
        )

    return list(await asyncio.gather(*(one(job) for job in jobs)))
