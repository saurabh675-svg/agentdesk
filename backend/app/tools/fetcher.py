"""Self-healing dynamic tool and dependency fetcher for AgentDesk.

When an operation fails due to a missing Python package, Windows CLI tool, or MCP server,
this engine automatically diagnoses the error, acquires the dependency via bundled pip,
winget, or npm/uvx, and enables seamless task resumption without human intervention.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from ..config import DATA_DIR

FETCH_LOG = DATA_DIR / "fetcher.log"


def _log(msg: str) -> None:
    try:
        FETCH_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(FETCH_LOG, "a", encoding="utf-8") as f:
            f.write(f"{msg}\n")
    except Exception:
        pass


def install_python_package(package_name: str) -> tuple[bool, str]:
    """Install a Python library directly into the active Python runtime."""
    clean_pkg = package_name.strip()
    if not clean_pkg:
        return False, "Package name cannot be empty."

    _log(f"[fetcher] Installing python package: {clean_pkg}")
    python_exe = sys.executable
    if not python_exe.lower().endswith("python.exe"):
        # Check bundled python runtime
        candidate = Path(__file__).resolve().parents[3] / "runtime" / "python" / "python.exe"
        if candidate.is_file():
            python_exe = str(candidate)
        else:
            candidate2 = Path(r"C:\Users\saura\agentdesk\installer\runtime\python\python.exe")
            if candidate2.is_file():
                python_exe = str(candidate2)
    try:
        proc = subprocess.run(
            [python_exe, "-m", "pip", "install", clean_pkg, "--no-warn-script-location"],
            capture_output=True,
            text=True,
            timeout=180,
        )
        if proc.returncode == 0:
            _log(f"[fetcher] Successfully installed python package: {clean_pkg}")
            return True, f"Successfully installed '{clean_pkg}'. Output:\n{proc.stdout[-500:]}"
        return False, f"Failed to install '{clean_pkg}'. Error:\n{proc.stderr[-1000:]}"
    except Exception as exc:
        return False, f"pip install error: {exc}"


def install_winget_tool(package_id: str) -> tuple[bool, str]:
    """Install a Windows software package or CLI tool via winget."""
    clean_id = package_id.strip()
    if not clean_id:
        return False, "Winget package ID cannot be empty."

    winget_exe = shutil.which("winget")
    if not winget_exe:
        return False, "winget is not available on this Windows installation."

    _log(f"[fetcher] Installing Windows tool via winget: {clean_id}")
    try:
        proc = subprocess.run(
            [
                winget_exe,
                "install",
                "--id",
                clean_id,
                "-e",
                "--silent",
                "--accept-source-agreements",
                "--accept-package-agreements",
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if proc.returncode in (0, 0x8A15002B):  # 0 = success, 0x8A15002B = already installed
            _log(f"[fetcher] Successfully installed winget tool: {clean_id}")
            return True, f"Successfully acquired '{clean_id}' via winget."
        return False, f"winget returned exit code {proc.returncode}:\n{(proc.stdout or proc.stderr)[-1000:]}"
    except Exception as exc:
        return False, f"winget error: {exc}"


def diagnose_and_auto_heal(error_message: str) -> tuple[bool, str]:
    """Analyze a tool error message and automatically fetch the missing dependency."""
    msg = str(error_message)

    # 1. Detect missing Python module: ModuleNotFoundError: No module named 'xyz'
    py_match = re.search(r"No module named ['\"]([^'\"]+)['\"]", msg)
    if py_match:
        mod_name = py_match.group(1).split(".")[0]
        # Mapping for common module names that differ from PyPI package names
        pypi_map = {
            "cv2": "opencv-python",
            "PIL": "pillow",
            "bs4": "beautifulsoup4",
            "yaml": "pyyaml",
            "sklearn": "scikit-learn",
            "dotenv": "python-dotenv",
        }
        pkg_to_install = pypi_map.get(mod_name, mod_name)
        ok, detail = install_python_package(pkg_to_install)
        if ok:
            return True, f"Auto-healed: Installed missing Python module '{pkg_to_install}'."
        return False, f"Auto-heal failed for Python module '{pkg_to_install}': {detail}"

    # 2. Detect missing Windows CLI command: 'xyz' is not recognized as an internal or external command
    cmd_match = re.search(r"['\"]?([a-zA-Z0-9_\-\.]+)['\"]? is not recognized as an internal or external command", msg)
    if cmd_match:
        cmd_name = cmd_match.group(1).lower()
        winget_map = {
            "ffmpeg": "Gyan.FFmpeg",
            "git": "Git.Git",
            "ripgrep": "BurntSushi.ripgrep.MSVC",
            "jq": "jqlang.jq",
            "curl": "cURL.cURL",
            "node": "OpenJS.NodeJS.LTS",
            "pandoc": "JohnMacFarlane.Pandoc",
            "power-automate": "Microsoft.PowerAutomateDesktop",
            "powerautomate": "Microsoft.PowerAutomateDesktop",
            "pad": "Microsoft.PowerAutomateDesktop",
            "docker": "Docker.DockerDesktop",
        }
        if cmd_name in winget_map:
            ok, detail = install_winget_tool(winget_map[cmd_name])
            if ok:
                return True, f"Auto-healed: Installed missing CLI utility '{cmd_name}' via winget."
            return False, f"Auto-heal failed for CLI '{cmd_name}': {detail}"

    return False, "Error did not match an automatic self-healing rule."
