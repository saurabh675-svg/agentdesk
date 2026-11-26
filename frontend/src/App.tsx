import { Component, useCallback, useEffect, useRef, useState } from "react"
import type { ErrorInfo, ReactNode } from "react"
import { AlertTriangle, Info, Loader2, X, Zap, Terminal, Globe, Cpu, Settings2, RefreshCw } from "lucide-react"
import Sidebar from "./components/Sidebar"
import ChatPane from "./components/ChatPane"
import RightPane from "./components/RightPane"
import SettingsModal from "./components/SettingsModal"
import FloatingPet from "./components/FloatingPet"
import { api, socketProtocols, wsUrl } from "./api"
import { t as tr } from "./i18n"
import type {
  ApprovalRequest,
  Attachment,
  BrowserPayload,
  ChatMode,
  Mission,
  Message,
  RightTab,
  Session,
  Settings,
  ToolRun,
  WorkspacePayload,
} from "./types"

const EMPTY_BROWSER: BrowserPayload = {
  state: { url: "about:blank", title: "", can_back: false, can_forward: false },
  frame: null,
}

function baseName(path: string | null): string {
  if (!path) return "No folder"
  return path.replace(/[\\/]+$/, "").split(/[\\/]/).pop() || path
}

interface ErrorBoundaryProps { children: ReactNode; onReset?: () => void }
interface ErrorBoundaryState { error: Error | null }

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null }
  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error }
  }
  componentDidCatch(error: Error, info: ErrorInfo) {
    // Render error caught before the UI goes blank. Log it where the user
    // can find it (DevTools) — we have no remote logger yet.
    // eslint-disable-next-line no-console
    console.error("[AgentDesk] render error boundary caught", error, info)
  }
  reset = () => {
    this.setState({ error: null })
    this.props.onReset?.()
  }
  render() {
    if (this.state.error) {
      return (
        <div className="splash" role="alert">
          <div className="splash-mark" style={{ color: "#e26b6b" }}>⚠</div>
          <div className="splash-title">Something went wrong</div>
          <div className="splash-error">{this.state.error.message || String(this.state.error)}</div>
          <button className="btn allow" onClick={this.reset}>Reload</button>
        </div>
      )
    }
    return this.props.children
  }
}

