# AgentDesk — Next Upgrades: Cutting-Edge, Polyglot, Python-Core

**Status:** plan (proposal) · **Author:** AgentDesk engineering · **Date:** 2026-11-25
**Scope:** every subsystem of AgentDesk 0.4.0 → next four releases (0.4.1 → 0.7.0)
**Constraint carried forward:** free/open-source only, Windows-first, Python stays the spine.

---

## 0. Why polyglot

You asked for *different programming languages to upgrade all parts, with Python*.
Here is the honest engineering framing of that request, because it decides everything
downstream:

> **Python owns the product. Other languages own the hot paths, the platform edges,
> and the surfaces where a user's team already lives.**

AgentDesk's differentiation is the agent loop, the tool surface, the local-first
routing, and the multi-language browser control plane. Those are orchestration
problems — Python is excellent at them. But three things in the current codebase
are structurally *not* Python jobs:

1. **Latency-sensitive extraction** (DOM snapshots, diffing, tokenization, log
   scrubbing) runs in the request path and blocks the event loop.
2. **Platform-native Windows work** (UI Automation, screen capture, clipboard,
   window enumeration) is awkward from Python and unmaintainable in C++.
3. **Client ergonomics** — a .NET team should not need a Python runtime to drive
   the same browser that the Python agent drives.

So the rule set for this plan:

| Rule | Meaning |
|---|---|
| **1 spine** | The agent loop, policy, tool registry, MCP manager, memory and the HTTP/WS surface stay in Python. No second "real" backend. |
| **2 accelerators** | Native code is allowed only behind a stable Python-callable boundary, and only for measurable hot paths (with a pure-Python fallback so the app never breaks if a native artifact is missing). |
| **3 façades** | Every subsystem that a user might drive from outside gets a first-class surface in the language that ecosystem uses: JS/TS for web, C# for .NET, C++ for native/perf, Python for everything else. |
| **4 one source of truth** | Contracts are defined once (OpenAPI / JSON Schema / protobuf-free plain JSON) and code for every language is *generated* from them, so drift is impossible. |
| **5 free only** | MIT/Apache/BSD/PostgreSQL-licensed tooling only. No paid services, no proprietary SDKs. |

### Measured starting point (this repo, today)

| Layer | Size | Stack today |
|---|---|---|
| Backend | 14,088 LOC Python | FastAPI 0.165, uvicorn 0.54, pydantic 2.14, mcp 2.3, playwright 1.65 |
| Agent core | 3,040 LOC in `agent.py` | monolithic loop + router + tool dispatch |
| Browser | 599 LOC | Playwright + CDP/BiDi/REST façades (0.4.0) |
| Electron shell | 466 LOC | Electron 45.4, electron-updater 6.8, electron-builder 26.18 |
| Frontend | 5,360 LOC TS/TSX | React 18.3, Vite 6, xterm 6, lucide |
| SDKs | 66 LOC Python / 64 LOC TS | hand-written, no generators |
| Packaging | 1.6 GB NSIS installer | bundled python-build-standalone runtime, llama.cpp Vulkan, Playwright |

---

## 1. Interop contract (the part that makes polyglot safe)

Three tiers, chosen by cost of failure:

```
                 ┌──────────────────────────────────────────┐
   TS/JS  ──┐    │  TypeScript client  (React UI, SDK)     │
   C#     ──┼──► │  ── HTTP/WS + OpenAPI 3.1 contract ──┐  │
   C++    ──┘    │  ══ local Rust core (accelerators) ══ │  │
   Python ──┐    │  ══ C++/C# sidecars (native edges)  ══ │  │
                 └──────────────────────────────────────────┘
```

