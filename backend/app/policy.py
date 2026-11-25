"""Per-action policy engine: allow / ask / deny for browser/shell/desktop/MCP/webchat."""

from typing import Any

DEFAULT_POLICIES = {
    "run_command": "ask",
    "browser_navigate": "allow",
    "browser_click": "ask",
    "browser_type": "ask",
    "browser_scroll": "allow",
    "browser_read": "allow",
    "browser_back": "allow",
    "browser_forward": "allow",
    "browser_wait": "allow",
    "browser_links": "allow",
    "browser_set_zoom": "allow",
    "list_files": "allow",
    "read_file": "allow",
    "search_files": "allow",
    "write_file": "allow",
    "edit_file": "allow",
    "list_skills": "allow",
    "use_skill": "allow",
    "plan_create": "allow",
    "plan_update_step": "allow",
    "plan_list": "allow",
    "earnings_report": "allow",
    "earnings_radar": "allow",
    "list_automations": "allow",
    "pc_info": "allow",
    "git_status": "allow",
    "mcp_search": "allow",
    "computer_screenshot": "ask",
    "computer_click": "ask",
    "computer_type": "ask",
    "mcp_fetch": "allow",
    "mcp_playwright_browser_navigate": "allow",
    "open_external": "ask",
    "web_search": "allow",
}


def check(name: str, settings: dict, allow_when_user_ok: bool = True) -> str:
    policy = settings.get("policies", {}).get(name) or settings.get("policy_defaults", {}).get(name) or DEFAULT_POLICIES.get(name, "ask")
    return policy if policy in {"allow", "ask", "deny"} else "ask"


def can_execute(name: str, args: dict, settings: dict, auto_approve: bool, approved: bool = False) -> bool:
    policy = check(name, settings)
    if policy == "allow":
        return True
    if policy == "deny":
        return False
    return approved or auto_approve
