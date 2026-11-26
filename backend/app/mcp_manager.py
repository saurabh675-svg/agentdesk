import asyncio
import json
import os
import re
import shutil
from contextlib import AsyncExitStack
from pathlib import Path

from .config import DATA_DIR, load_settings

MCP_CONFIG = DATA_DIR / "mcp.json"

PRESETS = [
    {
        "id": "fetch",
        "name": "Fetch (web pages)",
        "command": "uvx",
        "args": ["mcp-server-fetch"],
        "description": "Fetch web pages as Markdown for research (auto-installs via uvx).",
    },
    {
        "id": "drive",
        "name": "Google Drive MCP",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-google-drive"],
        "description": "Google Drive folders/files integration (sign-in required; add token in env).",
    },
    {
        "id": "github",
        "name": "GitHub MCP",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-github"],
        "description": "GitHub repos, issues, PRs, code search (auto-install via npx).",
    },
    {
        "id": "sentry",
        "name": "Sentry MCP",
        "command": "npx",
        "args": ["-y", "@getsentry/sentry-mcp"],
        "description": "Sentry issues/stack traces (sign-in required; add token in env).",
    },
    {
        "id": "notion",
        "name": "Notion MCP",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-notion"],
        "description": "Notion pages/workspace knowledge (sign-in required; add NOTION_TOKEN in env).",
    },
    {
        "id": "askui",
        "name": "AskUI Vision Agent",
        "command": "npx",
        "args": ["-y", "askui@latest"],
        "description": "AskUI test/automation framework (auto-install via npx).",
    },
    {
        "id": "playwright",
        "name": "Playwright MCP",
        "command": "npx",
        "args": ["-y", "@playwright/mcp@latest"],
        "description": "Accessibility-tree browser automation from Microsoft (auto-installs via npx).",
    },
    {
        "id": "filesystem",
        "name": "Filesystem MCP",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "{workspace}"],
        "description": "Structured file operations inside the workspace.",
    },
    {
        "id": "memory",
        "name": "Memory MCP",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-memory"],
        "description": "Knowledge-graph memory that persists across sessions.",
    },
    {
        "id": "sequential-thinking",
        "name": "Sequential Thinking",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"],
        "description": "Structured step-by-step reasoning helpers.",
    },
    {
        "id": "brave-search",
        "name": "Brave Search",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-brave-search"],
        "description": "Privacy-focused live web search (free BRAVE_API_KEY required).",
    },
    {
        "id": "tavily",
        "name": "Tavily Search",
        "command": "npx",
        "args": ["-y", "tavily-mcp"],
        "description": "AI-optimized web search/extract (free TAVILY_API_KEY required).",
    },
    {
        "id": "time",
        "name": "Time & Timezone",
        "command": "uvx",
        "args": ["mcp-server-time"],
        "description": "Current time and timezone conversion tools.",
    },
    {
        "id": "git",
        "name": "Git",
        "command": "uvx",
        "args": ["mcp-server-git"],
        "description": "Read/search/commit Git repositories from the agent.",
    },
    {"id": "sqlite", "name": "SQLite", "command": "uvx", "args": ["mcp-server-sqlite", "--db-path", "{workspace}"], "description": "Query SQLite databases read-only."},
    {"id": "docker", "name": "Docker", "command": "uvx", "args": ["mcp-server-docker"], "description": "List/inspect Docker containers (requires Docker daemon)."},
    {"id": "slack", "name": "Slack", "command": "npx", "args": ["-y", "@modelcontextprotocol/server-slack"], "description": "Slack messages/channels (SLACK_BOT_TOKEN required)."},
    {"id": "obsidian", "name": "Obsidian", "command": "uvx", "args": ["mcp-server-obsidian"], "description": "Obsidian vault notes (OBSIDIAN_API_KEY required)."},
    {"id": "linear", "name": "Linear", "command": "npx", "args": ["-y", "@modelcontextprotocol/server-linear"], "description": "Linear issues/projects (LINEAR_API_KEY required)."},
    {"id": "s3", "name": "S3", "command": "uvx", "args": ["mcp-server-s3"], "description": "Amazon S3 buckets/objects (AWS keys required)."},
    {"id": "huggingface", "name": "Hugging Face", "command": "uvx", "args": ["mcp-server-huggingface"], "description": "Hugging Face models/datasets (HF_TOKEN required)."},
    {"id": "perplexity", "name": "Perplexity", "command": "uvx", "args": ["mcp-server-perplexity"], "description": "Perplexity AI search (PERPLEXITY_API_KEY required)."},
    {"id": "openweather", "name": "OpenWeather", "command": "uvx", "args": ["mcp-server-openweather"], "description": "Weather forecasts (OPENWEATHER_API_KEY required)."},
    {"id": "postgres", "name": "Postgres", "command": "uvx", "args": ["mcp-server-postgres"], "description": "Query Postgres databases (DATABASE_URL required)."},
]

