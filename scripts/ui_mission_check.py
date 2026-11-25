"""Check that the right pane has a Mission tab and it renders without errors."""

import asyncio

from playwright.async_api import async_playwright


async def main() -> None:
    errors: list[str] = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page(viewport={"width": 1600, "height": 950})
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.on(
            "console",
            lambda m: errors.append(m.text) if m.type == "error" else None,
        )
        await page.goto("http://127.0.0.1:5173", wait_until="domcontentloaded")
        await page.wait_for_timeout(4000)
        await page.get_by_role("button", name="Mission", exact=True).click()
        await page.wait_for_timeout(1200)
        visible = await page.get_by_text("Mission", exact=True).first.is_visible()
        print("mission tab visible:", visible)
        print("automations UI:", (await page.locator(".mission-view").count()) > 0)
        print("errors:", errors or "none")
        await browser.close()


asyncio.run(main())
