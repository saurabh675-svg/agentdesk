"""DeskPet Expert — a generalist companion that can answer in any field.

Three knowledge sources, all free and local-first:

1. **Web search** (DuckDuckGo / `ddgs`, optional Firecrawl) for live facts.
2. **Knowledge database** — the brain (SQLite FTS5), saved skills, session
   history and the workspace index.
3. **MCP skills** — tools exposed by configured MCP servers, which the expert
   can call on request (e.g. "what are my Linear issues?").

The answer itself is produced by the same provider chain the chat uses
(free keyless gateways first, local llama.cpp as the offline fallback). If no
provider is reachable, the expert still returns a useful, source-backed digest
instead of failing.
"""

from __future__ import annotations

import asyncio
import re
import time
from typing import Any

from . import brain as _brain
from . import skills as _skills
from .config import load_settings, resolve_settings
from .engine.gateways import GATEWAY_ENDPOINTS, GATEWAY_MODELS, key_for_gateway
from .engine import llama_local

WEB_TIMEOUT_S = 12.0
MAX_SOURCE_CHARS = 320


# --------------------------------------------------------------------------- #
# 1. Web search
# --------------------------------------------------------------------------- #
def _search_web_sync(query: str, limit: int = 5) -> list[dict]:
    """DuckDuckGo text search. Runs in a worker thread (blocking HTTP)."""
    try:
        from ddgs import DDGS  # type: ignore
    except Exception:
        return []

    def _run() -> list[dict]:
        out: list[dict] = []
        try:
            with DDGS(timeout=8) as client:
                for hit in client.text(query, max_results=limit):
                    out.append({
                        "title": str(hit.get("title") or "")[:200],
                        "url": str(hit.get("href") or hit.get("url") or ""),
                        "snippet": str(hit.get("body") or hit.get("description") or "")[:MAX_SOURCE_CHARS],
                        "source": "web",
                    })
        except Exception:
            return out
        return out

    try:
        return _run()
    except Exception:
        return []


async def search_web(query: str, limit: int = 5) -> list[dict]:
    """Web search with an optional Firecrawl upgrade when the user has a key."""
    settings = load_settings()
    key = str(settings.get("firecrawl_api_key") or "").strip()
    if key:
        try:
            from .engine.firecrawl import search_web as _firecrawl_search
            text = await _firecrawl_search(query, limit)
            if text and "no results" not in text.lower():
                return [{
                    "title": f"Firecrawl: {query}",
                    "url": "https://firecrawl.dev",
                    "snippet": text[:MAX_SOURCE_CHARS],
                    "source": "firecrawl",
                }]
        except Exception:
            pass  # fall through to DDGS
    return await asyncio.to_thread(_search_web_sync, query, limit)


# --------------------------------------------------------------------------- #
# 2. Knowledge database (brain + skills + sessions + workspace)
# --------------------------------------------------------------------------- #
def search_knowledge(query: str, limit: int = 6) -> list[dict]:
    """Search the local knowledge base: brain notes, skills, recent sessions."""
    out: list[dict] = []
    terms = [t for t in re.split(r"\W+", query.lower()) if len(t) > 2][:6]
    if not terms:
        terms = [query.lower()[:40]] if query else []

    # --- brain (SQLite FTS5 when enabled, else JSON scan) -------------------
    try:
        for note in _brain.search_brain_notes(query, limit=limit):
            body = str(note.get("body") or "")
            out.append({
                "title": str(note.get("title") or "note"),
                "url": "",
                "snippet": body[:MAX_SOURCE_CHARS],
                "source": "memory",
                "score": float(note.get("score") or 0.0),
            })
    except Exception:
        pass

    # --- skills ------------------------------------------------------------
    try:
        for skill in _skills.list_skills():
            hay = f"{skill.get('name','')} {skill.get('description','')}".lower()
            if any(term in hay for term in terms) or not terms:
                out.append({
                    "title": f"Skill: {skill.get('name')}",
                    "url": "",
                    "snippet": str(skill.get("description") or "")[:MAX_SOURCE_CHARS],
                    "source": "skill",
                })
    except Exception:
        pass

    # --- session history (titles give context of what the user is doing) ----
    try:
        from . import db as _db
        sessions = _db.list_sessions()
        for s in sessions[:12]:
            title = str(s.get("title") or "")
            if any(term in title.lower() for term in terms) or not terms:
                out.append({
                    "title": f"Session: {title}",
                    "url": "",
                    "snippet": title[:MAX_SOURCE_CHARS],
                    "source": "session",
                })
            if len(out) >= limit * 2:
                break
    except Exception:
        pass

    # --- workspace files ----------------------------------------------------
    try:
        from pathlib import Path
        from .config import load_settings as _ls
        root = Path(str(_ls().get("workspace") or ""))
        if root and root.exists():
            hits = []
            for path in list(root.rglob("*"))[:4000]:
                if not path.is_file() or path.stat().st_size > 400_000:
                    continue
                rel = str(path.relative_to(root))
                if any(term in rel.lower() for term in terms):
                    hits.append({
                        "title": f"File: {rel}",
                        "url": "",
                        "snippet": rel[:MAX_SOURCE_CHARS],
                        "source": "workspace",
                    })
                if len(hits) >= 5:
                    break
            out.extend(hits)
    except Exception:
        pass

    return _dedupe(out)[: limit * 2]


