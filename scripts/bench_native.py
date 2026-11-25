"""Benchmark the native accelerators against the pure-Python fallback.

    python scripts/bench_native.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import native_core  # noqa: E402


def make_dom(nodes: int) -> str:
    tree = [
        {
            "tag": "button",
            "role": "button",
            "name": f"Action {i}",
            "value": f"v{i}",
            "children": [],
        }
        for i in range(nodes)
    ]
    return json.dumps(tree)


def time_it(fn, *args, repeat: int = 5):
    start = time.perf_counter()
    for _ in range(repeat):
        fn(*args)
    return (time.perf_counter() - start) / repeat


def main() -> int:
    backend = native_core.active_backend()
    print(f"native backend: {backend}")
    print(json.dumps(native_core.backend_info(), indent=1))

    import os
    size = int(os.environ.get("BENCH_NODES", "4000"))
    old = make_dom(size)
    new = make_dom(size).replace(f'"Action {size // 2}"', f'"Action {size // 2} changed"')

    py_diff = time_it(native_core._python_diff, old, new, repeat=3)
    all_diff = time_it(native_core.dom_diff, old, new, repeat=3)

    secret_text = (
        "contact bob@example.com with api_key=sk-abcdefghijklmnopqrstuvwxyz and "
        "token: eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N "
    ) * 40
    py_scrub = time_it(native_core._python_scrub, secret_text, repeat=5)
    all_scrub = time_it(native_core.scrub, secret_text, repeat=5)

    long_text = "AgentDesk native accelerator benchmark. " * 4000
    py_tokens = time_it(lambda: max(len(long_text) // 4, len(long_text.split()) or 0), repeat=5)
    all_tokens = time_it(native_core.count_tokens, long_text, repeat=5)

    print("\n--- results (ms, lower is better) ---")
    for label, py_value, native_value in (
        (f"dom_diff({size} nodes)", py_diff, all_diff),
        ("scrub(2KB secret)", py_scrub, all_scrub),
        ("count_tokens(160KB)", py_tokens, all_tokens),
    ):
        speedup = (py_value / native_value) if native_value else float("inf")
        print(f"{label:22} python={py_value * 1000:8.3f}ms  active={native_value * 1000:8.3f}ms  speedup={speedup:5.2f}x")

    # correctness: both paths must agree on the change count
    py_entries = native_core._python_diff(old, new)
    native_entries = native_core.dom_diff(old, new)
    print(f"\nchange entries: python={len(py_entries)} active={len(native_entries)}")
    scrubbed, count = native_core.scrub(secret_text)
    print(f"scrub redactions: {count} (leaked email: {'bob@example.com' in scrubbed})")
    print(f"content_ref: {native_core.content_ref(old)[:20]}")

    ok = len(py_entries) == len(native_entries) and count > 0 and "bob@example.com" not in scrubbed
    print("\nRESULT:", "OK" if ok else "MISMATCH")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
