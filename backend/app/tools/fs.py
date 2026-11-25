import os
import stat
from pathlib import Path

from ..config import DATA_DIR, UPLOADS_DIR
from ..encryption import decrypt_text, encrypt_text, is_encrypted

IGNORED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
    ".next",
    ".turbo",
    "target",
}
MAX_READ_CHARS = 80_000
MAX_TREE_ENTRIES = 600


class SafePathError(ValueError):
    """Typed safe-path failure. ``reason`` is one of outside_workspace,
    private_profile, symlink, or not_found. Kept as a ValueError subclass
    so existing callers keep working."""
    def __init__(self, message: str, reason: str = "outside_workspace"):
        super().__init__(message)
        self.reason = reason


def safe_path(root: str, relative: str) -> Path:
    root_path = Path(root).resolve()
    candidate = Path(relative)
    path = candidate.resolve() if candidate.is_absolute() else (root_path / candidate).resolve()
    data_root = DATA_DIR.resolve()
    uploads_root = UPLOADS_DIR.resolve()
    if path.is_relative_to(data_root) and not path.is_relative_to(uploads_root):
        raise SafePathError("AgentDesk profile files are private", reason="private_profile")
    allowed_roots = [root_path, uploads_root]
    allowed = False
    for allowed_root in allowed_roots:
        allowed_norm = os.path.normcase(str(allowed_root))
        path_norm = os.path.normcase(str(path))
        if path_norm == allowed_norm or path_norm.startswith(allowed_norm + os.sep):
            allowed = True
            break
    if not allowed:
        raise SafePathError(f"Path '{relative}' is outside the workspace or uploads directory", reason="outside_workspace")
    # Symlink escape check: resolve already handled, but flag reparse points.
    try:
        if path.exists() and path.is_symlink():
            raise SafePathError(f"Path '{relative}' is a symlink", reason="symlink")
    except SafePathError:
        raise
    except OSError:
        pass
    return path


def _is_ignored(name: str) -> bool:
    return name in IGNORED_DIRS or name.startswith(".") or name.startswith("~$")


def _skip_entry(entry: Path) -> bool:
    if _is_ignored(entry.name):
        return True
    try:
        info = entry.lstat()
        if entry.is_symlink() or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            return True
        return entry.resolve() == DATA_DIR.resolve()
    except OSError:
        return True


def build_tree(root: str, relative: str = ".", max_depth: int = 3) -> list[dict]:
    base = safe_path(root, relative)
    if not base.exists():
        raise ValueError(f"Path not found: {relative}")
    if not base.is_dir():
        raise ValueError(f"Not a directory: {relative}")
    counter = {"n": 0}

    def walk(path: Path, depth: int) -> list[dict]:
        if depth > max_depth or counter["n"] >= MAX_TREE_ENTRIES:
            return []
        try:
            entries = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except OSError:
            return []
        nodes = []
        for entry in entries:
            if counter["n"] >= MAX_TREE_ENTRIES:
                break
            if _skip_entry(entry):
                continue
            node = {
                "name": entry.name,
                "path": entry.relative_to(Path(root).resolve()).as_posix(),
                "type": "dir" if entry.is_dir() else "file",
            }
            counter["n"] += 1
            if entry.is_dir():
                node["children"] = walk(entry, depth + 1)
            nodes.append(node)
        return nodes

    return walk(base, 1)


def render_tree(nodes: list[dict], prefix: str = "") -> str:
    lines = []
    for i, node in enumerate(nodes):
        last = i == len(nodes) - 1
        branch = "└── " if last else "├── "
        suffix = "/" if node["type"] == "dir" else ""
        lines.append(f"{prefix}{branch}{node['name']}{suffix}")
        if node.get("children"):
            lines.extend(render_tree(node["children"], prefix + ("    " if last else "│   ")))
    return "\n".join(lines)


def read_file(
    root: str, relative: str, start_line: int | None = None, end_line: int | None = None
) -> str:
    path = safe_path(root, relative)
    if not path.is_file():
        raise ValueError(f"File not found: {relative}")
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
        text = decrypt_text(raw) if is_encrypted(raw) else raw
    except OSError as exc:
        raise ValueError(f"Cannot read {relative}: {exc}") from exc
    lines = text.splitlines()
    start = max((start_line or 1) - 1, 0)
    end = min(end_line or len(lines), len(lines))
    selected = lines[start:end]
    numbered = "\n".join(f"{start + i + 1:>5}│ {line}" for i, line in enumerate(selected))
    if len(numbered) > MAX_READ_CHARS:
        numbered = numbered[:MAX_READ_CHARS] + "\n... (truncated)"
    total = len(lines)
    header = f"{relative} ({total} lines)" + (f", showing {start + 1}-{end}" if (start or end != total) else "")
    return f"{header}\n{numbered}"


