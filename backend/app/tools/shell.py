import asyncio
import ctypes
import ctypes.wintypes
import os
import re
import sys
from pathlib import Path

MAX_OUTPUT = 30_000

_MINIMAL_ENV_KEYS = {
    "SystemRoot", "SystemDrive", "ComSpec", "WINDIR", "PATH", "PATHEXT",
    "TEMP", "TMP", "USERNAME", "USERPROFILE", "HOMEDRIVE", "HOMEPATH",
    "COMPUTERNAME", "PROCESSOR_ARCHITECTURE", "NUMBER_OF_PROCESSORS",
    "PROGRAMDATA", "PROGRAMFILES", "PROGRAMFILES(X86)", "APPDATA", "LOCALAPPDATA",
    "PYTHONIOENCODING",
}

DANGEROUS_PATTERNS = [
    (re.compile(r"(^|\s)(rm|del|rmdir|erase)\s+.*(/s|/q|-rf|-r|-f)"), "recursive/force delete"),
    (re.compile(r"(^|\s)(format|diskpart|mkfs)\b"), "disk formatting"),
    (re.compile(r"(^|\s)(shutdown|restart-computer|stop-computer)\b", re.I), "system power action"),
    (re.compile(r"Remove-Item\b.*-Recurse", re.I), "recursive delete (PowerShell)"),
    (re.compile(r"\b(curl|wget|iwr|Invoke-WebRequest)\b.*\|\s*(sh|bash|powershell|cmd)"), "pipe download to shell"),
    (re.compile(r"\b(reg\s+delete|sc\s+delete|net\s+user)\b", re.I), "system/registry/user change"),
    (re.compile(r">\s*/dev/|>>\s*/dev/"), "device overwrite"),
    (re.compile(r"\b(chmod|chown)\s+.*777"), "world-writable permissions"),
]

def classify_command(command: str) -> tuple[str, str]:
    """Return (level, reason): safe | caution | dangerous."""
    text = (command or "").strip()
    if not text:
        return "safe", ""
    for pattern, reason in DANGEROUS_PATTERNS:
        if pattern.search(text):
            return "dangerous", reason
    caution_patterns = [
        re.compile(r"\b(pip|npm|yarn|pnpm)\s+(install|uninstall|add|remove)\b", re.I),
        re.compile(r"\b(git\s+(push|reset|clean|checkout\s+--))\b", re.I),
        re.compile(r"[>&]\s*[^\s]"),
        re.compile(r"\b(Set-|New-|Remove-|Stop-|Start-Process)\b", re.I),
    ]
    for pattern in caution_patterns:
        if pattern.search(text):
            return "caution", "modifies files, packages, git state, or processes"
    return "safe", "read-only or build command"


def _ensure_unix_shims() -> str | None:
    """Create tiny .cmd wrappers so POSIX tools (head/grep/cat/ls/...) work on Windows.

    The agent writes POSIX-style commands by default. Without these shims every
    `head -60` / `grep -n` / `cat` call failed on Windows and burned a step.
    Returns the shim directory to prepend to PATH, or None on failure.
    """
    if sys.platform != "win32":
        return None
    try:
        from ..config import DATA_DIR
        from . import unixshim

        shim_dir = DATA_DIR / unixshim.SHIM_DIR_NAME
        shim_dir.mkdir(parents=True, exist_ok=True)
        helper = Path(__file__).with_name("unixshim.py")
        if not helper.is_file():
            return None
        python = sys.executable
        for tool in unixshim.TOOLS:
            wrapper = shim_dir / f"{tool}.cmd"
            content = (
                "@echo off\r\n"
                f'"{python}" "{helper}" "{tool}" %*\r\n'
            )
            if not wrapper.is_file() or wrapper.read_text(encoding="utf-8", errors="replace") != content:
                wrapper.write_text(content, encoding="utf-8")
        return str(shim_dir)
    except Exception:
        return None


def _minimal_environment() -> dict:
    """Build a minimal environment for child processes."""
    env = {}
    for key in _MINIMAL_ENV_KEYS:
        value = os.environ.get(key)
        if value:
            env[key] = value
    env.setdefault("PYTHONIOENCODING", "utf-8")
    shim_dir = _ensure_unix_shims()
    if shim_dir:
        existing = env.get("PATH") or os.environ.get("PATH") or ""
        env["PATH"] = f"{shim_dir}{os.pathsep}{existing}"
    return env

