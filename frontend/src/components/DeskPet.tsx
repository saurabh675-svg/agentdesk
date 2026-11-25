import { useEffect, useState } from "react"
import { Eye, Lightbulb, MessageSquare, Moon, Sun, X, Zap } from "lucide-react"
import { api } from "../api"

interface PetStatus {
  enabled: boolean
  state: "watching" | "learning" | "idle" | "sleeping"
  current_app: string
  current_title: string
  thought: string
  insights: string[]
}

export default function DeskPet({ onAsk }: { onAsk?: (prompt: string) => void }) {
  const [status, setStatus] = useState<PetStatus>({
    enabled: true,
    state: "watching",
    current_app: "Desktop",
    current_title: "Active Workspace",
    thought: "Observing your desktop to learn your workflows...",
    insights: [],
  })
  const [collapsed, setCollapsed] = useState(false)
  const [showInsights, setShowInsights] = useState(false)
  const [dismissed, setDismissed] = useState(false)

  // Poll status every 8 seconds
  useEffect(() => {
    if (dismissed) return
    let active = true

    const fetchStatus = async () => {
      try {
        const data = await api.get<PetStatus>("/api/pet/status")
        if (active) setStatus(data)
      } catch {
        // backend loading
      }
    }

    fetchStatus()
    const timer = setInterval(fetchStatus, 8000)
    return () => {
      active = false
      clearInterval(timer)
    }
  }, [dismissed])

  if (dismissed || !status.enabled) {
    return (
      <button
        className="deskpet-restore-pill" aria-label="Summon DeskPet companion"
        onClick={() => {
          setDismissed(false)
          api.post("/api/pet/toggle", {}).catch(() => undefined)
        }}
        title="Summon DeskPet Companion"
      >
        🐾 Summon Pet
      </button>
    )
  }

  const toggleSleep = async () => {
    try {
      const res = await api.post<PetStatus>("/api/pet/sleep", {})
      setStatus(res)
    } catch {
      // ignore
    }
  }

  const eyeColor =
    status.state === "learning"
      ? "#63d29a"
      : status.state === "sleeping"
        ? "#5f6a7e"
        : status.state === "watching"
          ? "#7c9cff"
          : "#e0b15c"

  return (
    <div className={`deskpet-widget ${collapsed ? "collapsed" : ""} ${status.state}`}>
      {/* Speech Thought Bubble */}
      {!collapsed && (
        <div className="deskpet-bubble">
          <div className="deskpet-bubble-header">
            <span className="deskpet-tag">
              <Eye size={10} /> {status.current_app}
            </span>
            <div className="deskpet-actions">
              <button
                className="deskpet-icon-btn"
                title={status.state === "sleeping" ? "Wake Pet" : "Sleep"}
                onClick={toggleSleep}
              >
                {status.state === "sleeping" ? <Sun size={11} /> : <Moon size={11} />}
              </button>
              <button
                className="deskpet-icon-btn"
                title="Workflow Insights"
                onClick={() => setShowInsights(!showInsights)}
              >
                <Lightbulb size={11} />
              </button>
              <button
                className="deskpet-icon-btn"
                title="Collapse"
                onClick={() => setCollapsed(true)}
              >
                <X size={11} />
              </button>
            </div>
          </div>

          {showInsights ? (
            <div className="deskpet-insights-box">
              <strong>💡 Learned Habits:</strong>
              <ul>
                {status.insights.length > 0 ? (
                  status.insights.slice(-4).map((ins, idx) => <li key={idx}>{ins}</li>)
                ) : (
                  <li>Watching your tasks... habits will appear here!</li>
                )}
              </ul>
            </div>
          ) : (
            <div className="deskpet-thought">
              <p>{status.thought}</p>
              <div className="deskpet-prompt-actions">
                <button
                  className="deskpet-quick-ask"
                  onClick={() =>
                    onAsk?.(`Based on what I am doing in ${status.current_app} (${status.current_title}), help me optimize this task.`)
                  }
                >
                  <MessageSquare size={10} /> Ask AgentDesk about this
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* CyberPet Animated Avatar */}
      <div
        className="deskpet-avatar"
        onClick={() => setCollapsed(!collapsed)}
        title={`${status.current_app} · ${status.state.toUpperCase()}`}
      >
        <svg viewBox="0 0 100 100" className="deskpet-svg">
          {/* Pet Body */}
          <rect x="15" y="15" width="70" height="70" rx="28" fill="url(#petGrad)" stroke="rgba(124,156,255,0.4)" strokeWidth="2.5" />
          {/* Cyber Ears */}
          <polygon points="20,20 10,2 35,16" fill="#1b243b" stroke="rgba(124,156,255,0.5)" strokeWidth="2" />
          <polygon points="80,20 90,2 65,16" fill="#1b243b" stroke="rgba(124,156,255,0.5)" strokeWidth="2" />
          {/* Glowing Eyes */}
          {status.state === "sleeping" ? (
            <>
              <line x1="30" y1="48" x2="44" y2="48" stroke={eyeColor} strokeWidth="4" strokeLinecap="round" />
              <line x1="56" y1="48" x2="70" y2="48" stroke={eyeColor} strokeWidth="4" strokeLinecap="round" />
            </>
          ) : (
            <>
              <ellipse cx="37" cy="46" rx="7" ry="9" fill={eyeColor} className="pet-eye" />
              <ellipse cx="63" cy="46" rx="7" ry="9" fill={eyeColor} className="pet-eye" />
              <circle cx="39" cy="43" r="2.5" fill="#ffffff" />
              <circle cx="65" cy="43" r="2.5" fill="#ffffff" />
            </>
          )}
          {/* Cyber Cheek Blush */}
          <circle cx="26" cy="56" r="3.5" fill="rgba(224,122,134,0.45)" />
          <circle cx="74" cy="56" r="3.5" fill="rgba(224,122,134,0.45)" />
          {/* Small Smile */}
          <path d="M 44 60 Q 50 64 56 60" stroke="rgba(255,255,255,0.7)" strokeWidth="2.5" fill="none" strokeLinecap="round" />
          <defs>
            <linearGradient id="petGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#1a2238" />
              <stop offset="100%" stopColor="#0c111d" />
            </linearGradient>
          </defs>
        </svg>
        <span className={`deskpet-status-dot ${status.state}`} />
      </div>
    </div>
  )
}