# Hints for MCP servers that close when they need external sign-in/credentials.
MCP_AUTH_HINTS = {
    "notion": "set NOTION_TOKEN (integration token) in the server env — Settings -> MCP -> Edit env",
    "drive": "set GOOGLE_APPLICATION_CREDENTIALS (service-account JSON) or OAuth vars (GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN) — Settings -> MCP -> Edit env",
    "sentry": "set a Sentry auth token (SENTRY_API_TOKEN + SENTRY_ACCOUNT_SLUG) in the server env — Settings -> MCP -> Edit env",
    "askui": "set ASKUI_WORKSPACE_ID and ASKUI_TOKEN in the server env — Settings -> MCP -> Edit env",
    "brave-search": "set BRAVE_API_KEY (free at brave.com/search/api) in the server env — Settings -> MCP -> Edit env",
    "tavily": "set TAVILY_API_KEY (free tier at tavily.com) in the server env — Settings -> MCP -> Edit env",
}

# Env vars that must be present before a server can start; missing ones show a
# "needs setup" state instead of a confusing crash/error.
# Env vars that must never be forwarded to MCP child processes.
MCP_ENV_DENYLIST = {"AGENTDESK_API_TOKEN", "AGENTDESK_GATEWAY_TOKEN", "AGENTDESK_DATA"}


def audit_env(env: dict) -> list[str]:
    """Return warning strings for env keys that look like leaked secrets."""
    warnings = []
    for key in (env or {}):
        if key in MCP_ENV_DENYLIST:
            warnings.append(f"{key} is an AgentDesk internal secret and will not be forwarded")
    return warnings


def scrub_env(env: dict) -> dict:
    return {k: v for k, v in (env or {}).items() if k not in MCP_ENV_DENYLIST}


REQUIRED_ENV = {
    "notion": ["NOTION_TOKEN"],
    "sentry": ["SENTRY_API_TOKEN"],
    "brave-search": ["BRAVE_API_KEY"],
    "tavily": ["TAVILY_API_KEY"],
}


def _has_credentials(env: dict) -> bool:
    """True when the server env contains anything that looks like a credential.

    Avoids hardcoding every vendor's variable names while still showing a clear
    "needs setup" state for known sign-in-only servers.
    """
    pattern = re.compile(r"TOKEN|KEY|SECRET|CREDENTIAL|PASSWORD|ACCOUNT|WORKSPACE|CLIENT|AUTH", re.I)
    return any(pattern.search(str(name)) and str(value or "").strip() for name, value in env.items())


def load_config() -> list[dict]:
    if MCP_CONFIG.exists():
        try:
            data = json.loads(MCP_CONFIG.read_text(encoding="utf-8"))
            return data.get("servers", [])
        except Exception:
            return []
    return []


def save_config(servers: list[dict]) -> None:
    MCP_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    MCP_CONFIG.write_text(json.dumps({"servers": servers}, indent=2), encoding="utf-8")


def default_servers() -> list[dict]:
    fetch = next(preset for preset in PRESETS if preset["id"] == "fetch")
    return [
        {
            "id": fetch["id"],
            "name": fetch["name"],
            "command": fetch["command"],
            "args": fetch["args"],
            "env": {},
            "enabled": False,
        }
    ]


def safe_name(server_id: str, tool: str) -> str:
    raw = f"mcp_{server_id}_{tool}"
    return re.sub(r"[^a-zA-Z0-9_-]", "_", raw)[:64]


