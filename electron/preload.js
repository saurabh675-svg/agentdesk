const { contextBridge, ipcRenderer } = require("electron")

const apiToken = process.argv.find((arg) => arg.startsWith("--agentdesk-api-token="))?.split("=")[1] || ""

contextBridge.exposeInMainWorld("desktop", {
  isDesktop: true,
  apiToken,
  openFolder: () => ipcRenderer.invoke("dialog:openFolder"),
  openExternal: (url) => ipcRenderer.invoke("app:openExternal", url),
  quit: () => ipcRenderer.invoke("app:quit"),
  restart: () => ipcRenderer.invoke("app:restart"),
  getBackendLog: (maxLines) => ipcRenderer.invoke("app:getBackendLog", maxLines ?? 200),
  openBackendLog: () => ipcRenderer.invoke("app:openBackendLog"),
})
