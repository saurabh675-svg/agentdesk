"""Web search for the model: Firecrawl first, free DuckDuckGo fallback.

AgentDesk must answer "check global competition"-style live queries even without a
paid Firecrawl key, so the fallback keeps the radar/earnings live signals real.
"""

import asyncio
from typing import Any

import httpx

from ..config import load_settings

FIRECRAWL_SEARCH_URL = "https://api.firecrawl.dev/v2/search"
FIRECRAWL_MAX_RESULTS = 20


def _summarize(results: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for result in results[:10]:
        title = str(result.get("title") or result.get("url") or "Result")
        url = str(result.get("url") or "")
        description = str(result.get("description") or "").strip()
        line = f"- **{title}**"
        if url:
            line += f" — {url}"
        if description:
            line += f": {description}"
        lines.append(line)
    return "\n".join(lines) or "(no results)"


def _search_ddgs(query: str, limit: int) -> list[dict[str, Any]]:
    """Free web search via DuckDuckGo (ddgs) when Firecrawl is not configured."""
    try:
        from ddgs import DDGS
    except Exception:
        return []
    out: list[dict[str, Any]] = []
    try:
        with DDGS() as ddgs:
            for result in ddgs.text(query[:300], max_results=max(1, limit)) or []:
                if not isinstance(result, dict):
                    continue
                href = str(result.get("href") or result.get("url") or "")
                out.append(
                    {
                        "title": str(result.get("title") or href or "Result"),
                        "url": href,
                        "description": str(result.get("body") or result.get("description") or "")[:400],
                    }
                )
    except Exception:
        return []
    return out


async def search_web(query: str, limit: int = 10) -> str:
    settings = load_settings()
    api_key = str(settings.get("firecrawl_api_key") or "").strip()
    try:
        limit = max(1, min(int(limit or 10), FIRECRAWL_MAX_RESULTS))
    except (TypeError, ValueError):
        limit = 10
    if not api_key:
        # No Firecrawl key: fall back to a free search so live queries still work.
        results = await asyncio.to_thread(_search_ddgs, query, limit)
        return _summarize(results) or "(no results)"
    payload: dict[str, Any] = {"query": query[:500], "limit": limit}
    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.post(
            FIRECRAWL_SEARCH_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
        )
        response.raise_for_status()
    data = response.json().get("data", {})
    results = data.get("web", []) if isinstance(data, dict) else []
    if not results:
        return "(no results)"
    return _summarize(results)
