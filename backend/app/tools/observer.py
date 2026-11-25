"""Desktop Screen Observer and Workflow Learner for AgentDesk Pet.

Silently monitors active desktop workspace, identifies current application and
window context, discovers repetitive workflow habits, and feeds observations into
the Nous Hermes episodic learning engine so AgentDesk continuously learns the
user's working style without interfering.
"""

from __future__ import annotations

import asyncio
import logging
import re
import subprocess
import time
from typing import Any

from ..learning import record_reflection

logger = logging.getLogger("agentdesk.pet_observer")

_STATE = {
    "enabled": False,
    "state": "sleeping",  # "watching", "learning", "idle", "sleeping"
    "current_app": "AgentDesk",
    "current_title": "Active Desktop",
    "thought": "Hello! I am your desktop pet companion. I observe your screen to learn your workflows.",
    "insights": [],
    "history": [],
    "last_observed_time": time.time(),
}

_OBSERVER_TASK: asyncio.Task | None = None


def get_foreground_window_info() -> dict[str, str]:
    """Capture foreground window title and process name via PowerShell."""
    ps_cmd = """
    Add-Type @"
      using System;
      using System.Runtime.InteropServices;
      using System.Text;
      public class WinAPI {
        [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
        [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int count);
        [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);
      }
"@
    $hwnd = [WinAPI]::GetForegroundWindow()
    $sb = New-Object System.Text.StringBuilder 256
    [WinAPI]::GetWindowText($hwnd, $sb, 256) | Out-Null
    [uint32]$windowProcessId = 0
    [WinAPI]::GetWindowThreadProcessId($hwnd, [ref]$windowProcessId) | Out-Null
    $pname = (Get-Process -Id $windowProcessId -ErrorAction SilentlyContinue).ProcessName
    [PSCustomObject]@{
        Title = $sb.ToString().Trim()
        Process = if ($pname) { $pname } else { "Unknown" }
    } | ConvertTo-Json -Compress
    """
    try:
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, timeout=5)
        import json
        if proc.returncode == 0 and proc.stdout.strip():
            data = json.loads(proc.stdout)
            return {
                "title": str(data.get("Title") or "Desktop").strip(),
                "process": str(data.get("Process") or "System").strip(),
            }
    except Exception:
        pass
    return {"title": "Desktop", "process": "System"}


def generate_pet_thought(app: str, title: str) -> str:
    """Generate dynamic contextual thoughts for the pet based on what user is doing."""
    app_lower = app.lower()
    title_lower = title.lower()

    if any(k in app_lower for k in ("code", "devenv", "pycharm", "sublime", "idea")):
        file_match = re.search(r"([\w\-\.]+\.[a-zA-Z0-9]+)", title)
        filename = file_match.group(1) if file_match else "code"
        return f"Watching you code in {app}! You're working on '{filename}'."
    elif any(k in app_lower for k in ("chrome", "msedge", "firefox", "brave")):
        if "github" in title_lower:
            return "Browsing GitHub! Checking repositories and issues."
        elif "stackoverflow" in title_lower or "google" in title_lower:
            return "Researching solutions on the web..."
        return f"Watching you browse in {app}: '{title[:45]}...'"
    elif any(k in app_lower for k in ("terminal", "powershell", "cmd", "pwsh")):
        return f"Executing CLI commands in {app}. Watching build & tests!"
    elif any(k in app_lower for k in ("discord", "slack", "teams", "telegram")):
        return f"Collaborating on {app}."
    elif "agentdesk" in app_lower or "electron" in app_lower:
        return "You're chatting with AgentDesk! I'm ready to assist."
    return f"Observing desktop activity: {app} ({title[:35]})."


async def observation_step() -> None:
    """A single observation tick."""
    if not _STATE["enabled"] or _STATE["state"] == "sleeping":
        return

    info = await asyncio.to_thread(get_foreground_window_info)
    app = info["process"]
    title = info["title"]

    if not title or title in ("Task Switching", "Program Manager"):
        return

    prev_app = _STATE["current_app"]
    prev_title = _STATE["current_title"]

    _STATE["current_app"] = app
    _STATE["current_title"] = title
    _STATE["last_observed_time"] = time.time()
    _STATE["thought"] = generate_pet_thought(app, title)

    # Record to history buffer (keep last 30 items)
    entry = {"app": app, "title": title, "time": time.time()}
    _STATE["history"].append(entry)
    if len(_STATE["history"]) > 30:
        _STATE["history"].pop(0)

    # Detect workflow shifts and record habits
    if app != prev_app and app not in ("System", "Unknown"):
        _STATE["state"] = "learning"
        insight = f"Switched from {prev_app} to {app} while working on '{title[:40]}'"
        if insight not in _STATE["insights"]:
            _STATE["insights"].append(insight)
            if len(_STATE["insights"]) > 10:
                _STATE["insights"].pop(0)
            # Store habit in Hermes learning DB
            try:
                record_reflection(
                    goal=f"Workflow habit: {app}",
                    error_pattern=f"User workflow context: {title[:80]}",
                    resolution=f"Frequent developer tool usage: {app}",
                    tags=["pet_observer", app.lower()],
                )
            except Exception:
                pass
        await asyncio.sleep(1.5)
        _STATE["state"] = "watching"
    else:
        _STATE["state"] = "watching"


async def _observer_loop() -> None:
    """Continuous background loop running every 15 seconds."""
    while True:
        try:
            await observation_step()
        except Exception as exc:
            logger.debug("Observer tick error: %s", exc)
        await asyncio.sleep(15)


def start_observer() -> None:
    """Start the background observer loop."""
    global _OBSERVER_TASK
    if _OBSERVER_TASK is None or _OBSERVER_TASK.done():
        try:
            loop = asyncio.get_running_loop()
            _OBSERVER_TASK = loop.create_task(_observer_loop())
        except RuntimeError:
            pass


def stop_observer() -> None:
    """Stop the background observer loop."""
    global _OBSERVER_TASK
    if _OBSERVER_TASK and not _OBSERVER_TASK.done():
        _OBSERVER_TASK.cancel()
        _OBSERVER_TASK = None


def get_pet_status() -> dict[str, Any]:
    """Get full pet status payload."""
    return dict(_STATE)


def toggle_pet(enabled: bool | None = None) -> dict[str, Any]:
    """Toggle or set the pet active state."""
    if enabled is None:
        _STATE["enabled"] = not _STATE["enabled"]
    else:
        _STATE["enabled"] = enabled

    _STATE["state"] = "watching" if _STATE["enabled"] else "sleeping"
    return dict(_STATE)


def toggle_sleep() -> dict[str, Any]:
    """Toggle sleep mode."""
    if _STATE["state"] == "sleeping":
        _STATE["state"] = "watching"
        _STATE["thought"] = "I'm awake and watching your workspace again! ✨"
    else:
        _STATE["state"] = "sleeping"
        _STATE["thought"] = "Zzz... taking a nap. Click wake when you need me."
    return dict(_STATE)
