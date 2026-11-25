"""HTTP bridge for the AgentDesk MCP server — 0.6.

The MCP server itself speaks stdio/HTTP. This route is the loopback
JSON-RPC surface so an external client (or the UI) can ask what the
server exposes without spawning a second process.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/capabilities")
def capabilities() -> dict:
    return {
        "server": "agentdesk-browser",
        "protocol": "agentdesk.ipc/1",
        "version": "0.7.0",
        "tools": [
            "browser_navigate",
            "browser_snapshot",
            "browser_elements",
            "browser_click_element",
            "browser_type_element",
            "browser_structured_extract",
            "workspace_list",
        ],
        "transports": ["stdio", "http"],
        "note": "Run `python -m app.mcp_server` for the stdio transport.",
    }


@router.post("/call")
async def call_tool(body: dict) -> dict:
    """Loopback bridge: call a tool by name (used by the UI + tests)."""
    name = str(body.get("name") or "")
    args = body.get("args") or {}
    from ..tools.browser import browser
    if name == "browser_navigate":
        out = await browser.navigate(str(args.get("url") or "about:blank"))
        return {"ok": True, "result": out.get("state", {})}
    if name == "browser_snapshot":
        out = await browser.snapshot(text_limit=int(args.get("text_limit", 3600)))
        return {"ok": True, "result": out.get("snapshot", {})}
    if name == "browser_elements":
        out = await browser.elements(limit=int(args.get("limit", 60)))
        return {"ok": True, "result": out.get("summary", "")}
    if name == "browser_click_element":
        out = await browser.click_element(int(args.get("index", 0)))
        return {"ok": True, "result": out.get("state", {})}
    if name == "browser_type_element":
        out = await browser.type_element(
            int(args.get("index", 0)), str(args.get("text") or ""), submit=bool(args.get("submit", False))
        )
        return {"ok": True, "result": out.get("state", {})}
    if name == "browser_structured_extract":
        out = await browser.structured_extract()
        return {"ok": True, "result": out.get("extract", {})}
    return {"ok": False, "error": f"Unknown tool: {name}"}
