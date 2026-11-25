import { useEffect, useState, type MouseEvent as ReactMouseEvent } from "react"
import {
  ArrowLeft,
  ArrowRight,
  Camera,
  ExternalLink,
  FileText,
  Globe,
  ListTodo,
  Monitor,
  RefreshCw,
  RotateCw,
  Shield,
  ShieldAlert,
  Terminal as TerminalIcon,
  TrendingUp,
  X,
} from "lucide-react"
import { api } from "../api"
import type { ApprovalEvent, Automation, BrowserPayload, Mission, RightTab } from "../types"
import EarnPane from "./EarnPane"
import TerminalView from "./TerminalView"

interface Props {
  browser: BrowserPayload
  tab: RightTab
  openFile: { path: string; content: string } | null
  computerFrame: string | null
  computerSize: { width: number; height: number } | null
  browserHeadless: boolean
  sessionId: number | null
  missionRefresh: number
  currentSessionId: number | null
  agentBusy: boolean
  onTabChange: (tab: RightTab) => void
  onAskAgent: (prompt: string) => void
  onBrowserAction: (body: Record<string, unknown>) => Promise<void> | void
  onPinCurrent: () => void
  onRunMission: (mission: Mission) => void
  onCloseFile: () => void
  onCaptureScreen: () => Promise<void> | void
  onRefreshComputerSize: () => void
}