def _find_command(command: str) -> str | None:
    """Resolve npx/npm/uvx even when they are not on PATH (node not on user PATH)."""
    resolved = shutil.which(command)
    if resolved:
        return resolved
    if command in ("npx", "npm"):
        candidates = [
            r"C:\Program Files\nodejs",
            r"C:\Program Files (x86)\nodejs",
            r"C:\nodejs",
        ]
        for base in candidates:
            exe = Path(base) / f"{command}.cmd"
            if exe.exists():
                return str(exe)
    if command == "uvx":
        candidates = [
            Path.home() / ".local" / "bin" / "uvx.exe",
            Path.home() / ".cargo" / "bin" / "uvx.exe",
        ]
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
    return None


class MCPManager:
    """Owns stdio + HTTP/SSE MCP connections (MCP 2.x client — 0.5/0.6). Each connection is entered and closed in its own task
    so anyio cancel scopes never cross task boundaries."""

    def __init__(self) -> None:
        self._servers: list[dict] = []
        self._sessions: dict[str, object] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._stops: dict[str, asyncio.Event] = {}
        self._tools: dict[str, dict] = {}
        self._states: dict[str, dict] = {}
        self._lock = asyncio.Lock()

    @property
    def servers(self) -> list[dict]:
        return self._servers

    def status(self) -> list[dict]:
        out = []
        for server in self._servers:
            state = self._states.get(server["id"], {})
            required = REQUIRED_ENV.get(server["id"], [])
            out.append({**server, "required_env": required, **state})
        return out

    def tool_schemas(self) -> list[dict]:
        try:
            workspace = (load_settings() or {}).get("workspace") or ""
        except Exception:
            workspace = ""
        schemas = []
        for name, info in self._tools.items():
            desc = f"[MCP:{info['server']}] {info['description']}"[:1000]
            if workspace:
                desc = f"{desc} Workspace scope: {workspace}. Stay inside it."[:1000]
            schemas.append(
                {
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": desc,
                        "parameters": info["schema"] or {"type": "object", "properties": {}},
                    },
                }
            )
        return schemas

    async def start(self) -> None:
        if not MCP_CONFIG.exists():
            save_config(default_servers())
        self._servers = load_config()
        for server in self._servers:
            if not server.get("enabled"):
                self._states[server["id"]] = {"status": "disabled", "error": None, "tools": []}
                continue
            required = REQUIRED_ENV.get(server["id"], [])
            env = server.get("env") or {}
            missing = [name for name in required if not str(env.get(name) or "").strip()]
            if missing:
                hint = MCP_AUTH_HINTS.get(server["id"], f"set {', '.join(missing)} in the server env")
                self._states[server["id"]] = {
                    "status": "needs_setup",
                    "error": f"Missing {', '.join(missing)}. {hint}",
                    "tools": [],
                    "required_env": required,
                }
                continue
            # Known sign-in-only servers without any credential in env: don't spawn a
            # process that is guaranteed to exit; show the exact setup hint instead.
            if server["id"] in MCP_AUTH_HINTS and not _has_credentials(env):
                self._states[server["id"]] = {
                    "status": "needs_setup",
                    "error": f"Sign-in required. {MCP_AUTH_HINTS[server['id']]}",
                    "tools": [],
                    "required_env": required,
                }
                continue
            self._spawn(server)

    def _spawn(self, server: dict) -> None:
        server_id = server["id"]
        self._states[server_id] = {"status": "connecting", "error": None, "tools": []}
        self._stops[server_id] = asyncio.Event()
        task = asyncio.create_task(self._connect(server))
        self._tasks[server_id] = task

    async def _connect(self, server: dict) -> None:
        server_id = server["id"]
        stop = self._stops[server_id]
        async with AsyncExitStack() as stack:
            try:
                from mcp import ClientSession, StdioServerParameters
                from mcp.client.stdio import stdio_client

                settings = load_settings()
                workspace = settings.get("workspace", str(Path.home()))
                url = server.get("url") or ""
                if url:
                    headers = {**(server.get("headers") or {})}
                    for k, v in (server.get("env") or {}).items():
                        if v and str(v).strip():
                            headers[k.replace("_", "-").lower()] = str(v).strip()
                    if url.rstrip("/").endswith("/sse"):
                        from mcp.client.sse import sse_client
                        read, write = await stack.enter_async_context(sse_client(url, headers))
                    else:
                        from mcp.client.streamable_http import streamable_http_client
                        read, write, _ = await stack.enter_async_context(
                            streamable_http_client(url, headers)
                        )
                else:
                    args = [str(arg).replace("{workspace}", workspace) for arg in server.get("args", [])]
                    command = server.get("command", "")
                    resolved = _find_command(command)
                    if not resolved:
                        raise RuntimeError(
                            f"Command '{command}' not found. Install Node.js (npx) or uv (uvx) first."
                        )
                    env = {**(server.get("env") or {})}
                    env.pop("AGENTDESK_API_TOKEN", None)
                    params = StdioServerParameters(command=resolved, args=args, env=env)
                    read, write = await stack.enter_async_context(stdio_client(params))
                session = await stack.enter_async_context(ClientSession(read, write))
                await asyncio.wait_for(session.initialize(), timeout=180)
                listed = await asyncio.wait_for(session.list_tools(), timeout=60)
                tools = []
                for tool in listed.tools:
                    full_name = safe_name(server_id, tool.name)
                    schema = getattr(tool, "inputSchema", None) or getattr(tool, "input_schema", {}) or {}
                    self._tools[full_name] = {
                        "server": server_id,
                        "original": tool.name,
                        "description": tool.description or "",
                        "schema": schema,
                        "session": session,
                    }
                    tools.append(
                        {"name": full_name, "original": tool.name, "description": tool.description or ""}
                    )
                self._sessions[server_id] = session
                self._states[server_id] = {"status": "ready", "error": None, "tools": tools}
                await stop.wait()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                detail = str(exc)
                for key, hint in MCP_AUTH_HINTS.items():
                    if key in server_id or key in str(server.get("name", "")):
                        detail = f"{detail} [{hint}]"
                self._states[server_id] = {"status": "error", "error": detail[:600], "tools": []}
            finally:
                self._sessions.pop(server_id, None)
                for name in [n for n, info in self._tools.items() if info["server"] == server_id]:
                    self._tools.pop(name, None)

    async def reload(self, servers: list[dict]) -> list[dict]:
        async with self._lock:
            await self._close_sessions()
            self._servers = servers
            save_config(servers)
            self._tools = {}
            for server in servers:
                if server.get("enabled"):
                    self._spawn(server)
                else:
                    self._states[server["id"]] = {"status": "disabled", "error": None, "tools": []}
        return self.status()

    async def list_resources(self, server_id: str) -> list[dict]:
        """MCP 2.x: resources discovery (best-effort; empty when unsupported)."""
        session = self._sessions.get(server_id)
        if session is None or not hasattr(session, "list_resources"):
            return []
        try:
            out = await asyncio.wait_for(session.list_resources(), timeout=30)
            return [
                {"uri": str(getattr(r, "uri", "")), "name": str(getattr(r, "name", "")), "description": str(getattr(r, "description", "") or "")}
                for r in (getattr(out, "resources", []) or [])
            ]
        except Exception:
            return []

    async def list_prompts(self, server_id: str) -> list[dict]:
        """MCP 2.x: prompts discovery (best-effort; empty when unsupported)."""
        session = self._sessions.get(server_id)
        if session is None or not hasattr(session, "list_prompts"):
            return []
        try:
            out = await asyncio.wait_for(session.list_prompts(), timeout=30)
            return [
                {"name": str(getattr(p, "name", "")), "description": str(getattr(p, "description", "") or "")}
                for p in (getattr(out, "prompts", []) or [])
            ]
        except Exception:
            return []

    async def call_tool(self, name: str, arguments: dict) -> str:
        info = self._tools.get(name)
        if not info:
            raise ValueError(f"Unknown MCP tool: {name}")
        # Workspace auto-scoping: inject workspace when the tool accepts it.
        try:
            schema = (info.get("schema") or {})
            props = (schema.get("properties") or {}) if isinstance(schema, dict) else {}
            if isinstance(arguments, dict) and ("workspace" in props or "root" in props or "path" in props):
                ws = (load_settings() or {}).get("workspace")
                if ws and not arguments.get("workspace") and not arguments.get("root"):
                    arguments = {**arguments, "workspace": ws} if "workspace" in props else arguments
        except Exception:
            pass
        result = await asyncio.wait_for(
            info["session"].call_tool(info["original"], arguments), timeout=180
        )
        chunks = []
        for item in result.content or []:
            text = getattr(item, "text", None)
            if text:
                chunks.append(text)
            elif getattr(item, "type", "") == "image":
                chunks.append("[image content]")
            else:
                chunks.append(str(item)[:2000])
        output = "\n".join(chunks) or "(no output)"
        return output[:20_000]

    async def _close_sessions(self) -> None:
        for stop in self._stops.values():
            stop.set()
        tasks = [task for task in self._tasks.values() if not task.done()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks = {}
        self._stops = {}
        self._sessions = {}

    async def shutdown(self) -> None:
        async with self._lock:
            await self._close_sessions()

    async def reconnect(self, server_id: str) -> list[dict]:
        """Restart one server (after editing env/args/enabled) and return all statuses."""
        server = next((s for s in self._servers if s["id"] == server_id), None)
        if not server:
            return self.status()
        stop = self._stops.get(server_id)
        if stop:
            stop.set()
        task = self._tasks.get(server_id)
        if task and not task.done():
            task.cancel()
            try:
                await asyncio.wait_for(task, timeout=5)
            except (asyncio.CancelledError, Exception):
                pass
        self._tasks.pop(server_id, None)
        self._stops.pop(server_id, None)
        self._sessions.pop(server_id, None)
        for name in [n for n, info in self._tools.items() if info["server"] == server_id]:
            self._tools.pop(name, None)
        if server.get("enabled", True):
            self._spawn(server)
        else:
            self._states[server_id] = {"status": "disabled", "error": None, "tools": []}
        await asyncio.sleep(0.5)
        return self.status()

    async def add_and_start_server(self, server: dict) -> list[dict]:
        """Dynamically add an MCP server to mcp.json and spawn it immediately."""
        self._servers = [s for s in self._servers if s["id"] != server["id"]]
        self._servers.append(server)
        save_config(self._servers)
        if server.get("enabled", True):
            self._spawn(server)
        await asyncio.sleep(1.0)
        return self.status()


async def search_mcp_registry(query: str) -> list[dict]:
    """Search public registries and curated catalog for compatible MCP servers."""
    q = query.lower().strip()
    catalog = [
        {"id": "github", "name": "GitHub MCP", "command": "npx", "args": ["-y", "@modelcontextprotocol/server-github"], "description": "Manage GitHub repos, issues, PRs and search code."},
        {"id": "postgres", "name": "PostgreSQL MCP", "command": "npx", "args": ["-y", "@modelcontextprotocol/server-postgres"], "description": "Inspect and query PostgreSQL databases with schema inspection."},
        {"id": "sqlite", "name": "SQLite MCP", "command": "uvx", "args": ["mcp-server-sqlite", "--db-path", "{workspace}/db.sqlite"], "description": "Inspect, query, and modify SQLite databases."},
        {"id": "puppeteer", "name": "Puppeteer MCP", "command": "npx", "args": ["-y", "@modelcontextprotocol/server-puppeteer"], "description": "Browser automation and web scraping via Puppeteer."},
        {"id": "slack", "name": "Slack MCP", "command": "npx", "args": ["-y", "@modelcontextprotocol/server-slack"], "description": "Send messages, search channels, and manage Slack workspaces."},
        {"id": "brave-search", "name": "Brave Search MCP", "command": "npx", "args": ["-y", "@modelcontextprotocol/server-brave-search"], "description": "Fast global web search via Brave API."},
        {"id": "fetch", "name": "Fetch MCP", "command": "uvx", "args": ["mcp-server-fetch"], "description": "Fetch and convert web pages to clean Markdown."},
        {"id": "memory", "name": "Memory Knowledge Graph MCP", "command": "npx", "args": ["-y", "@modelcontextprotocol/server-memory"], "description": "Persistent graph-based memory for entities and relations."},
        {"id": "docker", "name": "Docker MCP", "command": "npx", "args": ["-y", "@modelcontextprotocol/server-docker"], "description": "Manage containers, images, volumes, and compose files."},
    ]
    if not q:
        return catalog
    return [c for c in catalog if q in c["name"].lower() or q in c["description"].lower() or q in c["id"].lower()]


mcp_manager = MCPManager()
