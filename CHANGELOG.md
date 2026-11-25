## Unreleased (0.5.0-dev)

### Added
- **Context compaction** (`backend/app/agent_context.py`): the agent no longer
  drops the middle of a long conversation. Old tool outputs are evicted into
  stubs and the middle is summarized by the running provider (deepagents-style,
  MIT, ported without LangChain). A context-length error from a provider now
  compacts hard and retries instead of failing the turn. Measured on a
  62-message history: 37 684 -> 5 695 estimated tokens.
- **Sub-agents** (`backend/app/subagent_profiles.py`, tool `spawn_agent`):
  five profiles - `general-purpose`, `researcher`, `code-reviewer`,
  `test-runner`, `doc-writer` - each with its own prompt, step budget and
  restricted tool set. Children are stateless and only their final report
  returns to the parent; they reuse the parent's tool dispatcher, so policy,
  approvals and telemetry apply. `run_many()` runs them in parallel.
- **Skill pack import** (`backend/app/skills_import.py`): import skills from a
  folder or straight from a `.zip` archive - OpenHands, deepagents and
  GenAgent packs work as-is. New endpoints `GET /api/extensions/skills/scan`,
  `POST /api/extensions/skills/import` and `GET /api/extensions/skills/bundled`;
  Settings -> Skills gained an "Import a skill pack" panel with Scan/Import.
- **Bundled skill packs**: 14 MIT-licensed skills (252 KB) from OpenHands,
  deepagents and GenAgent, seeded on first run with their licence files and
  never overwriting user edits.
- `docs/OSS_INTEGRATIONS.md` records every upstream project, licence and what
  was ported.

### Fixed
- **Real Chrome now starts.** `chromium_sandbox=True` was preventing Chrome
  from launching on Windows; the browser launcher tries variants in order
  (channel -> executable -> bundled Chromium) and records why each one failed
  instead of failing silently.
- **Human-verification pages no longer time out.** A Cloudflare/Turnstile
  challenge never fires a load event, so navigation used to die with a
  timeout. The page is now inspected and reported as
  `HUMAN_VERIFICATION_REQUIRED`; the agent stops retrying and waits for a human,
  and the Right pane shows a "Human verification required" banner with a
  "Show me" button.
- Optional undetected drivers: `patchright` is available (Apache-2.0) as an
  opt-in; real Chrome + Playwright stays the default because it works.

### Changed
- API contract regenerated: 113 operations (was 103); `docs/openapi.json`,
  `sdk-ts/generated/client.ts` and `sdk-py/generated/client.py` regenerated.
- New module `backend/app/agent_context.py` and `backend/app/subagent_profiles.py`;
  `backend/app/subagents.py` keeps the existing background-agent pool and
  re-exports the profile helpers.

# AgentDesk — Changelog

All notable changes to AgentDesk are recorded here. Versions follow
[Semantic Versioning](https://semver.org/) loosely (Patcher-level bumps for fixes,
Minor for safely backwards-compatible improvements).

## [Unreleased]

### Added (one-by-one pass, 2026-11-24)
- Electron: window-bounds persistence, backend-log CTA, port probe, configurable hotkey, quit/restart/log preload API
- Agent: browser_pdf/browser_extract/apply_diff, session rewind, health-weighted routing, retry backoff, scope-bound approvals
- Security: rate limiting, settings validation, structured shell output, typed SafePathError, skills validation/cache
- MCP: 10 new presets + env scrub; Earnings CSV import; missions/plans/brain enhancements
- Frontend: diagnostics-driven engine pills + health dot, settings search/test/reset/effective preview, approvals filter, Earn chart, Copy message, LocalModels delete lock
- SDK: typed errors, retry/timeout, version, extended CompletionOptions; Packaging: NSIS ia32, portable/zip, CI, pre-commit
- Docs: HANDOFF_0.4.0.md fresh snapshot

