import asyncio
import time
import uuid
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import automations, earnings, skills, skills_import
from .agent import AgentRunner
from .db import create_session, init_db
from .diagnostics import agentdesk_log
from .engine import llama_local
from .mcp_manager import mcp_manager
from . import autoload
from .routes import (
    approvals_route,
    automations_route,
    backup_route,
    brain_route,
    browser_route,
    browser_bidi_route,
    browser_sdk_route,
    chat,
    computer_route,
    diagnostics_route,
    earnings_route,
    gateway_route,
    extensions_route,
    memory_route,
    missions_route,
    models_route,
    openrouter_route,
    pet_route,
    provider_health_route,
    mcp_server_route,
    brain_vector_route,
    automations_nl_route,
    skills_evolution_route,
    competitions_route,
    funds_route,
    downloads_route,
    sessions,
    settings_route,
    sandbox_route,
    terminal_route,
    uploads_route,
    worker_route,
    workspace,
)
from .security import LocalAccessMiddleware
from .terminal import terminal_manager
from .tools.browser import browser
from .watchdog import Watchdog

watchdog = Watchdog()


async def _automation_send(_payload: dict) -> None:
    return None


async def _automation_scheduler(stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            jobs = automations.due_automations(limit=1)
        except Exception as exc:
            agentdesk_log("error", "automation.scheduler.poll_failed", error=str(exc)[:400])
            await asyncio.sleep(10)
            continue
        if jobs:
            job = jobs[0]
            if job.get("status") != "active":
                await asyncio.sleep(1)
                continue
            # Idempotency: generate a unique run_key and claim the run atomically.
            # If another process already claimed this run, skip it to avoid duplicates.
            # Use uuid4 to avoid `int(time.time()*1000)` collisions when two
            # schedulers pick adjacent millisecond timestamps.
            run_key = f"auto-{job['id']}-{uuid.uuid4().hex}"
            if not automations.claim_run(job["id"], run_key):
                await asyncio.sleep(1)
                continue
            session = create_session(title=f"Automation: {job['name']}", workspace=job.get("workspace"))
            runner = AgentRunner(session["id"], _automation_send, interactive=False)
            started = time.time()
            agentdesk_log("info", "automation.start", job_id=job["id"], name=job.get("name"), run_key=run_key)
            try:
                await runner.start(job["prompt"], "auto")
                if runner._task:
                    await runner._task
                result = {
                    "status": runner.outcome,
                    "summary": f"Automation '{job['name']}' ran in session {session['id']}.",
                }
            except asyncio.CancelledError:
                result = {"status": "cancelled", "summary": "AgentDesk shut down during the task."}
                agentdesk_log("warn", "automation.cancelled", job_id=job["id"], run_key=run_key)
                raise
            except Exception as exc:
                result = {"status": "failed", "summary": str(exc)[:500]}
                agentdesk_log("error", "automation.failed", job_id=job["id"], run_key=run_key, error=str(exc)[:400])
            finally:
                seconds = round(time.time() - started, 1)
                automations.complete_run(run_key, result.get("status", "completed"), result.get("summary", ""), seconds)
                automations.mark_run(job["id"], {**result, "seconds": seconds})
                agentdesk_log("info", "automation.end", job_id=job["id"], run_key=run_key, status=result.get("status"), seconds=seconds)
        await asyncio.sleep(10)


async def _earnings_scheduler(stop: asyncio.Event) -> None:
    _radar_interval = 6 * 3600  # refresh live radar every 6 hours
    _last_radar: float = 0.0
    # Do not run blocking draft generation while FastAPI is still completing
    # startup: it would stall the event loop before the API port is bound.
    await asyncio.sleep(5)
    while not stop.is_set():
        try:
            await asyncio.to_thread(earnings.autopilot_tick)
        except Exception as exc:
            agentdesk_log("error", "earnings.autopilot_tick.failed", error=str(exc)[:400])
        # Periodic live radar refresh using default queries
        now = time.time()
        if now - _last_radar >= _radar_interval:
            try:
                await earnings.radar(query="remote freelance automation AI 2026 earn online")
                _last_radar = time.time()
            except Exception as exc:
                agentdesk_log("error", "earnings.radar.failed", error=str(exc)[:400])
        await asyncio.sleep(300)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    automations.migrate_legacy_json()
    # Built-in scheduled jobs (daily expert briefing + periodic self-check).
    with suppress(Exception):
        for job in automations.seed_scheduled_jobs():
            agentdesk_log("info", "automation.seeded", id=job.get("id"), name=job.get("name"))
    from . import learning as _learning
    _learning.init_db()
    earnings.init()
    skills.seed_starter_skills()
    # Bundled skill packs (OpenHands / deepagents / GenAgent, all MIT) are
    # installed once on first run and never overwrite user edits afterwards.
    with suppress(Exception):
        seeded = skills_import.seed_bundled_skills()
        for item in seeded.get("imported", []):
            agentdesk_log("info", "skills.seeded", name=item.get("name"), source=item.get("source"))
    # Phase 2 + 4 boot automation: discover MCP/skill packs + index Downloads.
    with suppress(Exception):
        mcp_added = autoload.apply_mcp_servers()
        if mcp_added.get("added"):
            agentdesk_log("info", "mcp.discovered", added=mcp_added["added"])
    with suppress(Exception):
        from . import downloads_ingest as _dl
        await asyncio.to_thread(_dl.scan)
    agentdesk_log("info", "app.start", version=app.version)
    # Start the always-on local llama.cpp model server (non-fatal - the cloud
    # gateways still work; the local route retries via `ensure()` when needed).
    # Do not time out the load: cancelling mid-start used to leave a half-loaded
    # server that the next chat would kill and respawn (30-60s stalls).
    async def warm_local_model():
        with suppress(Exception):
            await llama_local.ensure()

    model_task = asyncio.create_task(warm_local_model())

    async def warm_browser():
        # When the DevTools port is enabled, start Chromium eagerly so external
        # C++/C#/JS clients can attach immediately after launch.
        with suppress(Exception):
            from .config import load_settings as _load_settings
            if int(_load_settings().get("browser_cdp_port", 0) or 0) > 0:
                await browser.ensure()

    browser_task = asyncio.create_task(warm_browser())
    await mcp_manager.start()
    automation_stop = asyncio.Event()
    automation_task = asyncio.create_task(_automation_scheduler(automation_stop))
    earnings_stop = asyncio.Event()
    earnings_task = asyncio.create_task(_earnings_scheduler(earnings_stop))
    from .tools.observer import start_observer, stop_observer
    start_observer()
    await watchdog.start()
    try:
        yield
    finally:
        stop_observer()
        automation_stop.set()
        earnings_stop.set()
        for task in (automation_task, earnings_task, model_task, browser_task):
            task.cancel()
        await asyncio.gather(automation_task, earnings_task, model_task, browser_task, return_exceptions=True)
        await watchdog.stop()
        await mcp_manager.shutdown()
        terminal_manager.close_all()
        await browser.close()
        await llama_local.stop()


app = FastAPI(title="AgentDesk", version="0.7.0", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(LocalAccessMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["null", "http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(gateway_route.router, prefix="/v1", tags=["integration"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
app.include_router(workspace.router, prefix="/api/workspace", tags=["workspace"])
app.include_router(settings_route.router, prefix="/api/settings", tags=["settings"])
app.include_router(diagnostics_route.router, prefix="/api/diagnostics", tags=["diagnostics"])
app.include_router(browser_route.router, prefix="/api/browser", tags=["browser"])
# Language-neutral browser control plane (REST/WS + WebDriver BiDi).
app.include_router(browser_sdk_route.router, prefix="/api/browser/sdk", tags=["browser-sdk"])
app.include_router(browser_bidi_route.router, prefix="/api/browser/bidi", tags=["browser-bidi"])
app.include_router(computer_route.router, prefix="/api/computer", tags=["computer"])
app.include_router(extensions_route.router, prefix="/api/extensions", tags=["extensions"])
app.include_router(openrouter_route.router, prefix="/api/openrouter", tags=["openrouter"])
app.include_router(provider_health_route.router, prefix="/api/provider-health", tags=["provider-health"])
app.include_router(uploads_route.router, prefix="/api/uploads", tags=["uploads"])
app.include_router(chat.router)
app.include_router(automations_route.router, prefix="/api/automations", tags=["automations"])
app.include_router(terminal_route.router)
app.include_router(memory_route.router, prefix="/api/memory", tags=["memory"])
app.include_router(models_route.router, prefix="/api/models", tags=["models"])
app.include_router(missions_route.router, prefix="/api/missions", tags=["missions"])
app.include_router(sandbox_route.router, prefix="/api/sandbox", tags=["sandbox"])
app.include_router(worker_route.router, prefix="/api/workers", tags=["workers"])
app.include_router(brain_route.router, prefix="/api/brain", tags=["brain"])
app.include_router(approvals_route.router, prefix="/api/approvals", tags=["approvals"])
app.include_router(backup_route.router, prefix="/api/backup", tags=["backup"])
app.include_router(earnings_route.router, prefix="/api/earnings", tags=["earnings"])
app.include_router(pet_route.router, prefix="/api/pet", tags=["pet"])
app.include_router(mcp_server_route.router, prefix="/api/mcp-server", tags=["mcp-server"])
app.include_router(brain_vector_route.router, prefix="/api/brain", tags=["brain-vector"])
app.include_router(automations_nl_route.router, prefix="/api/automations", tags=["automations-nl"])
app.include_router(skills_evolution_route.router, prefix="/api/extensions/skills/evolution", tags=["skills-evolution"])
app.include_router(competitions_route.router, prefix="/api/competitions", tags=["competitions"])
app.include_router(funds_route.router, prefix="/api/earnings-plus", tags=["funds"])
app.include_router(downloads_route.router, prefix="/api/downloads", tags=["downloads"])


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "version": app.version}
