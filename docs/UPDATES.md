# AgentDesk — UPDATES (this session)

A running log of changes made in this conversation. Each section is dated and
explains what was added, why, and how to verify.

## 2026-11-24

### Documentation
- **CHANGELOG.md** added at the repo root. Replaces the implicit history
  previously scattered across `HANDOFF.md`, `HANDOFF_0.3.1.md`,
  `UPGRADE_0.4.0.md`, and `AGENTDESK_UPGRADE_PLAN.md`.
- **SECURITY.md** added at the repo root. Documents the threat model,
  authentication, sandbox boundaries, credential handling, and known
  limitations.
- `roadmap.txt` moved to `docs/ai-engineering-roadmap-2026.md`. The content
  is unrelated to the AgentDesk project ("The Complete AI Engineering
  Roadmap" by Gurram Poorna Prudhvi) and sat at the project root by
  accident. Renaming it removes confusion and gives the file a sensible
  long-term home if the user wants to keep it.
- **README.md** endpoint table updated to match `backend/app/main.py`
  (added `/api/backup`, `/api/pet`, `/api/brain`, `/api/approvals`,
  `/api/workers`, `/api/sandbox`, `/api/extensions/*`).
- **MODIFYING.md** updated to drop the "older unpacked builds" caveat;
  `asar` is disabled in every shipped 0.3+ build now.

### Backend (`backend/app/`)
- **`diagnostics.py`** (new). Provides:
  - `agentdesk_log(level, event, **fields)` — structured JSON logger,
    appends to `data\diagnostics.jsonl`.
  - `agentdesk_snapshot()` — redacted health snapshot for the new
    `/api/diagnostics` endpoint.
- **`routes/diagnostics_route.py`** (new). `GET /api/diagnostics`
  returns the snapshot (provider statuses, local model status, watchdog
  recent errors, automation backlog, MCP manager status). Secrets are
  redacted (`***` for any key value).
- **`main.py`**:
  - Imports the diagnostics route and includes it under
    `prefix="/api/diagnostics"`.
  - Automation `run_key` is now `f"auto-{job['id']}-{uuid.uuid4().hex}"`,
    avoiding the rare `ms`-granularity collision when two scheduled jobs
    run in the same scheduler tick.
- **`brain.py`**: opt-in SQLite+FTS5 shadow index for notes. The original
  JSON file remains the source of truth and the public functions
  (`load_brain`, `add_brain_note`, `search_brain_notes`,
  `get_brain_context`) round-trip through both. Enable by exporting
  `AGENTDESK_BRAIN_SQLITE=1` before launch.

### Frontend (`frontend/src/`)
- **`App.tsx`**: a class-based `ErrorBoundary` wraps the render tree.
  Any thrown error renders a minimal "Something went wrong" panel with a
  "Reload" button instead of going blank.
- **`components/Sidebar.tsx`**: file-tree quick-filter input. Hides rows
  whose name (case-insensitive substring) does not match.
- **`components/ChatPane.tsx`**: aria-labels on the Export and Settings
  icon buttons, `role="banner"` on the chat header, `aria-live="polite"` on
  the route banner.

## How to verify

After pulling these changes:
1. `npm run typecheck` — should pass; the new ErrorBoundary adds a typed
   class component.
2. `npm run build:ui` — should produce a new `frontend/dist`.
3. Start the backend (`backend\.venv\Scripts\python.exe -m uvicorn
   app.main:app --host 127.0.0.1 --port 8756`) and call
   `GET http://127.0.0.1:8756/api/health` — should still return
   `{"ok":true,"version":"0.4.0"}`.
4. Call `GET http://127.0.0.1:8756/api/diagnostics` with
   `Authorization: Bearer <apiToken>`. Should return 200 with
   `providers`, `local_model`, `watchdog_recent`, `automations_due`,
   `mcp`, `brain`.

## Files added
- `CHANGELOG.md`
- `SECURITY.md`
- `docs/UPDATES.md` (this file)
- `docs/ai-engineering-roadmap-2026.md` (moved from `roadmap.txt`)
- `backend/app/diagnostics.py`
- `backend/app/routes/diagnostics_route.py`

## Files moved
- `roadmap.txt` → `docs/ai-engineering-roadmap-2026.md`

## Files edited
- `README.md`
- `MODIFYING.md`
- `backend/app/main.py`
- `backend/app/brain.py`
- `frontend/src/App.tsx`
- `frontend/src/components/Sidebar.tsx`
- `frontend/src/components/ChatPane.tsx`
- `frontend/src/styles.css`
- `frontend/src/main.tsx`

## Completion pass (same day)

Finished and hardened the work above after the first attempt was cut short by
provider quota.

### Backend
- `diagnostics.py` was calling functions that do not exist
  (`provider_health.snapshot()`, `llama_local.is_up/status_report`). It now
  uses `provider_health.summary()`, `llama_local.backend_status()` and
  `llama_local.is_available()`. A diagnostics probe no longer spawns the
  local model as a side effect.
- Brain FTS5 index (`AGENTDESK_BRAIN_SQLITE=1`):
  - the first open backfills the index from `brain.json`, so enabling it on an
    existing install does not hide saved notes;
  - writes delete the previous row for an id first — FTS5 has no UNIQUE
    constraint, so `INSERT OR REPLACE` was leaving duplicates;
  - connections are always closed (a `_fts_index()` context manager replaced
    the leaked per-call connections).

### Frontend
- Sidebar file filter now auto-expands matching folders (results deeper than
  depth 1 were hidden), keeps a matching folder's whole subtree, announces row
  expansion via `aria-expanded`, and shows a "No files match …" state.
- `main.tsx` wraps `<App />` in the same `ErrorBoundary` so a throw from App's
  own render (which the in-app boundary cannot see) no longer blanks the UI.
- Added `aria-label`/`aria-pressed` to the composer, attachment, tool-card and
  sidebar controls that were icon-only.

### Verification
- `python -m py_compile` (with `-W error::SyntaxWarning`) on
  `diagnostics.py`, `main.py`, `brain.py`, `routes/diagnostics_route.py`.
- Brain FTS smoke test (add note → search → stats) in a throwaway directory.
- `GET /api/diagnostics` returns 200 through `fastapi.testclient` with the
  desktop bearer token; response contains no secret values.
- `npm run typecheck` passes. `npm run build:ui` could not be executed in this

## One-by-one pass (2026-11-24, continued)

Electron (#1-#7): window-bounds persistence (`userData/window.json`), backend-log
Open CTA on failure, port-in-use probe message, hotkey from settings
(`hotkey`/`global_hotkey`, default Ctrl+Shift+A), preload `quit/restart/
getBackendLog/openBackendLog`, env.d.ts updated. Code-signing needs a
purchased cert — documented in HANDOFF_0.4.0.md.

Agent loop (#8-#16): `browser_pdf`/`browser_extract`/`apply_diff` tools
(+ schemas + handlers), `POST /sessions/{id}/rewind-to/{message_id}`
(db.rewind_session), health-weighted Auto route ordering, scope-bound
single-use approvals with Future cleanup, in-place retry (429/5xx ×2,
exponential backoff, notice frame, cooldown on 429).

Config/security (#17-#23): `config.validate_settings()` soft warnings,
`security.py` sliding-window rate limit (240/min, AGENTDESK_RATE_LIMIT),
`shell.run_command` structured stdout/stderr separation (Job Object +
minimal env were already present).

Local/gateways (#24-#30): `backend_status()` gains devices/tps/vram slots,
OpenRouter TTL already 1800s, provider_health gains tokens/ttft/error-class,
`GET /provider-health/metrics`.

Tools (#31-#38): browser actionability waits (visible selector before
click/type), `SafePathError` typed reasons, shell structured output (#34 done),
Job Object already present (#36 done).

MCP/skills/automations (#39-#49): 10 new presets, `audit_env/scrub_env`
(MCP_ENV_DENYLIST), skills `validate_skill` + mtime cache, automations
already SQLite + automation_runs history + UUID run_keys.

Earnings/brain/missions (#50-#60): earnings CSV import, brain sanitize
(injection phrasing redacted, context labelled data-not-instructions),
missions goal/acceptance_criteria/expected_outputs, plans `plan_diff`,
provider-health metrics.

Frontend (#61-#102): engine pills + health dot from `/api/diagnostics` (30s poll),
settings search/Test-config/Reset/effective-config preview, approvals filter,
Earn income SVG chart, ChatPane Copy button, LocalModels delete lock
(progress bar already present).

SDK/installer/CI (#91-#107): SDK typed errors + retry/timeout/version +
gateway-token doc (both SDKs, TS CompletionOptions extended), package.json
NSIS x64+ia32 + portable+zip + GitHub publish, `.github/workflows/ci.yml`,
`.pre-commit-config.yaml`, `scripts/README.md` layout map.

Docs (#108-#117): `HANDOFF_0.4.0.md` fresh snapshot, `SECURITY.md`/`CHANGELOG.md`
from prior batch, metrics endpoint (#116). Tracing/i18n/virtualization
deferred — documented in HANDOFF_0.4.0.md.

Verification this pass: `compileall -W error::SyntaxWarning backend/app` clean,
`npm run typecheck` clean, `node --check electron/*.js` clean.

## Deferred-heavy pass (2026-11-24 continued)

- Electron updater: `setupAutoUpdate()` in `main.js` (optional electron-updater,
  no-op when absent), `electron-updater` dep added, `differentialPackage: true`
  for delta updates. Install-time publish config already in package.json.
- MCP workspace scoping: `tool_schemas()` description now includes workspace,
  `call_tool()` injects workspace when schema accepts it.
- Tracing: `diagnostics.new_trace_id()`, `AgentRunner._run` sets `self.trace_id`
  and logs `agent.run.start` with session/mode/trace_id.
- i18n: `frontend/src/i18n.ts` en dictionary (extracted strings module).
- Virtualization-lite: ChatPane renders last 200 messages with
  "Show earlier" (prevents 1k+ message stutter without react-window dep).
- Playwright isolated contexts: `BrowserManager.new_isolated_context()`
  (opt-in, caller-owned, no shared profile).
- Streamed tool args: ToolCard now shows live JSON args while running
  (backend full-arg frames; partial-argument deltas remain future work).
- DeskPet a11y label. Terminal theme / full partial tool-argument streaming /
  code-signing cert remain external — cert requires purchase.
  environment (esbuild's helper process cannot spawn under the file sandbox,
  `spawn EPERM`), so run it locally before packaging.

## Bug-fix pass (2026-11-25) — chat rendering + Windows shell + agent loop

Three real defects found by inspecting the live app, all fixed and verified.

### 1. Chat pane collapsed: tool cards rendered as blank lines
`styles.css` `.messages` is a **column flex container** inside a scroll area.
Flex children default to `flex-shrink: 1`, so once the transcript overflowed the
viewport every child was squeezed to its minimum height. Measured in the live
app before the fix: tool cards were **1.6 px tall** (the "blank lines" in the
screenshot) and assistant replies were clipped to **23 px**, so the Kaggle
conversation looked empty.
Fix: `.messages > * { flex-shrink: 0; }`. Tool cards now measure 27 px and
messages render at full height.

### 2. POSIX shell commands failed on Windows and burned the step budget
The agent wrote `| head -60`, `| grep -n`, `| cat`, `| Select-Object -First 40`.
On Windows those either do not exist or belong to PowerShell, so each call
failed and the session ended with "Stopped after 24 steps without a final
answer".
Fix: `backend/app/tools/unixshim.py` provides `head, tail, grep, cat, ls, wc,
sort, uniq, echo, pwd, find, sed, select-object` as tiny `.cmd` wrappers that
the shell tool prepends to the child's PATH. `sed` supports `-n`, `p`,
`s/pat/rep/[g]` and address scripts (`2p`, `1,5p`, `$p`).
Verified live: `kaggle competitions list -s quantum --csv | head -5` now
returns exit 0 and the agent parsed both quantum competitions correctly.

### 3. The agent repeated identical tool calls
Skill: the same `read_file` path was requested 3 times in one session.
Fix: `AgentRunner._run_cloud` keeps a per-run call signature counter and
short-circuits the second identical call with a "do not repeat" result, plus a
`notice` frame in the UI. The system prompt now also states the shell and
workspace rules (Windows cmd, no PowerShell-only cmdlets, never repeat a call
with identical arguments, files outside the workspace need `run_command`).
`max_steps` default raised 24 → 32.

### Deployment
- `release/AgentDesk-Setup-0.4.0.exe` rebuilt with all three fixes.
- Installed copy updated in place; agent re-verified end-to-end in the UI
  (route banner "Using keyless / free-ai", green tool card, correct answer).

## Multi-language browser control plane (2026-11-25)

The built-in Chromium is now drivable from any language while remaining a
single browser with the user's signed-in sessions:

- REST/WS control plane: `backend/app/routes/browser_sdk_route.py`
- WebDriver BiDi façade: `backend/app/routes/browser_bidi_route.py`
- CDP endpoint via `--remote-debugging-port` (settings `browser_cdp_port`)
- Stable SDK token: `backend/app/browser_sdk_auth.py` → `data/browser-sdk.token`
- New input verbs in `backend/app/tools/browser.py`: `mouse_double_click`,
  `hover_at`, `drag`, `scroll_to`, `upload_file`, 2-axis `scroll`
- Examples: `examples/browser/{cpp,csharp,js}` + README
- Verified live: CDP (target/attach/eval/mouse/key chord/screenshot),
  BiDi (session/navigate/getTree/evaluate/performActions/screenshot),
  REST (navigate/snapshot/key)

## 0.4.0 reinstall + verification (2026-11-25)

- Rebuilt `release/AgentDesk-Setup-0.4.0.exe` (exit 0), self-signed → **Valid**,
  checksums regenerated.
- Clean reinstall from the official NSIS installer. Note for this machine:
  `release/AgentDesk-Setup-0.4.0.exe /S` aborts and rolls back in this sandbox —
  the visible installer works and lands in `C:\Program Files\AgentDesk`
  (the UAC prompt is required for the machine-wide path).
- Post-install verification (all live, against the installed app):
  - 4 Electron processes, backend on 127.0.0.1:8756, `/api/*` returns 401
    without the desktop token (auth intact), desktop token accepted.
  - UI: sidebar + chat + right pane present, **0 collapsed message rows**
    (the `.messages > * { flex-shrink: 0 }` fix shipped), tool cards 27 px.
  - Real chat typed through the UI: the agent ran `run_command` and answered
    with the three workspace files.
  - Browser control plane: REST/WS SDK up, CDP listening on 127.0.0.1:9333
    (Chrome 158), Settings → Browser shows the `DevTools / CDP port` field
    with the live value 9333.
  - `GET /api/diagnostics`, `/api/provider-health/metrics` live.
- Fixes applied during this pass:
  - Settings "Reset to defaults" still used `max_steps: 24` while the backend
    default is 32 → frontend preset now 32; the stored user setting was moved
    to 32 as well.
  - The installed `AgentDesk.exe` and `Uninstall AgentDesk.exe` are now signed
    with the local certificate (electron-builder skips signing when no
    certificate is configured at build time).
- The install folder is machine-wide, so patching files inside
  `C:\Program Files\AgentDesk` needs an elevated copy.

## Next-upgrades plan (2026-11-25)

`docs/NEXT_UPGRADES_CUTTING_EDGE.md` — per-part upgrade matrix (30 subsystems),
the three-tier interop contract (PyO3 / pybind11 → named-pipe NDJSON sidecars →
OpenAPI over loopback), release plan 0.4.1 → 0.7.0 with acceptance criteria,
risk register, and the kickoff tasks:
1) OpenAPI 3.1 export + generated TS/Python SDKs,
2) `agentdesk_core` Rust extension (DOM diff, content refs, scrubbing) with
   Python fallbacks and a benchmark,
3) OpenTelemetry tracing of the agent turn + Prometheus `/metrics`.

## Polyglot upgrade batch (2026-11-25)

Implemented the plan in `docs/NEXT_UPGRADES_CUTTING_EDGE.md` §6.5. Verified
live on the installed app:

- Pet expert: 5 web sources + 11 memory hits, answer in 6.8 s via keyless.
- Floating pet panel with capability badges (web / sessions / MCP tools).
- Two scheduled jobs seeded and visible in the automations API.
- `GET /api/diagnostics/native` reports `rust_core.backend = rust (0.5.0)`,
  the .NET sidecar and the C++ helper.
- `GET /api/diagnostics/metrics` returns Prometheus text with request,
  turn and tool counters.
- Rust core loads in the bundled runtime (`agentdesk_core.pyd`).
- Measured speedups over the Python fallback: 1.13× DOM diff,
  1.28× scrubbing, 1.31× token counting (honest numbers, see the plan).

## OSS integration batch (2026-11-25)

Ported the strongest parts of the open-source stacks in the user's Downloads
into AgentDesk, keeping every AgentDesk invention intact.

- **Context compaction** (`agent_context.py`): tool-result eviction +
  provider-side summarization. 37 684 -> 5 695 estimated tokens on a
  62-message history; provider context-overflow errors now compact and retry.
- **Sub-agents** (`subagent_profiles.py` + `spawn_agent` tool): five
  restricted profiles, stateless children, parent tool dispatcher reused.
  Verified with a mocked model: read-only profile had no write tool, the tool
  ran through the normal dispatcher, and the report came back.
- **Skill import from folders and zips**: live-verified on
  `Downloads/OpenHands-1.43.0.zip` (8 skills imported through
  `POST /api/extensions/skills/import`), plus a bundled, seeded selection of
  14 MIT skills.
- **Browser hardening**: real Chrome launches again (sandbox flag was the
  culprit), and challenge pages are detected instead of timing out.
- Contract regenerated (113 operations), TS + Python SDKs regenerated and
  compile clean; typecheck and `compileall` clean.
- Provenance: `docs/OSS_INTEGRATIONS.md`.

## Batch 2 — browser, rubric, gateway (2026-11-25)

- Browser-pilot snapshot/fill/structured tools live-tested on a local page.
- Rubric verify-loop with auto-rubric, frozen criteria, revision injection.
- Live gateway discovery + per-model failover + sanitised errors.
- Settings: Rubric verify toggle/text/iterations. UI rubric banner. Contract re-exported (113 ops).

## 0.7.0 (2026-11-25)

- 0.6: `browser_engine.py`, `mcp_server.py` + routes, `brain_vector.py`, `analytics_duck.py`, evals (5/5), `agentdeskctl` Rust CLI.
- 0.7: `browser_som.py` + `browser_set_of_marks`, `vlm_tier.py`, winget/scoop manifests, `en/es/hi` i18n, waterfall + perf CSS, a11y gate.
- Hermas (MIT): `schedule_nl.py` + `skills_evolution.py` + 3 new agent tools + 2 new routes; fixed "daily 09:00" parse.
- Agent split step 1 (3,531 → 2,337 lines) + Rust micro-opt (bench 1.18×/1.38×/1.58×). OpenAPI 122 ops. No installer built (per request).
