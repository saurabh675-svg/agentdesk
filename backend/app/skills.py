import re
from pathlib import Path

import httpx
import yaml

from .config import DATA_DIR

SKILLS_DIR = DATA_DIR / "skills"
SKILLS_DIR.mkdir(parents=True, exist_ok=True)


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:60] or "skill"


def parse_skill(text: str) -> tuple[dict, str]:
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            try:
                meta = yaml.safe_load(parts[1]) or {}
                return meta if isinstance(meta, dict) else {}, parts[2].strip()
            except yaml.YAMLError:
                pass
    return {}, text.strip()


_SKILLS_CACHE: dict = {"mtime": None, "skills": []}


def _skills_cache_key():
    try:
        latest = max(
            ((f / "SKILL.md").stat().st_mtime for f in SKILLS_DIR.iterdir() if (f / "SKILL.md").exists()),
            default=0.0,
        )
        return latest
    except OSError:
        return None


def validate_skill(name: str, description: str, body: str) -> list[str]:
    errors = []
    if not (name or "").strip():
        errors.append("name is required")
    elif len(name.strip()) > 80:
        errors.append("name must be <= 80 characters")
    if not (description or "").strip():
        errors.append("description is required")
    elif len(description.strip()) > 500:
        errors.append("description must be <= 500 characters")
    if len(body or "") < 10:
        errors.append("body must be at least 10 characters")
    if len(body or "") > 200_000:
        errors.append("body must be <= 200000 characters")
    return errors


def list_skills() -> list[dict]:
    key = _skills_cache_key()
    if _SKILLS_CACHE["mtime"] == key and _SKILLS_CACHE["skills"]:
        return list(_SKILLS_CACHE["skills"])
    skills = []
    for folder in sorted(SKILLS_DIR.iterdir()):
        skill_file = folder / "SKILL.md"
        if not skill_file.is_file():
            continue
        text = skill_file.read_text(encoding="utf-8", errors="replace")
        meta, body = parse_skill(text)
        first_line = body.splitlines()[0] if body else ""
        skills.append(
            {
                "name": str(meta.get("name") or folder.name),
                "description": str(meta.get("description") or first_line),
                "slug": folder.name,
                "source": str(meta.get("source") or "local"),
                "size": len(text),
            }
        )
    _SKILLS_CACHE["mtime"] = key
    _SKILLS_CACHE["skills"] = skills
    return skills


def get_skill(name: str) -> str:
    slug = slugify(name)
    skill_file = SKILLS_DIR / slug / "SKILL.md"
    if not skill_file.is_file():
        for folder in SKILLS_DIR.iterdir():
            candidate = folder / "SKILL.md"
            if candidate.is_file() and folder.name.lower() == slug:
                skill_file = candidate
                break
        else:
            matches = [s for s in list_skills() if slugify(s["name"]) == slug]
            if not matches:
                raise ValueError(f"Skill not found: {name}")
            skill_file = SKILLS_DIR / matches[0]["slug"] / "SKILL.md"
    return skill_file.read_text(encoding="utf-8", errors="replace")


def save_skill(name: str, description: str, body: str, source: str = "local") -> dict:
    _errors = validate_skill(name, description, body)
    if _errors:
        raise ValueError("; ".join(_errors))
    slug = slugify(name)
    folder = SKILLS_DIR / slug
    folder.mkdir(parents=True, exist_ok=True)
    text = (
        f"---\nname: {slug}\ndescription: {description.strip()}\nsource: {source}\n---\n\n"
        f"{body.strip()}\n"
    )
    (folder / "SKILL.md").write_text(text, encoding="utf-8")
    return {"name": slug, "description": description, "slug": slug, "source": source}


def delete_skill(slug: str) -> None:
    import shutil

    folder = SKILLS_DIR / slugify(slug)
    if folder.is_dir():
        shutil.rmtree(folder)


