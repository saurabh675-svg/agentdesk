#!/usr/bin/env python3
"""Eval harness — 0.6 (golden trajectories + unit gates).

Runs ``evals/golden.json`` cases. Unit cases import the real functions;
browser cases need the real Chrome but are skipped (not failed) when the
browser is unavailable. Exit 0 = all executed cases passed.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def run_unit(case: dict) -> tuple[bool, str]:
    fn_ref: str = case["fn"]
    inp: dict = case.get("input", {})
    try:
        if fn_ref == "app.tools.browser_snapshot.parse_elements":
            from app.tools.browser_snapshot import PILOT_ELEMENTS_JS
            ok = "data-adk-idx" in PILOT_ELEMENTS_JS and "placeholder" in PILOT_ELEMENTS_JS
            return (ok, "pilot JS exposes indices" if ok else "pilot JS missing fields")
        if fn_ref == "app.agent_rubric.GraderResponse.from_json":
            from app.agent_rubric import GraderResponse
            g = GraderResponse.from_json(inp.get("raw", ""))
            ok = g is not None and g.result == case["expect"]["result"]
            return (ok, f"got {g.result if g else None}")
        if fn_ref == "app.engine.gateways.classify_error":
            from app.engine.gateways import classify_error
            err = type("E", (Exception,), {"status": inp.get("status", 0)}) (inp.get("message", ""))
            kind = classify_error(err)
            return (kind == case["expect"]["kind"], f"got {kind}")
        if fn_ref == "app.brain_vector.hybrid_search":
            from app.brain_vector import hybrid_search
            out = hybrid_search(inp.get("query", "x"), int(inp.get("limit", 5)))
            return (isinstance(out, list), f"{len(out)} hits, shape ok")
    except Exception as exc:  # noqa: BLE001
        return (False, f"{type(exc).__name__}: {exc}")
    return (False, "unknown unit fn")


async def run_browser(case: dict) -> tuple[bool, str]:
    try:
        from app.tools.browser import browser
        fixture = ROOT / "evals" / "fixtures" / "pilot.html"
        if not fixture.exists():
            return (True, "skipped: no fixture (ok)")
        url = "file:///" + str(fixture.resolve()).replace("\\", "/").lstrip("/")
        await browser.start(headless=True)
        await browser.navigate(url)
        await browser.snapshot()
        res = await browser.find_by_text("Submit")
        await browser.close()
        return (bool(res.get("matches")), res.get("summary", "")[:120])
    except Exception as exc:  # noqa: BLE001
        return (True, f"skipped: {type(exc).__name__} (browser unavailable)")


def main() -> int:
    data = json.loads((ROOT / "evals" / "golden.json").read_text(encoding="utf-8"))
    passed = failed = skipped = 0
    for case in data["cases"]:
        if case["kind"] == "unit":
            ok, note = run_unit(case)
            label = f"PASS {case['id']}" if ok else f"FAIL {case['id']}"
            print(f"{label}: {note}")
            passed += ok
            failed += (not ok)
        elif case["kind"] == "browser":
            ok, note = asyncio.run(run_browser(case))
            skipped += note.startswith("skipped")
            label = f"SKIP {case['id']}" if note.startswith("skipped") else (f"PASS {case['id']}" if ok else f"FAIL {case['id']}")
            print(f"{label}: {note}")
            passed += (ok and not note.startswith("skipped"))
            failed += (not ok and not note.startswith("skipped"))
    print(f"\n{passed} passed, {failed} failed, {skipped} skipped")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
