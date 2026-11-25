"""Python client for the Windows-native sidecar (`AgentDesk.Win`).

The sidecar is a small .NET 9 process that speaks newline-delimited JSON over
the named pipe ``\\\\.\\pipe\\agentdesk.win``. It owns the Windows-native work
that Python does poorly: UI Automation trees, the clipboard, window
enumeration and a real ConPTY console.

Everything is optional. If the sidecar is missing or fails, callers fall back
to the pure-Python implementations — the app never depends on it.
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

PIPE_NAME = r"\\.\pipe\agentdesk.win"


def _candidate_executables() -> list[Path]:
    here = Path(__file__).resolve().parent
    out: list[Path] = []
    env = os.environ.get("AGENTDESK_WIN_SIDECAR")
    if env:
        out.append(Path(env))
    # installed layout: resources/native/AgentDesk.Win/AgentDesk.Win.exe
    # development layout: <repo>/native/AgentDesk.Win/AgentDesk.Win.exe
    bases = [here.parents[1]] if len(here.parents) > 1 else []
    if len(here.parents) > 2:
        bases.append(here.parents[2])
    bases.append(here.parent)
    for base in bases:
        out.append(base / "native" / "AgentDesk.Win" / "AgentDesk.Win.exe")
        out.append(base / "native" / "AgentDesk.Win" / ".publish" / "AgentDesk.Win.exe")
    return out


class WinSidecar:
    """Thread-safe NDJSON client for the Windows sidecar."""

    def __init__(self) -> None:
        self._process: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._next_id = 0
        self._transport = "stdio"
        self._pipe = None
        self.last_error = ""

    # -- lifecycle ---------------------------------------------------------
    def executable(self) -> Path | None:
        for path in _candidate_executables():
            if path.exists():
                return path
        return None

    def available(self) -> bool:
        return self.executable() is not None

    def ensure_started(self) -> bool:
        with self._lock:
            if self._process and self._process.poll() is None:
                return True
            exe = self.executable()
            if exe is None:
                self.last_error = "sidecar binary not found"
                return False
            try:
                # Preferred transport: the named pipe (\.\pipegentdesk.win).
                # Fallback: the sidecar's stdio mode, which speaks the same NDJSON.
                self._process = subprocess.Popen(
                    [str(exe), "--stdio"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    encoding="utf-8",
                    bufsize=1,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                deadline = time.time() + 10
                while time.time() < deadline:
                    if self._connect_pipe() is not None:
                        self._transport = "pipe"
                        return True
                    if self._process.poll() is not None:
                        break
                    time.sleep(0.2)
                self._transport = "stdio"
                return True
            except Exception as exc:
                self.last_error = str(exc)
                self._process = None
                return False

    def _connect_pipe(self):
        """Open the named pipe in binary mode and return the file object."""
        try:
            handle = open(PIPE_NAME, "r+b", buffering=0)
            return handle
        except Exception:
            return None

    def stop(self) -> None:
        with self._lock:
            if self._process and self._process.poll() is None:
                try:
                    self._process.terminate()
                except Exception:
                    pass
            self._process = None

    # -- protocol ----------------------------------------------------------
    def call(self, method: str, **params: Any) -> dict:
        """Call a sidecar method. Returns ``{ok: bool, result?, error?}``."""
        if not self.ensure_started():
            return {"ok": False, "error": self.last_error or "sidecar unavailable"}
        with self._lock:
            self._next_id += 1
            request_id = self._next_id
            payload = json.dumps({"id": request_id, "method": method, "params": params})
            process = self._process
            if not process or not process.stdin or not process.stdout:
                return {"ok": False, "error": "sidecar not running"}
            try:
                process.stdin.write(payload + "\n")
                process.stdin.flush()
            except Exception as exc:
                return {"ok": False, "error": f"write failed: {exc}"}

            if self._transport == "pipe" and self._pipe is not None:
                return self._call_pipe(request_id, method, params)

            deadline = time.time() + 20
            while time.time() < deadline:
                line = process.stdout.readline()
                if not line:
                    time.sleep(0.05)
                    continue
                try:
                    response = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if response.get("id") != request_id:
                    continue
                if response.get("ok"):
                    return {"ok": True, "result": response.get("result")}
                return {"ok": False, "error": response.get("error", "unknown error")}
            return {"ok": False, "error": "timeout"}

    def _call_pipe(self, request_id: int, method: str, params: dict) -> dict:
        payload = json.dumps({"id": request_id, "method": method, "params": params})
        try:
            self._pipe.write(payload.encode("utf-8") + b"\n")
        except Exception as exc:
            return {"ok": False, "error": f"pipe write failed: {exc}"}
        deadline = time.time() + 20
        while time.time() < deadline:
            line = self._pipe.readline()
            if not line:
                time.sleep(0.05)
                continue
            try:
                response = json.loads(line.decode("utf-8", "replace"))
            except json.JSONDecodeError:
                continue
            if response.get("id") != request_id:
                continue
            if response.get("ok"):
                return {"ok": True, "result": response.get("result")}
            return {"ok": False, "error": response.get("error", "unknown error")}
        return {"ok": False, "error": "timeout"}

    # -- convenience -------------------------------------------------------
    def foreground_window(self) -> dict:
        response = self.call("window.foreground")
        return dict(response.get("result") or {}) if response.get("ok") else {}

    def list_windows(self) -> list[dict]:
        response = self.call("window.list")
        if response.get("ok"):
            return list((response.get("result") or {}).get("windows") or [])
        return []

    def uia_tree(self, depth: int = 6, max_nodes: int = 400) -> list[dict]:
        response = self.call("uia.tree", depth=depth, max=max_nodes)
        if response.get("ok"):
            return list((response.get("result") or {}).get("nodes") or [])
        return []

    def clipboard_get(self) -> str:
        response = self.call("clipboard.get")
        return str((response.get("result") or {}).get("text", "")) if response.get("ok") else ""

    def clipboard_set(self, text: str) -> bool:
        return bool(self.call("clipboard.set", text=text).get("ok"))

    def status(self) -> dict:
        exe = self.executable()
        return {
            "transport": self._transport,
            "available": bool(exe),
            "executable": str(exe) if exe else "",
            "pipe": PIPE_NAME,
            "running": bool(self._process and self._process.poll() is None),
            "last_error": self.last_error,
        }


sidecar = WinSidecar()