### Added
- `GET /api/diagnostics` — redacted health snapshot (providers, local model
  backend, browser, MCP, watchdog errors, automation backlog, brain index).
- `backend/app/diagnostics.py` — structured JSON event log at
  `data/diagnostics.jsonl` (`agentdesk_log(level, event, **fields)`).
- Opt-in SQLite + FTS5 brain index (`AGENTDESK_BRAIN_SQLITE=1`) with backfill
  and full-text `search_brain_notes()`.
- `CHANGELOG.md`, `SECURITY.md`, `docs/UPDATES.md`.

### Changed
- Automation run keys use a UUID suffix instead of millisecond timestamps, so
  two schedulers can no longer collide.
- README endpoint table and `MODIFYING.md` `asar` wording corrected.

### Fixed
- App shell render errors show a recoverable panel instead of a blank window.
- Sidebar file filter expands matching folders and reports empty results.
- Screen-reader labels on icon-only chat, tool and sidebar controls.

## [0.4.0] — 2026-11-23

### Routing
- **Saved** mode uses exactly the configured provider/model.
- **Auto** mode (replaces **Hard**) tries saved-key cloud gateways → bundled
  local **llama.cpp** (Vulkan when available, CPU fallback) → signed-in
  ChatGPT/Gemini browser tab, in that order. Local is time-boxed (12 s).
- Settings → Model → Auto route exposes a per-gateway toggle and override.

### Local models
- Curated GGUF catalog in **Settings → Local Models** with one-click download,
  activate, delete. Custom GGUF URLs accepted.
- Backend endpoints: `GET /api/models`, `/api/models/download`,
  `/api/models/activate`, `/api/models/status`,
  `GET/POST /api/models/backend`, `DELETE /api/models/{name}`.
- Models stored in `%APPDATA%\AgentDesk\data\models`.
- New **Inference backend** selector: `Auto (Vulkan if available) | Vulkan |
  CPU`. Default backend key was `local_backend` — now persisted and overridable.

### Browser
- New **Set-of-Marks** tools (`browser_elements`, `browser_click_element`,
  `browser_type_element`) make reliable self-clicking possible.
- Built-in browser prefers installed **Google Chrome** when available and hides
  automation flags; `data\backend.log` and `/api/browser/state` report the
  active engine.
- Browser pane synchronises active tab when an agent tool that touches the
  browser begins.

### Desktop
- `computer_elements` enumerates accessible controls of the foreground window.
- `windows_uia_click` clicks a named control via UIA InvokePattern with
  coordinate fallback. Approvals still required.

### MCP
- New presets: **Brave Search**, **Tavily**, **Time**, **Git**.
- Auth-gated servers (Drive, Notion, AskUI, Sentry) now surface a typed
  `needs_setup` hint with the exact missing env var instead of a raw `error`.

### Multi-agent
- Settings → Agents lets the user create named profiles. The active one
  overlays provider/model/base_url/key for new chats.

### Fixes
- Watchdog loopback health check no longer goes through a system proxy.
- llama.cpp auth key is persisted in `data\llama.key` so a restarted backend
  keeps talking to the still-running local model.
- Bundled GGUFs are protected from accidental deletion in the Models tab.
- Plain greetings (`hi`, `hello`, `thanks`) no longer trigger tool calls.
- Composer stops hiding behind Stop while a run is active (a Send button
  remains visible to queue the next message).
- Earn ventures resolve a real site URL from the platform when the catalog
  entry has none.

### Security
- The bundled runtime's persisted token is now rotatable per session.
- Approvals remain required for shell, desktop, `ask_chatbot`, and any
  browser session that requires sign-in.

## [0.3.1] — 2026-11-22

### Highlights
- Electron 45.4.1 packaged installer; per-user NSIS setup; `asar` disabled for
  post-install edits.
- Always-on local llama.cpp server on `127.0.0.1:11435` using the bundled
  `Qwen2.5-1.5B-Instruct` Q4_K_M GGUF.
