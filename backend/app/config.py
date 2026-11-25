import json
import os
import threading
from contextlib import suppress
from pathlib import Path

from .credentials import protect, reveal

APP_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("AGENTDESK_DATA") or (APP_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR = DATA_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
SETTINGS_PATH = DATA_DIR / "settings.json"
DB_PATH = DATA_DIR / "agentdesk.db"

PROJECTS_DIR = Path(os.environ.get("AGENTDESK_WORKSPACE") or (Path.home() / "AgentDeskProjects"))

DEFAULT_SETTINGS = {
    "config_version": 2,
    "provider": "local",
    "model": "",
    "base_url": "http://127.0.0.1:11435/v1",
    "api_key": "",
    "temperature": 0.2,
    "max_steps": 32,
    "disable_thinking": True,
    "auto_approve_commands": False,
    "allow_cloud_fallback": False,
    "allow_webchat_fallback": True,
    "learn_workflows": False,
    # Brain/memory/reflection injection is off by default: it was dragging stale
    # Kaggle notes into greetings and short requests.
    "inject_brain_context": False,
    "browser_headless": False,
    # Browser driver: auto | playwright | patchright (undetected) | camoufox
    "browser_driver": "playwright",
    "browser_engine": "auto",
    "vlm_enabled": True,
    # Chrome DevTools Protocol port so C++/C#/JS clients can attach to the very
    # same browser (Puppeteer.connect, Selenium debuggerAddress, raw CDP).
    # Set to 0 to disable external browser access.
    "browser_cdp_port": 9333,
    "webchat_site": "chatgpt",
    "hard_base_url": "https://openrouter.ai/api/v1",
    "hard_model": "auto",
    "hard_api_key": "",
    "hard_fallback_site": "chatgpt",
    "firecrawl_api_key": "",
    "github_token": "",
    "gateway_base_url": "https://ai-gateway.vercel.app/v1",
    "gateway_api_key": "",
    "gateway": "local",
    "keys": {},
    "local_model_path": "",
    # Local inference backend: auto uses Vulkan when the bundled binary is present.
    "local_backend": "auto",
    "local_gpu_layers": 99,
    "local_context_size": 4096,
    "local_threads": 4,
    "workspace": str(PROJECTS_DIR),
    # Auto route: ordered gateways tried after the local model, then browser tabs.
    "auto_gateways": ["keyless", "openrouter", "opencode", "vercel", "unorouter", "pollinations", "freeai", "openai"],
    "gateway_models": {},
    # Rubric verify (deepagents-style): grade the final answer before finishing.
    "rubric_enabled": False,
    "rubric_text": "",
    "rubric_max_iterations": 2,
    # Named agent profiles; the active one overlays provider/model/key.
    "agents": [],
    "active_agent": "",
}


def resolve_settings(settings: dict) -> dict:
    """Return a copy of settings with the active agent/gateway key filled in.

    Keys are stored per-gateway in ``settings["keys"]`` keyed by gateway id, so
    switching providers keeps every key alive. A named agent profile (if active)
    overlays provider/model/base_url and resolves its own gateway key.
    """
    resolved = dict(settings or {})
    keys = resolved.get("keys") or {}
    if isinstance(keys, str):  # tolerate legacy shapes
        keys = {}

    active_agent = str(resolved.get("active_agent") or "").strip()
    if active_agent:
        agents = resolved.get("agents") or []
        agent = next((a for a in agents if isinstance(a, dict) and a.get("id") == active_agent), None)
        if agent:
            for field in ("provider", "model", "base_url", "gateway", "disable_thinking"):
                if agent.get(field) not in (None, ""):
                    resolved[field] = agent[field]
            agent_gateway = str(agent.get("gateway") or agent.get("provider") or "").strip()
            agent_key = str(agent.get("api_key") or "").strip() or str(keys.get(agent_gateway) or "").strip()
            if agent_key:
                resolved["api_key"] = agent_key
            if agent_gateway:
                resolved["gateway"] = agent_gateway

    gateway = str(resolved.get("gateway") or "").strip() or "local"
    api_key = str(resolved.get("api_key") or "").strip()
    if not api_key:
        api_key = str(keys.get(gateway) or "").strip()
        if api_key:
            resolved["api_key"] = api_key
    if gateway == "local" and not resolved.get("base_url", "").strip():
        resolved["base_url"] = "http://127.0.0.1:11435/v1"
    return resolved

_lock = threading.RLock()
SECRET_FIELDS = {"api_key", "hard_api_key", "firecrawl_api_key", "github_token", "gateway_api_key", "freeai_api_key"}


def _map_secrets(settings: dict, transform) -> dict:
    out = dict(settings)
    for name in SECRET_FIELDS:
        if isinstance(out.get(name), str):
            out[name] = transform(out[name])
    keys = out.get("keys") or {}
    out["keys"] = {name: transform(key) for name, key in keys.items() if isinstance(key, str)} if isinstance(keys, dict) else {}
    agents = out.get("agents")
    if isinstance(agents, list):
        out["agents"] = [
            {**agent, "api_key": transform(agent["api_key"])}
            if isinstance(agent, dict) and isinstance(agent.get("api_key"), str)
            else agent
            for agent in agents
        ]
    return out


def _write_settings(settings: dict) -> None:
    payload = json.dumps(_map_secrets(settings, protect), indent=2)
    target = SETTINGS_PATH.with_suffix(".json.tmp")
    target.write_text(payload, encoding="utf-8")
    target.replace(SETTINGS_PATH)


def load_settings() -> dict:
    with _lock:
        settings = dict(DEFAULT_SETTINGS)
        if SETTINGS_PATH.exists():
            try:
                stored = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return settings
            if isinstance(stored, dict):
                def read_secret(value: str) -> str:
                    try:
                        return reveal(value)
                    except Exception:
                        # A copied profile may need credentials re-entered on this account.
                        return value
                settings.update(_map_secrets(stored, read_secret))
                changed = False
                try:
                    version = int(stored.get("config_version") or 0)
                except (TypeError, ValueError):
                    version = 0
                if version < 1:
                    settings["auto_approve_commands"] = False
                    changed = True
                if version < 2:
                    # 0.4.1 added the keyless gateway. Existing profiles were
                    # created before it existed, so add it without disabling any
                    # gateway the user already enabled.
                    gateways = settings.get("auto_gateways")
                    if isinstance(gateways, list):
                        if "keyless" not in gateways:
                            settings["auto_gateways"] = ["keyless", *gateways]
                            changed = True
                    else:
                        settings["auto_gateways"] = list(DEFAULT_SETTINGS["auto_gateways"])
                        changed = True
                if settings.get("config_version") != 2:
                    settings["config_version"] = 2
                    changed = True
                # Migrate pre-0.3.1 profiles: OpenRouter was historically configured
                # through hard_api_key, and older builds kept only one active api_key.
                keys = settings.get("keys")
                keys = dict(keys) if isinstance(keys, dict) else {}
                hard_key = str(settings.get("hard_api_key") or "").strip()
                if hard_key.startswith("dpapi:"):
                    hard_key = ""
                if hard_key and not keys.get("openrouter"):
                    keys["openrouter"] = hard_key
                    changed = True
                gateway = str(settings.get("gateway") or settings.get("provider") or "").strip()
                api_key = str(settings.get("api_key") or "").strip()
                if api_key.startswith("dpapi:"):
                    api_key = ""
                if gateway and api_key and not keys.get(gateway):
                    keys[gateway] = api_key
                    changed = True
                settings["keys"] = keys
                if settings.get("hard_fallback_site") not in ("chatgpt", "gemini"):
                    settings["hard_fallback_site"] = "chatgpt"
                    changed = True
                if changed:
                    with suppress(Exception):
                        _write_settings(settings)
                def usable(value: str) -> str:
                    return "" if value.startswith("dpapi:") else value
                settings = _map_secrets(settings, usable)
        return settings


def set_gateway_key(gateway: str, key: str) -> None:
    """Save an API key for one gateway (its '' value clears the per-gateway entry)."""
    settings = load_settings()
    gateway = str(gateway or "").strip()
    keys = settings.get("keys") or {}
    if isinstance(keys, str):
        keys = {}
    keys = dict(keys)
    if key:
        keys[gateway] = key
    else:
        keys.pop(gateway, None)
    settings["keys"] = keys
    _write_settings(settings)


def validate_settings(settings: dict) -> list[str]:
    """Soft-validate settings; returns human-readable warnings (never raises)."""
    warnings: list[str] = []
    if not isinstance(settings, dict):
        return ["settings must be an object"]
    unknown = set(settings) - set(DEFAULT_SETTINGS) - {"keys", "gateway_models", "agents", "hotkey", "global_hotkey"}
    for key in sorted(unknown):
        warnings.append(f"unknown setting ignored: {key}")
    temp = settings.get("temperature")
    if temp is not None and not (0 <= float(temp) <= 2):
        warnings.append("temperature out of range [0, 2]")
    if int(settings.get("max_steps") or 24) < 1:
        warnings.append("max_steps must be >= 1")
    return warnings


def save_settings(patch: dict) -> dict:
    with _lock:
        settings = load_settings()
        patch = dict(patch or {})
        # The active gateway: the patch's gateway wins, then the new provider,
        # then the old gateway, then "local".
        new_gateway = str(
            patch.get("gateway") or patch.get("provider") or settings.get("gateway") or "local"
        ).strip() or "local"
        keys = dict(settings.get("keys") or {})

        # Save any api_key under the active gateway id.
        if patch.get("api_key"):
            keys[new_gateway] = patch["api_key"]
        # Apply a per-gateway key map patch.
        if patch.get("keys") is not None:
            for key_id, value in (patch["keys"] or {}).items():
                key_id = str(key_id)
                if value:
                    keys[key_id] = value
                else:
                    keys.pop(key_id, None)

        # The single legacy `api_key` always mirrors the active gateway's key.
        if not patch.get("api_key"):
            patch["api_key"] = keys.get(new_gateway, "")
        patch.pop("gateway", None)
        settings.update(patch)
        settings["gateway"] = new_gateway
        settings["keys"] = keys
        settings["config_version"] = 1
        _write_settings(settings)
        return settings
