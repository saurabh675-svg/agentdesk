"""Browser driver layer: pluggable, anti-detection aware.

AgentDesk can drive the browser through several open-source drivers:

============  ======================================================  ========
driver        upstream project                                            licence
============  ======================================================  ========
``patchright`` patched Playwright (drops the CDP Runtime leak)          Apache-2.0
``playwright`` the reference driver                                       Apache-2.0
``camoufox``   anti-detect Firefox (real C++ engine, no automation API)  MIT
============  ======================================================  ========

``camoufox`` is optional and needs its own engine download; ``patchright`` is
a drop-in replacement for Playwright and is what most users want.

Whatever the driver, AgentDesk always launches **real Chrome** with a real
user profile, hides the automation fingerprint and keeps the window available
for sign-ins. When a site still shows a human check, the browser layer
detects it, brings the window forward and asks the user to complete it — the
challenge is never "solved" automatically, which is both the honest and the
legal behaviour.
"""

from __future__ import annotations

from typing import Any

# Chrome flags that reduce the automation fingerprint.
ANTI_DETECT_ARGS: tuple[str, ...] = (
    "--disable-blink-features=AutomationControlled",
    # NOTE: never pass --disable-features here. Chrome only honours the last
    # occurrence, so it would silently replace the driver's own feature list
    # and the browser fails to start.
    "--disable-infobars",
    "--no-default-browser-check",
    "--no-first-run",
    "--password-store=basic",
    "--use-mock-keychain",
)

# Injected before any page script runs: removes the obvious automation tells.
STEALTH_SCRIPT = r"""
(() => {
  const patch = (obj, prop, value) => {
    try {
      Object.defineProperty(obj, prop, { get: () => value, configurable: true });
    } catch (e) {}
  };

  // navigator.webdriver
  patch(Navigator.prototype, 'webdriver', undefined);

  // Permissions API: mask the notification/clipboard state changes that
  // headless browsers report differently.
  try {
    const originalQuery = navigator.permissions?.query;
    if (originalQuery) {
      navigator.permissions.query = (params) =>
        params && params.name === 'notifications'
          ? Promise.resolve({ state: Notification.permission, onchange: null })
          : originalQuery.call(navigator.permissions, params);
    }
  } catch (e) {}

  // window.chrome runtime
  try {
    if (!window.chrome) {
      window.chrome = { runtime: {}, app: { isInstalled: false }, csi: () => {}, loadTimes: () => {} };
    }
    if (!window.chrome.runtime) {
      window.chrome.runtime = { id: undefined, connect: () => {}, sendMessage: () => {} };
    }
  } catch (e) {}

  // Languages
  try {
    Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'], configurable: true });
  } catch (e) {}

  // Plugins (headless Chrome exposes none)
  try {
    const makePlugin = (name, filename, description) => {
      const plugin = Object.create(Plugin.prototype);
      Object.defineProperties(plugin, {
        name: { value: name }, filename: { value: filename },
        description: { value: description }, length: { value: 1 },
      });
      return plugin;
    };
    const plugins = [
      makePlugin('PDF Viewer', 'internal-pdf-viewer', 'Portable Document Format'),
      makePlugin('Chrome PDF Viewer', 'internal-pdf-viewer', 'Portable Document Format'),
      makePlugin('Chromium PDF Viewer', 'internal-pdf-viewer', 'Portable Document Format'),
    ];
    Object.defineProperty(navigator, 'plugins', { get: () => plugins, configurable: true });
  } catch (e) {}

  // WebGL vendor strings
  try {
    const getParameter = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function (parameter) {
      if (parameter === 37445) return 'Intel Inc.';
      if (parameter === 37446) return 'Intel Iris OpenGL Engine';
      return getParameter.apply(this, [parameter]);
    };
  } catch (e) {}

  // Ignore the automation flag on the command line
  try {
    if (navigator.getUserAgentData) {
      const original = navigator.getUserAgentData.bind(navigator);
      navigator.getUserAgentData = () => {
        const data = original();
        return { ...data, brands: data.brands.filter((b) => !/Chromium/i.test(b.brand)) };
      };
    }
  } catch (e) {}
})();
"""