STARTER_SKILLS = {
    "web-research": (
        "Research a question on the web and produce a cited answer.",
        """# Web research

Use this skill when the user asks for current information, comparisons, prices, news, or
anything that may have changed recently.

1. Start with `browser_navigate` to a search engine (for example `https://duckduckgo.com/?q=...`).
2. Use `browser_read` and `browser_links` to inspect results, then open the most authoritative
   sources with `browser_navigate`.
3. Prefer primary sources: official docs, release notes, vendor pages, standards.
4. Note the publication date and distinguish facts from opinion.
5. If a page is long, use `browser_read` and `browser_scroll`.
6. Answer with Markdown and a short **Sources** list containing the URLs you actually visited.
7. If sources disagree, say so explicitly instead of averaging them.

Never invent a URL. Only cite pages that appeared in the browser during this task.
""",
    ),
    "verify-changes": (
        "Build and test changes before reporting success.",
        """# Verify changes

Use this skill whenever you edit code.

1. Inspect the project manifest (`package.json`, `pyproject.toml`, `requirements.txt`, etc.) to
   find the real test and build commands.
2. Make the smallest change that solves the problem; keep the surrounding style.
3. Run the targeted test first, then the broader suite or build.
4. If a command needs approval, ask for it once with the exact command.
5. Read the actual error output. Do not claim success without a passing run.
6. Report: files changed, commands run, and their results. If something could not be verified,
   say exactly what is unverified and why.
""",
    ),
    "desktop-automation": (
        "Safely drive native Windows apps with screenshots and mouse/keyboard control.",
        """# Desktop automation

Use this skill only when the task cannot be done with files, shell commands, or the browser.

1. Call `computer_screenshot` first and look at the visible screen.
2. Describe the target coordinates relative to the screenshot before clicking.
3. Prefer keyboard shortcuts (`computer_hotkey`) over pixel clicks when possible.
4. After each click or hotkey, take a screenshot and verify the expected change.
5. Keep actions reversible. Never confirm dialogs that delete data, purchase anything, or change
   system security settings without explicit user confirmation.
6. If the screen is locked or the app is not visible, stop and tell the user.
""",
    ),
    "windows-power-automate": (
        "Run Microsoft Power Automate Desktop flows headlessly via PAD.Console.Host.exe or ms-powerautomate:// protocol",
        """# Windows Power Automate

Use this skill to invoke Microsoft Power Automate Desktop (PAD) flows programmatically.

1. Locate PAD.Console.Host.exe (typically under %LOCALAPPDATA%\\Microsoft\\Power Automate Desktop\\).
2. Invoke a flow headlessly: `PAD.Console.Host.exe /flow "FlowName"` or via the protocol `ms-powerautomate://run?flow=FlowName`.
3. Capture stdout/stderr to detect success or failure.
4. For flows requiring input variables, pass them as `/input key=value` arguments.
5. Report the flow result or any error codes returned.
""",
    ),
    "cline-diff-engineering": (
        "Delegate precise code diff and editing tasks to Cline CLI v3+ with --auto-approve and --json flags",
        """# Cline Diff Engineering

Use this skill to delegate precise code edits to Cline CLI v3+.

1. Ensure Cline CLI is installed and in PATH (`cline --version`).
2. Formulate a precise, unambiguous task description targeting specific files and line ranges.
3. Invoke: `cline --auto-approve --json "<task description>"`.
4. Parse the JSON output to verify which files were changed.
5. Run tests after the edit to confirm correctness.
6. If Cline is unavailable, fall back to direct file edits using read/write tools.
""",
    ),
    "openhands-swe-bench": (
        "Launch OpenHands in Docker for sandboxed software engineering tasks with full filesystem access",
        """# OpenHands SWE-Bench

Use this skill to run complex software engineering tasks inside an OpenHands Docker sandbox.

1. Ensure Docker Desktop is running.
2. Pull the latest OpenHands image: `docker pull ghcr.io/all-hands-ai/openhands:latest`.
3. Mount the workspace: `docker run --rm -v <workspace>:/workspace ghcr.io/all-hands-ai/openhands:latest`.
4. Pass the task description as an environment variable or stdin.
5. Capture the container output for results, diffs, and test outcomes.
6. Copy modified files back to the host workspace if needed.
""",
    ),
    "stealth-web-operations": (
        "Use Playwright stealth and rotating user-agents for web operations that bypass basic bot detection",
        """# Stealth Web Operations

Use this skill for web scraping or automation on sites with basic bot detection.

1. Install playwright-stealth if not present: `pip install playwright-stealth`.
2. Use `async_playwright` with stealth plugin applied before navigation.
3. Rotate user-agent strings from a curated list of real browser UAs.
4. Add random delays between actions (100–800 ms) to mimic human behaviour.
5. Avoid obvious bot signals: disable webdriver flag, spoof navigator properties.
6. For heavy anti-bot sites, prefer residential proxies or fall back to manual instructions.
7. Never violate a site's Terms of Service; confirm with the user if uncertain.
""",
    ),
    "self-healing-troubleshooting": (
        "Automatically diagnose ModuleNotFoundError and missing CLI errors, then install via pip or winget",
        """# Self-Healing Troubleshooting

Use this skill when a command fails with ModuleNotFoundError or a missing CLI tool error.

1. Parse the error message to extract the missing module or command name.
2. For Python modules: run `pip install <module>` (or `pip install --user <module>`).
3. For CLI tools on Windows: try `winget install <tool>` or `scoop install <tool>`.
4. After installation, re-run the original command to confirm the fix.
5. If installation requires admin rights, inform the user with the exact command to run elevated.
6. Log each fix attempt and its outcome for the session report.
""",
    ),
    "windows-task-scheduler": (
        "Schedule and manage persistent background Windows tasks via schtasks.exe that run headlessly",
        """# Windows Task Scheduler Automation

Use this skill to create and manage background cron jobs or daily routines that persist on Windows even when AgentDesk is closed.

1. Use `windows_schtask(action='create', task_name='DailyBrief', schedule='DAILY', time='09:00')`.
2. To inspect active jobs: call `windows_schtask(action='list')`.
3. To trigger immediate headless execution: call `windows_schtask(action='run', task_name='DailyBrief')`.
4. To clean up: call `windows_schtask(action='delete', task_name='DailyBrief')`.
5. Scheduled jobs run with HIGHEST privilege to guarantee execution without prompting.
""",
    ),
}


def seed_starter_skills() -> None:
    """Create a few built-in skills on first run without overwriting user edits."""
    for slug, (description, body) in STARTER_SKILLS.items():
        folder = SKILLS_DIR / slug
        if folder.exists():
            continue
        save_skill(slug, description, body, source="builtin")


def install_from_url(url: str) -> dict:
    url = url.strip()
    if url.startswith("https://github.com/") and "/blob/" in url:
        url = url.replace("https://github.com/", "https://raw.githubusercontent.com/").replace(
            "/blob/", "/"
        )
    response = httpx.get(url, follow_redirects=True, timeout=45)
    response.raise_for_status()
    text = response.text
    meta, body = parse_skill(text)
    if not body:
        raise ValueError("The URL did not return a skill document")
    name = str(meta.get("name") or url.rstrip("/").split("/")[-1].replace(".md", ""))
    description = str(meta.get("description") or body.splitlines()[0])
    return save_skill(name, description, body, source=url)
