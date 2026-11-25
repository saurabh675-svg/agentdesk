"""Inspect ChatGPT and Gemini pages for prompt-box selectors and blocking."""

import asyncio

from playwright.async_api import async_playwright


async def inspect(page, name: str, url: str) -> None:
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=45_000)
    except Exception as exc:
        print(name, "goto failed:", type(exc).__name__, str(exc)[:200])
    await page.wait_for_timeout(4000)
    print(f"--- {name} ---")
    print("url:", page.url)
    print("title:", await page.title())
    body = (await page.inner_text("body"))[:500].replace("\n", " | ")
    print("body:", body)
    for selector in (
        "#prompt-textarea",
        "textarea",
        "div[contenteditable='true']",
        "rich-textarea .ql-editor",
        "button[data-testid='send-button']",
        "[aria-label*='Sign in']",
        "[aria-label*='Log in']",
    ):
        try:
            print(f"  {selector}: {await page.locator(selector).count()}")
        except Exception as exc:
            print(f"  {selector}: error {exc}")
    await page.screenshot(path=rf"C:\Users\saura\agentdesk\probe-{name}.png")


async def main() -> None:
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=True, args=["--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(viewport={"width": 1280, "height": 900})
        page = await context.new_page()
        await inspect(page, "chatgpt", "https://chatgpt.com/")
        await inspect(page, "gemini", "https://gemini.google.com/app")
        await browser.close()


asyncio.run(main())
