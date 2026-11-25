"""Capture the AgentDesk UI and report console errors."""

import asyncio
import sys

from playwright.async_api import async_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5173"
OUT = sys.argv[2] if len(sys.argv) > 2 else "ui.png"


async def main() -> None:
    errors: list[str] = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page(viewport={"width": 1600, "height": 950})
        page.on(
            "console",
            lambda message: errors.append(f"{message.type}: {message.text}")
            if message.type == "error"
            else None,
        )
        page.on("pageerror", lambda exc: errors.append(f"pageerror: {exc}"))
        await page.goto(URL, wait_until="domcontentloaded", timeout=30_000)
        await page.wait_for_timeout(12000)
        print(await page.inner_text("body"))
        await page.screenshot(path=OUT, full_page=False)
        print(f"\nscreenshot: {OUT}")
        print("errors:", errors or "none")
        await browser.close()


asyncio.run(main())
