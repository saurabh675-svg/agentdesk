"""Lifecycle event hooks for AgentDesk tools and agent workflows.

Coordinates pre-flight validation, self-healing on failure, and post-task
Hermes skill distillation.
"""

from __future__ import annotations

import logging
from typing import Any

from .learning import distill_skill_from_trajectory, record_reflection

logger = logging.getLogger("agentdesk.hooks")


async def pre_tool_hook(tool_name: str, args: dict[str, Any], workspace: str) -> tuple[bool, str]:
    """Inspect and validate tool parameters before execution."""
    # Guardrail: Prevent accidental root/system directory destruction
    if tool_name in ("write_file", "edit_file"):
        path = str(args.get("path") or "")
        forbidden = [":\\windows", ":\\program files", ":\\users\\public"]
        if any(f in path.lower() for f in forbidden):
            return False, f"Modifications to system directories are restricted: {path}"
    return True, "OK"


async def on_tool_error_hook(tool_name: str, args: dict[str, Any], error_message: str, goal: str = "") -> tuple[bool, str]:
    """Intercept tool execution errors and trigger automatic self-healing."""
    logger.warning("Tool %s failed: %s", tool_name, error_message)
    
    # 1. Record error reflection to memory DB for continuous learning
    if goal:
        record_reflection(goal, error_message, f"Failed during {tool_name}")

    return False, error_message


async def post_task_hook(goal: str, steps: list[dict[str, Any]], summary: str = "") -> dict[str, Any] | None:
    """Evaluate completed task and synthesize a new persistent skill if appropriate."""
    try:
        new_skill = distill_skill_from_trajectory(goal, steps, summary)
        if new_skill:
            logger.info("Distilled new skill: %s", new_skill["name"])
            return new_skill
    except Exception as exc:
        logger.error("Skill distillation failed: %s", exc)
    return None
