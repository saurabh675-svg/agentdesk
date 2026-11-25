import asyncio
import shutil
import sys
import threading
from pathlib import Path


class TerminalSession:
    """A persistent PowerShell session for one chat session."""

    def __init__(self, cwd: str) -> None:
        self.cwd = cwd
        self.buffer = ""
        self.subscribers: set[asyncio.Queue] = set()
        self.proc = None
        self.error: str | None = None
        self._loop = asyncio.get_running_loop()
        self._start()

    def _shell_argv(self) -> list[str]:
        if sys.platform == "win32":
            shell = shutil.which("powershell.exe") or "powershell.exe"
            return [shell, "-NoLogo", "-NoProfile", "-NoExit"]
        shell = shutil.which("bash") or "/bin/bash"
        return [shell, "-i"]

    def _start(self) -> None:
        try:
            from winpty import PtyProcess

            self.proc = PtyProcess.spawn(self._shell_argv(), cwd=self.cwd, dimensions=(30, 120))
            if sys.platform == "win32":
                self.proc.write("chcp 65001 | Out-Null\r\n")
            thread = threading.Thread(target=self._reader, daemon=True)
            thread.start()
        except Exception as exc:
            self.error = str(exc)

    def _reader(self) -> None:
        while True:
            try:
                data = self.proc.read(4096)
            except EOFError:
                break
            except Exception as exc:
                self._push_nowait(f"\r\n[terminal closed: {exc}]\r\n")
                break
            if not data:
                break
            self._push_nowait(data)

    def _push_nowait(self, data: str) -> None:
        if not data:
            return
        self.buffer = (self.buffer + data)[-200_000:]
        for queue in list(self.subscribers):
            try:
                self._loop.call_soon_threadsafe(queue.put_nowait, data)
            except RuntimeError:
                pass

    def write(self, data: str) -> None:
        if self.proc:
            try:
                self.proc.write(data)
            except Exception as exc:
                self._push_nowait(f"\r\n[write failed: {exc}]\r\n")

    def resize(self, rows: int, cols: int) -> None:
        if self.proc:
            try:
                self.proc.setwinsize(max(rows, 5), max(cols, 20))
            except Exception:
                pass

    def restart(self) -> None:
        try:
            if self.proc:
                self.proc.close(force=True)
        except Exception:
            pass
        self.buffer = ""
        self._start()
        self._push_nowait("\r\n[terminal restarted]\r\n")

    def close(self) -> None:
        try:
            if self.proc:
                self.proc.close(force=True)
        except Exception:
            pass


class TerminalManager:
    def __init__(self) -> None:
        self.sessions: dict[int, TerminalSession] = {}

    def get(self, session_id: int, cwd: str) -> TerminalSession:
        terminal = self.sessions.get(session_id)
        if terminal is None or terminal.error:
            if terminal:
                terminal.close()
            Path(cwd).mkdir(parents=True, exist_ok=True)
            terminal = TerminalSession(cwd)
            self.sessions[session_id] = terminal
        return terminal

    def close_all(self) -> None:
        for terminal in self.sessions.values():
            terminal.close()
        self.sessions.clear()


terminal_manager = TerminalManager()
