import { useCallback, useEffect, useRef, useState } from "react"
import {
  BookOpen,
  Globe2,
  Loader2,
  Moon,
  Sparkles,
  Sun,
  Wrench,
  X,
} from "lucide-react"
import { api } from "../api"

interface PetStatus {
  enabled: boolean
  state: "watching" | "learning" | "idle" | "sleeping"
  current_app: string
  current_title: string
  thought: string
  insights: string[]
}

interface Source {
  title: string
  url: string
  snippet: string
  source: string
}

interface ExpertReply {
  answer: string
  sources: Source[]
  used: { web: number; knowledge: number; mcp_tools: number; mcp_called: boolean }
  provider: string
  elapsed_ms: number
}

interface Capabilities {
  mcp_servers: { id: string; name: string; status: string; tool_count: number }[]
  skills: number
  sessions: number
  knowledge: Record<string, unknown>
  mcp_tools: { name: string; description: string }[]
  web: boolean
}

type Vec = { x: number; y: number }

/** Floating DeskPet: a companion that drifts over the app and answers in any field. */
export default function FloatingPet() {
  const [status, setStatus] = useState<PetStatus | null>(null)
  const [open, setOpen] = useState(false)
  const [question, setQuestion] = useState("")
  const [reply, setReply] = useState<ExpertReply | null>(null)
  const [busy, setBusy] = useState(false)
  const [caps, setCaps] = useState<Capabilities | null>(null)
  const [pos, setPos] = useState<Vec>(() => {
    try {
      const raw = localStorage.getItem("agentdesk.pet.pos")
      if (raw) return JSON.parse(raw) as Vec
    } catch {
      /* ignore */
    }
    return { x: window.innerWidth - 96, y: window.innerHeight - 140 }
  })
  const dragState = useRef<{ offset: Vec; moved: boolean } | null>(null)
  const posRef = useRef(pos)
  posRef.current = pos

  // ---- status polling -----------------------------------------------------
  useEffect(() => {
    let active = true
    const tick = async () => {
      try {
        const data = await api.get<PetStatus>("/api/pet/status")
        if (active) setStatus(data)
      } catch {
        /* backend not ready */
      }
    }
    tick()
    const timer = setInterval(tick, 8000)
    return () => {
      active = false
      clearInterval(timer)
    }
  }, [])

  // ---- lazy capabilities --------------------------------------------------
  useEffect(() => {
    if (!open || caps) return
    api
      .get<Capabilities>("/api/pet/expert/capabilities")
      .then(setCaps)
      .catch(() => undefined)
  }, [open, caps])

  // ---- idle wandering -----------------------------------------------------
  useEffect(() => {
    if (open) return
    let raf = 0
    let last = performance.now()
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches
    if (reduce) return
    const wander = (now: number) => {
      const dt = now - last
      last = now
      if (dt > 4200 && !dragState.current) {
        const p = posRef.current
        const dx = (Math.random() - 0.5) * 160
        const dy = (Math.random() - 0.5) * 90
        const width = window.innerWidth
        const height = window.innerHeight
        setPos({
          x: Math.min(Math.max(p.x + dx, 16), width - 90),
          y: Math.min(Math.max(p.y + dy, 16), height - 100),
        })
        last = now
      }
      raf = requestAnimationFrame(wander)
    }
    raf = requestAnimationFrame(wander)
    return () => cancelAnimationFrame(raf)
  }, [open])

  // ---- persist position ---------------------------------------------------
  useEffect(() => {
    try {
      localStorage.setItem("agentdesk.pet.pos", JSON.stringify(pos))
    } catch {
      /* ignore */
    }
  }, [pos])

  const onPointerDown = useCallback((event: React.PointerEvent<HTMLDivElement>) => {
    const target = event.currentTarget
    target.setPointerCapture(event.pointerId)
    dragState.current = {
      offset: {
        x: event.clientX - posRef.current.x,
        y: event.clientY - posRef.current.y,
      },
      moved: false,
    }
  }, [])

  const onPointerMove = useCallback((event: React.PointerEvent<HTMLDivElement>) => {
    const state = dragState.current
    if (!state) return
    const dx = Math.abs(event.clientX - (state.offset.x + posRef.current.x))
    const dy = Math.abs(event.clientY - (state.offset.y + posRef.current.y))
    if (dx > 2 || dy > 2) state.moved = true
    setPos({
      x: Math.min(Math.max(event.clientX - state.offset.x, 8), window.innerWidth - 80),
      y: Math.min(Math.max(event.clientY - state.offset.y, 8), window.innerHeight - 80),
    })
  }, [])

  const onPointerUp = useCallback(() => {
    const state = dragState.current
    dragState.current = null
    if (state && !state.moved) setOpen((v) => !v)
  }, [])

  const toggleSleep = async () => {
    try {
      const res = await api.post<PetStatus>("/api/pet/sleep", {})
      setStatus(res)
    } catch {
      /* ignore */
    }
  }

  const ask = async () => {
    const text = question.trim()
    if (!text || busy) return
    setBusy(true)
    try {
      const res = await api.post<ExpertReply>("/api/pet/expert", { question: text })
      setReply(res)
    } catch {
      setReply({
        answer: "I could not reach the knowledge service. Check that the backend is running.",
        sources: [],
        used: { web: 0, knowledge: 0, mcp_tools: 0, mcp_called: false },
        provider: "error",
        elapsed_ms: 0,
      })
    } finally {
      setBusy(false)
    }
  }

  const mood = status?.state ?? "idle"
  const eye =
    mood === "learning"
      ? "#63d29a"
      : mood === "sleeping"
        ? "#5f6a7e"
        : mood === "watching"
          ? "#7c9cff"
          : "#e0b15c"

  return (
    <>
      <div
        className={`fp-shell ${open ? "open" : ""} ${mood}`}
        style={{ left: pos.x, top: pos.y }}
      >
        {open && (
          <div className="fp-panel animate-rise">
            <div className="fp-panel-head">
              <span className="fp-title">
                <Sparkles size={12} /> DeskPet Expert
              </span>
              <div className="fp-head-actions">
                <button className="fp-icon" title={mood === "sleeping" ? "Wake" : "Sleep"} onClick={toggleSleep}>
                  {mood === "sleeping" ? <Sun size={12} /> : <Moon size={12} />}
                </button>
                <button className="fp-icon" title="Close" onClick={() => setOpen(false)}>
                  <X size={12} />
                </button>
              </div>
            </div>

            {caps && (
              <div className="fp-caps">
                <span className="fp-cap" title="Live web search">
                  <Globe2 size={10} /> web
                </span>
                <span className="fp-cap" title="Memory database + skills + sessions">
                  <BookOpen size={10} /> {caps.sessions} sessions
                </span>
                <span className="fp-cap" title="MCP skills">
                  <Wrench size={10} /> {caps.mcp_servers.length} MCP · {caps.mcp_tools.length} tools
                </span>
              </div>
            )}

            <div className="fp-answer-area">
              {reply ? (
                <div className="fp-answer">
                  <pre className="fp-answer-body">{reply.answer}</pre>
                  {reply.sources.length > 0 && (
                    <div className="fp-sources">
                      <div className="fp-sources-title">Sources</div>
                      {reply.sources.slice(0, 6).map((source, idx) => (
                        <a
                          key={`${source.title}-${idx}`}
                          className="fp-source"
                          href={source.url || "#"}
                          target="_blank"
                          rel="noreferrer"
                          onClick={(event) => {
                            if (!source.url) event.preventDefault()
                          }}
                        >
                          <span className="fp-source-idx">{idx + 1}</span>
                          <span className="fp-source-title">{source.title}</span>
                          <span className="fp-source-kind">{source.source}</span>
                        </a>
                      ))}
                    </div>
                  )}
                  <div className="fp-meta">
                    {reply.provider} · {reply.elapsed_ms} ms · web {reply.used.web} · memory {reply.used.knowledge}
                    {reply.used.mcp_called ? " · MCP called" : ""}
                  </div>
                </div>
              ) : (
                <div className="fp-hint">
                  Ask about anything — I search the web, my memory database, and your MCP skills.
                </div>
              )}
            </div>

            <div className="fp-compose">
              <input
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.preventDefault()
                    void ask()
                  }
                }}
                placeholder="Ask the expert anything…"
                aria-label="Ask the DeskPet expert"
              />
              <button className="fp-send" onClick={() => void ask()} disabled={busy || !question.trim()}>
                {busy ? <Loader2 size={13} className="spin" /> : <Sparkles size={13} />}
              </button>
            </div>
          </div>
        )}

        <div
          className="fp-avatar"
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          title={`${status?.current_app ?? "Desktop"} · ${mood} — drag me, click to ask`}
        >
          <svg viewBox="0 0 100 100" className="fp-svg">
            <rect x="15" y="15" width="70" height="70" rx="28" fill="url(#fpGrad)" stroke="rgba(124,156,255,0.4)" strokeWidth="2.5" />
            <polygon points="20,20 10,2 35,16" fill="#1b243b" stroke="rgba(124,156,255,0.5)" strokeWidth="2" />
            <polygon points="80,20 90,2 65,16" fill="#1b243b" stroke="rgba(124,156,255,0.5)" strokeWidth="2" />
            {mood === "sleeping" ? (
              <>
                <line x1="30" y1="48" x2="44" y2="48" stroke={eye} strokeWidth="4" strokeLinecap="round" />
                <line x1="56" y1="48" x2="70" y2="48" stroke={eye} strokeWidth="4" strokeLinecap="round" />
              </>
            ) : (
              <>
                <ellipse cx="37" cy="46" rx="7" ry="9" fill={eye} className="fp-eye" />
                <ellipse cx="63" cy="46" rx="7" ry="9" fill={eye} className="fp-eye" />
                <circle cx="39" cy="43" r="2.5" fill="#ffffff" />
                <circle cx="65" cy="43" r="2.5" fill="#ffffff" />
              </>
            )}
            <circle cx="26" cy="56" r="3.5" fill="rgba(224,122,134,0.45)" />
            <circle cx="74" cy="56" r="3.5" fill="rgba(224,122,134,0.45)" />
            <path d="M 44 60 Q 50 64 56 60" stroke="rgba(255,255,255,0.7)" strokeWidth="2.5" fill="none" strokeLinecap="round" />
            <defs>
              <linearGradient id="fpGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#1a2238" />
                <stop offset="100%" stopColor="#0c111d" />
              </linearGradient>
            </defs>
          </svg>
          <span className={`fp-dot ${mood}`} />
        </div>
      </div>
    </>
  )
}
