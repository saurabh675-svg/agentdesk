import asyncio
import base64

from .browser_drivers import (
    ANTI_DETECT_ARGS,
    STEALTH_SCRIPT,
    chrome_executable,
    resolve as resolve_driver,
)

from ..config import DATA_DIR, load_settings

DEFAULT_STATE = {
    "url": "about:blank",
    "title": "Blank page",
    "can_back": False,
    "can_forward": False,
    "headless": True,
    "engine": "chromium",
}

# Persistent profile so ChatGPT/Gemini/Google logins survive restarts.
PROFILE_DIR = DATA_DIR / "browser-profile"

# Google rejects sign-in from stock automation Chromium ("this browser or app may
# not be secure"). Use the installed Chrome when present, hide the automation
# switch, and present a normal desktop user agent. The persistent profile keeps
# any cookies obtained after the user signs in.
CHROME_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
LAUNCH_ARGS = [
    # Hide the automation flag. Never add a second --disable-features here:
    # Chrome only honours the last one, which would drop the driver's own
    # feature list and stop the browser from starting.
    "--disable-blink-features=AutomationControlled",
]

# Default port for the Chrome DevTools Protocol endpoint. Any language can
# attach to the very same browser that the agent uses (C++ libcurl/websocket,
# C# Selenium/PuppeteerSharp, JS Puppeteer/Playwright, Python, Go, Rust).
DEFAULT_CDP_PORT = 9333


# --------------------------------------------------------------------------- #
# Bot / human-verification challenge detection
# --------------------------------------------------------------------------- #
# Sites answer automation with a challenge widget ("Verify you are human",
# "Press and hold", reCAPTCHA, Turnstile, hCaptcha, DataDome). These cannot be
# defeated automatically - by design. The honest behaviour is to detect the
# challenge, bring the browser on screen, ask the user to complete it and
# resume the agent as soon as it clears.
CHALLENGE_TEXT_MARKERS: tuple[tuple[str, str], ...] = (
    ("press and hold", "press_and_hold"),
    ("verify you are human", "human_check"),
    ("i'm not a robot", "human_check"),
    ("checking your browser", "cloudflare"),
    ("just a moment", "cloudflare"),
    ("attention required", "cloudflare"),
    ("enable javascript and cookies to continue", "cloudflare"),
    ("unusual traffic", "rate_limited"),
    ("complete the security check", "human_check"),
    ("confirm you are human", "human_check"),
    ("are you a robot", "human_check"),
)

CHALLENGE_SELECTORS: tuple[tuple[str, str], ...] = (
    ("iframe[src*='challenges.cloudflare.com']", "cloudflare"),
    ("iframe[src*='recaptcha']", "recaptcha"),
    ("iframe[title*='reCAPTCHA']", "recaptcha"),
    (".g-recaptcha", "recaptcha"),
    ("iframe[src*='hcaptcha']", "hcaptcha"),
    (".h-captcha", "hcaptcha"),
    ("#cf-challenge-running", "cloudflare"),
    ("iframe[src*='datadome']", "datadome"),
    ("iframe[src*='perimeterx']", "datadome"),
    ("[id*='px-captcha']", "datadome"),
    ("[class*='press-and-hold']", "press_and_hold"),
)

CHALLENGE_LABEL = {
    "cloudflare": "Cloudflare check",
    "recaptcha": "reCAPTCHA",
    "hcaptcha": "hCaptcha",
    "datadome": "DataDome bot check",
    "press_and_hold": "Press-and-hold check",
    "rate_limited": "Rate limit / unusual-traffic check",
    "human_check": "Human verification",
}

HUMAN_VERIFICATION_MARKER = "HUMAN_VERIFICATION_REQUIRED"