- Agentic chat with `Saved`, `Hard`, `ChatGPT`, `Gemini` modes; per-gateway
  saved API keys; persistent Chromium profile for ChatGPT/Gemini sign-in.
- Skills system (docx, pptx, xlsx, pdf, …) installed from URL or written in
  Settings.
- MCP presets: Fetch, Drive, GitHub, Sentry, Notion, AskUI, Playwright,
  Filesystem, Memory, Sequential Thinking.
- Earnings engine: opportunity radar, 30-day venture plans, draft-only
  autopilot, income ledger, lessons log.
- Local Python and TypeScript SDKs against the `/v1/*` integration API.

## [0.3.0] — 2026-11-19

- First public release after the private 0.1 / 0.2 series.
- Three-panel workspace + chat + browser / desktop / terminal / files UI.
- Firecrawl (`web_search`) with DuckDuckGo fallback.
- Approval flow for shell + desktop + `ask_chatbot`.
- Per-session SQLite storage.

## [Unreleased] — ongoing

### Added in this session (2026-11-24)
- New docs: `CHANGELOG.md`, `SECURITY.md`, `docs/UPDATES.md`,
  `docs/ai-engineering-roadmap-2026.md` (replaces the stale
  `roadmap.txt` at root).
- Backend `diagnostics.py`: structured logger + `GET /api/diagnostics`
  (redacted) health snapshot.
- Backend `main.py`: automation `run_key` now uses `uuid.uuid4().hex` to
  avoid collision when the scheduler fires faster than `ms` granularity.
- Brain: SQLite+FTS5 shadow index alongside the existing JSON file (read
  compatibility preserved, new schema is opt-in via env var).
- Frontend `App.tsx`: class-based `ErrorBoundary` wraps the whole render
  tree so an exception in any pane shows one recovery screen instead of
  going blank.
- Frontend `Sidebar.tsx`: file-tree quick-filter input.
- Frontend `ChatPane.tsx`: aria-labels on icon-only buttons (Export,
  Settings), `<header role="banner">`, `aria-live="polite"` region around
  the route banner.
- README endpoint table now matches `main.py`'s mounted routers.
- `MODIFYING.md`: removed the "older unpacked builds" caveat (asar is
  disabled in every shipped 0.3+ build).

### Planned / still TODO
See `docs/UPDATES.md` for the immediate list and
`AGENTDESK_UPGRADE_PLAN.md` for the long-running roadmap.

### Fixed (2026-11-25 bug-fix pass)
- Chat pane: tool cards no longer collapse to a 1.6px hairline (the "blank
  lines"). `.messages` is a column flex container, so children were being
  shrunk to their minimum; `.messages > *` now sets `flex-shrink: 0`, which
  also restores full-height assistant replies.
- Windows shell: POSIX-style pipes (`| head -60`, `| grep -n`, `| cat`, `| ls`,
  `| sed -n '2p'`) now work — new `backend/app/tools/unixshim.py` provides them
  as `.cmd` shims on the child's PATH. Previously these failed and exhausted
  the step budget.
- Agent loop: repeated identical tool calls are short-circuited instead of
  re-running; system prompt now documents the Windows shell, the workspace
  boundary and the no-repeat rule. `max_steps` default 24 → 32.

### Added (multi-language browser control plane, 2026-11-25)
- `GET/POST /api/browser/sdk/*` — language-neutral REST control plane for the
  shared browser: `info`, `tabs`, `navigate`, `act`, `snapshot`, `screenshot`,
  plus a WebSocket event stream.
- `ws://127.0.0.1:8756/api/browser/bidi/ws` — WebDriver BiDi façade
  (`session.*`, `browsingContext.*`, `script.*`, `input.performActions`) for
  Selenium 4, Playwright for .NET and Playwright for Java.
- Chrome DevTools Protocol endpoint on `127.0.0.1:<browser_cdp_port>`
  (default 9333, `0` disables) — C++, C#, JS, Go and Rust clients attach to the
  *same* browser, cookies and sign-ins included.
- New browser input verbs: double-click, hover, drag, scroll-to-element,
  file upload, horizontal scroll.
- Stable per-user SDK token (`data/browser-sdk.token`) so external clients
  authenticate without restarting the app.
- `examples/browser/` — C++ (raw CDP), C# (BiDi), JavaScript (Puppeteer +
  zero-dependency REST) clients with README.