export default function RightPane(props: Props) {
  const [url, setUrl] = useState("")
  const [challenge, setChallenge] = useState<{
    active: boolean
    label?: string
    message?: string
    kind?: string
  } | null>(null)
  const [challengeWaiting, setChallengeWaiting] = useState(false)
  const [loading, setLoading] = useState(false)
  const [screenBusy, setScreenBusy] = useState(false)
  const [automations, setAutomations] = useState<Automation[]>([])
  const [missions, setMissions] = useState<Mission[]>([])
  const [automationBusy, setAutomationBusy] = useState(false)
  const [approvals, setApprovals] = useState<ApprovalEvent[]>([])
  const [approvalsBusy, setApprovalsBusy] = useState(false)
  const [approvalFilter, setApprovalFilter] = useState("")

  useEffect(() => {
    if (props.tab !== "mission") return
    let cancelled = false
    api.get<Mission[]>("/api/missions").then((list) => {
      if (!cancelled) setMissions(list)
    }).catch(() => undefined)
    api
      .get<Automation[]>("/api/automations")
      .then((list) => {
        if (!cancelled) setAutomations(list)
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [props.tab, props.missionRefresh])

  useEffect(() => {
    if (props.tab !== "security") return
    let cancelled = false
    setApprovalsBusy(true)
    api
      .get<ApprovalEvent[]>("/api/approvals?limit=100")
      .then((list) => {
        if (!cancelled) setApprovals(list)
      })
      .catch(() => undefined)
      .finally(() => {
        if (!cancelled) setApprovalsBusy(false)
      })
    return () => {
      cancelled = true
    }
  }, [props.tab])

  useEffect(() => {
    if (props.browser.state.url && props.browser.state.url !== "about:blank") {
      setUrl(props.browser.state.url)
    }
  }, [props.browser.state.url])

  // Poll for bot / human-verification challenges so the user can take over.
  useEffect(() => {
    if (props.tab !== "browser") return
    let alive = true
    const check = async () => {
      try {
        const res = await api.get<{ active: boolean; challenge?: { label?: string; message?: string; kind?: string } }>(
          "/api/browser/challenge",
        )
        if (alive) setChallenge(res.active ? { active: true, ...(res.challenge ?? {}) } : null)
      } catch {
        /* backend not ready */
      }
    }
    void check()
    const timer = setInterval(check, 2500)
    return () => {
      alive = false
      clearInterval(timer)
    }
  }, [props.tab])

  // While a challenge is up, ask the backend to wait for the human to finish.
  useEffect(() => {
    if (!challenge?.active || challengeWaiting) return
    setChallengeWaiting(true)
    api
      .post<{ cleared: boolean }>("/api/browser/challenge/wait", { timeout: 300 })
      .then((res) => {
        if (res?.cleared) setChallenge(null)
      })
      .catch(() => undefined)
      .finally(() => setChallengeWaiting(false))
  }, [challenge?.active, challengeWaiting])

  useEffect(() => {
    if (props.tab !== "screen") return
    props.onRefreshComputerSize()
    if (props.computerFrame) return
    let cancelled = false
    setScreenBusy(true)
    Promise.resolve(props.onCaptureScreen())
      .catch(() => undefined)
      .finally(() => {
        if (!cancelled) setScreenBusy(false)
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [props.tab])

  const run = async (body: Record<string, unknown>) => {
    setLoading(true)
    try {
      await props.onBrowserAction(body)
    } finally {
      setLoading(false)
    }
  }

  // Map a click on the visible screenshot to exact viewport coordinates (CSS px,
  // 1:1 with the 1280x800 page screenshot), properly subtracting letterbox/pillarbox bars.
  const clickViewport = (event: ReactMouseEvent<HTMLImageElement>) => {
    const img = event.currentTarget
    if (!img || !props.browser.frame) return
    const rect = img.getBoundingClientRect()
    if (rect.width <= 0 || rect.height <= 0) return

    const natW = 1280
    const natH = 800
    const containerRatio = rect.width / rect.height
    const imgRatio = natW / natH

    let renW = rect.width
    let renH = rect.height
    let offX = 0
    let offY = 0

    if (containerRatio > imgRatio) {
      renW = rect.height * imgRatio
      offX = (rect.width - renW) / 2
    } else {
      renH = rect.width / imgRatio
      offY = (rect.height - renH) / 2
    }

    const clkX = event.clientX - rect.left - offX
    const clkY = event.clientY - rect.top - offY
    if (clkX < 0 || clkX > renW || clkY < 0 || clkY > renH) return

    const x = Math.round((clkX / renW) * natW)
    const y = Math.round((clkY / renH) * natH)
    void run({ action: "click_at", x, y })
  }

  const handleWheel = (event: React.WheelEvent) => {
    const deltaY = event.deltaY > 0 ? 300 : -300
    void run({ action: "scroll", delta_y: deltaY })
  }

  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === "Enter") {
      void run({ action: "key_press", key: "Enter" })
    } else if (event.key === "Backspace") {
      void run({ action: "key_press", key: "Backspace" })
    } else if (event.key.length === 1) {
      void run({ action: "type_direct", text: event.key })
    }
  }

  const capture = async () => {
    setScreenBusy(true)
    try {
      await props.onCaptureScreen()
      props.onRefreshComputerSize()
    } finally {
      setScreenBusy(false)
    }
  }

  const fileName = props.openFile?.path.split(/[\\/]/).pop() ?? ""

  return (
    <section className="right-pane">
      <div className="right-tabs">
        <button
          className={`right-tab ${props.tab === "browser" ? "active" : ""}`}
          onClick={() => props.onTabChange("browser")}
          title="Browser"
        >
          <Globe size={13} /> Browser
        </button>
        <button
          className={`right-tab ${props.tab === "screen" ? "active" : ""}`}
          onClick={() => props.onTabChange("screen")}
          title="Desktop screen"
        >
          <Monitor size={13} /> Screen
        </button>
        <button
          className={`right-tab ${props.tab === "terminal" ? "active" : ""}`}
          onClick={() => props.onTabChange("terminal")}
          title="Terminal"
        >
          <TerminalIcon size={13} /> Terminal
        </button>
        <button
          className={`right-tab ${props.tab === "file" ? "active" : ""}`}
          onClick={() => props.onTabChange("file")}
          title="File preview"
        >
          <FileText size={13} /> File
        </button>
        <button
          className={`right-tab ${props.tab === "mission" ? "active" : ""}`}
          onClick={() => props.onTabChange("mission")}
          title="Missions: automated tasks"
        >
          <ListTodo size={13} /> Mission
        </button>
        <button
          className={`right-tab ${props.tab === "security" ? "active" : ""}`}
          onClick={() => props.onTabChange("security")}
          title="Approval audit log and shell safety"
        >
          <Shield size={13} /> Security
        </button>
        <button
          className={`right-tab ${props.tab === "earn" ? "active" : ""}`}
          onClick={() => props.onTabChange("earn")}
          title="Global earnings: opportunities, ventures, income and recursive learning"
        >
          <TrendingUp size={13} /> Earn
          {props.agentBusy && <span className="tab-busy" title="Agent working" />}
        </button>
        <span className="right-spacer" />
        <span
          className="right-badge"
          title="The browser switches to a visible window while ChatGPT/Gemini sign-in is needed"
        >
          {loading ? <RotateCw size={11} className="spin" /> : <Monitor size={11} />}
          {(props.browser.state.headless ?? props.browserHeadless) ? "headless" : "windowed"}
        </span>
      </div>

      {props.tab === "browser" && (
        <>
          {challenge?.active && (
            <div className="browser-challenge" role="alert">
              <div className="browser-challenge-icon">
                <ShieldAlert size={16} />
              </div>
              <div className="browser-challenge-body">
                <strong>{challenge.label ?? "Human verification needed"}</strong>
                <span>
                  {challenge.message ??
                    "This site is asking a human to confirm. Finish the check in the browser window - the agent resumes by itself."}
                </span>
              </div>
              <button
                className="browser-challenge-action"
                onClick={() => {
                  setChallenge(null)
                  void run({ action: "focus" })
                }}
                title="Bring the browser window to the front"
              >
                Show me
              </button>
            </div>
          )}
          <div className="browser-toolbar">
            <button className="icon-button" onClick={() => run({ action: "back" })} title="Back">
              <ArrowLeft size={14} />
            </button>
            <button className="icon-button" onClick={() => run({ action: "forward" })} title="Forward">
              <ArrowRight size={14} />
            </button>
            <button className="icon-button" onClick={() => run({ action: "reload" })} title="Reload">
              <RotateCw size={14} />
            </button>
            <form
              className="url-form"
              onSubmit={(event) => {
                event.preventDefault()
                if (url.trim()) run({ action: "navigate", url: url.trim() })
              }}
            >
              <input
                value={url}
                onChange={(event) => setUrl(event.target.value)}
                placeholder="Enter a URL or search…"
                spellCheck={false}
              />
            </form>
            <button
              className="icon-button"
              title="Open in system browser"
              onClick={() => {
                const target = props.browser.state.url
                if (target && target.startsWith("http")) window.desktop?.openExternal(target)
              }}
            >
              <ExternalLink size={14} />
            </button>
          </div>

          <div
            className="browser-view"
            tabIndex={0}
            onWheel={handleWheel}
            onKeyDown={handleKeyDown}
            style={{ outline: "none" }}
          >
            {props.browser.frame ? (
              <img
                src={props.browser.frame}
                alt="Browser viewport"
                draggable={false}
                onClick={clickViewport}
                style={{ cursor: "crosshair" }}
                title="Click the visible page (agent maps it to a page click)"
              />
            ) : (
              <div className="browser-empty">
                <Globe size={34} />
                <h3>Browser is idle</h3>
                <p>
                  Ask the agent to open a page, or type a URL above. Every navigation and click is
                  visible here.
                </p>
              </div>
            )}
          </div>

          <div className="browser-status">
            <span className="status-title">{props.browser.state.title || "Untitled"}</span>
            <span className="status-url">{props.browser.state.url}</span>
          </div>
        </>
      )}

      {props.tab === "screen" && (
        <>
          <div className="browser-toolbar">
            <button className="mini-button" onClick={capture} disabled={screenBusy} aria-label="Capture screen">
              <Camera size={12} /> {screenBusy ? "capturing…" : "capture screen"}
            </button>
            <span className="screen-size">
              {props.computerSize
                ? `${props.computerSize.width} × ${props.computerSize.height}`
                : "desktop"}
            </span>
            <span className="right-spacer" />
            <span className="screen-note">agent mouse/keyboard needs approval</span>
          </div>
          <div
            className="browser-view"
            tabIndex={0}
            onWheel={handleWheel}
            onKeyDown={handleKeyDown}
            style={{ outline: "none" }}
          >
            {props.computerFrame ? (
              <img src={props.computerFrame} alt="Desktop screen" draggable={false} />
            ) : (
              <div className="browser-empty">
                <Monitor size={34} />
                <h3>Desktop screen</h3>
                <p>
                  The agent can see and control this screen for native apps. Ask it to take a
                  screenshot, or press capture above.
                </p>
              </div>
            )}
          </div>
          <div className="browser-status">
            <span className="status-title">Local desktop</span>
            <span className="status-url">mouse · keyboard · screenshots</span>
          </div>
        </>
      )}

      {props.tab === "terminal" &&
        (props.sessionId ? (
          <TerminalView sessionId={props.sessionId} />
        ) : (
          <div className="browser-empty">
            <TerminalIcon size={34} />
            <h3>No session</h3>
            <p>Create a chat session to open a terminal.</p>
          </div>
        ))}

      {props.tab === "file" && (
        <div className="file-view">
          {props.openFile ? (
            <>
              <div className="file-header">
                <FileText size={13} />
                <span title={props.openFile.path}>{fileName}</span>
                <span className="file-path">{props.openFile.path}</span>
                <button className="icon-button" onClick={props.onCloseFile} title="Close file" aria-label="Close file">
                  <X size={14} />
                </button>
              </div>
              <pre className="file-content">{props.openFile.content}</pre>
            </>
          ) : (
            <div className="browser-empty">
              <FileText size={34} />
              <h3>No file open</h3>
              <p>Pick a file from the tree in the left panel to preview it here.</p>
            </div>
          )}
        </div>
      )}

      {props.tab === "mission" && (
        <div className="mission-view">
          <div className="mission-head">
            <ListTodo size={13} />
            Mission · Automated tasks
          </div>
          <p className="mission-hint">
            Automations re-run the same AgentDesk prompt on a schedule while the app is open. Create
            jobs in Settings → General → Automations.
          </p>
          <div className="mission-actions">
            <button className="btn pin" onClick={props.onPinCurrent} disabled={!props.currentSessionId}>
              Pin current task
            </button>
          </div>
          {missions.map((mission) => (
            <div className="automation-row" key={mission.id}>
              <span>{mission.name}</span>
              <button className="btn" disabled={props.agentBusy || !mission.prompt} onClick={() => props.onRunMission(mission)}>Run</button>
              <button className="btn" title="Unpin mission" onClick={async () => {
                await api.delete(`/api/missions/${mission.id}`)
                setMissions((current) => current.filter((item) => item.id !== mission.id))
              }}><X size={12} /></button>
            </div>
          ))}
          <div className="automation-list">
            {automations.map((automation) => (
              <div className="automation-row" key={automation.id}>
                <div className="automation-main">
                  <div className="automation-name">
                    {automation.name}
                    <span className="automation-status">{automation.status}</span>
                  </div>
                  <div className="automation-meta">
                    every {automation.interval_minutes} min
                    {automation.last_status ? ` · last: ${automation.last_status}` : ""}
                  </div>
                </div>
                <button
                  className="icon-button tiny cancel"
                  title="Cancel automation"
                  disabled={automationBusy}
                  onClick={() => {
                    setAutomationBusy(true)
                    api
                      .post(`/api/automations/${automation.id}/cancel`)
                      .then(() => api.get<Automation[]>("/api/automations").then(setAutomations))
                      .catch(() => undefined)
                      .finally(() => setAutomationBusy(false))
                  }}
                >
                  <X size={12} />
                </button>
              </div>
            ))}
            {automations.length === 0 && (
              <div className="empty-hint">No automations yet. Create one in Settings → General → Automations.</div>
            )}
          </div>
          <button
            className="btn"
            onClick={() => {
              setAutomationBusy(true)
              api
                .get<Automation[]>("/api/automations")
                .then(setAutomations)
                .finally(() => setAutomationBusy(false))
            }}
            disabled={automationBusy}
          >
            <RefreshCw size={10} /> Refresh
          </button>
        </div>
      )}
      {props.tab === "earn" && (
        <EarnPane
          agentBusy={props.agentBusy}
          onAskAgent={props.onAskAgent}
          onOpenBrowser={(targetUrl) => {
            void props.onBrowserAction({ action: "navigate", url: targetUrl })
            props.onTabChange("browser")
          }}
        />
      )}
      {props.tab === "security" && (
        <div className="security-view">
          <div className="mission-head">
            <Shield size={13} /> Approval audit log
          </div>
          <p className="mission-hint">
            Every shell command is classified and logged. Dangerous commands always require approval.
          </p>
          <button
            className="btn"
            onClick={() => {
              setApprovalsBusy(true)
              api
                .get<ApprovalEvent[]>("/api/approvals?limit=100")
                .then(setApprovals)
                .catch(() => undefined)
                .finally(() => setApprovalsBusy(false))
            }}
            disabled={approvalsBusy}
          >
            <RefreshCw size={10} /> Refresh
          </button>
          <input className="file-filter-input" placeholder="Filter by tool / level…" value={approvalFilter} onChange={(e) => setApprovalFilter(e.target.value)} aria-label="Filter approvals" style={{ marginTop: 8 }} />
          <div className="automation-list">
            {approvals.filter((i) => !approvalFilter || `${i.tool} ${i.level} ${i.action}`.toLowerCase().includes(approvalFilter.toLowerCase())).map((item) => (
              <div className="automation-row" key={item.id}>
                <div className="automation-main">
                  <div className="automation-name">
                    {item.tool}
                    <span className={`automation-status ${item.approved ? "ok" : "denied"}`}>
                      {item.approved ? (item.auto ? "auto" : "approved") : "denied"}
                    </span>
                  </div>
                  <div className="automation-meta">
                    {item.level} · {new Date(item.created_at * 1000).toLocaleString()}
                  </div>
                  <div className="security-command">{item.action}</div>
                </div>
              </div>
            ))}
            {approvals.length === 0 && (
              <div className="empty-hint">No approvals logged yet.</div>
            )}
          </div>
        </div>
      )}
    </section>
  )
}
