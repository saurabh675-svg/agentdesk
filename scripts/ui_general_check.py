"""Check the new General tab: automations form and Firecrawl key field render."""

import asyncio

from playwright.async_api import async_playwright


async def main() -> None:
    errors: list[str] = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page(viewport={"width": 1600, "height": 950})
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        await page.goto("http://127.0.0.1:5173", wait_until="domcontentloaded")
        await page.wait_for_timeout(4000)
        await page.locator('button[title="Settings"]').first.click()
        await page.wait_for_timeout(800)
        await page.get_by_role("button", name="General").click()
        await page.wait_for_timeout(1000)
        await page.screenshot(path=r"C:\Users\saura\agentdesk\ui-settings-general.png")
        has_automations = await page.get_by_text("Automations").is_visible()
        has_firecrawl = await page.get_by_text("Firecrawl API key").is_visible()
        print("automations heading:", has_automations, "| firecrawl key:", has_firecrawl)
        print("errors:", errors or "none")
        await browser.close()


asyncio.run(main())