- Settings → Browser → DevTools/CDP port toggle.

### Fixed (0.4.0 reinstall pass)
- Settings → Model → "Reset to defaults" now resets `max_steps` to 32
  (the backend default) instead of the stale 24.
- The installed `AgentDesk.exe` and `Uninstall AgentDesk.exe` carry the
  `CN=AgentDesk Local` signature.

### Documentation
- `docs/NEXT_UPGRADES_CUTTING_EDGE.md` — roadmap for the next four releases with
  a polyglot architecture: Python keeps the agent/product spine, Rust provides
  in-process accelerators (PyO3), C++ provides the native CDP driver, C#/.NET the
  Windows-native sidecar (UIA3, ConPTY), TypeScript the surface and SDK layer.
  Includes the interop contract, a 30-row upgrade matrix, release plan with
  acceptance criteria, risks, and the free/open-source-only stack.

## 0.5.0-dev — polyglot upgrades, fluid UI, the expert pet

### New
- **DeskPet Expert** (`backend/app/pet_expert.py`, `GET/POST /api/pet/expert*`):
  a generalist companion that answers using three channels — live web search
  (DuckDuckGo/Firecrawl), the local knowledge database (brain FTS, skills,
  sessions, workspace files) and **MCP skills** (tools from connected servers,
  callable on request). Answers carry numbered source citations and report which
  channels were used.
- **Floating pet** (`frontend/src/components/FloatingPet.tsx`): the companion
  now drifts over the app, is draggable, blinks, reacts to your focus, and
  opens an expert panel with the compose box, capability badges and sources.
- **Fluid design system**: clamp()-based fluid type scale, spacing and radii,
  motion primitives (`riseIn`/`fadeIn`/`popIn`/`shimmer`), global transitions
  and a `prefers-reduced-motion` guard.
- **Scheduled jobs** seeded on every start: *Daily DeskPet briefing* (24 h) and
  *AgentDesk self-check* (6 h) — the latter verifies the browser control
  plane, CDP, the pet expert and MCP servers.
- **API contract**: `docs/openapi.json` (OpenAPI 3.1, 103 operations) exported
  from the live app, with generated clients in `sdk-ts/generated/client.ts` and
  `sdk-py/generated/client.py` (`python scripts/export_openapi.py`).
- **Telemetry**: `backend/app/telemetry.py` — OTLP-shaped spans plus a
  Prometheus endpoint at `GET /api/diagnostics/metrics` and `/api/diagnostics/spans`.
- **Rust native core** (`native/agentdesk_core`): PyO3 extension with DOM diff,
  content-addressed refs, secret scrubbing and token counting, plus pure
  Python fallbacks and `scripts/bench_native.py`.
- **C++ CDP helper** (`native/cdp_helper`): dependency-free Winsock WebSocket +
  CDP client (C++23) that drives the same browser from native code.
- **C#/.NET 9 Windows sidecar** (`native/AgentDesk.Win`): UIA3 tree walking,
  clipboard, window enumeration and a real ConPTY terminal over a named pipe.
- **`scripts/dev-setup.ps1` / `scripts/dev-env.ps1`**: install Rust, llvm-mingw
  and .NET 9 into `.toolchains/` without admin rights.
- CI matrix now builds Python, Node, Rust, C++ and .NET, and fails on API
  contract drift.

### Changed
- Tool output is scrubbed for secrets/PII before it reaches the model context.
- The app now installs per-user by default, so updates no longer need admin.