# Windows Job Object constants (via ctypes, no pywin32 dependency needed)
if sys.platform == "win32":
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    _kernel32.CreateJobObjectW.restype = ctypes.wintypes.HANDLE
    _kernel32.CreateJobObjectW.argtypes = (ctypes.wintypes.LPVOID, ctypes.wintypes.LPCWSTR)
    _kernel32.SetInformationJobObject.restype = ctypes.wintypes.BOOL
    _kernel32.SetInformationJobObject.argtypes = (
        ctypes.wintypes.HANDLE, ctypes.c_int, ctypes.wintypes.LPVOID, ctypes.wintypes.DWORD,
    )
    _kernel32.OpenProcess.restype = ctypes.wintypes.HANDLE
    _kernel32.OpenProcess.argtypes = (ctypes.wintypes.DWORD, ctypes.wintypes.BOOL, ctypes.wintypes.DWORD)
    _kernel32.AssignProcessToJobObject.restype = ctypes.wintypes.BOOL
    _kernel32.AssignProcessToJobObject.argtypes = (ctypes.wintypes.HANDLE, ctypes.wintypes.HANDLE)
    _kernel32.TerminateJobObject.restype = ctypes.wintypes.BOOL
    _kernel32.TerminateJobObject.argtypes = (ctypes.wintypes.HANDLE, ctypes.wintypes.UINT)
    _kernel32.CloseHandle.restype = ctypes.wintypes.BOOL
    _kernel32.CloseHandle.argtypes = (ctypes.wintypes.HANDLE,)

    class _JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.wintypes.LARGE_INTEGER),
            ("PerJobUserTimeLimit", ctypes.wintypes.LARGE_INTEGER),
            ("LimitFlags", ctypes.wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", ctypes.wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", ctypes.wintypes.DWORD),
            ("SchedulingClass", ctypes.wintypes.DWORD),
        ]

    class _JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", _JOBOBJECT_BASIC_LIMIT_INFORMATION),
            ("IoInfo", ctypes.c_void_p * 6),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
    _JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 0x00000008
    _JOB_OBJECT_LIMIT_DIE_ON_UNHANDLED_EXCEPTION = 0x00000400

    def _create_job_object() -> int:
        """Create a Windows Job Object with KILL_ON_JOB_CLOSE so all child processes
        are terminated when the job handle is closed (including on crash/timeout)."""
        job = _kernel32.CreateJobObjectW(None, None)
        if not job:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        limits.BasicLimitInformation.LimitFlags = (
            _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            | _JOB_OBJECT_LIMIT_ACTIVE_PROCESS
            | _JOB_OBJECT_LIMIT_DIE_ON_UNHANDLED_EXCEPTION
        )
        limits.BasicLimitInformation.ActiveProcessLimit = 16
        success = _kernel32.SetInformationJobObject(
            job, 9,  # JobObjectExtendedLimitInformation
            ctypes.byref(limits),
            ctypes.sizeof(limits),
        )
        if not success:
            error = ctypes.get_last_error()
            _kernel32.CloseHandle(job)
            raise ctypes.WinError(error)
        return job

    def _assign_process_to_job(job: int, pid: int) -> bool:
        PROCESS_SET_QUOTA = 0x0100
        PROCESS_TERMINATE = 0x0001
        handle = _kernel32.OpenProcess(PROCESS_SET_QUOTA | PROCESS_TERMINATE, False, pid)
        if not handle:
            return False
        try:
            return bool(_kernel32.AssignProcessToJobObject(job, handle))
        finally:
            _kernel32.CloseHandle(handle)

    def _terminate_job(job: int) -> None:
        try:
            _kernel32.TerminateJobObject(job, 1)
        except Exception:
            pass

    def _close_job(job: int) -> None:
        try:
            _kernel32.CloseHandle(job)
        except Exception:
            pass
else:
    def _create_job_object() -> int:
        return 0

    def _assign_process_to_job(job: int, pid: int) -> bool:
        return False

    def _terminate_job(job: int) -> None:
        return None

    def _close_job(job: int) -> None:
        return None


async def run_command(command: str, cwd: str, timeout: int = 180) -> dict:
    env = _minimal_environment()
    try:
        job = _create_job_object()
    except Exception:
        job = 0
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        if job:
            try:
                _assign_process_to_job(job, proc.pid)
            except Exception:
                pass
        timed_out = False
        stdout = b""
        stderr_bytes = b""
        try:
            stdout, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            timed_out = True
            if job:
                _terminate_job(job)
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            try:
                stdout, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=5)
            except asyncio.TimeoutError:
                stdout, stderr_bytes = b"", b""
        stdout_text = stdout.decode("utf-8", errors="replace") if stdout else ""
        stderr_text = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""
        output = stdout_text
        if stderr_text:
            output = (output + "\n[stderr]\n" + stderr_text).strip()
        if len(output) > MAX_OUTPUT:
            output = output[:MAX_OUTPUT] + "\n... (output truncated)"
        return {
            "exit_code": proc.returncode,
            "output": output,
            "stdout": stdout_text[:MAX_OUTPUT],
            "stderr": stderr_text[:MAX_OUTPUT],
            "timed_out": timed_out,
        }
    finally:
        if job:
            _close_job(job)