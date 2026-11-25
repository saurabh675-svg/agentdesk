"""Worker spawn: Cline, Kiro, OpenCode are visible background CLI workers."""

import shutil
import subprocess
import threading
from typing import Callable, Optional


class Worker:
    def __init__(self, worker_type: str, cli: str, args: list[str] | None = None) -> None:
        self.worker_type = worker_type
        self.cli = cli
        self.args = args or []
        self._proc: subprocess.Popen | None = None
        self._threads: list[threading.Thread] = []
        self.stdout_lines: list[str] = []
        self.stderr_lines: list[str] = []

    def start(self, on_output: Optional[Callable[[str], None]] = None) -> dict:
        exe = shutil.which(self.cli)
        if exe is None:
            raise FileNotFoundError(f"Worker CLI not found: {self.cli}")
        self._proc = subprocess.Popen(
            [exe, *self.args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace",
            bufsize=1,
        )

        def pump(stream, sink: list[str]) -> None:
            if stream is None:
                return
            for line in iter(stream.readline, ""):
                sink.append(line)
                if on_output:
                    on_output(line)
            stream.close()

        self._threads = [
            threading.Thread(target=pump, args=(self._proc.stdout, self.stdout_lines), daemon=True),
            threading.Thread(target=pump, args=(self._proc.stderr, self.stderr_lines), daemon=True),
        ]
        for thread in self._threads:
            thread.start()
        return {"id": self.worker_type, "type": self.worker_type, "cli": self.cli, "pid": self._proc.pid, "alive": True}

    def stop(self) -> dict:
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
        return {"ok": True, "stopped": True}

    def tail_stdout(self, limit: int = 200) -> list[str]:
        return self.stdout_lines[-limit:]
