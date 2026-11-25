"""Context-window management for the agent loop.

AgentDesk used to keep a crude sliding window: once the message list grew
past 20 entries, everything between the system prompt and the last 16
messages was silently dropped. Long tasks lost their middle - the model
forgot what it had already tried and repeated itself.

This module replaces that with the two techniques proven by LangChain's
deepagents project (MIT, Copyright (c) LangChain, Inc.):

1. **Tool-result eviction** - old tool outputs are replaced by short stubs
   that keep the shape of the result without paying for its tokens.
2. **Summarization** - the evicted middle is summarized into a compact
   digest instead of being thrown away.

Both are reimplemented here for AgentDesk's plain-Python agent loop: no
LangChain, no LangGraph, no extra dependency. Token estimates use the
native Rust core when it is available and a heuristic otherwise.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable

from . import native_core

SUMMARY_PROMPT = """You are compacting the working history of an AI agent so it can keep working
without running out of context.

Write a dense handover note, not a narrative. Preserve:
- the user's goal and any explicit constraints or preferences;
- decisions already made and the reasoning behind them (one line each);
- concrete facts the agent discovered (file paths, function names, values,
  URLs, error messages) exactly as they appeared;
- what has been done, what is in progress, what is still open;
- tool calls that were made and their outcome (success/failure).

Drop: pleasantries, repeated attempts, and any content that is pure noise.
Never invent facts. Keep every file path, identifier, number and URL verbatim.
Use short Markdown bullets. Stay under 400 words unless the history demands more."""


@dataclass
class ContextPolicy:
    """When and how aggressively to compact the context."""

    max_tokens: int = 24000
    max_messages: int = 64
    keep_recent: int = 14
    tool_results_to_keep: int = 6
    tool_result_chars: int = 4000
    force: bool = False


DEFAULT_POLICY = ContextPolicy()


# --------------------------------------------------------------------------- tokens

def estimate_tokens(text: str) -> int:
    """Estimate tokens for a string (native Rust core when available)."""
    if not text:
        return 0
    try:
        return int(native_core.count_tokens(text))
    except Exception:
        return max(1, len(text) // 4)


def _message_text(message: dict) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                parts.append(str(block.get("text") or ""))
            else:
                parts.append(str(block))
        return " ".join(parts)
    return ""


def messages_tokens(messages: list[dict]) -> int:
    total = 0
    for message in messages:
        total += estimate_tokens(_message_text(message))
        for call in message.get("tool_calls") or []:
            try:
                total += estimate_tokens(str(call.get("arguments") or ""))
            except Exception:
                pass
    return total


# --------------------------------------------------------------------------- eviction

def evict_tool_results(messages: list[dict], policy: ContextPolicy = DEFAULT_POLICY) -> tuple[list[dict], int]:
    """Replace old tool outputs with stubs.

    The newest ``tool_results_to_keep`` tool messages stay verbatim; older
    ones become a one-line stub that keeps the first line of output so the
    model still knows what the tool returned.
    """
    tool_indexes = [i for i, m in enumerate(messages) if m.get("role") == "tool"]
    if len(tool_indexes) <= policy.tool_results_to_keep:
        return list(messages), 0

    stale = tool_indexes[: len(tool_indexes) - policy.tool_results_to_keep]
    out = [dict(m) for m in messages]
    evicted = 0
    for index in stale:
        message = out[index]
        content = _message_text(message)
        if len(content) <= 400:
            continue
        first_line = content.strip().splitlines()[0][:160] if content.strip() else ""
        message["content"] = (
            f"[older tool output elided - {len(content)} chars. First line: {first_line}]"
        )
        evicted += 1
    return out, evicted


# --------------------------------------------------------------------------- digest

def digest_messages(messages: list[dict]) -> str:
    """Deterministic digest used when no model summarizer is available.

    It is deliberately factual: tool names, outcome hints, the user's goal and
    any errors - the things that keep a long task coherent.
    """
    lines: list[str] = []
    for message in messages:
        role = message.get("role")
        text = _message_text(message).strip()
        if role == "user" and text:
            lines.append(f"- User asked: {text[:300]}")
        elif role == "assistant":
            calls = message.get("tool_calls") or []
            if calls:
                names = ", ".join(str(c.get("name") or "?") for c in calls[:8])
                lines.append(f"- Assistant called tools: {names}")
            elif text:
                lines.append(f"- Assistant said: {text[:300]}")
        elif role == "tool":
            flat = text.replace("\n", " ")
            marker = "error" if ("error" in flat.lower()[:200] or "fail" in flat.lower()[:200]) else "ok"
            lines.append(f"- tool result ({marker}): {text[:300]}")
    body = "\n".join(lines[-80:])
    return (
        "[Compacted history - the middle of this conversation was summarized to fit the "
        "context window. Facts, paths and decisions below are preserved.]\n" + body
    )


# --------------------------------------------------------------------------- compaction

def should_compact(messages: list[dict], policy: ContextPolicy = DEFAULT_POLICY) -> bool:
    if policy.force:
        return True
    if len(messages) > policy.max_messages:
        return True
    return messages_tokens(messages) > policy.max_tokens


def partition(messages: list[dict], policy: ContextPolicy) -> tuple[list[dict], list[dict], list[dict]]:
    """Split into (head, middle, tail).

    The head keeps the system prompt and the original request, the tail keeps
    the most recent exchanges, and the middle is what gets compacted.
    """
    head: list[dict] = []
    body = list(messages)
    while body and body[0].get("role") == "system":
        head.append(body.pop(0))
    # keep the original user request in the head
    while body and body[0].get("role") == "user":
        head.append(body.pop(0))
    if len(body) > policy.keep_recent:
        tail = body[-policy.keep_recent:]
        middle = body[: -policy.keep_recent]
    else:
        tail = body
        middle = []
    return head, middle, tail


async def compact_messages(
    messages: list[dict],
    policy: ContextPolicy = DEFAULT_POLICY,
    summarizer: Callable[[str], Awaitable[str]] | None = None,
) -> tuple[list[dict], str]:
    """Compact the context window.

    Returns the new message list and a short note describing what happened
    (empty when nothing was compacted).
    """
    if not should_compact(messages, policy):
        return messages, ""

    evicted_messages, evicted_count = evict_tool_results(messages, policy)
    head, middle, tail = partition(evicted_messages, policy)

    if not middle:
        # Nothing old enough to summarize - eviction alone was enough.
        return evicted_messages, (f"elided {evicted_count} old tool outputs" if evicted_count else "")

    digest = ""
    if summarizer is not None:
        try:
            transcript = "\n\n".join(
                f"{m.get('role', '?')}: {_message_text(m)[:2000]}" for m in middle
            )[:24000]
            digest = await summarizer(transcript)
        except Exception:
            digest = ""
    if not digest:
        digest = digest_messages(middle)

    compacted = [
        *head,
        {"role": "user", "content": digest},
        *tail,
    ]
    note = f"compacted {len(middle)} messages ({evicted_count} tool outputs elided)"
    return compacted, note


def overflow_is_context_error(exc: Exception) -> bool:
    """True when a provider error looks like a context-window overflow."""
    status = getattr(exc, "status", None)
    if status == 413:
        return True
    text = str(exc).lower()
    return any(
        marker in text
        for marker in (
            "context length",
            "context_length_exceeded",
            "context window",
            "too many tokens",
            "maximum context",
            "prompt is too long",
            "request too large",
        )
    )
