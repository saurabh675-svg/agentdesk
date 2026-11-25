"""Check that the chat mode chips switch state and persist."""

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
            lambda message: errors.append(f"{message.type}: {message.text}")
            if message.type == "error"
            else None,
        )
        await page.goto("http://127.0.0.1:5173", wait_until="domcontentloaded")
        await page.wait_for_timeout(3500)
        for label in ("Hard · free", "ChatGPT", "Gemini", "Saved"):
            await page.get_by_role("button", name=label, exact=True).click()
            await page.wait_for_timeout(300)
            active = (await page.locator(".mode-chip.active").inner_text()).strip()
            hint = (await page.locator(".mode-hint").inner_text()).strip()
            print(f"{label} -> {active} | {hint}")
        stored = await page.evaluate("localStorage.getItem('agentdesk.chatMode')")
        print("stored mode:", stored)
        print("errors:", errors or "none")
        await browser.close()


asyncio.run(main())