# --------------------------------------------------------------------------- #
# 3. MCP skills
# --------------------------------------------------------------------------- #
def mcp_skills() -> list[dict]:
    """Tools exposed by the connected MCP servers."""
    try:
        from .mcp_manager import manager
        schemas = manager.tool_schemas()
    except Exception:
        return []
    out = []
    for schema in schemas:
        fn = schema.get("function") or {}
        out.append({
            "name": fn.get("name") or "",
            "description": str(fn.get("description") or "")[:200],
            "server": str(fn.get("name") or "").split("_", 2)[1] if "_" in str(fn.get("name") or "") else "",
        })
    return out


async def call_mcp_tool(tool_name: str, arguments: dict | None = None) -> dict:
    """Call one MCP tool by its safe name (`mcp_<server>_<tool>`)."""
    try:
        from .mcp_manager import manager
        result = await manager.call_tool(tool_name, arguments or {})
        return {"ok": True, "tool": tool_name, "result": result}
    except Exception as exc:
        return {"ok": False, "tool": tool_name, "error": str(exc)[:400]}


def capabilities() -> dict:
    """What the expert can do right now — shown as badges in the pet panel."""
    caps: dict[str, Any] = {}
    try:
        from .mcp_manager import manager
        caps["mcp_servers"] = [
            {"id": s.get("id"), "name": s.get("name"), "status": s.get("status"), "tool_count": len(s.get("tools") or [])}
            for s in manager.status()
        ]
    except Exception:
        caps["mcp_servers"] = []
    try:
        caps["skills"] = len(_skills.list_skills())
    except Exception:
        caps["skills"] = 0
    try:
        caps["knowledge"] = _brain.get_brain_stats()
    except Exception:
        caps["knowledge"] = {}
    try:
        from . import db as _db
        caps["sessions"] = len(_db.list_sessions())
    except Exception:
        caps["sessions"] = 0
    tools = mcp_skills()
    caps["mcp_tools"] = tools
    caps["web"] = True
    caps["providers"] = _provider_candidates()
    return caps


# --------------------------------------------------------------------------- #
# Provider routing (free gateways first, local model as fallback)
# --------------------------------------------------------------------------- #
def _provider_candidates() -> list[dict]:
    settings = resolve_settings(load_settings())
    out: list[dict] = []
    seen: set[str] = set()
    gateway_models = settings.get("gateway_models") or {}
    order = list(settings.get("auto_gateways") or ["keyless", "freeai", "vercel", "unorouter", "opencode", "pollinations", "openai"])
    for gateway in order:
        key = key_for_gateway(gateway, settings)
        endpoint = GATEWAY_ENDPOINTS.get(gateway)
        if not endpoint or not key or gateway in seen:
            continue
        seen.add(gateway)
        out.append({
            "provider": gateway,
            "base_url": endpoint,
            "model": str(gateway_models.get(gateway) or GATEWAY_MODELS.get(gateway, "")),
            "api_key": key,
        })
    if "local" not in seen:
        out.append({
            "provider": "local",
            "base_url": llama_local.LOCAL_URL,
            "model": settings.get("local_model") or "",
            "api_key": "local",
        })
    return out


def _compose(context: str, question: str, sources: list[dict], skills: list[dict]) -> str:
    cite = "\n".join(
        f"[{i + 1}] {s.get('title')} — {s.get('url') or s.get('source')}\n    {s.get('snippet','')[:220]}"
        for i, s in enumerate(sources[:8])
    )
    skill_txt = ", ".join(s.get("name", "") for s in skills[:10]) or "none connected"
    return (
        f"You are DeskPet, the expert companion inside AgentDesk. You are precise, "
        f"practical and you never invent facts.\n\n"
        f"You have three knowledge channels:\n"
        f"- WEB SEARCH results (fresh information from the internet)\n"
        f"- LOCAL KNOWLEDGE (the user's memory database, skills, sessions and files)\n"
        f"- MCP SKILLS (tools from connected servers: {skill_txt})\n\n"
        f"Use them when they help. Cite sources with [n] markers matching the list. "
        f"If the answer is uncertain, say so plainly.\n\n"
        f"SOURCES:\n{cite or '(none)'}\n\n"
        f"CONTEXT:\n{context[:6000]}\n\n"
        f"QUESTION: {question}\n\n"
        f"Answer clearly and completely (markdown)."
    )


