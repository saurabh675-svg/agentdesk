import { spawn } from "node:child_process"
import { createRequire } from "node:module"
import process from "node:process"

const require = createRequire(import.meta.url)
const electronPath = require("electron")
const prod = process.argv.includes("--prod")

let vite = null
if (!prod) {
  const { createServer } = await import("vite")
  try {
    vite = await createServer({ configFile: "./vite.config.ts" })
    await vite.listen()
    console.log("[agentdesk] Vite ready on http://127.0.0.1:5173")
  } catch {
    vite = null
    console.log("[agentdesk] Vite already running on http://127.0.0.1:5173")
  }
}

const child = spawn(electronPath, [".", ...(prod ? [] : ["--dev"])], {
  stdio: "inherit",
  env: { ...process.env, AGENTDESK_DEV: prod ? "0" : "1" },
})

child.on("exit", async (code) => {
  if (vite) await vite.close()
  process.exit(code ?? 0)
})