### Added (2026-11-25 batch 2)
- **Browser-pilot page tools**: `browser_snapshot`, `browser_find_by_text`, `browser_fill_form`, `browser_extract_text`, `browser_structured_extract`, `browser_scroll_to_element` — snapshot with scroll/a11y fields, batch form fill, structured JSON extract, settle + scrollIntoView + force fallback, previous_error surfacing.
- **Rubric verify-loop** (`backend/app/agent_rubric.py`): deepagents-style grader checks the transcript before finishing; `satisfied/needs_revision/failed` with per-criterion gaps, frozen criteria, coverage retry, revision injection (max 2). Tool `verify_work` + Settings toggle + `rubric_evaluation` UI banner.
- **Gateway failover** (GenAgent-style): live `/models` discovery with 1h cache, `pick_models()` preferences, per-model fallback on 404/empty, error classification + sanitised notices, health/cooldown-aware Auto routing.


## [0.7.0] - 2026-11-25

### Added
- **0.6 engine layer:** `BrowserEngine` protocol + `CdpNativeEngine` (wraps `cdp_helper.exe`, falls back to Playwright), AgentDesk-as-MCP-server (`POST /api/mcp-server/call`, stdio via `python -m app.mcp_server`), hybrid brain search (`GET /api/brain/search/hybrid` — FTS5 + dense with optional sqlite-vec/FastEmbed), DuckDB analytics with SQLite fallback, eval harness (`scripts/run_evals.py` — 5/5 pass), Rust `agentdeskctl` CLI.
- **0.7 grounding:** Set-of-Marks (`browser_set_of_marks` tool), local VLM tier (`vlm_tier.py` — honest "not installed" when no Qwen2.5-VL/LLaVA), winget/scoop manifests, full `en/es/hi` i18n, telemetry waterfall state + `content-visibility` perf CSS, a11y gate (`scripts/a11y_check.mjs`).
- **Hermas (MIT) port:** NL schedules (`schedule_nl.py`, `POST /api/automations/nl`, `schedule_create_nl` tool), skill evolution gate (`skills_evolution.py`, `skill_propose`/`skill_approve`/`skill_rollback`, evolution routes).
- **Agent split step 1:** `SYSTEM_PROMPT` → `agent_prompts.py`, `TOOL_SCHEMAS` → `agent_schemas.py`; `agent.py` 3,531 → 2,337 lines. Rust core micro-opt (FNV-1a hash, no child-clone) — bench 1.18× / 1.38× / 1.58×.
- **Account shortcut fixed:** `openapi.json` regenerated — **122 operations** (was 113).

### Changed
- Version 0.4.0 → **0.7.0** across `package.json`, `backend/app/main.py`, diagnostics, telemetry, SDK route, Rust crates and manifests.

### Follow-up (same 0.7.0 line)
- **Agent split step 2:** `AgentRunner` → `agent_runner.py`; `agent.py` is now a **15-line facade** (acceptance <900 LOC met). `agent.py` + `agent_runner.py` import-identical (89 tools verified).
- **MCP 2.x HTTP/SSE transport:** `mcp_manager.py` now supports `url`-configured servers (Streamable HTTP + SSE with env→header mapping); stdio unchanged.
- **Vector stack installed:** `sqlite-vec 0.1.9`, `duckdb 2.0.1`, `fastembed 0.9.1` + `onnxruntime` via `uv pip`. FastEmbed model download is blocked by the sandbox HF cache, so `brain_vector` uses the hash-embed fallback (384-dim, hybrid search verified); DuckDB is live with SQLite fallback.
- **Telemetry waterfall UI + i18n:** span bars under the engine bar, `en/es/hi` locale switch in Settings (Sidebar “New chat” wired).
- **Hermas tools wired to the agent:** `schedule_create_nl`, `skill_propose`, `skill_approve`, `skill_rollback` added as first-class tools.
- **A11y gate green:** 8 icon-only buttons labelled, `scripts/a11y_check.mjs` → 0 critical. `agentdeskctl` (Rust) `cargo check` passes.