def write_file(root: str, relative: str, content: str) -> str:
    path = safe_path(root, relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return f"Wrote {len(content)} characters to {relative}"


def edit_file(root: str, relative: str, old_string: str, new_string: str) -> str:
    path = safe_path(root, relative)
    if not path.is_file():
        raise ValueError(f"File not found: {relative}")
    raw = path.read_text(encoding="utf-8", errors="replace")
    text = decrypt_text(raw) if is_encrypted(raw) else raw
    count = text.count(old_string)
    if count == 1:
        updated = text.replace(old_string, new_string, 1)
        path.write_text(updated, encoding="utf-8")
        return f"Edited {relative} (replaced 1 occurrence)"
    if count > 1:
        raise ValueError(
            f"old_string occurs {count} times; include more surrounding context to make it unique"
        )
    # Line-normalized fallback for CRLF/whitespace differences
    norm_text = text.replace("\r\n", "\n")
    norm_old = old_string.replace("\r\n", "\n")
    norm_new = new_string.replace("\r\n", "\n")
    if norm_text.count(norm_old) == 1:
        # Re-apply preserving file's newline style
        target_nl = "\r\n" if "\r\n" in text else "\n"
        updated = norm_text.replace(norm_old, norm_new, 1)
        if target_nl == "\r\n":
            updated = updated.replace("\n", "\r\n")
        path.write_text(updated, encoding="utf-8")
        return f"Edited {relative} (fuzzy newline normalized match)"
    raise ValueError("old_string was not found in the file")


def search_files(
    root: str, query: str, relative: str = ".", max_matches: int = 50, regex: bool = False
) -> str:
    """Grep-like search across workspace files for a substring or regex pattern."""
    import re

    base = safe_path(root, relative)
    if not base.exists():
        raise ValueError(f"Path not found: {relative}")

    pattern = None
    if regex:
        try:
            pattern = re.compile(query, re.IGNORECASE)
        except re.error as exc:
            raise ValueError(f"Invalid regex: {exc}")
    else:
        query_lower = query.lower()

    matches = []
    root_resolved = Path(root).resolve()

    def scan_dir(folder: Path):
        nonlocal matches
        if len(matches) >= max_matches:
            return
        try:
            entries = sorted(folder.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except OSError:
            return
        for entry in entries:
            if len(matches) >= max_matches:
                break
            if _skip_entry(entry):
                continue
            if entry.is_dir():
                scan_dir(entry)
            elif entry.is_file():
                # Skip large binary files
                if entry.stat().st_size > 2_000_000:
                    continue
                try:
                    raw = entry.read_text(encoding="utf-8", errors="replace")
                    content = decrypt_text(raw) if is_encrypted(raw) else raw
                    for line_no, line in enumerate(content.splitlines(), start=1):
                        hit = pattern.search(line) if regex else (query_lower in line.lower())
                        if hit:
                            rel = entry.relative_to(root_resolved).as_posix()
                            matches.append(f"{rel}:{line_no}: {line.strip()[:140]}")
                            if len(matches) >= max_matches:
                                break
                except Exception:
                    continue

    if base.is_file():
        try:
            raw = base.read_text(encoding="utf-8", errors="replace")
            content = decrypt_text(raw) if is_encrypted(raw) else raw
            for line_no, line in enumerate(content.splitlines(), start=1):
                hit = pattern.search(line) if regex else (query_lower in line.lower())
                if hit:
                    matches.append(f"{relative}:{line_no}: {line.strip()[:140]}")
        except Exception:
            pass
    else:
        scan_dir(base)

    if not matches:
        return f"No matches found for '{query}'"
    header = f"Found {len(matches)} match(es)" + (f" (capped at {max_matches}):" if len(matches) >= max_matches else ":")
    return header + "\n" + "\n".join(matches)


def list_directory(root: str, relative: str = ".") -> str:
    path = safe_path(root, relative)
    if not path.is_dir():
        raise ValueError(f"Not a directory: {relative}")
    entries = []
    for entry in sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        if _is_ignored(entry.name):
            continue
        entries.append(entry.name + ("/" if entry.is_dir() else ""))
    return "\n".join(entries) or "(empty directory)"
