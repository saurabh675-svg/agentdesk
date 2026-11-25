# AgentDesk 0.4.0 — what changed

Installed and running at `C:\Users\saura\AppData\Local\Programs\AgentDesk`
(shortcut: `C:\Users\saura\OneDrive\Desktop\AgentDesk.lnk`). Backend `/api/health` → `0.4.0`;
`AgentDesk.exe` file/product version now reports **0.4.0.0**. Clean-installed from the fresh
`release\win-unpacked` build (staged copy also updated).

## Routing — no more hardcoded OpenRouter
- **Saved** mode: uses exactly the model you configure.
- **Auto** mode (replaces "Hard"): every gateway that has a saved key (user-ordered,
  OpenRouter first with the live `openrouter/free` router) → bundled local **llama.cpp
  (Vulkan GPU when available, CPU fallback)** as the offline fallback (12 s time-box) →
  signed-in **ChatGPT/Gemini browser tab** as last resort. Local used to be first, but a
  1.5B model takes ~20-40 s to prefill the agent prompt and cannot reliably emit tool
  calls, so it stalled chats. Saved mode still lets you force local deliberately (plain
  chat only — tools are disabled for the 1.5B model because its tool-call stream is
  unreliable).
- Settings → Model → **Auto route**: toggle gateways on/off, set a per-gateway model override,
  choose the browser fallback site. `hard` is kept as a backwards-compatible alias for `auto`.

## Local LLMs (llama.cpp) — download & manage in-app
- Settings → **Local Models**: curated GGUF catalog (Qwen2.5 1.5B/3B/7B, Qwen2.5-Coder 3B,
  Llama 3.2 3B, Phi 3.5 Mini) with one-click **Download** (progress bar), **Activate**
  (restarts llama.cpp), and delete. Custom GGUF URL download supported.
- Backend: `GET/POST /api/models`, `/api/models/download`, `/api/models/activate`,
  `/api/models/status`, `DELETE /api/models/{name}`. Models stored in `%APPDATA%\AgentDesk\data\models`.

### Vulkan GPU backend
- The official prebuilt `llama-server.exe` (Vulkan build, `b12670`) is bundled in
  `resources\runtime\llama-vulkan` and included in `package.json` `extraResources`.
- Settings → Local Models now has an **Inference backend** selector: `Auto (Vulkan if
  available)`, `Vulkan GPU`, or `CPU`. `POST /api/models/backend` saves the choice,
  stops the old server (including orphans on port 11435), and restarts it.
- `GET /api/models` and `GET /api/models/backend` report `selected`, `active`,
  `available`, `executable`, `gpu_layers`, and `context_size`. Defaults: 99 GPU layers,
  4096 context, 4 threads (`local_backend`, `local_gpu_layers`, `local_context_size`,
  `local_threads` in settings).
- The wrapper passes `--api-key-file data\llama.key` (the key is never on the command
  line) plus `-ngl`, `-c`, `--threads`, `-b`, `-ub`, and mirrors the child’s lifecycle.
- On this machine `llama-server.exe --list-devices` sees `Vulkan0: Intel(R) UHD Graphics`;
  a manual Vulkan bench answered `VULKAN OK`. The iGPU is still modest (~3 tok/s), so
  cloud-first Auto routing is unchanged.

## Multiple agents
- Settings → **Agents**: create named profiles (provider/model/key), **Activate** one to make it
  the default for new chats, or clear to use the main Model settings. Keys stay saved per gateway.

## Browser self-clicking (Set-of-Marks grounding)
- New tools: `browser_elements` (indexes visible interactive elements, optional numbered overlay),
  `browser_click_element`, `browser_type_element` — reliable clicking by index instead of guessing
  coordinates/selectors. Existing selector/coordinate tools remain.

## Computer use (Windows UI Automation)
- New tools: `computer_elements` (indexed controls of the foreground window) and
  `windows_uia_click` (click a named control via UIA InvokePattern, coordinate fallback).
  Approvals still required for desktop control.

