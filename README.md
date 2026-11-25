# AgentDesk

See [AgentDesk 0.3.1 handoff](HANDOFF_0.3.1.md) for the current Windows release, CPU setup, integration API, and SDKs.

## AgentDesk 0.3.1 on Windows

The packaged release uses Electron 45.4.1 and starts a private, authenticated local backend from the desktop app. Run `npm run build:installer` to build the Windows x64 installer. The build uses a cached Electron distribution when available and stages compiled UI assets without development dependencies.

The Model settings let you enable external fallback explicitly. Saved mode uses the selected model and can try the local model. Hard mode tries a tool-capable OpenRouter free model and then the local model. Explicit ChatGPT and Gemini modes submit chat context through the corresponding browser session.

Risk-sensitive agent tools ask for approval by default. Fresh profiles leave DeskPet observation and MCP servers disabled until you enable them. Sandbox commands run locally inside a bounded Windows Job Object (no remote runner). Chat compaction archives the original messages, and Windows protects saved service credentials for the current user account.

Read [RELIABILITY.md](RELIABILITY.md) for the release checks and research behind the roadmap. The remaining sections describe the earlier project layout and may mention superseded behaviours.

A three-panel agentic coding desktop app: **workspace + chat + live browser**, with an
always-on local llama.cpp model (llama-cpp-python server, GGUF on disk), OpenRouter free
models for cloud work, and the option to drive the real ChatGPT or Gemini web chat through
the built-in browser.

```
┌──────────────┬─────────────────────────┬──────────────────────────┐
│  Workspace   │   Agent chat            │  Live browser / screen   │
│  sessions    │   streaming replies     │  Playwright viewport     │
│  file tree   │   tool cards            │  URL bar + navigation    │
│              │   command approvals     │  desktop, terminal, file │
└──────────────┴─────────────────────────┴──────────────────────────┘
```

## Windows installer

```powershell
cd C:\Users\saura\agentdesk
npm install
npm run build:installer
```

The setup file is written to `release\AgentDesk-Setup-0.3.1.exe`. It bundles Python 3.11 with all
packages, Chromium for the built-in browser, the llama.cpp server, and the tiny-brain GGUF model.
Node.js, Python and Ollama are **not** required on the target machine — the local model is served
by the bundled llama.cpp (`python -m llama_cpp.server`) on `127.0.0.1:11435`. Node is still optional
for MCP presets.
`qwen3.5:4b` local model; cloud/browser modes work without it.

Choose your install directory during setup (default `%LOCALAPPDATA%\Programs\AgentDesk`).
`asar` is disabled, so every installed file can be edited afterwards — see `MODIFYING.md`
(also copied into `resources\docs` by the installer).

## Highlights

- **Agentic coding loop** — reads, writes and edits files; lists the workspace; runs
  commands with approval; iterates through tool calls until the task is done.
- **Real browser** — a persistent Chromium managed by Playwright. The agent can navigate,
  click, type, press keys, select options, wait, scroll, read page text, collect links, go
  back/forward. Every page is streamed to the right panel.
- **File attachments** — paperclip in the chat composer uploads files to `data/uploads/`.
  The agent reads them with `read_file`; up to `data/uploads/<id>` is shown to the model with
  its absolute path. Uploads survive restarts.
- **Live web search** — the agent calls `web_search` with Firecrawl (keyed) and cites real URLs.
  Create free search keys at `firecrawl.dev`.
- **Office skills installed from the web** — best-in-class Anthropic skills for `docx`, `pptx`,
  `xlsx`, and `pdf` are pre-installed; use them with normal file tools.
- **Git/GitHub tools** — `git_status` reads branch/status/diff stats; `github_pr_summary(repo)`
  lists recent/open PRs using `GITHUB_TOKEN` or Settings GitHub token. Full diff review is a
  roadmap item.
- **PC info** — `pc_info` reports OS, CPU, RAM, disk, hostname, Python, and installed tool paths.
- **Kaggle credits** — `kaggle_credits` reports Kaggle CLI/config/env/account state.
- **Google sign-in logins** — Settings → Browser has **Open Drive login**, **Open Gmail login**,
  and **Open Calendar login** that open a visible Chromium window. Browser automations can then
  browse Google apps; direct Drive/Gmail/Calendar API tools are a roadmap item.
