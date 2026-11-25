const { app, BrowserWindow, dialog, ipcMain, shell, Menu, Tray, nativeImage, globalShortcut } = require("electron")
const { spawn } = require("node:child_process")
const path = require("node:path")
const fs = require("node:fs")
const { randomBytes } = require("node:crypto")
const { pathToFileURL } = require("node:url")

const apiToken = randomBytes(32).toString("hex")

const BACKEND_PORT = 8756
const isDev = !app.isPackaged && process.env.AGENTDESK_DEV === "1"
let backendProcess = null
let mainWindow = null
let tray = null
let isQuitting = false
let closeHintShown = false
let currentHotkey = "CommandOrControl+Shift+A"

function dataDirPath() {
  return app.isPackaged
    ? path.join(app.getPath("userData"), "data")
    : path.join(app.getAppPath(), "data")
}
function windowStatePath() {
  return path.join(app.getPath("userData"), "window.json")
}
function readWindowBounds() {
  try {
    const raw = fs.readFileSync(windowStatePath(), "utf-8")
    const parsed = JSON.parse(raw)
    if (
      Number.isFinite(parsed.width) &&
      Number.isFinite(parsed.height) &&
      parsed.width >= 1100 &&
      parsed.height >= 700
    ) {
      return { width: parsed.width, height: parsed.height, x: parsed.x, y: parsed.y }
    }
  } catch {}
  return null
}
function saveWindowBounds() {
  if (!mainWindow) return
  try {
    const bounds = mainWindow.getBounds()
    fs.mkdirSync(path.dirname(windowStatePath()), { recursive: true })
    fs.writeFileSync(windowStatePath(), JSON.stringify(bounds), "utf-8")
  } catch {}
}
function readHotkeyFromSettings() {
  try {
    const settingsPath = path.join(dataDirPath(), "settings.json")
    const raw = fs.readFileSync(settingsPath, "utf-8")
    const parsed = JSON.parse(raw)
    const candidate = parsed.hotkey || parsed.global_hotkey
    if (typeof candidate === "string" && candidate.trim().length > 0) {
      currentHotkey = candidate.trim()
    }
  } catch {}
}
async function portInUse() {
  try {
    const response = await fetch(`http://127.0.0.1:${BACKEND_PORT}/api/health`, {
      signal: AbortSignal.timeout(800),
    })
    return response.status < 500
  } catch {
    return false
  }
}
async function showBackendError(title, detail) {
  const logPath = path.join(dataDirPath(), "backend.log")
  const result = await dialog.showMessageBox(mainWindow || undefined, {
    type: "error",
    title,
    message: detail,
    detail: `Backend log: ${logPath}`,
    buttons: ["Open log", "Quit"],
    defaultId: 1,
  })
  if (result.response === 0) {
    try {
      fs.mkdirSync(dataDirPath(), { recursive: true })
      if (!fs.existsSync(logPath)) fs.writeFileSync(logPath, "")
      await shell.openPath(logPath)
    } catch {}
  }
}

function createTray() {
  const iconBase64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAZElEQVQ4T2NkoBAwUqifYVQDGEeNejBqAC7D/zMwMDDBxFkYGBhSGBgYXjIQBoT+n2FgYDiAzwB8Ghh+/f/PwMBwhpHgAMIGoGt69P8fAx51uA3AZwDuMIIe4Bg1gGE0gEEDAEb2IxZg088pAAAAAElFTkSuQmCC"
  const icon = nativeImage.createFromDataURL(iconBase64)
  tray = new Tray(icon)
  tray.setToolTip("AgentDesk — Personal AI Agent")

  const contextMenu = Menu.buildFromTemplate([
    {
      label: "Show AgentDesk",
      click: () => {
        if (mainWindow) {
          mainWindow.show()
          mainWindow.focus()
        }
      },
    },
    {
      label: "Toggle Visibility (Ctrl+Shift+A)",
      click: () => toggleWindowVisibility(),
    },
    { type: "separator" },
    {
      label: "Quit AgentDesk",
      click: () => {
        isQuitting = true
        app.quit()
      },
    },
  ])
  tray.setContextMenu(contextMenu)
  tray.on("click", () => {
    toggleWindowVisibility()
  })
}

function toggleWindowVisibility() {
  if (!mainWindow) return
  if (mainWindow.isVisible() && mainWindow.isFocused()) {
    mainWindow.hide()
  } else {
    mainWindow.show()
    mainWindow.focus()
  }
}

function packagedPath(...parts) {
  return path.join(process.resourcesPath, ...parts)
}

function backendExecutable() {
  if (app.isPackaged) {
    return packagedPath(
      "runtime",
      "python",
      process.platform === "win32" ? "python.exe" : "python",
    )
  }
  const root = app.getAppPath()
  if (process.platform === "win32") {
    return path.join(root, "backend", ".venv", "Scripts", "python.exe")
  }
  return path.join(root, "backend", ".venv", "bin", "python")
}