async def _ask_model(system_prompt: str, question: str) -> tuple[str, str]:
    """Try the provider chain; return (answer, provider-used)."""
    from .engine.openai_compat import stream_completion

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question},
    ]
    settings = resolve_settings(load_settings())
    for cand in _provider_candidates():
        route_settings = {
            **settings,
            "provider": cand["provider"],
            "base_url": cand["base_url"],
            "model": cand["model"],
            "api_key": cand["api_key"],
            "timeout_s": 45,
        }
        if cand["provider"] == "local":
            try:
                await llama_local.ensure()
            except Exception:
                continue
        chunks: list[str] = []

        async def _on_token(text: str) -> None:
            chunks.append(text)

        try:
            await asyncio.wait_for(
                stream_completion(route_settings, messages, [], _on_token),
                timeout=float(route_settings.get("timeout_s") or 45),
            )
            answer = "".join(chunks).strip()
            if answer:
                return answer, cand["provider"]
        except Exception:
            continue
    return "", ""


def _digest_without_model(question: str, sources: list[dict], skills: list[dict]) -> str:
    """No model reachable — still return a source-backed digest."""
    if not sources:
        return (
            "I could not reach a model provider and found nothing in your local "
            f"knowledge base for “{question}”. Try again in a moment, or add an "
            "API key in Settings → Model."
        )
    lines = [f"**{question}**", "", "Direct answer unavailable (no model provider reachable), but here is what I found:", ""]
    for i, s in enumerate(sources[:6], start=1):
        lines.append(f"{i}. **{s.get('title')}** — {s.get('snippet','')[:180]}")
        if s.get("url"):
            lines.append(f"   {s['url']}")
    if skills:
        lines.append("")
        lines.append("Available MCP skills: " + ", ".join(s.get("name", "") for s in skills[:8]))
    return "\n".join(lines)


def _dedupe(items: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for item in items:
        key = (item.get("title") or "")[:80].lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


async def answer(
    question: str,
    use_web: bool = True,
    use_knowledge: bool = True,
    mcp_tool: str | None = None,
    mcp_arguments: dict | None = None,
) -> dict:
    """Answer a question using web + local knowledge + MCP skills."""
    question = (question or "").strip()
    started = time.time()
    if not question:
        return {"answer": "Ask me anything — I'll search the web, my memory and your MCP skills.", "sources": [], "used": {}}

    web_hits: list[dict] = []
    know_hits: list[dict] = []
    tool_result: dict | None = None

    if use_web:
        try:
            web_hits = await search_web(question, limit=5)
        except Exception:
            web_hits = []
    if use_knowledge:
        try:
            know_hits = await asyncio.to_thread(search_knowledge, question, 6)
        except Exception:
            know_hits = []
    if mcp_tool:
        tool_result = await call_mcp_tool(mcp_tool, mcp_arguments or {})

    skills = mcp_skills()
    sources = _dedupe(web_hits + know_hits)[:10]

    context_bits: list[str] = []
    if know_hits:
        context_bits.append("LOCAL KNOWLEDGE:\n" + "\n".join(
            f"- {s.get('title')}: {s.get('snippet','')[:200]}" for s in know_hits[:8]))
    if tool_result:
        context_bits.append("MCP TOOL RESULT:\n" + str(tool_result.get("result") or tool_result.get("error"))[:2000])
    if skills:
        context_bits.append("MCP SKILLS AVAILABLE:\n" + "\n".join(
            f"- {s.get('name')}: {s.get('description','')[:120]}" for s in skills[:12]))

    answer_text, provider = "", ""
    if sources or tool_result:
        answer_text, provider = await _ask_model(
            _compose("\n\n".join(context_bits), question, sources, skills), question
        )
    if not answer_text:
        answer_text = _digest_without_model(question, sources, skills)

    return {
        "answer": answer_text,
        "sources": sources,
        "mcp_tools": skills,
        "tool_result": tool_result,
        "used": {
            "web": len(web_hits),
            "knowledge": len(know_hits),
            "mcp_tools": len(skills),
            "mcp_called": bool(tool_result),
        },
        "provider": provider or "local-digest",
        "elapsed_ms": int((time.time() - started) * 1000),
    }


async def daily_brief() -> dict:
    """A short, sourced briefing built from today's context (used by the schedule)."""
    parts: list[str] = []
    try:
        from . import db as _db
        sessions = _db.list_sessions()[:8]
        if sessions:
            parts.append("RECENT SESSIONS:\n" + "\n".join(f"- {s.get('title')}" for s in sessions))
    except Exception:
        pass
    try:
        notes = _brain.search_brain_notes("recent work project notes", limit=5)
        if notes:
            parts.append("NOTES:\n" + "\n".join(f"- {n.get('title')}: {str(n.get('body') or '')[:160]}" for n in notes))
    except Exception:
        pass
    skills = mcp_skills()
    if skills:
        parts.append("MCP SKILLS: " + ", ".join(s.get("name", "") for s in skills[:8]))
    question = "Give me a short briefing of what I was working on and what deserves attention next."
    body, provider = await _ask_model(
        "You are DeskPet writing a 5-line daily briefing for the app owner. Be concrete.",
        question + "\n\n" + "\n\n".join(parts),
    )
    return {
        "brief": body or "No model provider reachable for the brief — your local context was collected but not summarised.",
        "provider": provider or "none",
        "sources": _dedupe(parts and [] or []),
    }