def _vendor_path() -> str:
    """Vendored third-party drivers (shipped inside the app)."""
    import sys
    from pathlib import Path

    vendor = Path(__file__).resolve().parents[1] / "vendor"
    if vendor.exists() and str(vendor) not in sys.path:
        sys.path.insert(0, str(vendor))
    return str(vendor)


def _try_import_patchright() -> Any | None:
    try:
        from patchright.async_api import async_playwright  # type: ignore

        return async_playwright
    except Exception:
        pass
    # Not installed system-wide: try the copy vendored inside the app.
    try:
        _vendor_path()
        from patchright.async_api import async_playwright  # type: ignore

        return async_playwright
    except Exception:
        return None


def _try_import_playwright() -> Any | None:
    try:
        from playwright.async_api import async_playwright  # type: ignore

        return async_playwright
    except Exception:
        return None


def _patchright_browser_present() -> bool:
    """Patchright needs its own patched Chromium build, not just the package."""
    try:
        import os
        from pathlib import Path

        roots = [
            Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "")),
            Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright",
        ]
        for root in roots:
            if not root or not root.exists():
                continue
            for folder in root.glob("chromium-*"):
                if "headless_shell" in folder.name:
                    continue
                if (folder / "chrome-win32" / "chrome.exe").exists() or (folder / "chrome-win64" / "chrome.exe").exists():
                    return True
    except Exception:
        pass
    return False


def available_drivers() -> list[dict]:
    """Which drivers are importable right now."""
    drivers = [
        {
            "id": "playwright",
            "label": "Playwright + real Chrome",
            "available": _try_import_playwright() is not None,
            "note": "default: real Chrome, real profile, headed",
        },
        {
            "id": "patchright",
            "label": "Patchright (undetected Chromium)",
            "available": _try_import_patchright() is not None and _patchright_browser_present(),
            "note": "optional: needs its own patched browser (scripts/setup-browser.ps1)",
        },
    ]
    try:
        import camoufox  # type: ignore  # noqa: F401

        drivers.append({"id": "camoufox", "label": "Camoufox (anti-detect Firefox)", "available": True})
    except Exception:
        drivers.append({"id": "camoufox", "label": "Camoufox (anti-detect Firefox)", "available": False})
    for driver in drivers:
        driver["license"] = {"playwright": "Apache-2.0", "patchright": "Apache-2.0", "camoufox": "MIT"}[driver["id"]]
    return drivers


def resolve(preference: str = "auto") -> tuple[Any, str]:
    """Return ``(async_playwright_factory, driver_id)`` for the preferred driver.

    ``auto`` prefers patchright (fewer bot checks) and falls back to the
    bundled Playwright. A missing optional driver is never fatal.
    """
    preference = (preference or "auto").strip().lower()
    if preference in ("auto", "playwright"):
        # Playwright + real Chrome is the reliable default: the browser is the
        # user's own, with their profile, logins and a visible window.
        factory = _try_import_playwright()
        if factory is not None:
            return factory, "playwright"
        if preference == "playwright":
            preference = "auto"
    if preference == "patchright":
        factory = _try_import_patchright()
        if factory is not None:
            return factory, "patchright"
        preference = "auto"
    factory = _try_import_patchright()
    if factory is not None and _patchright_browser_present():
        return factory, "patchright"
    factory = _try_import_playwright()
    if factory is not None:
        return factory, "playwright"
    if factory is None:
        factory = _try_import_patchright()
        if factory is not None:
            return factory, "patchright"
    raise RuntimeError(
        "No browser driver available. Install Playwright or Patchright "
        "(python -m pip install patchright) and the bundled Chromium."
    )


def chrome_executable() -> str:
    """Path to a real Chrome install (real Chrome is far less suspicious)."""
    import os
    from pathlib import Path

    candidates = [
        os.environ.get("AGENTDESK_CHROME_PATH", ""),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        str(Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return ""