- **Global automations** — Settings → General → Automations creates persistent jobs that
  re-run an AgentDesk prompt on an interval. Use OpenRouter free (Hard mode) for heavier
  unattended runs.
- **Export transcripts** — Export button in chat downloads Markdown for any session from
  `GET /api/sessions/{id}/export`.
- **Browser chat** — ChatGPT and Gemini modes automate the signed-in consumer web UI, so a
  free web account can answer coding questions without an API key.
- **Hard mode** — uses OpenRouter's current **free** models with tools, choosing the best
  available `:free` model automatically. If no key is set, or OpenRouter fails, it falls
  back to ChatGPT or Gemini in the built-in browser.
- **Desktop control** — screenshots plus mouse/keyboard automation (approval-gated).
- **Terminal** — a real PowerShell PTY in the right panel, powered by xterm.js.
- **Skills** — Markdown playbooks loaded on demand with `use_skill`; install from any raw
  URL or write your own.
- **MCP** — connect stdio MCP servers with one click (`uvx`/`npx` auto-install). The Fetch
  server is seeded by default and its tools are exposed to the agent as `mcp_<server>_<tool>`.

## Run it

Full setup + troubleshooting: `SETUP.md`.

Double-click `start-agentdesk.bat` (development mode), or:

```
cd C:\Users\saura\agentdesk
npm run dev
```

The Electron window starts and supervises the Python backend automatically. First launch
takes a few seconds while imports finish.

Production-style run (no Vite dev server):

```
npm run build:ui
npm start
```

## Chat modes

Choose a mode above the composer:

| Mode | What it does |
| --- | --- |
| **Saved** | Uses the provider/model configured in Settings (local llama.cpp by default). |
| **Hard · free** | OpenRouter free model with tools. No key or a failure → ChatGPT/Gemini in the browser. |
| **ChatGPT** | Automates ChatGPT's web UI in the visible persistent browser. |
| **Gemini** | Automates Gemini's web UI in the visible persistent browser. |

The mode is remembered per machine. The right panel switches to the browser automatically
when a web-chat route starts.

### OpenRouter free key

1. Create a free key at `https://openrouter.ai/keys`.
2. Settings → Model → **Hard coding route** → paste it into **OpenRouter API key**.
3. Pick **Auto — best current free model** (the list is fetched from OpenRouter and ranked
   for coding/tool use), or choose a specific free model.
4. Choose the browser fallback site (ChatGPT or Gemini).

Free model IDs rotate, so AgentDesk discovers the catalog each time instead of relying on a
fixed model. If the catalog cannot be fetched, it uses a known free fallback.

### Signing in to ChatGPT / Gemini

Browser automation needs a visible window for login and human checks:

1. Settings → Browser → **Open ChatGPT login** or **Open Gemini login**.
2. Finish the sign-in / Cloudflare check in the Chromium window that appears.
3. Send a message in ChatGPT or Gemini mode. The agent waits for the prompt box, then types,
   submits, streams the reply into the chat, and shows the page in the browser panel.

The persistent profile at `data/browser-profile` keeps the login across restarts. While a
web chat is running, the browser temporarily switches to a visible window and the badge in
the right panel reads **windowed**.

### Tiny brain (always-on llama.cpp)

Fast local model for quick decisions, no network round trip:

- Runtime: bundled official Vulkan `llama-server.exe` in `resources\runtime\llama-vulkan`
  (Intel/AMD iGPU or NVIDIA through the system Vulkan runtime), with a CPU fallback via
  `llama-cpp-python`. Settings → Local Models → **Inference backend** selects `Auto`,
  `Vulkan GPU`, or `CPU`; the active backend is reported by `GET /api/models/backend`.
- Model: bundled `resources\runtime\models\qwen2.5-1.5b-instruct-q4_k_m.gguf` (Qwen2.5
  1.5B Instruct, ChatML) or any GGUF activated in Settings → Local Models.