async function backendIsUp() {
  try {
    const response = await fetch(`http://127.0.0.1:${BACKEND_PORT}/api/health`, {
      signal: AbortSignal.timeout(1200),
      headers: { Authorization: `Bearer ${apiToken}` },
    })
    return response.ok
  } catch {
    return false
  }
}

async function startBackend() {
  const python = backendExecutable()
  if (!fs.existsSync(python)) {
    dialog.showErrorBox(
      "Backend not found",
      `Expected a Python environment at:\n${python}\n\nRun the setup steps in README.md first.`,
    )
    return false
  }
  const cwd = app.isPackaged ? packagedPath("backend") : path.join(app.getAppPath(), "backend")
  // In development/production-from-source keep everything in the project folder so the
  // SQLite DB, settings, skills, MCP config and browser logins are easy to inspect and back up.
  const dataDir = app.isPackaged
    ? path.join(app.getPath("userData"), "data")
    : path.join(app.getAppPath(), "data")
  fs.mkdirSync(dataDir, { recursive: true })

  const backendEnv = {
    ...process.env,
    AGENTDESK_DATA: dataDir,
    AGENTDESK_API_TOKEN: apiToken,
    PYTHONIOENCODING: "utf-8",
  }
  if (app.isPackaged) {
    backendEnv.AGENTDESK_PACKAGED = "1"
    backendEnv.PLAYWRIGHT_BROWSERS_PATH = packagedPath("runtime", "playwright")
    const tinyModel = packagedPath("runtime", "models", "qwen2.5-1.5b-instruct-q4_k_m.gguf")
    if (fs.existsSync(tinyModel)) backendEnv.TINY_BRAIN_MODEL = tinyModel
    // The bundled interpreter is self-contained; an inherited venv would break it.
    delete backendEnv.PYTHONHOME
    delete backendEnv.PYTHONPATH
  }

  backendProcess = spawn(
    python,
    ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", String(BACKEND_PORT)],
    {
      cwd,
      windowsHide: true,
      env: backendEnv,
      stdio: ["ignore", "pipe", "pipe"],
    },
  )
  backendProcess.once("error", (error) => {
    console.error("[agentdesk] backend launch failed", error.message)
    backendProcess = null
  })
  // Keep a durable backend log so startup/crash failures are diagnosable.
  let backendLog = null
  try {
    backendLog = fs.createWriteStream(path.join(dataDir, "backend.log"), { flags: "a" })
  } catch {}
  backendProcess.stdout.on("data", (chunk) => {
    backendLog?.write(chunk)
    process.stdout.write(`[backend] ${chunk}`)
  })
  backendProcess.stderr.on("data", (chunk) => {
    backendLog?.write(chunk)
    process.stderr.write(`[backend] ${chunk}`)
  })
  backendProcess.on("exit", (code) => {
    console.log(`[agentdesk] backend exited with code ${code}`)
    backendProcess = null
  })

  const deadline = Date.now() + 120_000
  while (Date.now() < deadline) {
    if (!backendProcess) break
    if (await backendIsUp()) return true
    await new Promise((resolve) => setTimeout(resolve, 400))
  }
  const occupied = await portInUse()
  const message = occupied
    ? "Another process is already listening on port 8756. It may be a different AgentDesk install or a stale backend. Quit it and relaunch AgentDesk."
    : "AgentDesk could not start its private backend. Quit older AgentDesk instances and check whether port 8756 is in use."
  await showBackendError("Backend unavailable", message)
  return false
}

function createWindow() {
  const savedBounds = readWindowBounds()
  mainWindow = new BrowserWindow({
    width: savedBounds?.width ?? 1500,
    height: savedBounds?.height ?? 950,
    x: savedBounds?.x,
    y: savedBounds?.y,
    minWidth: 1100,
    minHeight: 700,
    backgroundColor: "#0b0e14",
    title: "AgentDesk",
    show: false,
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      additionalArguments: [`--agentdesk-api-token=${apiToken}`],
    },
  })

  mainWindow.once("ready-to-show", () => mainWindow.show())

  if (isDev) {
    mainWindow.loadURL("http://127.0.0.1:5173")
  } else {
    mainWindow.loadFile(path.join(app.getAppPath(), "frontend", "dist", "index.html"))
  }

  mainWindow.webContents.on("will-navigate", (event) => event.preventDefault())
  mainWindow.webContents.session.setPermissionRequestHandler((_webContents, _permission, callback) => callback(false))
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (isWebUrl(url)) void shell.openExternal(url).catch(console.error)
    return { action: "deny" }
  })

  mainWindow.on("resize", saveWindowBounds)
  mainWindow.on("move", saveWindowBounds)
  mainWindow.on("close", (event) => {
    saveWindowBounds()
    if (!isQuitting) {
      event.preventDefault()
      mainWindow.hide()
      if (!closeHintShown && tray) {
        closeHintShown = true
        try {
          tray.displayBalloon({
            iconType: "info",
            title: "AgentDesk is still running",
            content: "Reopen from the tray icon (or Ctrl+Shift+A). Choose Quit in the tray menu to exit.",
          })
        } catch {}
      }
      return false
    }
  })

  mainWindow.on("closed", () => {
    mainWindow = null
  })
}

