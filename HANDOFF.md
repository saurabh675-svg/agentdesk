# AgentDesk — Handoff / Update Notes (2026-11-22)

This zip is a complete working snapshot of AgentDesk for another agent to continue bug fixing
and feature work. It contains all source, configuration, docs, the built UI, a helper to
recreate the bundled runtime, and the final Windows installer.

## Contents

```
.
├── HANDOFF.md                  <- this file: start here
├── README.md / SETUP.md / MODIFYING.md
├── package.json                <- scripts + electron-builder NSIS config
├── package-lock.json
├── vite.config.ts              <- includes the base: "./" bug fix
├── tsconfig.json
├── .gitignore
├── start-agentdesk.bat / start-agentdesk-prod.bat
├── backend/
│   ├── requirements.txt        <- 97 frozen Python packages
│   ├── app/                    <- FastAPI backend (editable, no compile step)
│   └── scripts/                <- debug helper
├── frontend/
│   ├── src/                    <- React + TypeScript UI source
│   ├── dist/                   <- prebuilt UI (relative ./assets paths)
│   └── index.html
├── electron/
│   ├── main.js                 <- launcher / backend process management
│   └── preload.js
├── scripts/
│   ├── dev.mjs                 <- dev + prod launcher
│   ├── stage-runtime.ps1       <- rebuild installer\runtime
│   └── *.py                    <- backend/UI smoke tests used during development
└── INSTALLER/
    ├── AgentDesk-Setup-0.1.0.exe   <- final NSIS installer (~1.5 GB, unsigned)
    └── builder-debug.yml           <- electron-builder metadata
```

## Deliberately excluded

| Path | Why |
| --- | --- |
| `node_modules/` | Regenerate with `npm install` (lockfile is included). |
| `backend/.venv/` | Recreate from `requirements.txt`. Backend venv has no pip; use the bundled runtime's python if adding packages. |
| `installer/runtime/` | ~2.4 GB of third-party Python/Chromium/model bytes already inside `INSTALLER\AgentDesk-Setup-0.1.0.exe`. Recreate with `scripts\stage-runtime.ps1`. |
| `release/win-unpacked/` | Portable build output; regenerable and redundant with the Setup.exe. |
| `data/`, `%APPDATA%\AgentDesk\data` | Personal/local runtime data (chats, browser logins, DBs). Not source. |
| `__pycache__/`, `*.pyc`, screenshots (`ui*.png`, `probe-*.png`) | Generated artifacts. |

## First steps for the next agent

```powershell
cd <extracted-folder>
npm install
npm run typecheck
npm run build:ui
npm start
```

`npm start` opens Electron **and starts its own backend**. Do **not** also run a separate
uvicorn on port 8756 — two backends on that port caused confusing test results earlier.

## Bugs already fixed — do not regress these

| # | Bug | Fix | Where |
| --- | --- | --- | --- |
| 1 | Blank screen on first render: `Rendered more hooks than during the previous render`. The command-palette `useEffect` sat after an early return. | Moved the Ctrl/Cmd+K keyboard `useEffect` above every conditional return. | `frontend/src/App.tsx` (~lines 125–136) |
| 2 | Command palette was unreachable. | Added Ctrl/Cmd+K handler + palette UI. | `frontend/src/App.tsx` |
| 3 | Right panel had no **Mission** tab even though the backend/missions API existed. | Added the Mission tab button and view. | `frontend/src/components/RightPane.tsx` |
| 4 | Installed app opened a blank window: built UI used absolute `/assets/...` URLs, which fail under Electron's `file://` loader. | Set Vite `base: "./"` and rebuilt `frontend/dist`. | `vite.config.ts`, `frontend/dist/index.html` |
| 5 | Installed app showed "Backend not available": packaged launcher looked for `backend/.venv/Scripts/python.exe` inside `resources`. | Use `process.resourcesPath/runtime/python/python.exe` when `app.isPackaged`; set `AGENTDESK_PACKAGED`, `PLAYWRIGHT_BROWSERS_PATH`, `TINY_BRAIN_MODEL`, and clear `PYTHONHOME`/`PYTHONPATH`. | `electron/main.js` |
| 6 | Desktop shortcut broke after deleting the silent-test install; Windows removed it and a stale registry entry pointed at the deleted temp folder. | Removed stale registry/Start Menu entries and temp install; reinstalled with explicit `/D=<path>`. Desktop is OneDrive-redirected: `C:\Users\saura\OneDrive\Desktop`. | environment / installer invocation, not source |

## Architecture quick map

