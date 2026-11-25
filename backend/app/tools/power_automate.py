"""Headless Microsoft Power Automate Desktop (PAD) runner for AgentDesk.

Enables silent, background execution of Windows desktop flows via PAD.Console.Host.exe,
direct protocol URIs, input argument passing, and automated registry configuration to
disable external invocation confirmation dialogs.
"""

from __future__ import annotations

import json
import os
import subprocess
import urllib.parse
from pathlib import Path
from typing import Any

from ..config import DATA_DIR


def set_silent_external_execution(enable: bool = True) -> tuple[bool, str]:
    """Configure Windows registry to suppress the 'external flow run' confirmation dialog."""
    try:
        import winreg

        key_path = r"Software\Microsoft\Power Automate Desktop"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            val = 0 if enable else 1
            winreg.SetValueEx(key, "EnableAskBeforeRunningAFlowExternally", 0, winreg.REG_DWORD, val)
        return True, "Successfully configured Power Automate registry for silent background execution."
    except Exception as exc:
        return False, f"Registry configuration error: {exc}"


def find_pad_executable() -> str | None:
    """Find the PAD console host executable across standard Windows installation paths."""
    candidates = [
        r"C:\Program Files (x86)\Power Automate Desktop\dotnet\PAD.Console.Host.exe",
        r"C:\Program Files\Power Automate Desktop\dotnet\PAD.Console.Host.exe",
        r"C:\Program Files (x86)\Power Automate Desktop\PAD.Console.Host.exe",
        r"C:\Program Files\Power Automate Desktop\PAD.Console.Host.exe",
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


def run_pad_flow(flow_name: str, input_args: dict[str, Any] | None = None) -> tuple[bool, str]:
    """Execute a Power Automate Desktop flow headlessly with optional JSON input arguments."""
    clean_name = flow_name.strip()
    if not clean_name:
        return False, "Flow name cannot be empty."

    # Build URI
    encoded_name = urllib.parse.quote(clean_name)
    uri = f"ms-powerautomate:/console/flow/run?workflowName={encoded_name}"
    if input_args:
        args_json = json.dumps(input_args)
        encoded_args = urllib.parse.quote(args_json)
        uri += f"&inputArguments={encoded_args}"

    # Try executing via PAD.Console.Host.exe
    pad_exe = find_pad_executable()
    if pad_exe:
        try:
            proc = subprocess.run([pad_exe, uri], capture_output=True, text=True, timeout=45)
            if proc.returncode == 0:
                return True, f"Triggered Power Automate flow '{clean_name}' successfully via PAD.Console.Host."
            return True, f"Dispatched flow '{clean_name}'. Output: {(proc.stdout or proc.stderr)[:500]}"
        except Exception as exc:
            pass

    # Fallback to system protocol invocation
    try:
        os.startfile(uri)  # type: ignore[attr-defined]
        return True, f"Dispatched Power Automate flow '{clean_name}' via Windows protocol URI."
    except Exception as exc:
        return False, f"Failed to dispatch Power Automate flow: {exc}"
