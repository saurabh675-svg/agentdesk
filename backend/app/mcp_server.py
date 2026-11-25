"""AgentDesk as an MCP server — 0.6.

Publishes the same browser + workspace tools the agent uses so any MCP
client (Claude Desktop, Cline, Continue, Goose…) can drive the signed-in
browser over stdio or loopback HTTP. Thin adapter over ``tools/browser.py``;
policy stays in ``policy.py``.

Run as a server: ``python -m app.mcp_server``  (stdio transport)
"""

from __future__ import annotations

import asyncio
import json

try:
    from mcp.server.mcpserver import MCPServer  # mcp >= 2.0
except Exception:  # pragma: no cover
    from mcp.server.fastmcp import FastMCP as MCPServer  # mcp < 2.0 fallback

from .policy import can_execute


def _result(text: str) -> dict:
    return {"content": [{"type": "text", "text": text}]}


class AgentDeskMCPServer:
    """MCP server packaging the browser tools (loopback + stdio)."""

    def __init__(self) -> None:
        self.server = MCPServer("agentdesk-browser")

        @self.server.tool()
        async def browser_navigate(url: str) -> dict:  # noqa: ANN204
            from .tools.browser import browser
            out = await browser.navigate(url)
            return _result(f"Navigated. {out.get('state', {})}")

        @self.server.tool()
        async def browser_snapshot(text_limit: int = 3600) -> dict:  # noqa: ANN204
            from .tools.browser import browser
            out = await browser.snapshot(text_limit=text_limit)
            snap = out.get("snapshot", {})
            lines = [f"URL: {snap.get('url')}", f"Title: {snap.get('title')}", "", snap.get("text", "")[:2000]]
            return _result("\n".join(lines))

        @self.server.tool()
        async def browser_elements(limit: int = 60) -> dict:  # noqa: ANN204
            from .tools.browser import browser
            out = await browser.elements(limit=limit)
            return _result(out.get("summary", ""))

        @self.server.tool()
        async def browser_click_element(index: int) -> dict:  # noqa: ANN204
            from .tools.browser import browser
            out = await browser.click_element(index)
            return _result(f"Clicked [{index}]. {out.get('state', {})}")

        @self.server.tool()
        async def browser_type_element(index: int, text: str, submit: bool = False) -> dict:  # noqa: ANN204
            from .tools.browser import browser
            out = await browser.type_element(index, text, submit=submit)
            return _result(f"Typed [{index}]. {out.get('state', {})}")

        @self.server.tool()
        async def browser_structured_extract() -> dict:  # noqa: ANN204
            from .tools.browser import browser
            out = await browser.structured_extract()
            return _result(json.dumps(out.get("extract", {}), ensure_ascii=False)[:4000])

        @self.server.tool()
        async def workspace_list(path: str = ".") -> dict:  # noqa: ANN204
            from .tools import fs
            from .config import load_settings
            ws = load_settings().get("workspace")
            text = await fs.list_files(ws, path)
            return _result(text[:4000])

    async def run_stdio(self) -> None:
        await self.server.run_stdio_async() if hasattr(self.server, "run_stdio_async") else self.server.run()


def run_stdio() -> None:
    asyncio.run(AgentDeskMCPServer().run_stdio())


if __name__ == "__main__":
    run_stdio()