- Backend: `127.0.0.1:8756`, FastAPI + uvicorn, WS `/ws/chat/{sessionId}`, `/ws/terminal/{sessionId}`
- UI dev server: `127.0.0.1:5173`; built UI served from `file://` in Electron
- Ollama (optional): `127.0.0.1:11434`, default model `qwen3.5:4b`
- Tiny brain: Qwen2.5-1.5B-Instruct Q4_K_M GGUF, overridable with `TINY_BRAIN_MODEL`
- Browser: Playwright persistent Chromium profile at `<DATA_DIR>/browser-profile`
- Data dir: `AGENTDESK_DATA` env var, else `<APP_DIR>/data` in dev, `%APPDATA%\AgentDesk\data` when installed
- Local model: always-on llama.cpp server (`python -m llama_cpp.server`) on `http://127.0.0.1:11435/v1`, started at backend startup (n_ctx 8192, Vulkan enabled). Default model: largest GGUF in `~/.llama` or the bundled installer model.
- Model routing (`AgentRunner._route_plan`, `app/engine/gateways.py`): active provider → local llama.cpp → free gateways (OpenRouter free, Pollinations, Vercel, UnoRouter, OpenCode) → OpenAI → ChatGPT/Gemini browser fallback.
- Per-gateway API keys: saved in `settings.json` under `keys` + `gateway`; `config.resolve_settings()` fills the active gateway's key; activating any gateway reuses its saved key. Settings UI has a **Saved API keys (per gateway)** grid (Settings → Model).
- "Smarter/high thinker": `SYSTEM_PROMPT` includes thinking discipline; new `credentials_check` + `kaggle_credits` tools check PC credentials (Kaggle config/env/CLI, all saved gateway keys, suspects/missing). `kaggle_credits` fetches competition lists from pages 1 and 2 (staleness check). Browser clicks in the viewport are real now: `POST /api/browser/action {action:"click_at", x, y}` + UI maps clicks to page coordinates.
- Earn: `earnings.radar()` uses Firecrawl when a key is set, else falls back to DuckDuckGo (`app/engine/firecrawl.search_web`). Earn is honest — catalog scores are heuristics, not income guarantees; everything is draft-only until approved.
- Web search: `search_web` — Firecrawl → free DuckDuckGo fallback, so "check global competition" gets live results even without a Firecrawl key.
- Browser viewport clicks: `POST /api/browser/action {action:"click_at", x, y}` (CSS px in the 1280×800 screenshot). The UI computes these coords from the viewport on click (`RightPane.tsx`). `GET /api/browser/state` returns a fresh screenshot each poll.

## Commands

```powershell
npm install                  # node deps
npm run dev                  # Electron + Vite dev server + backend
npm run build:ui             # build frontend/dist (relative assets)
npm start                    # Electron in production mode (self-managed backend)
npm run typecheck            # tsc --noEmit
npm run build:installer      # rebuild Setup.exe (NSIS)
npm run build:portable       # rebuild win-unpacked only

# backend checks (from repo root)
& "C:\Users\saura\agentdesk\installer\runtime\python\python.exe" -m compileall -q backend\app
```

Validation already run successfully in this snapshot: `python -m compileall -q app`,
`npx tsc --noEmit`, `npm run build:ui`, clean silent install, launch via desktop shortcut,
`/api/health` OK, UI API calls (`/api/settings`, `/api/sessions`, `/api/browser/state`,
`/api/computer/state`) all 200 with no console errors.

## Rebuilding the installer after fixes

```powershell
# 1. apply source edits, then verify
npm run typecheck
npm run build:ui

# 2. recreate the runtime bundle (only needed once; ~2.4 GB)
powershell -ExecutionPolicy Bypass -File scripts\stage-runtime.ps1

# 3. build Setup.exe -> release\AgentDesk-Setup-0.1.0.exe
npm run build:installer
```

`stage-runtime.ps1` copies from an installed AgentDesk at
`%LOCALAPPDATA%\Programs\AgentDesk\resources\runtime` when available, otherwise from the
original uv Python / venv site-packages / ms-playwright / `~/.llama` model paths on the
build machine. Edit `electron/main.js` env paths if you relocate the runtime.

### Silent install / repair

Always pass the directory explicitly — NSIS otherwise reuses a previous install location
and can leave broken shortcuts:

```powershell
$setup  = "<extracted>\INSTALLER\AgentDesk-Setup-0.1.0.exe"
$target = "$env:LOCALAPPDATA\Programs\AgentDesk"
$p = Start-Process -FilePath $setup -ArgumentList @('/S', "/D=$target") -PassThru -Wait
$p.ExitCode   # expect 0
```

Check shortcut target with:

```powershell
$lnk = [Environment]::GetFolderPath('Desktop') + '\AgentDesk.lnk'
(New-Object -ComObject WScript.Shell).CreateShortcut($lnk).TargetPath
```

## Installed layout (for hot-fixing without rebuilding)

Default install: `%LOCALAPPDATA%\Programs\AgentDesk`. `asar` is disabled — all files are plain.

- `resources\app\electron\main.js` — launcher/port (edit + restart)
- `resources\app\frontend\dist\` — built UI
- `resources\backend\app\` — backend source (edit + restart)
- `resources\runtime\python\` — Python + site-packages; add packages with
  `python.exe -m pip install <pkg>`
- `resources\runtime\playwright\` — bundled Chromium
- `resources\runtime\models\` — tiny-brain GGUF
- `resources\docs\MODIFYING.md` — full installed-app edit guide

Data lives in `%APPDATA%\AgentDesk\data` and survives reinstall/uninstall.

## Known optional blockers / integrations

These need credentials or extra tools and are not required for the app to run:
OpenRouter / OpenCode API keys, Firecrawl key, Vercel AI Gateway token, Kaggle CLI, and
Ollama for the default local model. Cloud/browser modes work without Ollama.

The installer is **unsigned** — SmartScreen shows "More info → Run anyway" on a fresh machine.
