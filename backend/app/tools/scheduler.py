"""Windows Task Scheduler (schtasks.exe) integration for AgentDesk background automations.

Allows missions, automations, and self-healing scripts to persist as native Windows
Scheduled Tasks that run headlessly even when the AgentDesk GUI is closed.
"""

from __future__ import annotations

import csv
import io
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


def _get_schtasks() -> str | None:
    return shutil.which("schtasks") or shutil.which("schtasks.exe") or r"C:\Windows\System32\schtasks.exe"


def create_windows_task(
    task_name: str,
    schedule: str = "DAILY",
    time_str: str = "09:00",
    command: str = "",
    run_level: str = "HIGHEST",
) -> tuple[bool, str]:
    """Create a persistent Windows Scheduled Task via schtasks /Create."""
    sch = _get_schtasks()
    if not sch or not os.path.isfile(sch):
        return False, "schtasks.exe not found on this Windows installation."

    clean_name = f"AgentDesk_{task_name}".replace(" ", "_")
    valid_schedules = ["DAILY", "HOURLY", "MINUTE", "ONLOGON", "ONSTART", "WEEKLY", "MONTHLY"]
    sc = schedule.upper() if schedule.upper() in valid_schedules else "DAILY"

    # Default action if none provided: run AgentDesk headless radar or check
    if not command:
        python_exe = Path(__file__).resolve().parents[3] / "runtime" / "python" / "python.exe"
        if not python_exe.is_file():
            python_exe = Path(r"C:\Users\saura\agentdesk\installer\runtime\python\python.exe")
        command = f'"{python_exe}" -m app.main --headless'

    cmd = [
        sch,
        "/Create",
        "/TN", clean_name,
        "/TR", command,
        "/SC", sc,
        "/F",
    ]
    if sc not in ("ONLOGON", "ONSTART"):
        cmd.extend(["/ST", time_str])
    if run_level.upper() == "HIGHEST":
        cmd.extend(["/RL", "HIGHEST"])

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if proc.returncode == 0:
            return True, f"Successfully created scheduled task '{clean_name}' (Schedule: {sc} at {time_str})."
        return False, f"schtasks error (code {proc.returncode}): {proc.stderr or proc.stdout}"
    except Exception as exc:
        return False, f"Failed to execute schtasks: {exc}"


def list_windows_tasks(prefix: str = "AgentDesk") -> list[dict[str, Any]]:
    """Enumerate Windows Scheduled Tasks matching a prefix name."""
    sch = _get_schtasks()
    if not sch or not os.path.isfile(sch):
        return []

    try:
        proc = subprocess.run([sch, "/Query", "/FO", "CSV", "/V"], capture_output=True, text=True, timeout=15)
        if proc.returncode != 0 or not proc.stdout.strip():
            return []

        tasks = []
        reader = csv.DictReader(io.StringIO(proc.stdout))
        for row in reader:
            task_name = row.get("TaskName", "") or row.get("Task Name", "")
            if prefix.lower() in task_name.lower():
                tasks.append({
                    "name": task_name.lstrip("\\"),
                    "next_run_time": row.get("Next Run Time", ""),
                    "status": row.get("Status", ""),
                    "task_to_run": row.get("Task To Run", ""),
                    "author": row.get("Author", ""),
                    "schedule_type": row.get("Schedule Type", ""),
                })
        return tasks
    except Exception:
        return []


def delete_windows_task(task_name: str) -> tuple[bool, str]:
    """Delete a Windows Scheduled Task by name."""
    sch = _get_schtasks()
    if not sch:
        return False, "schtasks.exe not found."
    clean_name = task_name if task_name.startswith("AgentDesk_") else f"AgentDesk_{task_name}"
    try:
        proc = subprocess.run([sch, "/Delete", "/TN", clean_name, "/F"], capture_output=True, text=True, timeout=15)
        if proc.returncode == 0:
            return True, f"Deleted scheduled task '{clean_name}'."
        return False, f"Failed to delete task: {proc.stderr or proc.stdout}"
    except Exception as exc:
        return False, f"schtasks delete error: {exc}"


def run_windows_task_now(task_name: str) -> tuple[bool, str]:
    """Trigger an immediate run of a registered Windows Scheduled Task."""
    sch = _get_schtasks()
    if not sch:
        return False, "schtasks.exe not found."
    clean_name = task_name if task_name.startswith("AgentDesk_") else f"AgentDesk_{task_name}"
    try:
        proc = subprocess.run([sch, "/Run", "/TN", clean_name], capture_output=True, text=True, timeout=15)
        if proc.returncode == 0:
            return True, f"Triggered immediate execution of task '{clean_name}'."
        return False, f"Failed to run task: {proc.stderr or proc.stdout}"
    except Exception as exc:
        return False, f"schtasks run error: {exc}"
