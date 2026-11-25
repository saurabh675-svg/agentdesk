"""Unix-command compatibility shims for the Windows shell.

The agent writes POSIX-flavoured commands by default (``head -60``, ``grep -n``,
``cat``, ``ls``, ``sed -n``). On Windows those are not present, so every such call
failed and burned a step. These shims are tiny ``.cmd`` wrappers that the shell
tool puts on the child's PATH; each one runs this module with the original
tool name and arguments, so the common POSIX subset "just works" on Windows
without changing the agent's habits.

Only the shim directory is prepended to PATH — the rest of the environment is
still the minimal whitelist used by :mod:`app.tools.shell`.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

SHIM_DIR_NAME = "unixshims"

# tool name -> python implementation in this module
TOOLS = (
    "head",
    "tail",
    "grep",
    "cat",
    "ls",
    "wc",
    "sort",
    "uniq",
    "echo",
    "pwd",
    "find",
    "sed",
    "select-object",
)


def _read_lines(path: str) -> list[str]:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fp:
            return fp.read().splitlines()
    except OSError as exc:
        print(f"{path}: {exc.strerror or exc}")
        return []


def _stdin_lines() -> list[str]:
    try:
        return sys.stdin.read().splitlines()
    except Exception:
        return []


def _collect_files(args: list[str]) -> tuple[list[str], bool]:
    """Return (files, use_stdin)."""
    files = [a for a in args if not a.startswith("-")]
    return files, not files


def do_head(args: list[str]) -> int:
    count = 10
    rest: list[str] = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == "-n" and i + 1 < len(args):
            count = int(args[i + 1] or 10)
            i += 2
            continue
        if re.fullmatch(r"-\d+", a):
            count = int(a[1:])
            i += 1
            continue
        rest.append(a)
        i += 1
    files, use_stdin = _collect_files(rest)
    lines: list[str] = []
    if use_stdin:
        lines = _stdin_lines()
    else:
        for f in files:
            lines.extend(_read_lines(f))
    for line in lines[: max(0, count)]:
        print(line)
    return 0


def do_tail(args: list[str]) -> int:
    count = 10
    rest: list[str] = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == "-n" and i + 1 < len(args):
            count = int(args[i + 1] or 10)
            i += 2
            continue
        if re.fullmatch(r"-\d+", a):
            count = int(a[1:])
            i += 1
            continue
        rest.append(a)
        i += 1
    files, use_stdin = _collect_files(rest)
    lines: list[str] = []
    if use_stdin:
        lines = _stdin_lines()
    else:
        for f in files:
            lines.extend(_read_lines(f))
    for line in lines[-max(0, count) :] if count else []:
        print(line)
    return 0


def do_grep(args: list[str]) -> int:
    ignore_case = False
    show_line_no = False
    invert = False
    fixed = False
    pattern = None
    files: list[str] = []
    i = 0
    while i < len(args):
        a = args[i]
        if a.startswith("-") and len(a) > 1 and not a.startswith("--"):
            if "i" in a:
                ignore_case = True
            if "n" in a:
                show_line_no = True
            if "v" in a:
                invert = True
            if "F" in a:
                fixed = True
            i += 1
            continue
        if pattern is None:
            pattern = a
        else:
            files.append(a)
        i += 1
    if pattern is None:
        print("usage: grep [-in] pattern [file...]", file=sys.stderr)
        return 2
    flags = re.IGNORECASE if ignore_case else 0
    if fixed:
        rx = re.compile(re.escape(pattern), flags)
    else:
        try:
            rx = re.compile(pattern, flags)
        except re.error as exc:
            print(f"grep: {exc}", file=sys.stderr)
            return 2
    sources = files or ["-"]
    matched = False
    for src in sources:
        lines = _stdin_lines() if src == "-" else _read_lines(src)
        for n, line in enumerate(lines, start=1):
            hit = bool(rx.search(line))
            if hit != invert:
                matched = True
                prefix = f"{src}:" if src != "-" else ""
                num = f"{n}:" if show_line_no else ""
                print(f"{prefix}{num}{line}")
    return 0 if matched else 1


def do_cat(args: list[str]) -> int:
    files = [a for a in args if not a.startswith("-")]
    if not files:
        for line in _stdin_lines():
            print(line)
        return 0
    for f in files:
        for line in _read_lines(f):
            print(line)
    return 0


def do_ls(args: list[str]) -> int:
    long = any(a.startswith("-") and "l" in a for a in args if a.startswith("-"))
    paths = [a for a in args if not a.startswith("-")] or ["."]
    for idx, raw in enumerate(paths):
        p = Path(raw)
        if idx > 0:
            print()
        print(f"{raw}:")
        try:
            entries = sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
        except OSError as exc:
            print(f"ls: {raw}: {exc.strerror or exc}", file=sys.stderr)
            continue
        for entry in entries:
            if long:
                try:
                    size = entry.stat().st_size
                except OSError:
                    size = 0
                kind = "d" if entry.is_dir() else "-"
                print(f"{kind}rw-r--r-- {size:>10} {entry.name}")
            else:
                print(entry.name + ("/" if entry.is_dir() else ""))
    return 0


def do_wc(args: list[str]) -> int:
    files = [a for a in args if not a.startswith("-")]
    lines_mode = any(a in ("-l", "-lw", "-lw") for a in args)
    words_mode = any(a in ("-w", "-lw") for a in args)
    chars_mode = any(a in ("-c", "-m") for a in args)
    sources = files or ["-"]
    for src in sources:
        text = "\n".join(_stdin_lines() if src == "-" else _read_lines(src))
        if not (lines_mode or words_mode or chars_mode):
            lines_mode = words_mode = chars_mode = True
        parts = []
        if lines_mode:
            parts.append(str(len(text.splitlines())))
        if words_mode:
            parts.append(str(len(text.split())))
        if chars_mode:
            parts.append(str(len(text)))
        label = "" if src == "-" else f" {src}"
        print(" ".join(parts) + label)
    return 0


def do_sort(args: list[str]) -> int:
    numeric = any(a.startswith("-") and "n" in a for a in args if a.startswith("-"))
    reverse = any(a.startswith("-") and "r" in a for a in args if a.startswith("-"))
    unique = any(a.startswith("-") and "u" in a for a in args if a.startswith("-"))
    files = [a for a in args if not a.startswith("-")]
    lines = _stdin_lines() if not files else [ln for f in files for ln in _read_lines(f)]
    lines.sort(key=lambda x: (float(x) if _is_num(x) else float("inf")) if numeric else x,
               reverse=reverse)
    if unique:
        seen = set()
        out = []
        for line in lines:
            if line not in seen:
                seen.add(line)
                out.append(line)
        lines = out
    for line in lines:
        print(line)
    return 0


def _is_num(value: str) -> bool:
    try:
        float(value)
        return True
    except ValueError:
        return False


def do_uniq(args: list[str]) -> int:
    count_mode = any(a.startswith("-") and "c" in a for a in args if a.startswith("-"))
    files = [a for a in args if not a.startswith("-")]
    lines = _stdin_lines() if not files else [ln for f in files for ln in _read_lines(f)]
    groups: list[tuple[str, int]] = []
    for line in lines:
        if groups and groups[-1][0] == line:
            groups[-1] = (line, groups[-1][1] + 1)
        else:
            groups.append((line, 1))
    for line, count in groups:
        print(f"{count:>7} {line}" if count_mode else line)
    return 0


def do_echo(args: list[str]) -> int:
    newline = True
    if args and args[0] == "-n":
        newline = False
        args = args[1:]
    text = " ".join(args)
    sys.stdout.write(text + ("\n" if newline else ""))
    return 0


def do_pwd(args: list[str]) -> int:
    print(os.getcwd())
    return 0


def do_find(args: list[str]) -> int:
    root = "."
    name_pattern = None
    ftype = None
    i = 0
    while i < len(args):
        a = args[i]
        if a == "-name" and i + 1 < len(args):
            name_pattern = args[i + 1]
            i += 2
            continue
        if a == "-type" and i + 1 < len(args):
            ftype = args[i + 1]
            i += 2
            continue
        if not a.startswith("-"):
            root = a
        i += 1
    base = Path(root)
    try:
        walker = base.rglob("*")
    except OSError as exc:
        print(f"find: {exc}", file=sys.stderr)
        return 1
    rx = re.compile(re.escape(name_pattern).replace(r"\*", ".*").replace(r"\?", ".")) if name_pattern else None
    for entry in walker:
        if name_pattern and not (rx.match(entry.name) or rx.match(str(entry))):
            continue
        if ftype == "f" and not entry.is_file():
            continue
        if ftype == "d" and not entry.is_dir():
            continue
        print(entry)
    return 0


def do_sed(args: list[str]) -> int:
    """Supports ``-n``, ``p``, ``s/pattern/replacement/[g]`` and simple
    line-address scripts such as ``2p``, ``1,5p``, ``$p``.

    The agent commonly uses ``sed -n 'Np'`` to show one line of a file.
    """
    quiet = False
    script = ""
    files: list[str] = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == "-n":
            quiet = True
            i += 1
            continue
        if a.startswith("-") and len(a) > 1:
            i += 1
            continue
        if not script:
            script = a
        else:
            files.append(a)
        i += 1
    if not script:
        print("usage: sed [-n] 's/pat/rep/[g]' [file...]", file=sys.stderr)
        return 2

    substitution = None
    print_only = False
    address: tuple[int, int] | None = None
    if script == "p":
        print_only = True
    elif re.fullmatch(r"\d+(,\d*)?p", script):
        start_text, _, end_text = script[:-1].partition(",")
        start = int(start_text)
        end = int(end_text) if end_text else (10**9 if not end_text and "," in script else start)
        address = (start, end)
        print_only = True
    elif script == "$p":
        address = (-1, -1)
        print_only = True
    else:
        match = re.match(r"^s(.)(.*?)(?<!\\)\1(.*?)(?<!\\)\1([gi]*)(p?)$", script)
        if not match:
            print(f"sed: unsupported script: {script}", file=sys.stderr)
            return 2
        _sep, pattern, repl, flags, trailing_p = match.groups()
        substitution = (pattern, repl, "g" in flags)
        print_only = bool(trailing_p)

    lines = _stdin_lines() if not files else [ln for f in files for ln in _read_lines(f)]
    for index, line in enumerate(lines, start=1):
        out = line
        if substitution:
            pattern, repl, global_flag = substitution
            try:
                rx = re.compile(pattern)
            except re.error as exc:
                print(f"sed: {exc}", file=sys.stderr)
                return 2
            repl_fixed = repl.replace("\\", "\\\\")
            out = rx.sub(repl_fixed, line) if global_flag else rx.sub(repl_fixed, line, count=1)
        if address is not None:
            start, end = address
            if start == -1:
                if index != len(lines):
                    continue
            elif not (start <= index <= end):
                continue
        if print_only or not quiet:
            print(out)
    return 0


def do_select_object(args: list[str]) -> int:
    """PowerShell-ish ``Select-Object -First N`` / ``-Last N`` over stdin."""
    count = 0
    last = False
    i = 0
    while i < len(args):
        a = args[i]
        if a in ("-First", "-f") and i + 1 < len(args):
            count = int(args[i + 1] or 0)
            i += 2
            continue
        if a in ("-Last", "-l") and i + 1 < len(args):
            count = int(args[i + 1] or 0)
            last = True
            i += 2
            continue
        i += 1
    lines = _stdin_lines()
    if count > 0:
        lines = lines[-count:] if last else lines[:count]
    for line in lines:
        print(line)
    return 0


DISPATCH = {
    "head": do_head,
    "tail": do_tail,
    "grep": do_grep,
    "cat": do_cat,
    "ls": do_ls,
    "wc": do_wc,
    "sort": do_sort,
    "uniq": do_uniq,
    "echo": do_echo,
    "pwd": do_pwd,
    "find": do_find,
    "sed": do_sed,
    "select-object": do_select_object,
}


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: unixshim <tool> [args...]", file=sys.stderr)
        return 2
    name = argv[0].strip().lower()
    handler = DISPATCH.get(name)
    if not handler:
        print(f"unixshim: unknown tool '{name}'", file=sys.stderr)
        return 127
    try:
        return handler(argv[1:])
    except Exception as exc:  # never crash the caller's pipeline
        print(f"{name}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