- Settings: `local_backend`, `local_gpu_layers` (default `99`), `local_context_size`
  (`4096`), `local_threads` (`4`). Env overrides: `AGENTDESK_LLAMA_VULKAN_EXE`,
  `AGENTDESK_LLAMA_GPU_LAYERS`, `AGENTDESK_LLAMA_CTX`, `AGENTDESK_LLAMA_THREADS`.
- Agent tool: `tiny_brain(prompt)` in `backend/app/engine/tiny_brain.py`.

## Stack

- **Desktop shell:** Electron (`electron/main.js`) — spawns and supervises the backend
- **Backend:** FastAPI + WebSocket (`backend/app`) — agent loop, SQLite sessions, tools
- **Frontend:** React + Vite + TypeScript (`frontend/src`) — three-panel UI
- **Browser:** Playwright Chromium, persistent context
- **Terminal:** pywinpty + xterm.js
- **Desktop:** PyAutoGUI + Pillow
- **Models:** always-on local llama.cpp + per-gateway saved keys (OpenRouter, Vercel, UnoRouter, OpenCode, Pollinations, OpenAI) with browser fallback

## Layout

```
agentdesk/
├── electron/            Electron main + preload
├── backend/app/
│   ├── agent.py          agent loop, tool schemas, approvals, browser chat
│   ├── engine/           OpenAI-compatible client, OpenRouter discovery, web chat
│   ├── tools/            fs, shell, browser, computer
│   ├── routes/           sessions, workspace, settings, browser, computer,
│   │                     extensions (skills/MCP), terminal WS, chat WS
│   ├── mcp_manager.py    MCP presets, lifecycle, tool bridging
│   ├── skills.py         skill install/list/delete + starter skills
│   └── terminal.py       PowerShell PTY session manager
├── frontend/src/         React UI (App, Sidebar, ChatPane, RightPane, Settings, Terminal)
├── data/                 SQLite DB, settings.json, mcp.json, skills, uploads, automations.json, browser profile
└── scripts/              dev launcher + smoke tests
```

## Settings

- **General** — Firecrawl API key for `web_search`, GitHub token for PR summaries, and the
  automation list.
- **Model** — provider preset, base URL, model, key, temperature, max steps, thinking and
  auto-approval toggles, plus the Hard-mode route.
- **Browser** — headless toggle, default web-chat site, login buttons for ChatGPT/Gemini and
  Google Drive/Gmail/Calendar.
- **Skills** — best-in-class Anthropic skills (`docx`, `pptx`, `xlsx`, `pdf`) are installed by
  default; install from URL, inspect, delete, or write a new skill inline.
- **MCP** — connect presets/servers, enable/disable, add custom stdio servers.
- **MCP** — add presets (Fetch, Playwright, Filesystem, Memory, Sequential Thinking),
  enable/disable, add custom stdio servers, inspect live status and exposed tools.

`Disable model thinking` sends `reasoning_effort: "none"` for cloud models. **Local llama.cpp**
is always-on — the bundled server starts automatically at launch on `127.0.0.1:11435`; fallback
is: local → OpenRouter free → Pollinations/Vercel/UnoRouter/OpenCode → OpenAI → ChatGPT/Gemini in
the browser. Click the visible page in the browser tab — the agent maps clicks to page clicks.
MCP presets need Node (`npx`) on PATH, or a Node install in `C:\Program Files\nodejs`.

Shell commands and desktop automation require approval unless auto-approve is enabled.
File tools are sandboxed to the selected workspace folder.

## HTTP / WebSocket surface

> The canonical list is registered in `backend/app/main.py`. Anything not listed
> there won't be reachable even if documented here.

### Health & settings
- `GET /api/health` — `{"ok": true, "version": "0.4.0"}`
- `GET /api/diagnostics` — redacted health snapshot (providers, local model,
  MCP, watchdog, automations, brain stats).
- `GET /api/provider-health` — per-provider live status.
- `GET /api/openrouter/models`, `GET /api/openrouter/recommended`
- `GET/PUT /api/settings`