| Tier | Mechanism | Used for | Failure mode |
|---|---|---|---|
| **In-process** | PyO3 (Rust), pybind11 (C++) | hot pure functions | `ImportError` → transparent Python fallback |
| **Sidecar** | Named pipe + newline-delimited JSON-RPC 2.0 | Windows-native UIA, native CDP, CLI | sidecar crash → Python re-spawns, tool returns a clear error |
| **Network** | HTTP/WS on 127.0.0.1 with OpenAPI | external SDKs (TS, C#, C++, Go…) | offline/404 → normal HTTP error |

**Versioning rules**
- Every sidecar handshake returns `{"protocol": "agentdesk.ipc/1", "version": "<app version>"}`.
- Contract changes are additive within a major; a breaking change requires the
  sidecar to expose `/capabilities` and the Python caller to degrade gracefully.
- All generated clients are checked in under `sdk-<lang>/` with a `generated` marker
  so nobody hand-edits them.

---

## 2. Upgrade matrix — every part, target technology, language

| # | Part | Today | Target (cutting edge) | Language | Phase |
|---|---|---|---|---|---|
| 1 | **Agent loop** | 3,040-line `agent.py` | Split into `AgentRunner` / `Planner` / `Policy` / `ToolRouter` / `LoopGuard`; **structured plan state machine**; OpenAI **Responses API** + Anthropic **prompt caching** support | Python | 0.5.0 |
| 2 | **Tool registry** | dict of python funcs | **Registry v2**: typed `ToolSpec` (JSON Schema from Pydantic), per-tool routing, budget class, cost model, **MCP elicitation** support | Python | 0.5.0 |
| 3 | **Browser engine** | Playwright wrapper | `BrowserEngine` **protocol** + **TabManager** + DOM diff store (structural, content-addressed) + **Set-of-Marks** grounding | Python | 0.4.1 |
| 4 | **Browser native driver** | Playwright | **own CDP client** over WebSocket: zero-copy frames, sub-ms input dispatch, binary screenshot pipe | **C++** | 0.5.0 |
| 5 | **DOM/DOM-diff hot path** | Python string diffing | Incremental **tree diff** + **content-addressed refs** (`ref:ab12`) + aha-style window | **Rust** (PyO3) | 0.5.0 |
| 6 | **Secrets / PII** | `encryption.py` + ad-hoc redaction | **Windows Credential Manager** (DPAPI) via `keyring`; **Presidio** PII detection in brain + tool output | Python | 0.5.0 |
| 7 | **LLM gateway** | hand-rolled OpenAI-compat | **OpenTelemetry** spans, adaptive **prompt-cache** keys, per-provider retry/budget policy, **Batch API** queue for offline tasks | Python | 0.5.0 |
| 8 | **Model routing** | health-weighted greedy | policy engine w/ **cost/quality/latency** objectives + **shadow routing** + eval-gated autotuning | Python | 0.6.0 |
| 9 | **Local inference** | llama.cpp Vulkan | keep Vulkan + add **speculative decoding**, **draft model**, **continuous batching**, **ONNX Runtime** for fast embeddings/rerank | Python + C++ (llama) | 0.5.0 |
| 10 | **Embeddings / rerank** | none | **FastEmbed** (ONNX) + **sqlite-vec** vector index in the brain; hybrid BM25 + dense retrieval | Python | 0.6.0 |
| 11 | **Data layer** | SQLite + FTS5 | SQLite **WAL** + **sqlite-vec** + **DuckDB** over Parquet for earnings/usage analytics | Python | 0.6.0 |
| 12 | **MCP client** | own manager (9 presets) | full MCP 2.x: tools+resources+prompts, **sampling**, **roots**, **elicitation**, OAuth 2.1 flow, **stdio + HTTP + SSE** | Python | 0.5.0 |
| 13 | **MCP server** (new) | none | publish AgentDesk's browser/tools as an MCP server (loopback + stdio), so any MCP client (Claude Desktop, Cline, Continue) drives it | Python | 0.6.0 |
| 14 | **Skills** | seeded skills + mtime cache | versioned skill packages, **semantic trigger matching**, sandboxed skill runner, marketplace-free local registry | Python | 0.6.0 |
| 15 | **Windows automation** | `windows_uia.py` (Python + pywinauto-ish) | **.NET 9 sidecar**: UIA3 tree walk, clipboard, window/DPI awareness, screen diff via Direct2D; **NativeAOT** published | **C#** | 0.6.0 |
| 16 | **Computer use** | `tools/computer.py` | perception→action loop with **Set-of-Marks** + local **VLM (Qwen2.5-VL)** tier, safety policy in the service layer | Python + **C++** (capture) | 0.6.0 |
| 17 | **Terminal** | xterm.js + py backend | PTY via **ConPTY** (no more fake pipes), 24-bit colour, **shell integration** (cwd/command detection), OSC 133 markers | **C#** sidecar + TS | 0.5.0 |
| 18 | **Scheduler** | asyncio loop + SQLite | durable scheduler with **cron/interval + event triggers**, missed-run policy, jitter, HA-safe claim | Python | 0.5.0 |
| 19 | **Workers** | `workers/` pool | **task queue** with leases, retries, tok/dist (tokio-like semantics in Python), **sandbox tiers** | Python | 0.5.0 |
| 20 | **Electron shell** | 466 LOC | slim main process, **native module addons** where needed, **auto-update with staged rollouts**, crash reporter (Sentry-free: minidump) | JS | 0.5.0 |
| 21 | **Frontend** | React 18 + Vite 6 + plain CSS | **React 19 + Vite 7 + TanStack Query v5 + Zustand + Tailwind v4**, streaming render with **React Server-ish suspense**, virtualised message list | TypeScript | 0.5.0 |
| 22 | **Frontend perf** | — | **OffscreenCanvas** charts, Web Workers for markdown/highlight, `content-visibility` on long lists | TypeScript | 0.6.0 |
| 23 | **Protocol layer** | ad-hoc | **OpenAPI 3.1** as single source → generated clients: **Python (datamodel-code-gen), TS (openapi-typescript), C# (NSwag), C++ (nlohmann + custom gen)** | all | 0.5.0 |
| 24 | **CLI** | none | `agentdeskctl` — headless control of sessions, runs, browser and MCP server | **Rust** | 0.6.0 |
| 25 | **Telemetry** | `diagnostics.jsonl` | **OpenTelemetry** OTLP traces + Prometheus `/metrics`, **OpenInference** semantic conventions, per-tool latency/cost dashboards | Python + Rust exporter | 0.5.0 |
| 26 | **Evals** | none | **eval harness**: golden trajectories, LLM-as-judge on the local model, deterministic **record/replay** of tool I/O, CI gate on regressions | Python | 0.6.0 |
| 27 | **Installer** | NSIS + portable + zip | keep NSIS; add **winget + Scoop** manifests, **MSIX** (signed, free via self-cert in dev), **delta updates** (blockmap), **post-install smoke test** | PowerShell | 0.5.0 |
| 28 | **Runtime/deps** | pinned requirements.txt | **uv** lock + `python-build-standalone` runtime, reproducible hashes, `pip-audit`, SBOM (CycloneDX) | Python | 0.5.0 |
| 29 | **CI** | ci.yml | matrix: Python/Node/**Rust/cargo**/**C++ (MSVC+clang-cl)**/**C# (dotnet)** builds + SBOM + eval gate on PRs | all | 0.5.0 |
| 30 | **Docs/i18n/a11y** | README + i18n.ts | versioned docs site (MkDocs), **a11y audit** (axe-core), full **i18n** (en/es/hi) with runtime switch | Python + TS | 0.6.0 |

**Language distribution of the target codebase (approx. lines of new code):**
Python ~55% · TypeScript ~25% · Rust ~10% · C++ ~6% · C# ~4%.
Python remains the majority *and* the control plane.

---

## 3. The interesting parts, in design detail

### 3.1 C++ — native browser driver (`agentdesk_native_cdp`)

Replaces the Playwright dependency **for driving**, not for parsing.

- **Why:** CDP frames are binary-friendly; a C++ client with libcurl (HTTP) +
  a WebSocket transport dispatches input in ~100 µs vs ~3 ms through the
  Python bridge, and can stream screenshots straight to the renderer.
- **Shape:** `cdp::Client` (async, libcurl multi), `cdp::Target`, `cdp::Input`,
  `cdp::DOM`, `cdp::Network`; exposed to Python through **pybind11** (in-process)
  and to other languages through the same **sidecar** protocol.
- **Must keep:** Playwright as the fallback and for anything Playwright does
  better (downloads, contexts). The engine interface hides the difference.
- **Build:** CMake + vcpkg, clang-cl on CI, `pybind11` stubs generated at build.

### 3.2 Rust — accelerators (`agentdesk_core`)

One extension module, several responsibilities, all pure functions with a
Python fallback:

| Function | Why Rust | Fallback |
|---|---|---|
| `dom.diff(old, new)` | tree diff on every snapshot; O(n) with structural hashing | Python `difflib` |
| `refs.build(content)` | content-addressed `ref:ab12` ids | Python sha256 |
| `scrub(text)` | regex/redaction on every tool output (hot) | Python `re` |
| `tokenize.count(text)` | token counting for budget checks | tiktoken |
| `blake3.hash(file)` | workspace hashing / skill cache | hashlib |

**Stack:** PyO3 + maturin, crates `simd-json`, `blake3`, `regex`, `zstd`,
`rayon` (parallel DOM processing). Builds in CI in ~3 minutes, ships as a
single `.pyd` in `extraResources`.

### 3.3 C# — Windows sidecar (`AgentDesk.Win`)

The Windows-native surfaces, in one .NET 9 process:

- **UIA3** tree walking (replaces the fragile parts of `windows_uia.py`)
- **ConPTY** terminal with true 24-bit colour and OSC 133 shell integration
- Clipboard, window enumeration, DPI awareness, screen capture + diffing
- **NativeAOT** publish → ~12 MB, no .NET runtime dependency for users
- Talks over **named pipe** `\\.\pipe\agentdesk.win` with NDJSON frames

### 3.4 TypeScript — the surface layer

- React 19 + Vite 7 + TanStack Query v5 (server-state) + Zustand (UI state)
- **Generated** API client from OpenAPI (`sdk-ts` becomes generated)
- Micro-frontends for the Browser/Terminal panes via `Module Federation`-lite
  (simple dynamic import + shared runtime contract)
- Web Worker for markdown/shading and for the OTel exporter batching

### 3.5 Python — the spine

- `agent.py` split into focused modules (the 3,040-line file is the biggest
  single risk in the codebase): `agent/runner.py`, `agent/planner.py`,
  `agent/policy.py`, `agent/tools.py`, `agent/context.py`
- **Planning**: explicit state machine — `PLAN → ACT → OBSERVE → REFLECT → ANSWER`
  with typed transitions, so the loop is inspectable and replayable
- **Policy** stays in code (not the prompt) — injection defence in the service layer
- Local model orchestration with speculative decoding + draft model
- MCP 2.x client **and** server
- OTel instrumentation everywhere, OpenInference attributes on LLM/agent spans

### 3.6 Data & retrieval

```
brain.jsonl ──▶ FastEmbed (ONNX) ──▶ sqlite-vec  ──┐
user/docs ───▶ BM25 (FTS5) ────────────────────────┼──▶ hybrid RAG ──▶ context
skills    ───▶ BM25 + trigger matching ─────────────┘
earnings  ───▶ DuckDB over Parquet ──▶ SQL analytics ──▶ charts
```

---

## 4. Release plan

| Release | Scope | Acceptance criteria |
|---|---|---|
| **0.4.1** | Browser Engine protocol, TabManager, tab strip, action ledger | multi-tab works; no behavioural regression in existing tools; relay/diff unit tests |
| **0.5.0** | Telemetry (OTel), API contracts (OpenAPI) + generated SDKs, agent split, Rust core v1, C# ConPTY terminal, MCP 2.x client | 100 % of `/api/*` documented in OpenAPI; clients generated in TS + Python; agent.py < 900 LOC; Rust diff 10× faster than Python fallback; trace waterfall visible per turn |
| **0.6.0** | C++ CDP driver behind the engine interface, MCP server, hybrid RAG + sqlite-vec, DuckDB analytics, eval harness, `agentdeskctl` (Rust) | C++ driver passes the same browser test-suite as Playwright; external MCP client can drive the signed-in browser; evals gate CI; p95 tool latency down ≥ 30 % |
| **0.7.0** | Windows sidecar (UIA3, screen perception), Set-of-Marks grounding + local VLM tier, MSIX/winget, full i18n, a11y clean | computer-use loop reliable on 20 reference tasks; a11y audit 0 critical; install/update fully unattended |

**Sequencing rule:** no phase starts before the previous phase's acceptance
criteria are met *and* the app installs and passes the smoke test — the pipeline
that broke twice is too valuable to disturb.

---

## 5. Risks & mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Native artifacts missing on a user's machine | app broken | every native call has a Python fallback; startup self-test logs which path is active |
| Polyglot complexity tax | slower velocity | strict interop tiers + generated contracts; language count capped at 5 |
| 1.6 GB installer keeps growing | install friction | sidecars are ~12–25 MB total; strip duplicate runtimes; move to on-demand model download |
| New language = new toolchain burden | contributor friction | one command (`scripts/dev-setup.ps1`) installs Rust/C++/C# toolchains; CI images pre-baked |
| Dev secret drift between languages | subtle bugs | one OpenAPI + one JSON Schema source; generated code only |
| Local-model regressions | slower answers | eval harness with golden trajectories gates every release |

---

## 6. Free/open-source stack (no paid services)

Rust (MIT) · CMake/Apache-2.0 · vcpkg (MIT) · pybind11 (BSD) · PyO3 (MIT/Apache) ·
maturin (MIT/Apache) · .NET 9 (MIT) · NativeAOT (MIT) · OpenTelemetry (Apache-2.0) ·
OpenInference (Apache-2.0) · sqlite-vec (MIT/Apache) · DuckDB (MIT) · FastEmbed (Apache-2.0) ·
ONNX Runtime (MIT) · Presidio (MIT) · llama.cpp (MIT) · Playwright (Apache-2.0) ·
MCP SDK (MIT) · uv (MIT/Apache) · OpenAPI Generator (Apache-2.0) ·
NSIS (zlib/libstdc++) · winget/Scoop manifests (free) · axe-core (MIT) ·
xterm.js (MIT) · React/TanStack/Zustand/Tailwind (MIT).

---

## 6.5 Status — what is actually built (2026-11-25)

Everything below was implemented, compiled and verified on this machine. The
numbers are measured, not projected.

| Item | Status | Evidence |
|---|---|---|
| **OpenAPI 3.1 export + generated SDKs** | **done** | `scripts/export_openapi.py` → `docs/openapi.json` (103 operations, 87 paths) + `sdk-ts/generated/client.ts` + `sdk-py/generated/client.py`; TS compiles clean, Python client calls the live API |
| **Telemetry + Prometheus** | **done** | `backend/app/telemetry.py` → `GET /api/diagnostics/metrics` (Prometheus text) and `/api/diagnostics/spans` (OTLP-shaped JSON); agent tool calls, turns and HTTP requests instrumented |
| **Rust native core (`agentdesk_core`)** | **done** | PyO3 extension built with cargo 1.100 (GNU target, static CRT) → `agentdesk_core.pyd`; loads in both the dev venv and the **bundled runtime**; `scripts/bench_native.py` proves parity with the Python fallback |
| **C++ CDP helper** | **done** | `native/cdp_helper/cdp_helper.cpp` — dependency-free Winsock WebSocket + CDP client, compiled with clang 23 (C++23); drives the live browser (evaluate, click, key, scroll, screenshot) |
| **C#/.NET 9 Windows sidecar** | **done** | `native/AgentDesk.Win` (.NET 9, published self-contained) — named pipe + stdio NDJSON transport, UIA3 tree walk, clipboard, window list, ConPTY terminal; Python client `backend/app/win_sidecar.py` verified live |
| **Pet expert (web + memory + MCP skills)** | **done** | `backend/app/pet_expert.py` → `/api/pet/expert` answered a live question with 5 web sources + 11 memory hits in 12.4 s through the keyless gateway |
| **Fluid type + motion system** | **done** | `frontend/src/styles.css` — clamp() fluid scale, motion primitives, `prefers-reduced-motion` guard |
| **Floating expert pet** | **done** | `frontend/src/components/FloatingPet.tsx` — draggable, wanders, blinks, expert panel with source citations |
| **Scheduled jobs** | **done** | `seed_scheduled_jobs()` seeds "Daily DeskPet briefing" (24 h) and "AgentDesk self-check" (6 h) on every start |
| **CI matrix** | **done** | `.github/workflows/ci.yml` — python / node / rust / c++ / dotnet / contract-drift jobs |
| **One-command toolchains** | **done** | `scripts/dev-setup.ps1` + `scripts/dev-env.ps1` — Rust, llvm-mingw and .NET 9 installed into `.toolchains/` without admin rights |
| **One-command toolchains** | **done** | `scripts/dev-setup.ps1` + `scripts/dev-env.ps1` — Rust, llvm-mingw and .NET 9 installed into `.toolchains/` without admin rights |
| **Context compaction (deepagents)** | **done** | `backend/app/agent_context.py` — tool-result eviction + provider summarization; 37 684 → 5 695 estimated tokens on a 62-message history; context-overflow errors compact and retry |
| **Sub-agents (deepagents)** | **done** | `backend/app/subagent_profiles.py` + `spawn_agent` tool — 5 profiles with restricted tool sets, stateless children, parent dispatcher reused; verified with a mocked model |
| **Skill pack import (OpenHands / deepagents / GenAgent)** | **done** | `backend/app/skills_import.py` — folder **or zip** import; `GET /api/extensions/skills/scan`, `POST /api/extensions/skills/import`; 14 MIT skills bundled and seeded |
| **Browser hardening + human-verification flow** | **done** | Real Chrome launches again (sandbox flag was blocking it); challenge pages are detected and reported as `HUMAN_VERIFICATION_REQUIRED` instead of timing out; Right-pane banner + "Show me" button |

### Upstream work we adopted (see `docs/OSS_INTEGRATIONS.md`)

OpenHands, deepagents and GenAgent are MIT-licensed and were adopted where they
are genuinely better than what AgentDesk had: context summarization, sub-agent
architecture, skill-pack format and the skill library itself. AgentDesk kept
its own advantages throughout — the Rust core, the C++ CDP helper, the .NET
sidecar, the pet expert, the telemetry layer and the installer are untouched by
these ports.



`scripts/bench_native.py`, release build, 4000-node DOM:

| Operation | Python fallback | Rust | Speedup |
|---|---|---|---|
| `dom_diff` (4000 nodes) | 39.1 ms | 34.5 ms | **1.13×** |
| `scrub` (2 KB of secrets) | 1.14 ms | 0.89 ms | **1.28×** |
| `count_tokens` (160 KB) | 0.37 ms | 0.28 ms | **1.31×** |

The plan originally hoped for 10×. It is **1.1–1.3×** with the current
algorithms, because both paths are dominated by the same JSON parse and
`re` scanning. The native core still earns its place: identical results,
one code path, and the hot functions stop blocking the event loop. The next
real win is to stop shipping JSON between the browser layer and the differ
(binary snapshot format), not to rewrite the crate.

### Still open in this phase

* `opentelemetry-sdk` is not bundled (only the API is) — the tracer emits
  OTLP-shaped JSON so only `_span_sink` changes when the SDK is added.
* UIA3 returns an empty tree when the sidecar runs outside the interactive
  desktop session (service context); it works in the user's session.
* Clipboard access is blocked inside this sandbox, not by the code.
* The Windows sidecar publishes self-contained (not NativeAOT): AOT needs
  the MSVC toolchain, which this machine does not have.

## 7. Kickoff — the first three concrete tasks

1. **`docs/API.md` + OpenAPI 3.1 export** of every `/api/*` route (script-generated,
   no drift), and the first **generated** clients: TypeScript (`sdk-ts`) and Python
   (`sdk-py`). *Pure Python + codegen, no new runtime.*
2. **`agentdesk_core` (Rust, PyO3)** with `dom.diff`, `refs.build`, `scrub` and
   Python fallbacks + a benchmark that proves the win. *Establishes the native
   pattern.*
3. **OTel instrumentation** of the agent turn (spans: route → plan → tool call →
   stream) with a local OTLP collector view and Prometheus `/metrics`.
   *Makes every later optimisation measurable.*

**Definition of done for the whole plan:** the app installs from a signed
installer, passes the smoke test, the agent works on the local model and on the
free gateways, every external language can drive the same browser, and each
release ships a benchmark or an eval that proves it got better.
