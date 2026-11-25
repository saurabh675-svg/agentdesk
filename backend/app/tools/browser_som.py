"""Set-of-Marks grounding for the browser — 0.7.

Annotates the live page with numbered badges (same numbering as
``browser_elements``) and returns the screenshot + element list so a
vision model (VLM tier) or the user can ground a target to a number,
which the agent then clicks by index. DOM path (deterministic); the VLM
is an enhancement, not a requirement.
"""

from __future__ import annotations

SOM_SCRIPT = r"""() => {
  document.querySelectorAll('[data-adk-som]').forEach(n => n.remove());
  const els = Array.from(document.querySelectorAll('[data-adk-idx]'));
  els.forEach(el => {
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) return;
    const badge = document.createElement('div');
    badge.setAttribute('data-adk-som', '1');
    badge.textContent = el.getAttribute('data-adk-idx');
    badge.style.cssText = `position:fixed;left:${Math.max(0,r.x)}px;top:${Math.max(0,r.y)}px;z-index:2147483647;background:#0a84ff;color:#fff;font:700 11px/14px monospace;padding:1px 5px;border-radius:3px;pointer-events:none;`;
    document.body.appendChild(badge);
  });
  return els.length;
}"""

SOM_CLEANUP = "() => document.querySelectorAll('[data-adk-som]').forEach(n=>n.remove())"


async def set_of_marks(page, screenshot_fn) -> dict:
    """Draw numbered badges, capture, clean up. ``page`` is a Playwright Page."""
    count = await page.evaluate(SOM_SCRIPT)
    frame = await screenshot_fn()
    try:
        await page.evaluate(SOM_CLEANUP)
    except Exception:
        pass
    return {
        "frame": frame.get("frame") if isinstance(frame, dict) else frame,
        "count": int(count or 0),
        "note": f"Set-of-Marks: {count} elements numbered; click by index via browser_click_element.",
    }
