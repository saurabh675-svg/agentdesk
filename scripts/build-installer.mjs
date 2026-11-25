import { execFileSync, spawnSync } from "node:child_process"
import { cpSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, statSync, writeFileSync } from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"
import { build, Platform } from "electron-builder"

const root = fileURLToPath(new URL("../", import.meta.url))
const manifest = JSON.parse(readFileSync(path.join(root, "package.json"), "utf8"))
const { name, version, description, main } = manifest
const releaseDir = path.resolve(root, process.env.AGENTDESK_RELEASE_DIR || "release")
const config = {
  ...manifest.build,
  asar: false,
  npmRebuild: false,
  directories: { output: releaseDir },
  extraResources: [],
  afterPack: ({ appOutDir }) => {
    for (const { from, to, exclude } of manifest.build.extraResources) {
      const source = path.resolve(root, from)
      const destination = path.join(appOutDir, "resources", to)
      if (statSync(source).isDirectory()) {
        // "native" is excluded from the backend copy: the same binaries are
        // already shipped as resources/native, and duplicating them would
        // add ~170 MB to the installer.
        const excluded = ["__pycache__", ...(exclude || [])]
        const result = spawnSync("robocopy.exe", [source, destination, "/E", "/R:2", "/W:1", "/NFL", "/NDL", "/NJH", "/NJS", "/NP", "/XD", ...excluded, "/XF", "*.pyc"], { stdio: "inherit" })
        if (result.error || result.status === null || result.status >= 8) {
          throw new Error(`Could not stage ${from}: ${result.error || result.status}`)
        }
      } else {
        mkdirSync(path.dirname(destination), { recursive: true })
        cpSync(source, destination)
      }
    }
  },
}

const offlineElectron = path.join(root, "installer", "build-cache", `electron-${config.electronVersion}`)
if (existsSync(path.join(offlineElectron, "electron.exe"))) config.electronDist = offlineElectron
const offlineTools = path.join(root, "installer", "build-cache", "electron-builder")
if (existsSync(offlineTools)) process.env.ELECTRON_BUILDER_CACHE ||= offlineTools
process.env.ELECTRON_BUILDER_COMPRESSION_LEVEL ||= "1"

execFileSync(process.execPath, [path.join(root, "node_modules/vite/bin/vite.js"), "build"], { cwd: root, stdio: "inherit" })
const appDir = mkdtempSync(path.join(root, "installer", "release-app-"))
try {
  writeFileSync(path.join(appDir, "package.json"), JSON.stringify({ name, version, description, main, author: "AgentDesk" }, null, 2))
  for (const file of ["electron/main.js", "electron/preload.js"]) {
    mkdirSync(path.dirname(path.join(appDir, file)), { recursive: true })
    cpSync(path.join(root, file), path.join(appDir, file))
  }
  cpSync(path.join(root, "frontend/dist"), path.join(appDir, "frontend/dist"), { recursive: true })
  await build({
    projectDir: appDir,
    targets: Platform.WINDOWS.createTarget(process.argv.includes("--directory") ? ["dir"] : ["nsis"], 1),
    config,
  })
} finally {
  rmSync(appDir, { recursive: true, force: true })
}
