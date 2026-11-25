"""Process entry point for the bundled llama.cpp server.

Uses the official Vulkan-enabled native server when available (GPU offload via
Vulkan, with the system Vulkan runtime), and falls back to the bundled
llama-cpp-python server on CPU. Both expose the same OpenAI-compatible `/v1`
API on the loopback port and are protected by the persisted API key.
"""
import hmac
import os
import subprocess
from contextlib import suppress
import sys
import threading
from pathlib import Path

import uvicorn
from llama_cpp.server.app import create_app
from llama_cpp.server.settings import ModelSettings, ServerSettings
from starlette.responses import JSONResponse


def _exit_when_owner_closes(child: subprocess.Popen | None = None) -> None:
    """Exit with the backend process; also stop the native child if present."""
    try:
        sys.stdin.buffer.read(1)
    except Exception:
        pass
    if child is not None and child.poll() is None:
        with suppress(Exception):
            child.terminate()
    os._exit(0)


def _run_python(model_path: str, port: int, token: str) -> None:
    settings = ServerSettings(api_key=token)
    model = ModelSettings(
        model=model_path, n_ctx=4096, n_gpu_layers=0,
        n_threads=min(4, max(1, (os.cpu_count() or 2) // 2)), n_batch=256, n_ubatch=128,
    )
    app = create_app(server_settings=settings, model_settings=[model])

    @app.middleware("http")
    async def verify(request, call_next):
        supplied = request.headers.get("authorization", "").encode()
        if not hmac.compare_digest(supplied, f"Bearer {token}".encode()):
            return JSONResponse({"detail": "Model authorization required"}, 401)
        return await call_next(request)

    uvicorn.run(app, host="127.0.0.1", port=port)


def _run_vulkan(exe: Path, model_path: str, port: int) -> None:
    """Launch the official Vulkan llama-server.exe and mirror its lifecycle."""
    key_file = os.environ.get("AGENTDESK_LLAMA_KEY_FILE", "")
    args = [
        str(exe),
        "-m", str(model_path),
        "--host", "127.0.0.1",
        "--port", str(port),
        "-ngl", os.environ.get("AGENTDESK_LLAMA_GPU_LAYERS", "99"),
        "-c", os.environ.get("AGENTDESK_LLAMA_CTX", "4096"),
        "--threads", os.environ.get("AGENTDESK_LLAMA_THREADS", "4"),
        "-b", "256",
        "-ub", "128",
    ]
    if key_file and Path(key_file).exists():
        # Avoid putting the loopback API key on the command line.
        args.extend(["--api-key-file", key_file])
    child = subprocess.Popen(
        args,
        cwd=str(exe.parent),
        env=os.environ.copy(),
        stdin=subprocess.DEVNULL,
        stdout=sys.stdout,
        stderr=sys.stderr,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    threading.Thread(target=_exit_when_owner_closes, args=(child,), daemon=True).start()
    try:
        child.wait()
    finally:
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=5)
            except Exception:
                child.kill()


def main() -> None:
    model_path, port = sys.argv[1:3]
    token = os.environ.pop("AGENTDESK_LLAMA_TOKEN", "")
    exe = Path(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] else None
    if exe is not None and exe.exists():
        _run_vulkan(exe, model_path, int(port))
        return
    if not token:
        raise RuntimeError("Missing AGENTDESK_LLAMA_TOKEN")
    _run_python(model_path, int(port), token)


if __name__ == "__main__":
    main()
