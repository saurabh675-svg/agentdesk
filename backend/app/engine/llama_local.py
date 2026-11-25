"""Local llama.cpp (llama-cpp-python) OpenAI-compatible server manager.

AgentDesk runs this as an always-on local LLM so the "local" provider never
leaves the machine. The server is a plain `python -m llama_cpp.server` process
that exposes an OpenAI-compatible `/v1` API.
"""

import asyncio
import os
import secrets
import signal
import subprocess
import sys
from pathlib import Path

import httpx

from ..config import DATA_DIR, load_settings

DEFAULT_PORT = 11435
LOCAL_URL = f"http://127.0.0.1:{DEFAULT_PORT}/v1"

_proc: subprocess.Popen | None = None
_lock = asyncio.Lock()
_resolved_model: str | None = None


def _load_access_key() -> str:
    """Persist the llama.cpp auth token so a restarted backend can still use the
    already-running local server instead of getting 401s on every request."""
    key_file = DATA_DIR / "llama.key"
    try:
        existing = key_file.read_text(encoding="utf-8").strip()
        if existing:
            return existing
    except Exception:
        pass
    key = secrets.token_urlsafe(32)
    try:
        key_file.parent.mkdir(parents=True, exist_ok=True)
        key_file.write_text(key, encoding="utf-8")
    except Exception:
        pass
    return key


_access_key = _load_access_key()


def _model_candidates() -> list[Path]:
    candidates: list[Path] = []
    for name in ("qwen2.5-1.5b-instruct-q4_k_m.gguf", "tinyllama-1.1b-instruct-v0.3-q4_k_m.gguf"):
        home_model = Path.home() / ".llama" / name
        if home_model.exists():
            candidates.append(home_model)
    llama_dir = Path.home() / ".llama"
    if llama_dir.exists():
        candidates.extend(sorted(llama_dir.glob("*.gguf"), key=lambda p: p.stat().st_size, reverse=True))
    for base in (Path(sys.executable).parent.parent / "models", Path(__file__).resolve().parents[3] / "installer" / "runtime" / "models"):
        try:
            for candidate in sorted(base.glob("*.gguf"), key=lambda p: p.stat().st_size, reverse=True):
                if candidate.exists() and candidate not in candidates:
                    candidates.append(candidate)
        except Exception:
            pass
    # Deduplicate by resolved path, largest first.
    seen: set[Path] = set()
    unique: list[Path] = []
    for candidate in candidates:
        try:
            key = candidate.resolve()
        except Exception:
            key = candidate
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    unique.sort(key=lambda p: (p.name != "qwen2.5-1.5b-instruct-q4_k_m.gguf", p.stat().st_size))
    return unique


def resolve_model_path() -> Path | None:
    settings = load_settings()
    custom = str(settings.get("local_model_path") or "").strip()
    if custom:
        candidate = Path(custom)
        if candidate.exists():
            return candidate
    candidates = _model_candidates()
    if candidates:
        # Prefer the explicitly configured model if it is in the list.
        for candidate in candidates:
            if custom and candidate.name == Path(custom).name:
                return candidate
        return candidates[0]
    return None


def base_url() -> str:
    return LOCAL_URL


def access_key() -> str:
    return _access_key


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_access_key}"}


def health_url() -> str:
    return f"http://127.0.0.1:{DEFAULT_PORT}/v1/models"


def vulkan_exe() -> Path | None:
    """Locate the bundled official Vulkan-enabled llama-server.exe, if present."""
    name = "llama-server.exe" if os.name == "nt" else "llama-server"
    candidates: list[Path] = []
    configured = str(os.environ.get("AGENTDESK_LLAMA_VULKAN_EXE") or "").strip()
    if configured:
        candidates.append(Path(configured))
    candidates.extend([
        # Packaged app: resources/runtime/python/python.exe -> resources/runtime/llama-vulkan
        Path(sys.executable).resolve().parent.parent / "llama-vulkan" / name,
        # Source tree: backend/app/engine/llama_local.py -> installer/runtime/llama-vulkan
        Path(__file__).resolve().parents[3] / "installer" / "runtime" / "llama-vulkan" / name,
    ])
    for candidate in candidates:
        try:
            if candidate.is_file():
                return candidate
        except Exception:
            continue
    return None


def backend_status() -> dict:
    """Report which local backend will be used (and why)."""
    settings = load_settings()
    selected = str(settings.get("local_backend") or "auto").strip().lower()
    if selected not in ("auto", "vulkan", "cpu"):
        selected = "auto"
    exe = vulkan_exe()
    available = exe is not None
    active = "cpu"
    if selected == "vulkan" and available:
        active = "vulkan"
    elif selected == "auto" and available:
        active = "vulkan"
    return {
        "selected": selected,
        "active": active,
        "available": available,
        "executable": str(exe) if exe else "",
        "gpu_layers": settings.get("local_gpu_layers", 99),
        "context_size": settings.get("local_context_size", 4096),
        "devices": [],
        "tokens_per_second": None,
        "vram_mb": None,
    }