## MCP
- Auth-gated servers now show **needs_setup** with the exact missing env var instead of a crash.
  This includes Google Drive (service-account/OAuth vars) and AskUI (workspace + token), which
  previously showed raw `error` states.
- New presets: Brave Search, Tavily, Time, Git. Existing presets unchanged.
- Credential detection is generic: adding any token/key/credential env var lets the server start.

## Fixes
- Watchdog loopback health check no longer goes through a system proxy (local model reported correctly).
- Watchdog self-health no longer spawns PowerShell every 30 s; it uses a direct proxy-free request,
  so `backend_ok`/`local_ok` are accurate and the browser auto-ensure runs.
- llama.cpp auth key is persisted to `data\llama.key`, so a restarted backend can still talk to the
  already-running local model (previously every request 401'd after a restart).
- The active local model is now highlighted correctly even when using the default/bundled GGUF.
- Bundled and default-home GGUFs are protected from deletion in the Models tab.
- Earn autopilot runs in a background thread after startup (no longer blocks the API port).
- Packaged UI (`Origin: file://`) can open the chat WebSocket; previously it got HTTP 403.
- llama.cpp warm-up is no longer cancelled mid-load, and an already-running local server is reused.
- The local integration API (`agentdesk-hard`) now follows the same multi-gateway Auto policy instead
  of a hardcoded OpenRouter route.
- Closing the window shows an explanatory tray balloon; the app stays running until **Quit** in the
  tray menu. Backend output is logged to `data\backend.log`.
- Plain greetings no longer trigger tools: `hi`/`hello` are answered directly instead of
  the model dumping stale brain context such as Kaggle CLI JSON. The UI also remembers the
  last selected chat in local storage, so a backend restart reopens the same conversation
  instead of appearing to lose it. Auto’s selected route (`Using …`) now stays visible in a
  banner above the chat, and a second Send button remains available while a run is active so
  the next message can be queued instead of the composer only showing Stop. The chat layout now
  gives `.messages` `min-height: 0` and keeps `.composer-wrap` non-shrinking/sticky, so long
  replies scroll inside the message list instead of pushing the input box off the bottom.
- Built-in browser now prefers installed **Google Chrome** over stock Chromium and hides the
  automation flags/user agent. Google/Gmail sign-in no longer hits the “this browser or app
  may not be secure” block in the bundled automation browser. The browser panel reports the
  active engine (`chrome`/`chromium`) in its state.
- Earn ventures now derive a real site URL from their platform when the catalog entry has no
  link. **Open venture** opens the matching site (Superprof, Upwork, Rev, etc.) in the same
  built-in browser; the selected venture card also has a direct **Open site** button.

## Verified
- `scripts/verify_release.py --in-process` passes; `npm run typecheck` passes.
- Live: exe **0.4.0.0**, health 0.4.0, packaged `file://` WebSocket connects, Auto returns
  `AUTO LIVE OK` via `openrouter / openrouter/free` in a few seconds, **Vulkan local returns
  `VULKAN CHAT OK` with `Using local` and no tool calls**, CPU↔Vulkan backend switching keeps
  `/v1/models` healthy on 11435, `hi` returns only the short greeting (no Kaggle tool dump) and
  persists both messages, active model shown, models catalog endpoint, sandbox command, MCP
  statuses (ready or needs_setup with hints), new UI bundle, saved settings/keys preserved.
  Browser state reports `engine: chrome`; Google account page loads as `myaccount.google.com`
  (already signed in) without the insecure-browser block. Earn ventures resolve to real URLs
  and `Open venture` navigates the inbuilt Chrome window (e.g. `https://www.superprof.com/`).
  Layout regression check with 200 long messages: composer stays at the viewport bottom
  (800px) while the message list scrolls (`scrollHeight 15921`, `clientHeight 619`).

## Still to do (next pass)
- Generate the packaged **Setup.exe** artifact (the app is installed and `release\win-unpacked`
  is the current install source; NSIS compression was the only unreliable step).
- Optional: vision-based grounding (OmniParser) for canvas-heavy pages; more MCP presets.
