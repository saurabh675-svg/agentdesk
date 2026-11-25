"""Drive ChatGPT or Gemini through the built-in Chromium window.

Both sites are consumer web apps without an API, so we automate their real UI in the
persistent browser profile. The window is kept visible while doing this: the sites show
human checks and sign-in screens that the user must be able to solve.
"""

import asyncio
import re
from typing import Awaitable, Callable
from urllib.parse import urlparse

from ..tools.browser import browser

Status = Callable[[str], Awaitable[None]]

SITES = {
    "chatgpt": {
        "label": "ChatGPT",
        "url": "https://chatgpt.com/",
        "hosts": ("chatgpt.com", "chat.openai.com"),
        "input": "#prompt-textarea, div[contenteditable='true']",
        "send": "button[data-testid='send-button'], button[aria-label*='Send']",
        # ChatGPT's 2026 UI dropped data-message-author-role. Assistant replies are
        # wrapped in a MarkdownRoot-* div; keep legacy selectors as fallbacks.
        "assistant": (
            "[data-message-author-role='assistant']",
            "div[class*='MarkdownRoot']",
            "[data-testid='assistant-message']",
            ".markdown",
        ),
        "stop": "button[data-testid='stop-button'], button[aria-label*='Stop']",
    },
    "gemini": {
        "label": "Gemini",
        "url": "https://gemini.google.com/app",
        "hosts": ("gemini.google.com",),
        # Gemini moved its editor out of <rich-textarea> in 2026; the role and
        # aria-label are stable, so prefer those over hashed Angular classes.
        "input": (
            "div[role='textbox'][aria-label*='prompt for Gemini'], "
            "rich-textarea .ql-editor, div[contenteditable='true']"
        ),
        "send": "button[aria-label='Send message'], button[aria-label*='Send'], button.send-button",
        "assistant": "model-response",
        "stop": "button[aria-label*='Stop'], button[aria-label*='stop']",
    },
}

CHALLENGE_HINTS = (
    "just a moment",
    "verify you are human",
    "checking your browser",
    "enable javascript and cookies",
    "cloudflare",
)

SIGN_IN_HINTS = ("sign in", "log in", "sign up")


async def _visible(page, selector: str, timeout: int = 600) -> bool:
    try:
        return await page.locator(selector).first.is_visible(timeout=timeout)
    except Exception:
        return False


async def _body_text(page, limit: int = 2500) -> str:
    try:
        return (await page.inner_text("body"))[:limit]
    except Exception:
        return ""


async def _last_assistant_text(page, selectors: str | tuple[str, ...]) -> str:
    """Return the newest visible answer, trying stable selectors in priority order."""
    candidates = (selectors,) if isinstance(selectors, str) else selectors
    for selector in candidates:
        try:
            locator = page.locator(selector)
            count = await locator.count()
            if not count:
                continue
            for index in range(count - 1, -1, -1):
                try:
                    node = locator.nth(index)
                    if await node.is_visible():
                        return _clean_reply(await node.inner_text())
                except Exception:
                    continue
            return _clean_reply(await locator.nth(count - 1).inner_text())
        except Exception:
            continue
    return ""


def _clean_reply(text: str) -> str:
    """Drop ChatGPT/Gemini button labels that appear in the message element's text."""
    junk = {
        "copy",
        "edit",
        "share",
        "regenerate",
        "good response",
        "bad response",
        "read aloud",
        "listen",
        "show more",
        "show less",
    }
    lines = [line.rstrip() for line in text.strip().splitlines()]
    labels = {"gemini said", "chatgpt said", "assistant said", "you said"}
    while lines and lines[0].strip().lower() in labels:
        lines.pop(0)
    while lines and lines[-1].strip().lower() in junk:
        lines.pop()
    return "\n".join(lines).strip()


