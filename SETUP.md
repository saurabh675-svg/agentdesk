# AgentDesk — Setup Guide

For the 0.3.1 release, start the app from the Windows installer or `npm start`. The Electron app issues the backend authentication token, so opening the dev frontend directly or sending unauthenticated requests to the API will fail. Run `npm run typecheck` and `installer\runtime\python\python.exe -B scripts\verify_release.py` for source verification. The checklist in `RELIABILITY.md` covers live Windows installation and provider tests.

This is a three-panel agentic coding desktop app: **workspace / chat / browser, screen, terminal, files**, with the built-in browser for ChatGPT/Gemini/Google, a terminal, desktop automation, MCP, skills, and web search.

## Windows installer (recommended)

Build the installer once from the source project:

```powershell
cd C:\Users\saura\agentdesk
npm install
npm run build:installer
```

Run `release\AgentDesk-Setup-0.3.1.exe` and choose an install folder. The installer contains
Python 3.11 + all Python packages, Playwright Chromium, the llama.cpp server, and the tiny-brain
model, so the target machine needs **no** Node.js or Python installation. The default model is
the bundled tiny GGUF served by llama.cpp (always-on) at `http://127.0.0.1:11435`; cloud modes
(OpenRouter free, Vercel, UnoRouter, OpenCode, Pollinations, OpenAI) work without it. MCP presets
need Node on PATH (or a Node install in `C:\Program Files\nodejs`).

Installed data lives in `%APPDATA%\AgentDesk\data` and survives upgrades/uninstalls.
See `MODIFYING.md` for how to edit the installed app, add packages, or migrate old data.

## Quick start

```powershell
cd C:\Users\saura\agentdesk
npm install
npm run dev
```

The Electron window opens and:

- runs the FastAPI backend on `http://127.0.0.1:8756`
- serves the React UI from `http://127.0.0.1:5173`

First launch may take 5–20s (backend imports, Chromium, MCP install).

### Ports

| Service | URL |
| --- | --- |
| Frontend (Electron in dev) | `http://127.0.0.1:5173` |
| Backend | `http://127.0.0.1:8756` |
| Local llama.cpp model (always-on) | `http://127.0.0.1:11435` |

### Production-style run

```powershell
cd C:\Users\saura\agentdesk
npm run build:ui
npm start
```

### Standalone backend (if you want a separate backend process)

```powershell
cd C:\Users\saura\agentdesk\backend
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8756
```

### Standalone frontend (if you want a separate Vite process)

```powershell
cd C:\Users\saura\agentdesk
npx vite --host 127.0.0.1 --port 5173
```

### Electron headless (without Vite)

```powershell
cd C:\Users\saura\agentdesk
npm run start
```

## First steps after first launch

1. **Pick a folder** (`AgentDeskProjects` is default) from the sidebar.
2. **Select a model** (Settings → Model):
   - **Local (llama.cpp)** — the always-on default; the bundled GGUF model is served by
     `python -m llama_cpp.server` on `http://127.0.0.1:11435`.
   - **Hard mode:** OpenRouter free model — requires a free key from `openrouter.ai/keys`.
   - **ChatGPT / Gemini browser mode:** requires sign-in in the visible Chromium window.
3. **Optional keys** (in **Settings → General / Model / Browser**):
   - Firecrawl API key — enables agent `web_search`.
   - GitHub token — enables `github_pr_summary`.
4. **Try a first chat:** “Explain this codebase” or “Research on the web”.

## Data & config

```text
agentdesk/data/
├── agentdesk.db          SQLite sessions/messages
├── settings.json         provider, model, keys, workspace
├── mcp.json              MCP server list (Fetch seeded, Playwright enabled)
├── skills/               docx, pptx, xlsx, pdf, web-research, ...
├── uploads/              chat file attachments
├── automations.json      persistent background jobs
└── browser-profile/      persistent Chromium profile
```

## Verification

After `npm run dev`:

- Open `http://127.0.0.1:5173` (Electron opens it automatically).
- **Settings** gear → **Model/Browser/General/Skills/MCP**.
- **Browser tab** should show the Chromium toolbar; `GET http://127.0.0.1:8756/api/health` → `{"ok": true}`.
- **General tab** shows Automations and Firecrawl/GitHub keys.
- **Skills tab** lists `docx`, `pptx`, `xlsx`, `pdf`, `desktop-automation`, `verify-changes`, `web-research`.
- **MCP tab** shows Fetch (`ready`) and Playwright (`ready`, ~25 `browser_*` tools).

## Troubleshooting

- **Electron fails: “please delete node_modules/electron and try installing again”**
  ```powershell
  cd C:\Users\saura\agentdesk
  Remove-Item node_modules\electron -Recurse -Force
  npm install
  ```
- **Port 5173 already in use**
  - Close other Vite servers, or
  - run `npm run dev` again (it now reuses an existing Vite on 5173 and just starts Electron).
- **Backend won’t start**
  - Check `backend/.venv\Scripts\python.exe -m uvicorn app.main:app` in `backend/`.
  - Restart Electron after touching backend files.
- **Firecrawl says “key not set”** — add key at `firecrawl.dev` and save in Settings → General.
- **Local model slow** — expected on CPU; later turns reuse context cache. For heavier/coding work use Hard mode + OpenRouter free.
- **Tiny brain (llama.cpp) won’t answer**
  - Model path: `%USERPROFILE%\.llama\qwen2.5-1.5b-instruct-q4_k_m.gguf`; override with `TINY_BRAIN_MODEL`.
  - GPU: install the Vulkan wheel from `abetlen/llama-cpp-python` (`v0.3.37-vulkan`, Windows wheel) into `backend\.venv`. Set `LLAMA_GPU_LAYERS=99` for iGPU offload (default) or `0` for CPU.

## Common workflows

- **Explain a file** — ask the agent; it reads/edits in the workspace.
- **Web research** — “Research X online” → `web_search` (Firecrawl) + browser.
- **Read attached files** — add files via the paperclip, then ask “Summarize the attachments”.
- **Recurring reports** — Settings → General → Automations → Add daily job.
- **Google Drive/Gmail/Calendar** — Settings → Browser → Open Drive/Gmail/Calendar login; browse in the Browser panel.
- **Office work** — skills `docx`, `pptx`, `xlsx`, `pdf` are installed; the agent uses normal file tools plus LibreOffice.
- **Terminal** — click Terminal in the right panel; shell commands use PowerShell PTY with a soft “allow” approval from chat.

## Roadmap / later upgrades

- Tauri/mobile shell, portable installer, dark mode, transcript export.
- Direct Google Drive/Gmail/Calendar API tools.
- MCP catalog auto-discovery + auto-install.
- Diff review/revert UI, desktop screenshot tooling.
- System tray, cross-session global context, agent delegation.

Happy building! 🚀
