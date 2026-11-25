"""Exercise the settings tabs and right-pane views, capturing screenshots."""

import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

URL = "http://127.0.0.1:5173"
OUT = Path(r"C:\Users\saura\agentdesk")


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
        await page.wait_for_timeout(4000)

        await page.locator('button[title="Settings"]').first.click()
        await page.wait_for_timeout(1200)
        await page.screenshot(path=str(OUT / "ui-settings-model.png"))
        await page.locator(".modal").evaluate("el => el.scrollTo(0, el.scrollHeight)")
        await page.wait_for_timeout(600)
        await page.screenshot(path=str(OUT / "ui-settings-hard.png"))
        await page.locator(".modal").evaluate("el => el.scrollTo(0, 0)")

        tabs = page.locator(".modal-tabs")
        await tabs.get_by_role("button", name="Skills").click()
        await page.wait_for_timeout(1200)
        await page.screenshot(path=str(OUT / "ui-settings-skills.png"))

        await tabs.get_by_role("button", name="MCP").click()
        await page.wait_for_timeout(1500)
        await page.screenshot(path=str(OUT / "ui-settings-mcp.png"))

        await tabs.get_by_role("button", name="Browser").click()
        await page.wait_for_timeout(500)
        await page.screenshot(path=str(OUT / "ui-settings-browser.png"))

        await page.get_by_role("button", name="Cancel").click()
        await page.wait_for_timeout(400)

        await page.get_by_role("button", name="Screen").click()
        await page.wait_for_timeout(2500)
        await page.screenshot(path=str(OUT / "ui-screen.png"))

        await page.get_by_role("button", name="Terminal").click()
        await page.wait_for_timeout(3500)
        await page.screenshot(path=str(OUT / "ui-terminal.png"))

        print("tabs:", await page.locator(".right-tab").all_inner_texts())
        print("errors:", errors or "none")
        await browser.close()


asyncio.run(main())
