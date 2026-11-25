# AgentDesk Browser Upgrade Plan — "OpenBrowser"

Status: **proposed** · Owner: desktop app · Target: 0.5.0 (Phases 0–3), 0.6.0 (Phases 4–6)

Goal: turn the built-in tab into a **first-class, sign-in-capable, fully agent-drivable
browser** — multi-tab, human-in-the-loop sign-in, pixel *and* DOM grounding, real mouse
and keyboard synthesis, MCP exposure in both directions, and local-first inference —
built on open-source components only, with no paid API dependency.

---

## 1. Where the browser is today (grounded in this repo)

| Capability | Today | File |
|---|---|---|
| Engine | Playwright persistent Chromium, prefers installed Chrome | `backend/app/tools/browser.py` |
| Page model | **single** page/tab, one shared profile | `browser.py` (`BrowserManager._page`) |
| Sign-in | Works only because one global profile persists cookies (`data/browser-profile`) | `browser.py` `PROFILE_DIR` |
| Grounding | Set-of-Marks: `data-adk-idx` attributes + screenshot overlay | `browser.py` `elements()` / `click_element()` |
| Inputs | Click by CSS, fill, single key press, wheel scroll, coordinate click | `browser.py` `click/type_text/press/scroll/click_at` |
| Reading | `inner_text("body")`, links, PDF, HTML tables | `tools/browser.py`, `agent.py` |
| Web-chat | ChatGPT/Gemini driven through the same page | `engine/webchat.py` |
| MCP | Playwright MCP exists only as an *optional preset* with its own browser | `mcp_manager.py` PRESETS |
| UI | Browser tab is a URL bar + a single screenshot frame | `components/RightPane.tsx` |
| Tools | 18 `browser_*` schemas | `agent.py` `TOOL_SCHEMAS` |

**Gaps that block "full browser":** one tab; no tab-switching; no downloadable-file
handling; no upload; no clipboard; no real hover/drag/arrow-key semantics; no DOM-diff
(intel) — only pixels (vision) for grounding; no structured a11y snapshot as a
token-efficient agent interface; MCP cannot drive *our* browser (only its own).

---

## 2. Design principles

1. **Local-first, cloud-optional.** DOM/a11y/tool calls are deterministic and cheap —
   they run locally (llama.cpp). Only genuinely visual reasoning (canvas, WebGL,
   image QA) escalates to a cloud vision model.
2. **DOM before pixels.** A DOM snapshot costs ~1–3k tokens; a screenshot costs ~1.5k
   *plus* vision tokens and is ambiguous. Use DOM by default, vision as verification.
3. **Every action is auditable.** One action log, one approval scope, one replayable
   trace. No hidden browser state.
4. **Open-source only.** Playwright/CDP, browser-use/BrowserGym harnesses, MCP,
   open OCR/VLM models. No proprietary browser, no paid vision API.
5. **Boring, testable seams.** Third-party browser engines are accessed behind one
   interface (`BrowserEngine`) so CDP/WebDriver-BiDi can be swapped in.

---

## 3. Target architecture

```
┌────────────────────────────────────────────────────────────────────┐
│ Agent (llama.cpp local  ▸  keyless/openrouter cloud  ▸  browser)  │
│   tool calls ──► BrowserService ──► TabManager ──► PageActor       │
└────────────────────────────────────────────────────────────────────┘
                                     │                │
                        BrowserEngine (iface)   Grounder (DOM|a11y|VLM)
                                     │                │
                            Chromium/CDP ◄─────► DOM Diff Store (SQLite+FTS)
                                     │
                      ProfileVault (per-site encrypted profiles)
```

### 3.1 `BrowserEngine` interface (`backend/app/browser/engine.py`, new)

Abstracts the driver so Playwright can be replaced by raw CDP or WebDriver BiDi:

```python
class BrowserEngine(Protocol):
    async def launch(self, profile: Profile) -> None: ...
    async def new_tab(self, url: str | None = None) -> Tab: ...
    async def close_tab(self, tab_id: str) -> None: ...
    async def snapshot(self, tab_id: str) -> DomSnapshot: ...      # a11y + DOM
    async def act(self, tab_id: str, action: Action) -> ActionResult: ...
    async def screenshot(self, tab_id: str, mode: str = "viewport") -> str: ...
    async def focus(self, tab_id: str) -> None: ...
```

`Action` is a typed registry (roadmap item "safe workflow runner" from
`AGENTDESK_UPGRADE_PLAN.md`): `navigate|click|type|press|hover|drag|scroll_to|upload|
download|select|wait_for|run_js_eval(capability-gated)|copy|paste`.