def _spawn() -> subprocess.Popen:
    model = resolve_model_path()
    if model is None:
        raise RuntimeError(
            "No local GGUF model found. Set a path in Settings → General → Local model file."
        )
    env = {
        **os.environ,
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUNBUFFERED": "1",
    }
    for name in ("HOST", "PORT", "CONFIG_FILE"):
        env.pop(name, None)
    settings = load_settings()
    status = backend_status()
    exe = vulkan_exe() if status["active"] == "vulkan" else None
    env["AGENTDESK_LLAMA_TOKEN"] = _access_key
    env["AGENTDESK_LLAMA_KEY_FILE"] = str(DATA_DIR / "llama.key")
    env["AGENTDESK_LLAMA_GPU_LAYERS"] = str(settings.get("local_gpu_layers", 99))
    env["AGENTDESK_LLAMA_CTX"] = str(settings.get("local_context_size", 4096))
    env["AGENTDESK_LLAMA_THREADS"] = str(settings.get("local_threads", 4))
    args = [
        sys.executable,
        str(Path(__file__).with_name("llama_server.py")),
        str(model),
        str(DEFAULT_PORT),
    ]
    if exe is not None:
        args.append(str(exe))
    log_file = DATA_DIR / "llama_local.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a", encoding="utf-8") as output:
        return subprocess.Popen(
            args,
            cwd=str(Path.cwd()),
            env=env,
            stdin=subprocess.PIPE,
            stdout=output,
            stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )


def _alive(proc: subprocess.Popen | None) -> bool:
    return proc is not None and proc.poll() is None


async def _wait_healthy(timeout: float = 90.0) -> None:
    deadline = asyncio.get_event_loop().time() + timeout
    last_err: Exception | None = None
    async with httpx.AsyncClient(trust_env=False, timeout=httpx.Timeout(connect=2.0, read=2.0, write=2.0, pool=2.0)) as client:
        while asyncio.get_event_loop().time() < deadline:
            if not _alive(_proc):
                raise RuntimeError("Local model server exited. Check llama_local.log.")
            try:
                response = await client.get(health_url(), headers=_auth_headers())
                if response.status_code == 200:
                    return
            except httpx.HTTPError as exc:
                last_err = exc
            await asyncio.sleep(2.0)
    raise RuntimeError(f"Local model server did not become healthy: {last_err}")


async def ensure() -> str:
    """Ensure the local llama.cpp server is running; return its base URL."""
    global _proc, _resolved_model
    async with _lock:
        # Reuse a server left running by a previous backend process (persisted
        # auth key makes this possible), instead of fighting it for the port.
        async with httpx.AsyncClient(trust_env=False, timeout=5.0) as client:
            try:
                if (await client.get(health_url(), headers=_auth_headers())).status_code == 200:
                    return LOCAL_URL
            except Exception:
                pass
        # Our own process may still be loading the model; give it time to finish
        # before deciding it is unhealthy.
        if _alive(_proc):
            try:
                await _wait_healthy(timeout=60)
                return LOCAL_URL
            except Exception:
                pass
        if _proc is not None:
            try:
                _proc.terminate()
                await asyncio.to_thread(_proc.wait, timeout=5)
            except Exception:
                try:
                    _proc.kill()
                except Exception:
                    pass
        _resolved_model = None
        _proc = _spawn()
        await _wait_healthy()
        return LOCAL_URL


def is_available() -> bool:
    return _alive(_proc)


async def resolve_model_name() -> str:
    """Ask the server for the active model id, or fall back to the GGUF name."""
    global _resolved_model
    if _resolved_model:
        return _resolved_model
    async with httpx.AsyncClient(trust_env=False, timeout=10.0) as client:
        try:
            response = await client.get(f"{LOCAL_URL}/models", headers=_auth_headers())
            data = response.json().get("data") or []
            if data:
                _resolved_model = str(data[0].get("id") or data[0].get("name"))
        except Exception:
            pass
    if not _resolved_model:
        model_path = resolve_model_path()
        _resolved_model = model_path.name if model_path else "local-gguf"
    return _resolved_model


def _pids_on_port() -> list[int]:
    """Best-effort list of local llama server processes to stop before a restart.

    Windows does not always expose the owning PID for a loopback listener, so we
    combine netstat with a command-line scan. Switching backend/model must stop
    an orphan left by a previous backend process, not just our tracked child.
    """
    pids: set[int] = set()
    no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        output = subprocess.run(
            ["netstat", "-ano", "-p", "tcp"],
            capture_output=True, text=True, timeout=5,
            creationflags=no_window,
        ).stdout
        for line in output.splitlines():
            if f"127.0.0.1:{DEFAULT_PORT}" not in line or "LISTENING" not in line.upper():
                continue
            parts = line.split()
            if parts and parts[-1].isdigit():
                pids.add(int(parts[-1]))
    except Exception:
        pass
    if os.name == "nt":
        try:
            script = (
                "Get-CimInstance Win32_Process | Where-Object { "
                "($_.CommandLine -like '*AgentDesk*') -and "
                "(($_.Name -eq 'llama-server.exe') -or "
                "($_.Name -like 'python*.exe' -and $_.CommandLine -like '*llama_server.py*')) "
                "} | ForEach-Object { $_.ProcessId }"
            )
            output = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                capture_output=True, text=True, timeout=8,
                creationflags=no_window,
            ).stdout
            for line in output.splitlines():
                if line.strip().isdigit():
                    pids.add(int(line.strip()))
        except Exception:
            pass
    return [pid for pid in pids if pid != os.getpid()]


async def stop() -> None:
    global _proc
    async with _lock:
        proc, _proc = _proc, None
        if proc is not None:
            try:
                proc.terminate()
                await asyncio.to_thread(proc.wait, timeout=10)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        for pid in _pids_on_port():
            try:
                os.kill(pid, getattr(signal, "SIGTERM", signal.SIGKILL))
            except Exception:
                pass