### Workspace, sessions, uploads
- `GET/POST /api/workspace`, `GET /api/workspace/tree`, `GET /api/workspace/file`
- `POST /api/uploads/files`
- `GET /api/memory`, `POST /api/memory/...` — short/long-term memory routes
- `GET/POST/DELETE/PATCH /api/sessions`, `GET /api/sessions/{id}/messages`,
  `GET /api/sessions/{id}/export`
- `GET/POST /api/missions`, `POST /api/missions/{id}/run`

### Browser, computer, terminal
- `GET /api/browser/state`, `POST /api/browser/action`
- `GET /api/computer/size`, `GET /api/computer/state`, `POST /api/computer/capture`
- `WS /ws/terminal/{sessionId}` — output, input, resize, restart

### Automations, plugins, models
- `GET/POST /api/automations`, `POST /api/automations/{id}/cancel`
- `GET/POST /api/backup`
- `GET/POST /api/brain/...`
- `GET /api/extensions/skills`, `POST /api/extensions/skills`,
  `DELETE /api/extensions/skills/{slug}`
- `GET/PUT /api/extensions/mcp/servers`, `GET /api/extensions/mcp/presets`
- `GET/POST /api/models`, `/api/models/download`, `/api/models/activate`,
  `/api/models/status`, `/api/models/backend`, `DELETE /api/models/{name}`

### Sandbox & workers
- `POST /api/sandbox/...`
- `GET/POST /api/workers/...`

### Approvals & Earn & Pet
- `GET /api/approvals`
- `GET/POST /api/earnings/...`
- `GET/POST /api/pet/...`

### Chat
- `WS /ws/chat/{sessionId}` — events: `ready`, `notice`, `message_start`, `token`,
  `message_commit`, `message_end`, `tool_call`, `tool_result`, `approval_request`,
  `browser_frame`, `computer_frame`, `file_changed`, `compacted`,
  `model_switched`, `error`, `stopped`, `done`.

### Integration (`/v1/*`)
- `GET /v1/models`, `POST /v1/chat/completions` — bearer-authenticated via
  `AGENTDESK_GATEWAY_TOKEN`. Used by the Python and TypeScript SDKs.

## Global earning tab

- `GET /api/earnings/overview` - income, ventures, task counts, best opportunities, next actions, lessons
- `GET /api/earnings/opportunities`, `POST /api/earnings/radar`, `POST /api/earnings/launch`
- `GET /api/earnings/ventures/{id}`, `POST /api/earnings/ventures/{id}/tasks/{task_id}/complete`
- `GET/POST /api/earnings/income`, `GET/POST /api/earnings/learning`, `GET/PUT /api/earnings/settings`
- `GET /api/earnings/brief`, `POST /api/earnings/autopilot/tick`
- Agent tools: `earnings_radar`, `earnings_launch`, `earnings_brief`, `earnings_complete_task`,
  `earnings_log_income`, `earnings_learn`, `earnings_autopilot`, `earnings_report`
- Autopilot only drafts local assets; sends, accounts, spend, contracts and payouts need approval.

## Security notes

- The backend binds to `127.0.0.1` only and has no auth — this is a local single-user app.
- File tools reject paths that escape the workspace.
- Shell and computer tools require approval by default.
- `ask_chatbot` requires approval because the prompt leaves the machine.
- Web-chat logins live in a local Chromium profile; nothing is uploaded by AgentDesk.

## Roadmap

Full plan: [`docs/NEXT_UPGRADES_CUTTING_EDGE.md`](docs/NEXT_UPGRADES_CUTTING_EDGE.md)
(polyglot upgrade matrix, interop contract, releases 0.4.1 → 0.7.0) and
[`docs/BROWSER_UPGRADE_PLAN.md`](docs/BROWSER_UPGRADE_PLAN.md) (in-app browser).

`backend/app/engine/` is the seam for additional engines:

- an `opencode` engine that proxies the OpenCode server/SDK
- diff review and revert for file edits
- multi-file patch tool + test-runner presets
- screenshot annotation and element picking in the browser panel