def _free_port(preferred: int) -> int:
    """Return `preferred` if bindable, else the next free port."""
    import socket

    for candidate in range(preferred, preferred + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", candidate))
            except OSError:
                continue
            return candidate
    return 0


class BrowserManager:
    """Single Chromium page that the agent, web-chat engine and UI share."""

    def __init__(self) -> None:
        self._playwright = None
        self._context = None
        self._page = None
        self._lock = asyncio.Lock()
        self._subscribers: set = set()
        self.last_frame: str | None = None
        self.last_state: dict = dict(DEFAULT_STATE)
        self._started = False
        self._headless: bool | None = None
        self._elements: list[dict] = []
        self.engine = "chromium"
        self.cdp_port: int = 0
        self.cdp_enabled: bool = False
        self.driver: str = "playwright"
        # Bot-check state (Cloudflare / reCAPTCHA / hCaptcha / press-and-hold).
        self.challenge: dict | None = None
        self.challenge_checked_at: float = 0.0
        self.launch_errors: list[str] = []
        self.last_error: str = ""

    async def start(self, headless: bool | None = None) -> None:
        if self._started:
            return
        settings = load_settings()
        PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        factory, self.driver = resolve_driver(str(settings.get("browser_driver") or "auto"))
        self._playwright = await factory().start()
        if headless is None:
            headless = bool(settings.get("browser_headless", False))
        # Patchright and friends fall back to the old `chrome-headless-shell`
        # in headless mode, which is both unstable and trivially detectable.
        # Real Chrome in a real window is what passes bot checks - and it is
        # also what makes a human take-over possible.
        if self.driver != "playwright":
            headless = False
        self._headless = headless
        launch_args = list(LAUNCH_ARGS) + list(ANTI_DETECT_ARGS)
        # Chrome refuses to start when both --remote-debugging-port and
        # --remote-debugging-pipe are present. Playwright always adds the pipe,
        # so the extra DevTools port is only offered on drivers that do not.
        wants_pipe = self.driver in ("patchright",)
        wanted = int(settings.get("browser_cdp_port", DEFAULT_CDP_PORT) or 0)
        if wanted > 0 and not wants_pipe:
            port = _free_port(wanted)
            if port:
                launch_args += [
                    f"--remote-debugging-port={port}",
                    "--remote-allow-origins=*",
                ]
                self.cdp_port = port
                self.cdp_enabled = True
        kwargs = dict(
            headless=headless,
            viewport={"width": 1280, "height": 800},
            device_scale_factor=1,
            chromium_sandbox=True,
            ignore_default_args=["--enable-automation"],
            args=launch_args,
            user_agent=CHROME_USER_AGENT,
            locale="en-US",
        )
        # Real Chrome is trusted by Google sign-in and by bot checks; the
        # bundled Chromium is the fallback. Some drivers (patchright) do not
        # know the "chrome" channel, so point them at the executable directly.
        real_chrome = chrome_executable()
        if self.driver != "playwright" and real_chrome:
            kwargs["executable_path"] = real_chrome

        # Launch attempts, most trusted first. Each failure is recorded so the
        # UI can explain *why* the browser is degraded instead of failing
        # silently.
        attempts: list[tuple[str, dict]] = []
        base = dict(kwargs)
        no_sandbox = {**base, "chromium_sandbox": False}
        if self.driver == "playwright":
            attempts.append(("chrome", {**base, "channel": "chrome"}))
            # Some Chrome builds refuse to start when the sandbox flag is
            # forced on Windows; retry without it before giving up.
            attempts.append(("chrome-nosandbox", {**no_sandbox, "channel": "chrome"}))
        if real_chrome:
            attempts.append(("chrome-exe", {**no_sandbox, "executable_path": real_chrome}))
        # Bundled Chromium: drop the DevTools port (the driver already adds
        # --remote-debugging-pipe and Chrome refuses to start with both).
        minimal = {k: v for k, v in no_sandbox.items() if k != "args"}
        minimal["args"] = [a for a in base.get("args", []) if not a.startswith("--remote-debugging-")]
        attempts.append(("chromium", minimal))

        self.launch_errors: list[str] = []
        for label, attempt_kwargs in attempts:
            try:
                self._context = await self._playwright.chromium.launch_persistent_context(
                    str(PROFILE_DIR), **attempt_kwargs
                )
                self.engine = "chrome" if label.startswith("chrome") else "chromium"
                break
            except Exception as exc:
                self.launch_errors.append(f"{label}: {str(exc)[:180]}")
                continue
        else:
            raise RuntimeError("Could not start the browser. " + " | ".join(self.launch_errors))
        # Hide the automation fingerprint before any site script runs.
        try:
            await self._context.add_init_script(STEALTH_SCRIPT)
        except Exception:
            pass
        pages = self._context.pages
        self._page = pages[0] if pages else await self._context.new_page()
        self._page.set_default_timeout(20_000)
        self._started = True

    async def ensure(self) -> None:
        if not self._started:
            await self.start()

    async def new_isolated_context(self):
        """Opt-in isolated browser context (no shared profile). Caller must close it."""
        await self.ensure()
        if self._playwright is None:
            raise RuntimeError("Browser not started")
        try:
            browser_obj = self._context.browser
        except Exception:
            browser_obj = None
        if browser_obj is None:
            raise RuntimeError("Persistent context has no browser handle for isolated contexts")
        return await browser_obj.new_context(viewport={"width": 1280, "height": 800}, user_agent=CHROME_USER_AGENT)

    async def ensure_headed(self) -> bool:
        """Make sure the window exists on screen, restarting if it was headless.

        Web chats (ChatGPT/Gemini) need a visible window so the user can sign in and pass
        human checks; cookies still come from the same persistent profile.
        """
        await self.ensure()
        if self._headless is False:
            return False
        await self.close()
        # Chrome can keep the profile lock for a moment after a headless restart.
        # Retry instead of failing the whole browser fallback on a transient lock.
        last_error: Exception | None = None
        for _ in range(8):
            try:
                await self.start(headless=False)
                return True
            except Exception as exc:
                last_error = exc
                await self.close()
                await asyncio.sleep(0.75)
        raise last_error or RuntimeError("Could not open a visible browser window")

    # ------------------------------------------------------------ challenges
    async def detect_challenge(self, force: bool = False) -> dict | None:
        """Detect a bot / human-verification challenge on the current page.

        Returns ``None`` for a normal page, otherwise a dict describing the
        challenge so the UI can ask the user to solve it.
        """
        import time as _time

        now = _time.time()
        if not force and self.challenge_checked_at and now - self.challenge_checked_at < 3:
            return self.challenge
        self.challenge_checked_at = now
        try:
            page = self._page
            if page is None or page.is_closed():
                return self.challenge
            url = page.url
            try:
                title = (await page.title()) or ""
            except Exception:
                title = ""

            kind = None
            for selector, name in CHALLENGE_SELECTORS:
                try:
                    if await page.locator(selector).count():
                        kind = name
                        break
                except Exception:
                    continue

            if kind is None:
                try:
                    body = (await page.inner_text("body", timeout=2500))[:1200].lower()
                except Exception:
                    body = ""
                haystack = f"{title} {body}"
                for marker, name in CHALLENGE_TEXT_MARKERS:
                    if marker in haystack:
                        kind = name
                        break

            if kind is None:
                self.challenge = None
                return None

            label = CHALLENGE_LABEL.get(kind, CHALLENGE_LABEL["human_check"])
            self.challenge = {
                "active": True,
                "kind": kind,
                "label": label,
                "url": url,
                "title": title,
                "message": (
                    f"{label} is showing on this page. Complete it in the browser window "
                    "(the agent waits and resumes automatically)."
                ),
                "detected_at": now,
                "headless": bool(self._headless),
                "driver": self.driver,
            }
            return self.challenge
        except Exception:
            return self.challenge

    async def challenge_status(self) -> dict:
        found = await self.detect_challenge()
        return {
            "active": bool(found),
            "challenge": found,
            "marker": HUMAN_VERIFICATION_MARKER,
            "headed": not self._headless,
            "driver": self.driver,
            "engine": self.engine,
        }

    async def wait_for_challenge_clear(self, timeout: float = 180.0) -> dict:
        """Wait until the bot check is gone (the human solved it)."""
        import time as _time

        deadline = _time.time() + max(5.0, timeout)
        while _time.time() < deadline:
            found = await self.detect_challenge(force=True)
            if not found:
                self.challenge = None
                return {"cleared": True}
            await asyncio.sleep(2)
        return {"cleared": False, "challenge": self.challenge}


    async def _settle(self, timeout_ms: int = 6000) -> None:
        """browser-pilot settle(): wait for domcontentloaded + brief pause."""
        try:
            await self._page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
        except Exception:
            pass
        try:
            await self._page.wait_for_timeout(400)
        except Exception:
            pass

    async def snapshot(self, text_limit: int = 3600, element_limit: int = 120) -> dict:
        """browser-pilot extractPage(): LLM-friendly page snapshot.

        Returns snapshot dict plus frame/state for the UI.
        """
        async with self._lock:
            await self.ensure()
            from .browser_snapshot import PILOT_SNAPSHOT_JS
            data = await self._page.evaluate(PILOT_SNAPSHOT_JS, {"limit": element_limit, "textLimit": text_limit})
            self._elements = data.get("elements", [])
            payload = await self.capture()
            return {"snapshot": data, "frame": payload["frame"], "state": payload["state"]}

    async def find_by_text(self, text: str, element_limit: int = 120) -> dict:
        """Find elements whose visible text contains `text` (case-insensitive)."""
        async with self._lock:
            await self.ensure()
            needle = (text or "").strip().lower()
            if not needle:
                return {"matches": [], "summary": "(empty search text)"}
            from .browser_snapshot import PILOT_SNAPSHOT_JS
            data = await self._page.evaluate(PILOT_SNAPSHOT_JS, {"limit": element_limit, "textLimit": 3600})
            self._elements = data.get("elements", [])
            matches = [e for e in self._elements if needle in (e.get("name") or "").lower()]
            payload = await self.capture()
            if not matches:
                return {"matches": [], "summary": f"(no element matching {text!r})", "frame": payload["frame"], "state": payload["state"]}
            summary = chr(10).join(f"[{m['id']}] {m.get('tag')}{' (' + m.get('type') + ')' if m.get('type') else ''}: {m.get('name') or '(no label)'}" for m in matches)
            return {"matches": matches, "summary": summary, "frame": payload["frame"], "state": payload["state"]}

    async def fill_form(self, fields: list) -> dict:
        """Fill multiple indexed fields in one call (browser-pilot type batch)."""
        async with self._lock:
            await self.ensure()
            results: list[str] = []
            for field in fields or []:
                try:
                    idx = int(field.get("index", -1))
                    text = str(field.get("text", ""))
                    submit = bool(field.get("submit", False))
                except Exception:
                    continue
                selector = f'[data-adk-idx="{idx}"]'
                try:
                    locator = self._page.locator(selector).first
                    await locator.scroll_into_view_if_needed(timeout=4000)
                except Exception:
                    pass
                try:
                    await self._page.fill(selector, text)
                    if submit:
                        await self._page.press(selector, "Enter")
                    results.append(f"[{idx}] filled {text[:60]!r}")
                except Exception as exc:
                    results.append(f"[{idx}] failed: {str(exc)[:160]}")
            await self._settle()
            payload = await self.capture()
            return {"results": results, "frame": payload["frame"], "state": payload["state"]}

    async def extract_element_text(self, index=None) -> str:
        """browser-pilot extract: read one element or the page main."""
        async with self._lock:
            await self.ensure()
            if index is not None:
                selector = f'[data-adk-idx="{int(index)}"]'
                try:
                    text = await self._page.locator(selector).first.inner_text(timeout=5000)
                    return f"Element [{index}]: {text[:3000]}"
                except Exception as exc:
                    return f"Element [{index}] unreadable: {str(exc)[:220]}"
            try:
                text = await self._page.evaluate("() => (document.querySelector('main, [role=\"main\"], article') || document.body).innerText.slice(0, 2000)")
                return text or "(empty main content)"
            except Exception as exc:
                return f"Could not extract: {exc}"

    async def structured_extract(self) -> dict:
        """Structured extraction: headings, links, tables and key text as JSON."""
        async with self._lock:
            await self.ensure()
            data = await self._page.evaluate("""() => {
              const clean = s => String(s||'').replace(/\s+/g,' ').trim();
              const headings = Array.from(document.querySelectorAll('h1,h2,h3')).slice(0,12).map(h => ({level: h.tagName, text: clean(h.innerText).slice(0,120)})).filter(h=>h.text);
              const links = Array.from(document.querySelectorAll('a[href]')).slice(0,30).map(a => ({text: clean(a.innerText).slice(0,80), href: a.href})).filter(l=>l.href);
              const tables = Array.from(document.querySelectorAll('table')).slice(0,3).map(t => Array.from(t.querySelectorAll('tr')).slice(0,6).map(tr => Array.from(tr.querySelectorAll('th,td')).map(c=>clean(c.innerText).slice(0,60))));
              const main = document.querySelector('main, [role="main"], article') || document.body;
              const text = clean(main?.innerText || '').slice(0, 3600);
              return { headings, links, tables, text, url: location.href, title: document.title };
            }""")
            payload = await self.capture()
            return {"extract": data, "frame": payload["frame"], "state": payload["state"]}

    async def set_of_marks(self) -> dict:
        """Set-of-Marks: annotate screenshot with numbered element badges."""
        async with self._lock:
            await self.ensure()
            from .browser_som import SOM_SCRIPT, SOM_CLEANUP
            count = await self._page.evaluate(SOM_SCRIPT)
            payload = await self.capture()
            try:
                await self._page.evaluate(SOM_CLEANUP)
            except Exception:
                pass
            frame = payload.get("frame")
            return {
                "frame": frame,
                "count": int(count or 0),
                "summary": f"Set-of-Marks: {int(count or 0)} elements numbered; click by index.",
                "state": payload.get("state", {}),
            }

    async def scroll_to_element(self, index: int) -> dict:
        """Scroll an indexed element into view."""
        async with self._lock:
            await self.ensure()
            selector = f'[data-adk-idx="{int(index)}"]'
            try:
                await self._page.locator(selector).first.scroll_into_view_if_needed(timeout=5000)
            except Exception as exc:
                self.last_error = str(exc)[:220]
                return await self.capture()
            await self._settle()
            self.last_error = ""
            return await self.capture()

    async def page(self):
        await self.ensure()
        return self._page

    @property
    def context(self):
        """The live Playwright browser context (tabs, cookies)."""
        return self._context

    # ---------------------------------------------------------------- inputs

    async def mouse_double_click(self, x: int, y: int) -> dict:
        async with self._lock:
            await self.ensure()
            await self._page.mouse.dblclick(int(x), int(y))
            try:
                await self._page.wait_for_load_state("domcontentloaded", timeout=5000)
            except Exception:
                pass
            return await self.capture()

    async def hover_at(self, x: int, y: int, settle_ms: int = 350) -> dict:
        """Move the mouse and let hover UI (menus, tooltips) settle."""
        async with self._lock:
            await self.ensure()
            await self._page.mouse.move(int(x), int(y))
            try:
                await self._page.wait_for_timeout(settle_ms)
            except Exception:
                pass
            return await self.capture()

    async def drag(self, x: int, y: int, to_x: int, to_y: int, steps: int = 20) -> dict:
        """Press, move in steps, release — real drag and drop."""
        async with self._lock:
            await self.ensure()
            await self._page.mouse.move(int(x), int(y))
            await self._page.mouse.down()
            try:
                await self._page.mouse.move(int(to_x), int(to_y), steps=max(1, int(steps)))
            except Exception:
                pass
            await self._page.mouse.up()
            try:
                await self._page.wait_for_load_state("domcontentloaded", timeout=5000)
            except Exception:
                pass
            return await self.capture()

    async def scroll_to(self, selector: str) -> dict:
        """Scroll an element into view without pixel guessing."""
        async with self._lock:
            await self.ensure()
            await self._page.eval_on_selector(
                selector, "el => el.scrollIntoView({block: 'center', inline: 'nearest'})"
            )
            try:
                await self._page.wait_for_timeout(300)
            except Exception:
                pass
            return await self.capture()

    async def upload_file(self, selector: str, path: str) -> dict:
        """Attach a local file to a file input."""
        async with self._lock:
            await self.ensure()
            await self._page.set_input_files(selector, path)
            try:
                await self._page.wait_for_timeout(300)
            except Exception:
                pass
            return await self.capture()

    async def close(self) -> None:
        try:
            if self._context:
                await self._context.close()
            if self._playwright:
                await self._playwright.stop()
        finally:
            self._started = False
            self._context = None
            self._page = None
            self._headless = None
            self.cdp_port = 0
            self.cdp_enabled = False

    def subscribe(self, callback) -> None:
        self._subscribers.add(callback)

    def unsubscribe(self, callback) -> None:
        self._subscribers.discard(callback)

    async def capture(self) -> dict:
        await self.ensure()
        page = self._page
        frame = self.last_frame
        try:
            data = await page.screenshot(type="jpeg", quality=72)
            frame = "data:image/jpeg;base64," + base64.b64encode(data).decode("ascii")
        except Exception:
            pass
        try:
            title = await page.title()
        except Exception:
            title = ""
        state = {
            "url": page.url,
            "title": title,
            "can_back": True,
            "can_forward": True,
            "headless": bool(self._headless),
            "engine": self.engine,
        }
        self.last_frame = frame
        self.last_state = state
        payload = {"state": state, "frame": frame}
        for callback in list(self._subscribers):
            try:
                await callback(payload)
            except Exception:
                pass
        return payload

    # Backwards-compatible alias
    _capture = capture

    async def state(self) -> dict:
        # Fresh frame on every state request so the UI never shows a stale image.
        if self._started:
            try:
                await self.capture()
            except Exception:
                pass
        return {"frame": self.last_frame, "state": self.last_state}

    async def set_zoom(self, factor: float = 1.0) -> dict:
        async with self._lock:
            await self.ensure()
            try:
                factor = max(0.2, min(3.0, float(factor)))
            except (TypeError, ValueError):
                factor = 1.0
            await self._page.evaluate(f"document.body.style.zoom = {factor!r}; window.dispatchEvent(new Event('resize'));")
            # Let the browser process the resize event instead of a fixed sleep.
            try:
                await self._page.wait_for_load_state("domcontentloaded", timeout=3000)
            except Exception:
                pass
            return await self.capture()

    async def navigate(self, url: str) -> dict:
        async with self._lock:
            await self.ensure()
            if not url.startswith(("http://", "https://", "about:", "file://")):
                url = "https://" + url
            try:
                await self._page.goto(url, wait_until="domcontentloaded", timeout=20000)
            except Exception as exc:
                # Challenge pages (Cloudflare and friends) never reach a load
                # state, so a timeout here is normal, not a failure. The page
                # is already showing the check - report it as such.
                challenge = await self.detect_challenge(force=True)
                if challenge:
                    self.last_state = {
                        **self.last_state,
                        "url": self._page.url if self._page else url,
                        "title": challenge.get("title") or "Human verification",
                        "challenge": challenge,
                    }
                    return await self.capture()
                if "Timeout" not in type(exc).__name__ and "Timeout" not in str(exc):
                    raise
                # Not a challenge: the page is simply slow. Keep going and let
                # the caller see what is on screen.
            challenge = await self.detect_challenge()
            if challenge:
                self.last_state = {
                    **self.last_state,
                    "url": self._page.url if self._page else url,
                    "title": challenge.get("title") or "Human verification",
                    "challenge": challenge,
                }
            return await self.capture()

    async def click(self, selector: str) -> dict:
        async with self._lock:
            await self.ensure()
            try:
                await self._page.click(selector, timeout=8000)
            except Exception as exc:
                if "Execution context was destroyed" in str(exc):
                    await self._page.goto("about:blank")
                raise
            # Wait for page to settle after click instead of fixed sleep.
            try:
                await self._page.wait_for_load_state("domcontentloaded", timeout=5000)
            except Exception:
                pass
            return await self.capture()

    async def click_at(self, x: int, y: int) -> dict:
        """Click at viewport coordinates (CSS px, 1:1 with the screenshot)."""
        async with self._lock:
            await self.ensure()
            try:
                await self._page.mouse.click(int(x), int(y))
                # Wait for page to settle after click instead of fixed sleep.
                try:
                    await self._page.wait_for_load_state("domcontentloaded", timeout=5000)
                except Exception:
                    pass
            except Exception:
                raise
            return await self.capture()

    async def type_text(self, selector: str, text: str, submit: bool = False) -> dict:
        async with self._lock:
            await self.ensure()
            await self._page.fill(selector, text)
            if submit:
                await self._page.press(selector, "Enter")
            # Wait for page to settle after submit instead of fixed sleep.
            try:
                await self._page.wait_for_load_state("domcontentloaded", timeout=5000)
            except Exception:
                pass
            return await self.capture()

    async def keyboard_type(self, text: str) -> dict:
        async with self._lock:
            await self.ensure()
            await self._page.keyboard.type(text)
            # Let the input event propagate instead of a fixed sleep.
            try:
                await self._page.wait_for_load_state("domcontentloaded", timeout=3000)
            except Exception:
                pass
            return await self.capture()

    async def press(self, key: str) -> dict:
        async with self._lock:
            await self.ensure()
            await self._page.keyboard.press(key)
            # Let the key event propagate instead of a fixed sleep.
            try:
                await self._page.wait_for_load_state("domcontentloaded", timeout=3000)
            except Exception:
                pass
            return await self.capture()

    async def select(self, selector: str, value: str) -> dict:
        async with self._lock:
            await self.ensure()
            await self._page.select_option(selector, value)
            # Let the change event propagate instead of a fixed sleep.
            try:
                await self._page.wait_for_load_state("domcontentloaded", timeout=3000)
            except Exception:
                pass
            return await self.capture()

    async def wait_for(self, selector: str | None, text: str | None, timeout: int = 20000) -> dict:
        async with self._lock:
            await self.ensure()
            if selector:
                await self._page.wait_for_selector(selector, timeout=timeout)
            if text:
                await self._page.wait_for_function(
                    "t => document.body.innerText.includes(t)", arg=text, timeout=timeout
                )
            return await self.capture()

    async def scroll(self, delta_y: int = 600, delta_x: int = 0) -> dict:
        async with self._lock:
            await self.ensure()
            await self._page.mouse.wheel(int(delta_x), int(delta_y))
            # Let the scroll settle instead of a fixed sleep.
            try:
                await self._page.wait_for_load_state("domcontentloaded", timeout=3000)
            except Exception:
                pass
            return await self.capture()

    async def back(self) -> dict:
        async with self._lock:
            await self.ensure()
            await self._page.go_back()
            return await self.capture()

    async def forward(self) -> dict:
        async with self._lock:
            await self.ensure()
            await self._page.go_forward()
            return await self.capture()

    async def reload(self) -> dict:
        async with self._lock:
            await self.ensure()
            await self._page.reload()
            return await self.capture()

    async def links(self, limit: int = 80) -> str:
        async with self._lock:
            await self.ensure()
            items = await self._page.eval_on_selector_all(
                "a",
                """(nodes) => nodes.slice(0, 200).map(a => ({text: (a.innerText || '').trim().slice(0, 120), href: a.href})).filter(x => x.href)""",
            )
            lines = [f"- {item['text'] or '(no text)'} -> {item['href']}" for item in items[:limit]]
            return "\n".join(lines) or "(no links found)"

    async def elements(self, limit: int = 60, annotate: bool = False) -> dict:
        """Index visible interactive elements (browser-pilot style).

        Each element gets a stable ``data-adk-idx`` / ``data-pilot-id`` so the
        agent can click/type by index. Includes href, placeholder, checked,
        expanded, disabled and offscreen for precise targeting.
        """
        async with self._lock:
            await self.ensure()
            from .browser_snapshot import PILOT_ELEMENTS_JS
            items = await self._page.evaluate(PILOT_ELEMENTS_JS, limit)
            self._elements = items
            if annotate:
                await self._page.evaluate(
                    """() => {
                      document.querySelectorAll('[data-adk-mark]').forEach(n => n.remove());
                      document.querySelectorAll('[data-adk-idx]').forEach(el => {
                        const r = el.getBoundingClientRect();
                        const badge = document.createElement('div');
                        badge.setAttribute('data-adk-mark', '1');
                        badge.textContent = el.getAttribute('data-adk-idx');
                        badge.style.cssText = `position:fixed;left:${Math.max(0,r.x)}px;top:${Math.max(0,r.y)}px;z-index:2147483647;background:#ff3b30;color:#fff;font:700 11px/14px monospace;padding:1px 4px;border-radius:3px;pointer-events:none;`;
                        document.body.appendChild(badge);
                      });
                    }"""
                )
            payload = await self.capture()
            if annotate:
                await self._page.evaluate("() => document.querySelectorAll('[data-adk-mark]').forEach(n => n.remove())")
            def _label(item):
                base = item.get('name') or item.get('text') or '(no label)'
                extra = []
                if item.get('placeholder'): extra.append(f"ph={item['placeholder']}")
                if item.get('checked') is not None: extra.append(f"checked={item['checked']}")
                if item.get('expanded'): extra.append(f"expanded={item['expanded']}")
                if item.get('disabled'): extra.append("disabled")
                if item.get('offscreen'): extra.append("offscreen")
                suffix = f" [{', '.join(extra)}]" if extra else ""
                return f"[{item['index']}] {item.get('tag')}{'(' + item.get('type') + ')' if item.get('type') else ''}: {base}{suffix}"
            summary = chr(10).join(_label(item) for item in items) or "(no interactive elements found)"
            return {"elements": items, "summary": summary, "frame": payload["frame"], "state": payload["state"]}

    async def click_element(self, index: int) -> dict:
        async with self._lock:
            await self.ensure()
            selector = f'[data-adk-idx="{int(index)}"]'
            try:
                await self._page.wait_for_selector(selector, timeout=5000, state="visible")
            except Exception:
                pass
            try:
                try:
                    await self._page.locator(selector).first.scroll_into_view_if_needed(timeout=4000)
                except Exception:
                    pass
                await self._page.click(selector, timeout=8000)
            except Exception as exc:
                try:
                    await self._page.locator(selector).first.click(force=True, timeout=8000)
                except Exception:
                    item = next((e for e in getattr(self, "_elements", []) if e.get("index") == int(index) or e.get("id") == int(index)), None)
                    if not item:
                        self.last_error = f"Element {index} is no longer on the page. Re-read the element list."
                        raise RuntimeError(self.last_error)
                    try:
                        await self._page.mouse.click(item["x"] + item["w"] // 2, item["y"] + item["h"] // 2)
                    except Exception as exc2:
                        self.last_error = str(exc2)[:220]
                        raise
            try:
                await self._page.wait_for_load_state("domcontentloaded", timeout=5000)
            except Exception:
                pass
            return await self.capture()

    async def type_element(self, index: int, text: str, submit: bool = False) -> dict:
        async with self._lock:
            await self.ensure()
            selector = f'[data-adk-idx="{int(index)}"]'
            try:
                await self._page.wait_for_selector(selector, timeout=5000, state="visible")
            except Exception:
                pass
            try:
                await self._page.locator(selector).first.scroll_into_view_if_needed(timeout=4000)
            except Exception:
                pass
            # browser-pilot: empty first so existing content is replaced cleanly
            try:
                await self._page.fill(selector, "")
            except Exception:
                pass
            await self._page.fill(selector, text)
            if submit:
                await self._page.press(selector, "Enter")
            try:
                await self._page.wait_for_load_state("domcontentloaded", timeout=5000)
            except Exception:
                pass
            return await self.capture()

    async def save_pdf(self, filename: str = "page.pdf") -> str:
        async with self._lock:
            await self.ensure()
            from pathlib import Path
            from ..config import DATA_DIR
            target = Path(filename)
            if not target.is_absolute():
                uploads = DATA_DIR / "uploads"
                uploads.mkdir(parents=True, exist_ok=True)
                target = uploads / target.name
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
            await self._page.pdf(path=str(target), format="A4", print_background=True)
            return str(target)

    async def extract_tables(self, max_tables: int = 5) -> str:
        async with self._lock:
            await self.ensure()
            tables = await self._page.eval_on_selector_all(
                "table",
                """(nodes) => nodes.slice(0, %d).map(t => Array.from(t.querySelectorAll('tr')).map(tr => Array.from(tr.querySelectorAll('th,td')).map(c => (c.innerText||'').replace(/\\s+/g,' ').trim())).filter(r => r.some(Boolean)))""" % max_tables,
            )
            if not tables:
                return "(no tables found on page)"
            out = []
            for idx, rows in enumerate(tables):
                if not rows:
                    continue
                out.append(f"Table {idx+1} ({len(rows)} rows):")
                header = rows[0]
                out.append("| " + " | ".join(header) + " |")
                out.append("| " + " | ".join("---" for _ in header) + " |")
                for row in rows[1:]:
                    out.append("| " + " | ".join(cell.replace('|', '\\|') for cell in row) + " |")
                out.append("")
            return "\n".join(out) or "(no tables found on page)"

    async def read_text(self, limit: int = 20_000) -> str:
        async with self._lock:
            await self.ensure()
            try:
                text = await self._page.inner_text("body")
            except Exception as exc:
                return f"Could not read the page: {exc}"
            title = await self._page.title()
            url = self._page.url
            return f"URL: {url}\nTitle: {title}\n\n{text[:limit]}"

    async def describe(self) -> str:
        payload = await self.capture()
        state = payload["state"]
        try:
            scroll_y = await self._page.evaluate("Math.round(window.scrollY)")
            scroll_h = await self._page.evaluate("Math.max(document.documentElement.scrollHeight, document.body ? document.body.scrollHeight : 0)")
            viewport_h = await self._page.evaluate("window.innerHeight")
        except Exception:
            scroll_y, scroll_h, viewport_h = 0, 0, 0
        extra = ""
        if getattr(self, "last_error", ""):
            extra += f" Previous error: {self.last_error}"
        return (
            f"Current page: {state['url']} (title: {state['title'] or 'untitled'}, "
            f"scroll {scroll_y}/{scroll_h}, viewport {viewport_h}). "
            "A screenshot is shown in the browser panel." + extra
        )


browser = BrowserManager()
