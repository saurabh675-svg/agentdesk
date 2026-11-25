# Modifying the installed AgentDesk

The installer does **not** seal the app inside an archive. `asar` is disabled, so all files are
plain files on disk and can be edited after installation.

## Where things are installed

Default (per-user install): `C:\Users\<you>\AppData\Local\Programs\AgentDesk`

You can choose a different folder during setup. Inside the install folder:

| Path | What it is |
| --- | --- |
| `AgentDesk.exe` | Launcher |
| `resources\app\electron\main.js` | Electron main process / backend launcher |
| `resources\app\frontend\dist\` | Built React UI |
| `resources\backend\app\` | FastAPI backend source (editable) |
| `resources\backend\requirements.txt` | Frozen Python dependency list |
| `resources\runtime\python\` | Python 3.11 + all site-packages (fastapi, uvicorn, playwright, llama-cpp, …) |
| `resources\runtime\playwright\` | Chromium + headless shell used by the built-in browser |
| `resources\runtime\models\` | Tiny-brain GGUF model |
| `resources\docs\` | README, SETUP, this file |

Your data is **separate** so reinstalls/upgrades keep it:

`C:\Users\<you>\AppData\Roaming\AgentDesk\data\`

It contains `settings.json`, `agentdesk.db`, `agent_memory.db`, `earnings.db`, `plans.json`,
`skills\`, `uploads\` and `browser-profile\`. To migrate from the source project, copy your old
`agentdesk\data\*` into that folder while AgentDesk is closed.

## Common changes

### Edit backend behaviour
1. Close AgentDesk.
2. Edit files under `resources\backend\app\`.
3. Start AgentDesk again. There is no compile step.

### Add a Python package
```bat
cd /d "C:\Users\<you>\AppData\Local\Programs\AgentDesk\resources\runtime\python"
python.exe -m pip install <package>
```
The bundled interpreter is self-contained; do not install into a different Python.

### Change UI text/logic
The installed `frontend\dist` is already built. For source edits, work in the original project:

```bat
cd C:\Users\saura\agentdesk
npm run build:ui
```

Then copy `frontend\dist\*` over `resources\app\frontend\dist\` in the install folder.
Node.js is only needed for rebuilding the UI, not for running the installed app.

### Change the backend port
The port `8756` appears in two places:
- `resources\app\electron\main.js` → `BACKEND_PORT`
- `frontend\src\api.ts` → `API_BASE` (requires a UI rebuild)

Keep them in sync.

### Reset data
Close AgentDesk, rename/delete `C:\Users\<you>\AppData\Roaming\AgentDesk\data`, then start again.
A fresh default `data` folder is created automatically.

### Uninstall
Use Settings → Apps → AgentDesk → Uninstall. `deleteAppDataOnUninstall` is **off**, so your
settings, chat history, skills and browser logins are preserved.
