from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..tools.browser import browser

router = APIRouter()


class BrowserAction(BaseModel):
    action: str
    url: str | None = None
    selector: str | None = None
    text: str | None = None
    key: str | None = None
    submit: bool = False
    delta_y: int = 600
    # Coordinates for click_at (CSS px in the 1280x800 viewport screenshot).
    x: int | None = None
    y: int | None = None


@router.get("/state")
async def get_browser_state() -> dict:
    return await browser.state()


@router.post("/action")
async def browser_action(body: BrowserAction) -> dict:
    try:
        if body.action == "navigate":
            if not body.url:
                raise ValueError("url is required")
            await browser.navigate(body.url)
        elif body.action == "focus":
            # Bring the real browser window to the front so the user can
            # complete a human check.
            try:
                await browser.ensure_headed()
            except Exception:
                pass
            page = await browser.page()
            try:
                await page.bring_to_front()
            except Exception:
                pass
            await browser.challenge_status()
        elif body.action == "back":
            await browser.back()
        elif body.action == "forward":
            await browser.forward()
        elif body.action == "reload":
            await browser.reload()
        elif body.action == "click":
            if not body.selector:
                raise ValueError("selector is required")
            await browser.click(body.selector)
        elif body.action == "click_at":
            if body.x is None or body.y is None:
                raise ValueError("x and y are required for click_at")
            await browser.click_at(body.x, body.y)
        elif body.action == "type":
            if body.selector:
                await browser.type_text(body.selector, body.text or "", body.submit)
            elif body.text:
                await browser.keyboard_type(body.text)
        elif body.action in ("type_direct", "keyboard_type"):
            if body.text:
                await browser.keyboard_type(body.text)
        elif body.action in ("press", "key_press"):
            key = body.key or body.text or "Enter"
            await browser.press(key)
        elif body.action == "scroll":
            await browser.scroll(body.delta_y)
        else:
            raise ValueError(f"Unknown action: {body.action}")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return await browser.state()


class ChallengeWaitBody(BaseModel):
    timeout: float = 180.0


@router.get("/challenge")
async def browser_challenge() -> dict:
    """Current bot / human-verification challenge state."""
    return await browser.challenge_status()


@router.post("/challenge/wait")
async def browser_challenge_wait(body: ChallengeWaitBody) -> dict:
    """Wait for the human to finish the check; the agent resumes afterwards."""
    # Make sure the window is on screen so the user can actually interact.
    try:
        await browser.ensure_headed()
    except Exception:
        pass
    return await browser.wait_for_challenge_clear(body.timeout)


@router.get("/drivers")
async def browser_drivers() -> dict:
    """Which open-source browser drivers are available in this install."""
    from ..tools.browser_drivers import available_drivers

    return {"drivers": available_drivers(), "active": browser.driver, "engine": browser.engine}