function isWebUrl(value) {
  try {
    return ["http:", "https:"].includes(new URL(value).protocol)
  } catch {
    return false
  }
}

function isTrustedFrame(event) {
  const expected = isDev
    ? "http://127.0.0.1:5173/"
    : pathToFileURL(path.join(app.getAppPath(), "frontend", "dist", "index.html")).href
  return event.sender === mainWindow?.webContents && event.senderFrame?.url === expected
}

ipcMain.handle("dialog:openFolder", async (event) => {
  if (!isTrustedFrame(event)) return null
  const result = await dialog.showOpenDialog(mainWindow, { properties: ["openDirectory"] })
  return result.canceled ? null : result.filePaths[0]
})

ipcMain.handle("app:openExternal", async (event, url) => {
  if (isTrustedFrame(event) && typeof url === "string" && isWebUrl(url)) await shell.openExternal(url)
})

ipcMain.handle("app:quit", async (event) => {
  if (!isTrustedFrame(event)) return false
  isQuitting = true
  saveWindowBounds()
  app.quit()
  return true
})

ipcMain.handle("app:restart", async (event) => {
  if (!isTrustedFrame(event)) return false
  isQuitting = false
  saveWindowBounds()
  app.relaunch()
  app.exit(0)
  return true
})

ipcMain.handle("app:getBackendLog", async (event, maxLines = 200) => {
  if (!isTrustedFrame(event)) return ""
  try {
    const logPath = path.join(dataDirPath(), "backend.log")
    if (!fs.existsSync(logPath)) return ""
    const lines = fs.readFileSync(logPath, "utf-8").split(/\r?\n/)
    return lines.slice(-Math.max(1, Math.min(maxLines, 2000))).join("\n")
  } catch {
    return ""
  }
})

ipcMain.handle("app:openBackendLog", async (event) => {
  if (!isTrustedFrame(event)) return false
  try {
    const logPath = path.join(dataDirPath(), "backend.log")
    fs.mkdirSync(dataDirPath(), { recursive: true })
    if (!fs.existsSync(logPath)) fs.writeFileSync(logPath, "")
    await shell.openPath(logPath)
    return true
  } catch {
    return false
  }
})

if (!app.requestSingleInstanceLock()) {
  isQuitting = true
  app.quit()
} else {
  app.on("second-instance", () => {
    mainWindow?.show()
    mainWindow?.focus()
  })

app.whenReady().then(async () => {
  Menu.setApplicationMenu(null)
  readHotkeyFromSettings()
  createTray()
  try {
    globalShortcut.register(currentHotkey, () => {
      toggleWindowVisibility()
    })
  } catch (err) {
    console.error("Global shortcut registration failed:", err)
  }

  if (!await startBackend()) {
    app.quit()
    return
  }
  createWindow()
  setupAutoUpdate()

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
    else mainWindow?.show()
  })
})
}

app.on("before-quit", () => {
  isQuitting = true
  saveWindowBounds()
  try {
    globalShortcut.unregisterAll()
  } catch {}
  if (tray) {
    tray.destroy()
    tray = null
  }
  if (backendProcess) {
    backendProcess.kill()
    backendProcess = null
  }
})

// Auto-update (electron-updater, optional — no-op when dep is absent).
function setupAutoUpdate() {
  if (!app.isPackaged) return
  try {
    const { autoUpdater } = require("electron-updater")
    autoUpdater.autoDownload = false
    autoUpdater.on("update-available", async (info) => {
      const result = await dialog.showMessageBox(mainWindow || undefined, {
        type: "info", title: "Update available", message: `AgentDesk ${info.version} is available.`, buttons: ["Download", "Later"], defaultId: 0,
      })
      if (result.response === 0) void autoUpdater.downloadUpdate().catch(console.error)
    })
    autoUpdater.on("update-downloaded", async () => {
      const result = await dialog.showMessageBox(mainWindow || undefined, {
        type: "info", title: "Update ready", message: "Restart AgentDesk to install the update.", buttons: ["Restart", "Later"], defaultId: 0,
      })
      if (result.response === 0) { isQuitting = true; autoUpdater.quitAndInstall() }
    })
    void autoUpdater.checkForUpdates().catch(console.error)
  } catch (err) {
    console.log("[agentdesk] electron-updater not available:", err.message)
  }
}

app.on("window-all-closed", () => {
  if (isQuitting && process.platform !== "darwin") app.quit()
})