Implemented by `PlaywrightEngine` (today's code, refactored) and later `CdpEngine`
(chromium `--remote-debugging-port`, gives us raw `Input.dispatchMouseEvent`).

### 3.2 Tabs (`TabManager`)

- Tab registry in SQLite (`tabs` table: id, url, title, favicon, active, created, domain).
- The UI grows a **tab strip** above the URL bar: new tab, close, switch, pin, group by
  domain, and a "restore session" list (Chrome-style session restore).
- Per-tab state machine: `idle → loading → interactive → blocked → error`, so the agent
  can wait deterministically instead of sleeping.

### 3.3 Sign-in & profile vault

- **Profile = one encrypted cookie jar + storage state**, keyed by site domain.
  `Chrome/Users/<domain>.json` (encrypted with the existing DPAPI/`encryption.py`).
- Flow: agent hits a login wall → emits `signin_required` → the UI shows a **"Take over"
  banner** → the human signs in in the *same* real profile → agent calls
  `browser_resume_signin` → the session continues with the authenticated state.
  No credential ever passes through the model.
- Optional **detached** profile for high-risk sites (own Chrome instance, own window).
- 2FA/loss-recovery always stays human — by design, never automated.

### 3.4 Grounding: three tiers, escalating

| Tier | Signal | Cost | Model | When |
|---|---|---|---|---|
| 1 | DOM + accessibility tree snapshot (JSON, refs) | ~1–3k tok | local | default |
| 2 | Set-of-Marks overlay (existing) + DOM diff | ~2k tok + screenshot | local | dense pages |
| 3 | VLM grounding (bbox prediction) on screenshot | ~1.5k tok + vision | local VLM (Qwen2.5-VL/UI-TARS-class) or cloud fallback | canvas/WebGL, no DOM |

Refs are **content-addressed** (`ref:ab12`) and invalidated by a DOM hash, so a stale ref
fails loudly instead of clicking the wrong field. This is the core safety property.

### 3.5 DOM diff store (the "intel" layer)

- After every action, store a normalized DOM hash + snapshot delta in SQLite (FTS5).
- The agent gets a *change summary* ("3 new elements, submit button now enabled")
  instead of a full re-read → large token and latency savings vs. re-snapshotting.
- Enables "what changed since I clicked?" and cheap rollback/undo.

### 3.6 Input synthesis (mouse & keyboard, done properly)

- **Keyboard**: named keys incl. arrows (`ArrowUp/Down/Left/Right`), Home/End/PageUp/Down,
  Tab/Shift+Tab, chords (`Control+Shift+K`), `type_text` with per-char delay, IME-safe
  `insertText`.
- **Mouse**: `move(x,y)`, `click(x,y, {button, click_count, modifiers})`, `double_click`,
  `right_click`, `context_menu`, `drag(from → to, steps)`, `wheel(dx,dy)`,
  `hover` with settle time, plus `scroll_to(element_ref)` (scroll-into-view, no pixels).
- **Files**: `upload(ref, path)` and download handling (`downloads/` dir + auto-detect
  via CDP `Browser.setDownloadBehavior`, expose the file to the agent).
- **Clipboard**: read/write system clipboard for copy-paste flows.
- All coordinates are in **CSS px of the live viewport**, with the device scale factor
  and scroll offset tracked so model-provided coordinates always map correctly.

### 3.7 MCP in both directions

**Outbound (AgentDesk → external agents):** publish AgentDesk's browser as an MCP server
(`stdio` + optional HTTP) so Claude Desktop / OpenCode / any MCP client can drive *this*
browser — including the human's signed-in sessions. Expose `browser_snapshot`,
`browser_click`, `browser_type`, `browser_navigate`, `browser_tabs`, `browser_signin_*`.

**Inbound (external MCP → AgentDesk's browser):** implement an MCP **client bridge**
that can attach to the Playwright-MCP server (already a preset) but *bind it to our
context* so it inherits the signed-in profile instead of spawning a fresh browser.
Precedence rule: our native tools > Playwright MCP > BrowserGym/browser-use > raw
`computer_*` (pixel fallback).

### 3.8 Local-vs-fallback routing for browser work

| Task | Preferred | Fallback |
|---|---|---|
| read/Navigate/click/type | local llama.cpp (tool calls) | keyless → openrouter → webchat |
| dense-page reasoning | local VLM (Qwen2.5-VL 3B) | cloud vision model |
| extraction to JSON | local + `response_format` strict JSON | cloud |
| captcha / anti-bot | **human handoff** | never automate |

The existing `_route_plan` health-weighted ordering already covers provider choice; the
browser adds a *tool-class → route* hint (DOM tasks never need a VLM).

---

## 4. Agent tool surface (new/changed)

Keep the current 18 tools working; add:

| Tool | Purpose |
|---|---|
| `browser_tabs` | list / open / close / switch tabs |
| `browser_snapshot` | structured DOM+a11y JSON with refs (replaces ad-hoc `read`) |
| `browser_find` | locate elements by text/role/label → refs |
| `browser_click_ref` / `browser_type_ref` | act on a ref (not a CSS selector) |
| `browser_key` | arrows, chords, Tab, Enter, Escape, etc. |
| `browser_mouse` | move / click / double / right / drag at coords |
| `browser_scroll_to` | scroll an element into view |
| `browser_upload` | attach a workspace file to an input |
| `browser_downloads` | list/save/read recent downloads |
| `browser_signin` | request human sign-in, then `browser_resume_signin` |
| `browser_diff` | what changed since the last action |

Remove/deprecate the fragile ones (`browser_click` by raw CSS) from the *model's* tool
list — keep them for the UI, but advertise ref-based tools to the model.

---

## 5. UI plan (`RightPane`)

1. **Tab strip** (new): favicons, titles, close, + new, drag-reorder, right-click menu.
2. **Address bar**: URL + domain + TLS state + "sign-in required" badge + blocklist indicator.
3. **Viewport frame**: live screenshot (existing `browser_frame`) with element overlays
   on hover; click a coordinate → tool `click_at`.
4. **Inspector drawer** (new, collapsible): DOM snapshot viewer, console log, network
   failures, downloads. (DevTools-lite, not full DevTools.)
5. **Sign-in takeover modal**: explains what the agent needs, offers "open in Chrome",
   "switch to this window", "cancel".
6. **Action ledger**: every browser action with timestamp, redacted args, undo/replay.

---

## 6. Safety & privacy

- **Domain policy**: allow/deny lists + per-domain "never submit forms / never spend".
- **Scope-bound approvals**: an approval binds to `(action_class, domain, target_ref)`;
  consent is single-use and expires.
- **Injection defence**: page text is untrusted data (already fenced); the DOM snapshot
  gets the same fence + instruction-stripping.
- **Secret handling**: cookies/tokens never enter the transcript; typed passwords are
  flagged and redacted before storing to the action ledger.
- **Egress guard**: warn when the agent is about to send workspace content to a
  different domain than the current page.
- **PII redaction** toggle for downloads/screenshots stored to disk.

---

## 7. Phases, deliverables, acceptance criteria

| Phase | Scope | Deliverable | Accept when |
|---|---|---|---|
| **P0 Foundation** | `BrowserEngine` interface, refactor `browser.py` onto it, typed `Action` registry, action ledger table | `backend/app/browser/*` | All existing `browser_*` tools pass the existing smoke suite unchanged |
| **P1 Tabs** | TabManager, SQLite tab table, tab strip UI, `browser_tabs` tools | multi-tab browsing | 5 tabs open/close/switch survives backend restart; UI strip matches page count |
| **P2 Grounding v2** | a11y+DOM snapshot with stable refs, `browser_find`, ref-based click/type, DOM-diff store | token-efficient, robust clicking | 50-task suite: ≥95% first-click success on real sites; tokens/action ↓60% vs screenshots |
| **P3 Sign-in** | ProfileVault (encrypted per-site), take-over modal, `browser_signin`/`resume` | real authenticated flows | Google/Kaggle/GitHub sign-in survives app restart; no credential in transcript |
| **P4 Input realism** | arrows/chords, hover, drag, scroll-to, upload, downloads, clipboard | completes real forms | End-to-end: create account on a sandbox site, upload a file, download it back |
| **P5 MCP** | AgentDesk-as-MCP-server; Playwright-MCP bound to our context; precedence rules | external agents can drive it | From an external MCP client: snapshot → click → read; authenticated session reused |
| **P6 VLM tier** | local VLM grounding (bbox), canvas/WebGL path, cloud vision fallback | handles visual-only UIs | 20 canvas/visual tasks: ≥80% solved (local first) |
| **P7 Scale & perf** | parallel contexts (one per task), context pooling, latency budgets, caching | concurrency without lock contention | 3 concurrent agent tasks on separate profiles, no profile-lock errors |
| **P8 Release** | hardening, docs, installers, telemetry, self-signed signing flow | shippable | 0.5.0 installer passes `verify_release.py` + manual sign-in matrix |

Effort shape: P0–P2 ≈ 2 weeks, P3–P5 ≈ 3 weeks, P6–P8 ≈ 2–3 weeks (one engineer).

---

## 8. Open-source building blocks to adopt

| Component | Use | License |
|---|---|---|
| **Playwright** (existing) | engine + CDP session | Apache-2.0 |
| **browser-use** (already a dep) | high-level agent loop reference | MIT |
| **BrowserGym / browser-harness** (already deps) | eval harness + task suites | MIT |
| **MCP Python SDK** | in/out MCP bridge | MIT |
| **Playwright MCP** (existing preset) | bind to our profile | Apache-2.0 |
| **Stagehand / Skyvern** | action-model patterns to borrow (MIT/Apache) | reference only |
| **Qwen2.5-VL / InternVL (3B)** | local VLM grounding | Apache-2.0 |
| **PaddleOCR / tesseract** | local OCR for canvas text | Apache-2.0 / Apache-2.0 |
| **OpenDevin / OpenHands** | agent-loop + sandbox patterns | MIT |
| **onnxruntime** | local inference for OCR/VLM | MIT |

Nothing here requires a paid API. The only paid piece remains optional code-signing.

---

## 9. Engineering practices to apply (2026-era)

- **Evals first.** Every phase ships a task suite (BrowserGym-style), run in CI, with
  success-rate and token-budget gates. No "it seems to work" releases.
- **Deterministic replay.** Store `(tab snapshot hash, action)` pairs; replay a failure to
  reproduce. Cheaper than guessing from logs.
- **Contracts over prose.** Tools are JSON-Schema typed; the snapshot format is versioned
  (`snapshot/v2`) so prompts and MCP clients can pin a version.
- **Structured outputs.** Extraction tasks request strict JSON and validate against a
  schema before it reaches the transcript.
- **Prompt caching** for the (large) system prompt + tool schemas, so per-turn cost is
  only the delta.
- **Model routing by task class**, with a local-first ladder and cloud fallback
  (mirrors the existing health-weighted `_route_plan`).
- **Trace everything**: one `trace_id` per turn, spans around each browser action
  (latency, tokens, DOM diff size) — feeds `/api/diagnostics` and the metrics endpoint.
- **Guardrails as code**: injection filters, egress checks and scope-bound approvals
  enforced in the service layer, never only in the prompt.
- **Small-model trick**: use the local model for routine steps (click ref, type, scroll)
  and escalate to cloud only when the step fails or needs judgment — mirrors the
  existing local-vs-cloud routing but per-tool.
- **Local vision-first**: attempt DOM grounding, fall back to OCR, then to a VLM — each
  tier recorded so we can measure how often pixels are truly needed.

---

## 10. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Anti-bot / captcha walls | Human takeover path; never brute-force; per-domain cooldown |
| Profile lock contention (two contexts, one Chrome profile) | one profile per browser instance; isolated contexts for parallel tasks; explicit lock detection + retry |
| Token blow-up on huge pages | DOM-diff store, viewport-scoped snapshots, hard per-action char caps |
| Stale refs → wrong click | content-addressed refs with hash validation; fail loudly, re-snapshot |
| Consent scope creep | single-use, domain-bound approvals + ledger + undo |
| Heavy dependency weight | keep the engine layer thin so Vendors can be swapped; optional extras behind flags |
| Regression in existing flows | P0 is a pure refactor with the existing smoke suite as the gate |

---

## 11. Immediate next actions (this week)

1. **P0.1** — create `backend/app/browser/` with `engine.py` (protocol), `actions.py`
   (typed registry), and move `browser.py` behind it. No behaviour change.
2. **P0.2** — action ledger table + `ActionResult` shape; emit `browser_action` frames to
   the UI so the ledger can render live.
3. **P0.3** — refactor `browser_click`/`type`/`press`/`scroll` in `agent.py` to call the
   new service; keep the old tool names as aliases.
4. **P1.1** — `tabs` table + TabManager; multi-tab support in `BrowserManager`;
   `browser_tabs` tools; tab strip UI.
5. **P2.1** — `snapshot()` returning a11y+DOM JSON with refs; `browser_find`;
   ref-based click/type; measure tokens/action vs today (expect ~60% drop).

Ship P0+P1 as **0.4.1**, P2+P3 as **0.5.0**, P4–P6 as **0.5.x**, P7+P8 as **0.6.0**.

---

## 12. Definition of done for "OpenBrowser"

- [ ] Multiple tabs with a real tab strip, restored across restarts
- [ ] Human sign-in takeover; session persists; no secrets in transcripts
- [ ] Agent acts via stable refs (DOM) with vision fallback; ≥95% first-click success
- [ ] Full keyboard (arrows/chords) and mouse (move/click/drag/hover) synthesis
- [ ] Upload + download round-trip handled by the agent
- [ ] AgentDesk exposes its browser over MCP; external client reuses the signed-in session
- [ ] Local-first: routine steps run on llama.cpp; cloud only as fallback
- [ ] Every action in a replayable ledger with undo + scope-bound approvals
- [ ] Task suite green in CI with token/latency budgets

---

## Appendix A — Multi-language integration (implemented in 0.4.0)

The browser is now exposed to **any** language. One Chromium instance, three
standards-compatible façades — no second browser, no per-language engine.

| Façade | Endpoint | Consumers |
|---|---|---|
| **REST + WebSocket** | `http://127.0.0.1:8756/api/browser/sdk` | anything with an HTTP client (C++, C#, Java, JS, Go, Rust, PowerShell) |
| **Chrome DevTools Protocol** | `http://127.0.0.1:9333` | Puppeteer, Selenium (`debuggerAddress`), ChromeDriver, raw CDP, libcurl + websocket |
| **WebDriver BiDi** (W3C) | `ws://127.0.0.1:8756/api/browser/bidi/ws` | Selenium 4, Playwright for .NET, Playwright for Java, any BiDi client |

### What lands in each language

Because all three hit the same Chromium, a C++ program and the Python agent
share **cookies, logins, the visible window and the same page**. Python is
excellent for orchestration (it is), but the parts that need real speed, real
input fidelity, native plugins or a team's existing stack are usually C++/C#/JS.
Rather than three browser stacks, they get three *protocol adapters* over one.

| Need | Best façade | Why |
|---|---|---|
| C++ high-speed scraping, native libs | CDP or REST | no managed runtime needed, libcurl + ws |
| C# / .NET enterprise + Playwright.NET | **BiDi** | W3C standard, first-class in Selenium 4 |
| JS/TS (Node, Electron, workers) | **Puppeteer** | attach with `puppeteer.connect`, no Chromium download |
| Java / Kotlin | BiDi | Playwright for Java speaks BiDi |
| Quick scripting / glue | REST | one HTTP call |

### Delivered

- `backend/app/routes/browser_sdk_route.py` — REST/WS control plane:
  `info`, `tabs`, `navigate`, `act`, `snapshot`, `screenshot`, `events`.
  `act` supports `click`, `click_at`, `double_click_at`, `type`, `key`
  (arrows + chords), `hover`, `drag`, `scroll`, `scroll_to`, `select`,
  `wait_for`, `upload`, `back`, `forward`, `reload`.
- `backend/app/routes/browser_bidi_route.py` — BiDi command subset:
  `session.*`, `browsingContext.*`, `script.evaluate/callFunction`,
  `input.performActions`, `browsingContext.locateNodes`.
- `backend/app/browser_sdk_auth.py` — stable per-user token
  (`data/browser-sdk.token`) so native clients authenticate without restarting
  the app; the desktop token still works.
- `backend/app/security.py` — token (desktop **or** SDK) accepted on
  `/api/browser/sdk/*` and `/api/browser/bidi/*`, including the `?token=` query
  form for clients that cannot set headers on a WS handshake.
- `backend/app/tools/browser.py` — launches Chromium with
  `--remote-debugging-port` (settings `browser_cdp_port`, default 9333,
  `0` disables) and adds the missing input verbs
  (`mouse_double_click`, `hover_at`, `drag`, `scroll_to`, `upload_file`).
- `examples/browser/` — C++ (raw CDP), C# (BiDi), JavaScript (Puppeteer +
  dependency-free REST) clients with a README.
- Settings → Browser → **DevTools / CDP port** toggle.

### Verified live

- CDP: `Target.createTarget` → `attachToTarget` → `Runtime.evaluate` →
  `Input.dispatchMouseEvent` (press/release) → `Input.dispatchKeyEvent`
  (`ArrowDown`, `Ctrl+K` chord) → `Page.captureScreenshot` → `Target.closeTarget`
- BiDi: `session.status` → `session.new` → `browsingContext.navigate` →
  `browsingContext.getTree` → `script.evaluate` → `input.performActions` →
  `browsingContext.captureScreenshot`
- REST: navigate + snapshot + `key ArrowDown`

### Next (P5 remainder)

- Full BiDi coverage: `browsingContext.locateNodes` → ref-based actions,
  `script.callFunction` with realms, network interception, preload scripts
- Publish AgentDesk as an **MCP server** so any MCP client (not just
  protocol-aware ones) drives this browser
- Per-language SDKs (typed clients for Python/C++/C#/JS) generated from one
  OpenAPI document
