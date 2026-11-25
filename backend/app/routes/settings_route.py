from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..config import load_settings, save_settings
from ..tools.browser import browser

router = APIRouter()


class SettingsPatch(BaseModel):
    provider: str | None = None
    model: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    temperature: float | None = None
    max_steps: int | None = None
    disable_thinking: bool | None = None
    auto_approve_commands: bool | None = None
    allow_cloud_fallback: bool | None = None
    allow_webchat_fallback: bool | None = None
    learn_workflows: bool | None = None
    browser_headless: bool | None = None
    browser_cdp_port: int | None = None
    webchat_site: str | None = None
    hard_base_url: str | None = None
    hard_model: str | None = None
    hard_api_key: str | None = None
    hard_fallback_site: str | None = None
    firecrawl_api_key: str | None = None
    freeai_api_key: str | None = None
    github_token: str | None = None
    gateway_base_url: str | None = None
    gateway_api_key: str | None = None
    gateway: str | None = None
    keys: dict[str, str] | None = None
    local_model_path: str | None = None
    policies: dict[str, str] | None = None
    workspace: str | None = None
    auto_gateways: list[str] | None = None
    gateway_models: dict[str, str] | None = None
    rubric_enabled: bool | None = None
    rubric_text: str | None = None
    rubric_max_iterations: int | None = None
    agents: list[dict] | None = None
    active_agent: str | None = None


@router.get("")
def get_settings() -> dict:
    return load_settings()


@router.put("")
async def update_settings(body: SettingsPatch) -> dict:
    patch = body.model_dump(exclude_none=True)
    if "base_url" in patch and not patch["base_url"].strip():
        raise HTTPException(status_code=400, detail="Base URL cannot be empty")
    previous = load_settings()
    updated = save_settings(patch)
    if "browser_headless" in patch and patch["browser_headless"] != previous.get("browser_headless"):
        await browser.close()
    if "browser_cdp_port" in patch and patch["browser_cdp_port"] != previous.get("browser_cdp_port"):
        # The DevTools port is a launch flag, so the browser must restart to apply it.
        await browser.close()
    return updated