export default function App() {
  const [settings, setSettings] = useState<Settings | null>(null)
  const [workspace, setWorkspace] = useState<WorkspacePayload>({ path: null, exists: false, tree: [] })
  const [sessions, setSessions] = useState<Session[]>([])
  const [sessionId, setSessionId] = useState<number | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [liveText, setLiveText] = useState("")
  const [streaming, setStreaming] = useState(false)
  const [toolRuns, setToolRuns] = useState<ToolRun[]>([])
  const [approval, setApproval] = useState<ApprovalRequest | null>(null)
  const [browser, setBrowser] = useState<BrowserPayload>(EMPTY_BROWSER)
  const [computerFrame, setComputerFrame] = useState<string | null>(null)
  const [computerSize, setComputerSize] = useState<{ width: number; height: number } | null>(null)
  const [rightTab, setRightTab] = useState<RightTab>("browser")
  const [openFile, setOpenFile] = useState<{ path: string; content: string } | null>(null)
  const [showSettings, setShowSettings] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [paletteQuery, setPaletteQuery] = useState("")
  const [notice, setNotice] = useState<string | null>(null)
  const [attachments, setAttachments] = useState<Attachment[]>([])
  const [chatMode, setChatMode] = useState<ChatMode>(() => {
    const saved = localStorage.getItem("agentdesk.chatMode")
    if (saved === "hard") return "auto"
    return saved === "saved" || saved === "auto" || saved === "chatgpt" || saved === "gemini" ? saved : "auto"
  })
  const [missionRefresh, setMissionRefresh] = useState(0)
  const [wsState, setWsState] = useState<"connecting" | "open" | "closed">("closed")
  const [booted, setBooted] = useState(false)
  const [bootError, setBootError] = useState<string | null>(null)
  const [rightWidth, setRightWidth] = useState<number>(() => {
    const saved = Number(localStorage.getItem("agentdesk.rightWidth"))
    return saved >= 24 && saved <= 60 ? saved : 38
  })

  useEffect(() => {
    if (sessionId != null) localStorage.setItem("agentdesk.sessionId", String(sessionId))
  }, [sessionId])

  const [engineStatus, setEngineStatus] = useState<{
    vulkan: "active" | "idle" | "error"
    cline: "active" | "idle" | "error"
    openclaw: "active" | "idle" | "error"
    pad: "active" | "idle" | "error"
    browser: "active" | "idle" | "error"
  }>({ vulkan: "idle", cline: "idle", openclaw: "idle", pad: "idle", browser: "idle" })
  const [healthDot, setHealthDot] = useState<"ok" | "degraded" | "down">("ok")

  // Derive engine pills + health dot from the real diagnostics snapshot.
  useEffect(() => {
    let cancelled = false
    const poll = async () => {
      try {
        const snap = await api.get<{ local_model?: { available?: boolean }; browser?: { url?: string }; providers?: Record<string, unknown>; watchdog_recent?: unknown[] }>("/api/diagnostics")
        if (cancelled) return
        if (snap.local_model?.available) setEngineStatus((s) => ({ ...s, vulkan: "active" }))
        if (snap.browser?.url && snap.browser.url !== "about:blank") setEngineStatus((s) => ({ ...s, browser: "active" }))
        const errors = Array.isArray(snap.watchdog_recent) ? snap.watchdog_recent.length : 0
        api.get<{ spans?: { name: string; duration_ms?: number; durationMs?: number }[] }>("/api/diagnostics/spans").then((sp) => { if (!cancelled && Array.isArray(sp.spans)) setSpans(sp.spans.slice(-6)) }).catch(() => undefined)
        setHealthDot(errors > 3 ? "degraded" : "ok")
      } catch {
        if (!cancelled) setHealthDot("down")
      }
    }
    void poll()
    const id = window.setInterval(poll, 30000)
    return () => { cancelled = true; window.clearInterval(id) }
  }, [])
  const [compactToast, setCompactToast] = useState<string | null>(null)
  const [modelBanner, setModelBanner] = useState<string | null>(null)
  const [spans, setSpans] = useState<{ name: string; duration_ms?: number; durationMs?: number }[]>([])
  const [routeNotice, setRouteNotice] = useState<string | null>(null)

  const wsRef = useRef<WebSocket | null>(null)
  const chatModeRef = useRef(chatMode)
  const pendingMission = useRef<{ sessionId: number; prompt: string } | null>(null)

  const refreshWorkspace = useCallback(async () => {
    try {
      setWorkspace(await api.get<WorkspacePayload>("/api/workspace"))
    } catch {
      // ignore transient failures
    }
  }, [])

  const refreshSessions = useCallback(async () => {
    try {
      setSessions(await api.get<Session[]>("/api/sessions"))
    } catch {
      // ignore transient failures
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    const boot = async (attempt = 0) => {
      try {
        const [settingsData, workspaceData, sessionList, browserData] = await Promise.all([
          api.get<Settings>("/api/settings"),
          api.get<WorkspacePayload>("/api/workspace"),
          api.get<Session[]>("/api/sessions"),
          api.get<BrowserPayload>("/api/browser/state"),
        ])
        api
          .get<{ frame: string | null }>("/api/computer/state")
          .then((data) => !cancelled && setComputerFrame(data.frame))
          .catch(() => undefined)
        if (cancelled) return
        setSettings(settingsData)
        setWorkspace(workspaceData)
        setBrowser(browserData)
        let list = sessionList
        if (list.length === 0) {
          const created = await api.post<Session>("/api/sessions", { title: tr("newChat") })
          list = [created]
        }
        setSessions(list)
        const remembered = Number(localStorage.getItem("agentdesk.sessionId"))
        const restored = list.find((session) => session.id === remembered)
        setSessionId(restored ? restored.id : list[0].id)
        setBooted(true)
      } catch (err) {
        if (cancelled) return
        if (attempt < 15) {
          setTimeout(() => boot(attempt + 1), 800)
        } else {
          setBootError(`Cannot reach the AgentDesk backend: ${err instanceof Error ? err.message : err}`)
        }
      }
    }
    boot()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault()
        setPaletteOpen((open) => !open)
        setPaletteQuery("")
      }
      if (event.key === "Escape") setPaletteOpen(false)
    }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [])

  useEffect(() => {
    if (!sessionId) return
    let disposed = false
    let retry: ReturnType<typeof setTimeout> | undefined

    setMessages([])
    setLiveText("")
    setStreaming(false)
    setToolRuns([])
    setApproval(null)

    api
      .get<Message[]>(`/api/sessions/${sessionId}/messages`)
      .then((data) => !disposed && setMessages(data))
      .catch(() => undefined)

    const handle = (event: Record<string, any>) => {
      switch (event.type) {
        case "ready":
          setWsState("open")
          if (pendingMission.current?.sessionId === sessionId) {
            socketSendMission(pendingMission.current.prompt)
            pendingMission.current = null
          }
          break
        case "browser_frame":
          setBrowser({ state: event.state, frame: event.frame })
          break
        case "computer_frame":
          if (event.frame) setComputerFrame(event.frame)
          break
        case "message_start":
          setStreaming(true)
          setLiveText("")
          break
        case "token":
          setLiveText((current) => current + (event.text ?? event.token ?? ""))
          break
        case "message_commit":
          setMessages((current) => [...current, event.message])
          setLiveText("")
          break
        case "message_end":
          setMessages((current) =>
            current.some((item) => item.id === event.message.id) ? current : [...current, event.message],
          )
          setLiveText("")
          setStreaming(false)
          refreshSessions()
          break
        case "tool_call":
          // Update engine status based on tool name
          if (typeof event.name === "string") {
            if (event.name.startsWith("browser_") || event.name === "ask_chatbot") setRightTab("browser")
            if (event.name.startsWith("computer_")) setRightTab("screen")
            if (event.name === "cline_run") setEngineStatus(s => ({ ...s, cline: "active" }))
            if (event.name === "openclaw_run") setEngineStatus(s => ({ ...s, openclaw: "active" }))
            if (event.name === "power_automate_flow") setEngineStatus(s => ({ ...s, pad: "active" }))
            if (event.name.startsWith("browser_")) setEngineStatus(s => ({ ...s, browser: "active" }))
          }
          setToolRuns((current) => [
            ...current,
            { id: event.id, name: event.name, args: event.args ?? {}, status: "running" },
          ])
          break
        case "tool_call_partial": {
          const id = String(event.id || "")
          const argsText = String(event.args_text || "")
          setToolRuns((current) => current.some(r => r.id === id) ? current.map(r => r.id === id ? { ...r, name: event.name || r.name, argsText } : r) : [...current, { id, name: String(event.name || "tool"), args: {}, argsText, status: "running" }])
          break
        }
        case "tool_result":
          setToolRuns((current) =>
            current.map((run) =>
              run.id === event.id
                ? { ...run, status: "done", ok: event.ok, result: event.result }
                : run,
            ),
          )
          break
        case "approval_request":
          setApproval({ id: event.id, command: event.command })
          break
        case "notice":
          setNotice(event.message)
          if (/^using /i.test(String(event.message || ""))) setRouteNotice(event.message)
          if (/stopped early|trying the next|provider unavailable/i.test(String(event.message || ""))) setLiveText("")
          if (/built-in browser|chromium window|browser window/i.test(event.message)) setRightTab("browser")
          break
        case "file_changed":
          refreshWorkspace()
          break
        case "error":
          setError(event.message)
          setStreaming(false)
          setLiveText("")
          api
            .get<Message[]>(`/api/sessions/${sessionId}/messages`)
            .then(setMessages)
            .catch(() => undefined)
          break
        case "stopped":
          setStreaming(false)
          setLiveText("")
          setApproval(null)
          break
        case "done":
          setStreaming(false)
          setToolRuns([])
          setApproval(null)
          setEngineStatus({ vulkan: "idle", cline: "idle", openclaw: "idle", pad: "idle", browser: "idle" })
          refreshSessions()
          api
            .get<Message[]>(`/api/sessions/${sessionId}/messages`)
            .then(setMessages)
            .catch(() => undefined)
          break
        case "compacted":
          setCompactToast(`✦ Compacted ${event.message_count ?? ""} messages`)
          setTimeout(() => setCompactToast(null), 3500)
          api
            .get<Message[]>(`/api/sessions/${sessionId}/messages`)
            .then(setMessages)
            .catch(() => undefined)
          break
        case "model_switched":
          setModelBanner(`⚡ Model → ${event.label || event.model || "updated"}`)
          setTimeout(() => setModelBanner(null), 4000)
          break
        case "rubric_evaluation": {
          const result = String(event.result || "")
          const icon = result === "satisfied" ? "✅" : result === "needs_revision" ? "✍️" : "⚠️"
          setModelBanner(`${icon} Rubric ${result} — ${String(event.explanation || "").slice(0, 90)}`)
          setTimeout(() => setModelBanner(null), 4200)
          break
        }
      }
    }

    const socketSendMission = (prompt: string) => {
      wsRef.current?.send(JSON.stringify({ type: "chat", text: prompt, mode: chatModeRef.current }))
      setMessages((current) => [...current, { id: -Date.now(), role: "user", content: prompt, created_at: Date.now() / 1000 }])
      setStreaming(true)
    }
    const connect = () => {
      if (disposed) return
      setWsState("connecting")
      const socket = new WebSocket(wsUrl(sessionId), socketProtocols())
      wsRef.current = socket
      socket.onopen = () => !disposed && setWsState("open")
      socket.onmessage = (messageEvent) => {
        if (disposed) return
        try {
          handle(JSON.parse(messageEvent.data))
        } catch {
          // ignore malformed events
        }
      }
      socket.onclose = () => {
        if (disposed) return
        setWsState("closed")
        wsRef.current = null
        retry = setTimeout(connect, 1200)
      }
      socket.onerror = () => socket.close()
    }

    connect()
    return () => {
      disposed = true
      if (retry) clearTimeout(retry)
      wsRef.current?.close()
      wsRef.current = null
    }
  }, [sessionId, refreshSessions, refreshWorkspace])

  useEffect(() => {
    if (!error) return
    const timer = setTimeout(() => setError(null), 6000)
    return () => clearTimeout(timer)
  }, [error])

  useEffect(() => {
    if (!notice) return
    const timer = setTimeout(() => setNotice(null), 12000)
    return () => clearTimeout(timer)
  }, [notice])

  const changeMode = (mode: ChatMode) => {
    chatModeRef.current = mode
    setChatMode(mode)
    localStorage.setItem("agentdesk.chatMode", mode)
  }

  const exportChat = async () => {
    if (!sessionId) return
    try {
      const payload = await api.get<{ session: Session; messages: Message[] }>(
        `/api/sessions/${sessionId}/export`,
      )
      const title = payload.session?.title || "AgentDesk transcript"
      const body = payload.messages
        .map((message) => `## ${message.role.charAt(0).toUpperCase() + message.role.slice(1)}\n\n${message.content}\n\n`)
        .join("")
      const url = URL.createObjectURL(new Blob([body], { type: "text/markdown" }))
      const link = document.createElement("a")
      link.href = url
      link.download = `${title.replace(/[^a-z0-9-_ ]/gi, "-").trim() || "session"}.md`
      link.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  const uploadFiles = async (files: FileList | null) => {
    if (!files || files.length === 0) return
    try {
      const form = new FormData()
      for (let i = 0; i < files.length; i++) form.append("files", files[i])
      const uploaded = await api.upload<Attachment[]>("/api/uploads/files", form)
      setAttachments((current) => [...current, ...uploaded])
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  const runMission = (mission: Mission) => {
    if (!mission.session_id) {
      setError("Pinned mission has no session. Run it from that chat first.")
      return
    }
    if (mission.session_id === sessionId) {
      send(mission.prompt, [])
      return
    }
    pendingMission.current = { sessionId: mission.session_id, prompt: mission.prompt }
    setSessionId(mission.session_id)
  }

  const pinCurrentMission = async () => {
    if (!sessionId) {
      setError("Select a session first")
      return
    }
    const session = sessions.find((s) => s.id === sessionId)
    const prompt = [...messages].reverse().find((message) => message.role === "user")?.content
    if (!prompt?.trim()) {
      setError("Send a task before pinning it.")
      return
    }
    try {
      await api.post("/api/missions", {
        name: session?.title || "Pinned task",
        session_id: sessionId,
        prompt,
      })
      setMissionRefresh((value) => value + 1)
      setNotice("Task pinned to Mission")
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  const send = (text: string, attachmentsList?: Attachment[]) => {
    const socket = wsRef.current
    if (!socket || socket.readyState !== WebSocket.OPEN || streaming) return
    setRouteNotice(null)
    const attached = attachmentsList ?? attachments
    socket.send(
      JSON.stringify({
        type: "chat",
        text,
        mode: chatMode,
        attachments: attached.length ? attached : undefined,
      }),
    )
    setAttachments([])
    setMessages((current) => [
      ...current,
      { id: -Date.now(), role: "user", content: text, created_at: Date.now() / 1000 },
    ])
    setLiveText("")
    setToolRuns([])
    setStreaming(true)
    setApproval(null)
  }

  const stop = () => {
    wsRef.current?.send(JSON.stringify({ type: "stop" }))
    setStreaming(false)
  }

  const respondApproval = (approved: boolean, persist = false) => {
    if (!approval) return
    wsRef.current?.send(
      JSON.stringify({ type: "approval", id: approval.id, approved, persist }),
    )
    setApproval(null)
  }

  const newSession = async () => {
    try {
      const created = await api.post<Session>("/api/sessions", { title: tr("newChat") })
      setSessions((current) => [created, ...current])
      setSessionId(created.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  const deleteSession = async (id: number) => {
    try {
      await api.delete(`/api/sessions/${id}`)
      const remaining = sessions.filter((session) => session.id !== id)
      setSessions(remaining)
      if (id === sessionId) {
        if (remaining.length > 0) setSessionId(remaining[0].id)
        else {
          const created = await api.post<Session>("/api/sessions", { title: tr("newChat") })
          setSessions([created])
          setSessionId(created.id)
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  const pickFolder = async () => {
    let path: string | null = null
    if (window.desktop) path = await window.desktop.openFolder()
    else path = window.prompt("Workspace folder path")
    if (!path) return
    try {
      const payload = await api.post<WorkspacePayload>("/api/workspace", { path })
      setWorkspace(payload)
      if (sessionId) {
        const updated = await api.patch<Session>(`/api/sessions/${sessionId}`, { workspace: payload.path })
        setSessions((current) => current.map((item) => (item.id === updated.id ? updated : item)))
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  const openFileByPath = async (path: string) => {
    try {
      const file = await api.get<{ path: string; content: string }>(
        `/api/workspace/file?path=${encodeURIComponent(path)}`,
      )
      setOpenFile({ path: file.path, content: file.content })
      setRightTab("file")
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  const browserAction = async (body: Record<string, unknown>) => {
    try {
      const payload = await api.post<BrowserPayload>("/api/browser/action", body)
      setBrowser(payload)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  const captureScreen = async () => {
    try {
      const payload = await api.post<{ frame: string | null }>("/api/computer/capture")
      setComputerFrame(payload.frame)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  const refreshComputerSize = () => {
    api
      .get<{ width: number; height: number }>("/api/computer/size")
      .then(setComputerSize)
      .catch(() => undefined)
  }

  const saveSettings = async (patch: Partial<Settings>) => {
    const updated = await api.put<Settings>("/api/settings", patch)
    setSettings(updated)
    setShowSettings(false)
  }

  const startDrag = (event: React.PointerEvent) => {
    event.preventDefault()
    const startX = event.clientX
    const startWidth = rightWidth
    document.body.classList.add("dragging")
    const move = (moveEvent: PointerEvent) => {
      const delta = ((startX - moveEvent.clientX) / window.innerWidth) * 100
      const next = Math.min(60, Math.max(24, startWidth + delta))
      setRightWidth(next)
      localStorage.setItem("agentdesk.rightWidth", String(next))
    }
    const up = () => {
      document.body.classList.remove("dragging")
      window.removeEventListener("pointermove", move)
      window.removeEventListener("pointerup", up)
    }
    window.addEventListener("pointermove", move)
    window.addEventListener("pointerup", up)
  }

  if (!booted || !settings) {
    return (
      <div className="splash">
        <div className="splash-mark">◆</div>
        <div className="splash-title">AgentDesk</div>
        {bootError ? (
          <>
            <div className="splash-error">{bootError}</div>
            <button className="btn allow" onClick={() => window.location.reload()}>
              Retry
            </button>
          </>
        ) : (
          <div className="splash-sub">
            <Loader2 size={14} className="spin" /> starting local engine…
          </div>
        )}
      </div>
    )
  }

  const currentSession = sessions.find((session) => session.id === sessionId)
  const savedGatewayKeys = Object.entries(settings.keys || {}).filter(
    ([gateway, key]) => gateway !== "local" && Boolean(key),
  )
  const autoHint = savedGatewayKeys.length
    ? `local → ${savedGatewayKeys.map(([gateway]) => gateway).join(" → ")}${settings.allow_webchat_fallback ? " → browser" : ""}`
    : settings.allow_webchat_fallback
      ? "local → browser tabs"
      : "local model only"
  const activeModel =
    chatMode === "auto"
      ? "Auto route"
      : chatMode === "chatgpt"
        ? "ChatGPT · browser"
        : chatMode === "gemini"
          ? "Gemini · browser"
          : settings.model || "local"

  return (
    <ErrorBoundary onReset={() => window.location.reload()}>
    <div className="app">
      <Sidebar
        sessions={sessions}
        currentSession={sessionId}
        workspace={workspace}
        wsState={wsState}
        onSelectSession={setSessionId}
        onNewSession={newSession}
        onDeleteSession={deleteSession}
        onPickFolder={pickFolder}
        onRefreshTree={refreshWorkspace}
        onOpenFile={openFileByPath}
        onOpenSettings={() => setShowSettings(true)}
      />

      <div className="chat-column">
        <ChatPane
          sessionTitle={currentSession?.title ?? tr("newChat")}
          model={activeModel}
          workspaceName={baseName(workspace.path)}
          wsState={wsState}
          messages={messages}
          liveText={liveText}
          streaming={streaming}
          toolRuns={toolRuns}
          approval={approval}
          mode={chatMode}
          autoHint={autoHint}
          routeNotice={routeNotice}
          attachments={attachments}
          onModeChange={changeMode}
          onFilesSelected={uploadFiles}
          onSend={send}
          onRemoveAttachment={(id) => setAttachments((current) => current.filter((a) => a.id !== id))}
          onExport={exportChat}
          onStop={stop}
          onApprove={respondApproval}
          onOpenSettings={() => setShowSettings(true)}
        />

        {/* Engine Status Bar */}
        <div className="engine-status-bar" aria-label={`Backend health: ${healthDot}`}>
          <span className={`engine-pill ${healthDot === "ok" ? "active" : healthDot === "degraded" ? "idle" : "error"}`} title={`Backend: ${healthDot}`}>
            <span className="engine-pill-dot" /> {healthDot === "ok" ? "Backend ok" : healthDot === "degraded" ? "Backend degraded" : "Backend down"}
          </span>
          {([
            { key: "vulkan", icon: "⚡", label: "Vulkan" },
            { key: "cline", icon: "💻", label: "Cline" },
            { key: "openclaw", icon: "🤖", label: "OpenClaw" },
            { key: "pad", icon: "⚙️", label: "PAD" },
            { key: "browser", icon: "🌐", label: "Browser" },
          ] as const).map(({ key, icon, label }) => (
            <span
              key={key}
              className={`engine-pill ${engineStatus[key]}`}
              title={`${label}: ${engineStatus[key]}`}
            >
              <span className="engine-pill-dot" />
              {icon} {label}
            </span>
          ))}
        </div>

        {spans.length > 0 ? (
          <div className="waterfall" aria-label="Telemetry waterfall (last spans)">
            {spans.map((sp, i) => {
              const ms = sp.duration_ms ?? sp.durationMs ?? 1
              const max = Math.max(1, ...spans.map((x) => x.duration_ms ?? x.durationMs ?? 1))
              const w = Math.min(100, Math.max(1, (ms / max) * 100))
              return (
                <div key={i} className="span-row" title={`${sp.name} ${Math.round(ms)}ms`}>
                  <span className="span-name">{sp.name}</span>
                  <span className="span-bar" style={{ width: `${w}%` }} />
                  <span>{Math.round(ms)}ms</span>
                </div>
              )
            })}
          </div>
        ) : null}

        {/* Compact toast */}
        {compactToast && <div className="compact-toast">{compactToast}</div>}
        {/* Model switched banner */}
        {modelBanner && <div className="model-switched-banner">{modelBanner}</div>}
      </div>

      <div className="splitter" onPointerDown={startDrag} />

      <div className="right" style={{ width: `${rightWidth}%` }}>
        <RightPane
          browser={browser}
          tab={rightTab}
          openFile={openFile}
          computerFrame={computerFrame}
          computerSize={computerSize}
          browserHeadless={settings.browser_headless}
          sessionId={sessionId}
          missionRefresh={missionRefresh}
          currentSessionId={sessionId}
          agentBusy={streaming}
          onTabChange={setRightTab}
          onAskAgent={(prompt) => {
            if (streaming) {
              setError("Agent is busy — wait for the current task to finish.")
              return
            }
            setRightTab("earn")
            send(prompt)
          }}
          onBrowserAction={browserAction}
          onCaptureScreen={captureScreen}
          onRefreshComputerSize={refreshComputerSize}
          onPinCurrent={pinCurrentMission}
          onRunMission={runMission}
          onCloseFile={() => {
            setOpenFile(null)
            setRightTab("browser")
          }}
        />
      </div>

      {showSettings && (
        <SettingsModal
          settings={settings}
          onClose={() => setShowSettings(false)}
          onSave={saveSettings}
          onSettingsChanged={setSettings}
        />
      )}

      {notice && (
        <div className="toast notice">
          <Info size={14} />
          <span>{notice}</span>
          <button className="icon-button" onClick={() => setNotice(null)}>
            <X size={13} />
          </button>
        </div>
      )}

      {error && (
        <div className="toast">
          <AlertTriangle size={14} />
          <span>{error}</span>
          <button className="icon-button" onClick={() => setError(null)}>
            <X size={13} />
          </button>
        </div>
      )}
      {paletteOpen && (
        <div className="palette-overlay" onClick={() => setPaletteOpen(false)}>
          <div className="palette" onClick={(event) => event.stopPropagation()}>
            <input
              autoFocus
              value={paletteQuery}
              onChange={(event) => setPaletteQuery(event.target.value)}
              placeholder="Type a command..."
            />
            <div className="palette-list">
              {[
                { label: tr("newChat"), action: () => { newSession(); setPaletteOpen(false) } },
                { label: "Open settings", action: () => { setShowSettings(true); setPaletteOpen(false) } },
                { label: "Tab: Browser", action: () => { setRightTab("browser"); setPaletteOpen(false) } },
                { label: "Tab: Screen", action: () => { setRightTab("screen"); setPaletteOpen(false) } },
                { label: "Tab: Terminal", action: () => { setRightTab("terminal"); setPaletteOpen(false) } },
                { label: "Tab: File", action: () => { setRightTab("file"); setPaletteOpen(false) } },
                { label: "Tab: Mission", action: () => { setRightTab("mission"); setPaletteOpen(false) } },
                { label: "Tab: Earn", action: () => { setRightTab("earn"); setPaletteOpen(false) } },
                { label: "Tab: Security", action: () => { setRightTab("security"); setPaletteOpen(false) } },
                { label: "Export chat", action: () => { exportChat(); setPaletteOpen(false) } },
                { label: "Refresh workspace", action: () => { refreshWorkspace(); setPaletteOpen(false) } },
                {
                  label: "Create backup",
                  action: () => {
                    api.post("/api/backup/create").catch((err) => setError(err instanceof Error ? err.message : String(err)))
                    setPaletteOpen(false)
                  },
                },
              ]
                .filter((item) => item.label.toLowerCase().includes(paletteQuery.toLowerCase()))
                .map((item) => (
                  <button key={item.label} onClick={item.action}>
                    {item.label}
                  </button>
                ))}
            </div>
          </div>
        </div>
      )}
      {/* Floating expert pet that drifts over the app (replaces the docked pet) */}
      <FloatingPet />
    </div>
    </ErrorBoundary>
  )
}
