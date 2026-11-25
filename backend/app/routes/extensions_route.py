import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .. import skills, skills_import
from ..mcp_manager import PRESETS, mcp_manager, save_config

router = APIRouter()


class SkillIn(BaseModel):
    name: str
    description: str = ""
    content: str


class SkillInstall(BaseModel):
    url: str


class SkillImportIn(BaseModel):
    path: str
    overwrite: bool = True


class MCPServerIn(BaseModel):
    id: str | None = None
    name: str
    command: str
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    enabled: bool = True


class MCPConfigIn(BaseModel):
    servers: list[MCPServerIn]


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:40] or "server"


@router.get("/skills")
def get_skills() -> list[dict]:
    return skills.list_skills()


@router.post("/skills")
def create_skill(body: SkillIn) -> dict:
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="Skill name is required")
    return skills.save_skill(body.name, body.description, body.content)


@router.post("/skills/install")
def install_skill(body: SkillInstall) -> dict:
    try:
        return skills.install_from_url(body.url)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Install failed: {exc}") from exc


@router.delete("/skills/{slug_name}")
def delete_skill(slug_name: str) -> dict:
    skills.delete_skill(slug_name)
    return {"ok": True}


@router.get("/mcp/presets")
def mcp_presets() -> list[dict]:
    return PRESETS


@router.get("/mcp/servers")
def mcp_servers() -> list[dict]:
    return mcp_manager.status()


@router.put("/mcp/servers")
async def update_mcp_servers(body: MCPConfigIn) -> list[dict]:
    servers = []
    seen: set[str] = set()
    for item in body.servers:
        server_id = slug(item.id or item.name)
        if server_id in seen:
            continue
        seen.add(server_id)
        servers.append(
            {
                "id": server_id,
                "name": item.name,
                "command": item.command,
                "args": item.args,
                "env": item.env,
                "enabled": item.enabled,
            }
        )
    return await mcp_manager.reload(servers)


@router.post("/mcp/servers/{server_id}/reconnect")
async def reconnect_mcp_server(server_id: str) -> list[dict]:
    """Restart one server (e.g. after adding a sign-in token in its env)."""
    return await mcp_manager.reconnect(server_id)


class MCPServerUpdate(BaseModel):
    env: dict[str, str] = Field(default_factory=dict)


@router.put("/mcp/servers/{server_id}")
async def update_mcp_server(server_id: str, body: MCPServerUpdate) -> list[dict]:
    """Update one server's env/args and reconnect it."""
    server = next((s for s in mcp_manager.servers if s["id"] == server_id), None)
    if server is None:
        raise HTTPException(status_code=404, detail="Server not found")
    server["env"] = dict(body.env)
    save_config(mcp_manager.servers)
    return await mcp_manager.reconnect(server_id)


@router.get("/skills/scan")
def scan_skill_path(path: str) -> dict:
    """List the skills found in a folder or zip archive."""
    target = (path or "").strip()
    if not target:
        raise HTTPException(status_code=400, detail="Path is required")
    return {"path": target, "skills": skills_import.scan(target)}


@router.post("/skills/import")
def import_skills(body: SkillImportIn) -> dict:
    """Import skill packs from a folder or a zip archive."""
    target = (body.path or "").strip()
    if not target:
        raise HTTPException(status_code=400, detail="Path is required")
    try:
        return skills_import.import_path(target, overwrite=body.overwrite)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Import failed: {exc}") from exc


@router.get("/skills/bundled")
def bundled_skills() -> dict:
    """Skill packs that ship with AgentDesk."""
    return {"packs": skills_import.BUNDLED_PACKS, "skills": skills_import.bundled_skills()}