async def _wait_for_prompt(
    page, site: str, config: dict, on_status: Status | None, timeout: int = 120
) -> None:
    """Wait for the prompt box, letting the user clear sign-in or human checks."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    label = config["label"]
    warned_check = False
    warned_login = False
    started = loop.time()

    while loop.time() < deadline:
        if await _visible(page, config["input"], timeout=800):
            return

        title = ""
        try:
            title = (await page.title()).lower()
        except Exception:
            pass
        body = (await _body_text(page, 1600)).lower()
        blob = f"{title}\n{body}"

        if not warned_check and any(hint in blob for hint in CHALLENGE_HINTS):
            warned_check = True
            if on_status:
                await on_status(
                    f"{label} is showing a human check. Solve it in the Chromium window — "
                    "the agent continues automatically when the prompt box appears."
                )
        elif not warned_login and any(hint in blob for hint in SIGN_IN_HINTS):
            warned_login = True
            if on_status:
                await on_status(
                    f"Sign in to {label} in the Chromium window. The agent continues automatically "
                    "once the chat box is available."
                )
        elif on_status and loop.time() - started > 25:
            started = loop.time()
            if on_status:
                await on_status(
                    f"Still waiting for the {label} prompt box. Finish sign-in or any human check "
                    "in the Chromium window."
                )
        await asyncio.sleep(2)

    raise RuntimeError(
        f"Could not reach the {label} prompt box. A Chromium window is open — finish signing in "
        f"or clear the human check, then send your message again."
    )


async def _submit(page, config: dict) -> None:
    send = config.get("send")
    if send and await _visible(page, send, timeout=1500):
        try:
            await page.locator(send).first.click()
            return
        except Exception:
            pass
    await page.keyboard.press("Enter")


async def respond(
    site: str,
    prompt: str,
    on_token: Callable[[str], Awaitable[None]],
    on_status: Status | None = None,
) -> str:
    """Drive ChatGPT or Gemini through the embedded browser and stream the reply."""
    config = SITES.get(site) or SITES["chatgpt"]
    label = config["label"]

    restarted = await browser.ensure_headed()
    if restarted and on_status:
        await on_status(f"Opened a visible Chromium window for {label}.")

    page = await browser.page()
    url = page.url or ""
    if urlparse(url).hostname not in config["hosts"]:
        try:
            await browser.navigate(config["url"])
        except Exception:
            # Cloudflare sometimes keeps the navigation pending; the page is still usable.
            pass
        await page.wait_for_timeout(2500)

    await _wait_for_prompt(page, site, config, on_status)
    if urlparse(page.url).hostname not in config["hosts"]:
        raise RuntimeError(f"Finish signing in on the official {label} site before retrying.")
    await browser.capture()

    before = await _last_assistant_text(page, config["assistant"])

    input_locator = page.locator(config["input"]).first
    await input_locator.click()
    await page.wait_for_timeout(150)
    await page.keyboard.insert_text(prompt)
    await page.wait_for_timeout(300)
    await _submit(page, config)
    await page.wait_for_timeout(800)

    # Some contenteditable editors swallow Enter while composing; try the send button once more.
    if await _visible(page, config["input"], timeout=300):
        try:
            remaining = await page.locator(config["input"]).first.inner_text()
        except Exception:
            remaining = ""
        if remaining.strip().startswith(prompt.strip()[:40]):
            await _submit(page, config)

    await browser.capture()

    deadline = asyncio.get_running_loop().time() + 300
    last_emitted = ""
    stable = 0
    text = ""
    while asyncio.get_running_loop().time() < deadline:
        await asyncio.sleep(1.5)
        text = await _last_assistant_text(page, config["assistant"])
        streaming = await _visible(page, config["stop"], timeout=250)
        if text and text != before and text != last_emitted:
            delta = text[len(last_emitted) :] if text.startswith(last_emitted) else text
            await on_token(delta)
            last_emitted = text
            stable = 0
        else:
            stable += 1
        if text and text != before and not streaming and stable >= 2:
            break
        if stable > 120:
            break

    if not text or text == before:
        raise RuntimeError(
            f"{label} did not answer. The Chromium window is still open — check that you are "
            "signed in and the chat box works, then retry."
        )
    await browser.capture()
    return text


def clean_prompt(text: str) -> str:
    return re.sub(r"\s+\n", "\n", text).strip()


__all__ = ["respond", "clean_prompt"]
