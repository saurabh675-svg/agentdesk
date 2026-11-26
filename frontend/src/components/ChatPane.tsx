import { t } from "../i18n"
import { useEffect, useRef, useState } from "react"
import Markdown from "react-markdown"
import remarkGfm from "remark-gfm"
import {
  AlertTriangle,
  Bot,
  Check,
  ChevronDown,
  ChevronRight,
  Cpu,
  Download,
  FileText,
  Folder,
  Globe,
  Loader2,
  Monitor,
  Paperclip,
  Pencil,
  Plug,
  Puzzle,
  Search,
  Send,
  Settings as SettingsIcon,
  Sparkles,
  Square,
  Terminal,
  Volume2,
  Wrench,
  X,
  Zap,
  Mic,
} from "lucide-react"
import type { ApprovalRequest, Attachment, ChatMode, Message, ToolRun } from "../types"

interface Props {
  sessionTitle: string
  model: string
  workspaceName: string
  wsState: "connecting" | "open" | "closed"
  messages: Message[]
  liveText: string
  streaming: boolean
  toolRuns: ToolRun[]
  approval: ApprovalRequest | null
  mode: ChatMode
  autoHint: string
  routeNotice?: string | null
  attachments: Attachment[]
  onModeChange: (mode: ChatMode) => void
  onFilesSelected: (files: FileList | null) => void
  onSend: (text: string, attachments?: Attachment[]) => void
  onRemoveAttachment: (id: string) => void
  onExport: () => void
  onStop: () => void
  onApprove: (approved: boolean, persist?: boolean) => void
  onOpenSettings: () => void
}

const MODES: Array<{ id: ChatMode; label: string; icon: typeof Cpu; title: string }> = [
  { id: "saved", label: "Saved", icon: Cpu, title: "Use exactly the model configured in Settings" },
  {
    id: "auto",
    label: "Auto",
    icon: Zap,
    title: "Keyless/cloud gateways → local offline model → ChatGPT/Gemini browser tabs, automatically",
  },
  { id: "chatgpt", label: "ChatGPT", icon: Bot, title: "Drive the signed-in ChatGPT web chat" },
  { id: "gemini", label: "Gemini", icon: Sparkles, title: "Drive the signed-in Gemini web chat" },
]

const TOOL_ICONS: Record<string, typeof Wrench> = {
  list_files: Folder,
  read_file: Search,
  write_file: Pencil,
  edit_file: Pencil,
  run_command: Terminal,
  browser_navigate: Globe,
  browser_click: Globe,
  browser_type: Globe,
  browser_scroll: Globe,
  browser_read: Globe,
  browser_press: Globe,
  browser_select: Globe,
  browser_wait: Globe,
  browser_links: Globe,
  browser_back: Globe,
  browser_forward: Globe,
  open_external: Globe,
  browser_set_zoom: Globe,
  ask_chatbot: Bot,
  list_skills: Puzzle,
  use_skill: Puzzle,
  computer_screenshot: Monitor,
  computer_click: Monitor,
  computer_type: Monitor,
  computer_hotkey: Monitor,
  computer_scroll: Monitor,
}

function toolSummary(name: string, args: Record<string, unknown>): string {
  if (name === "run_command") return String(args.command ?? "")
  if (name === "browser_navigate") return String(args.url ?? "")
  if (name === "browser_click") return String(args.selector ?? "")
  if (name === "browser_type") return `${args.selector ?? ""} ← ${args.text ?? ""}`
  if (name === "browser_wait") return String(args.selector ?? args.text ?? "")
  if (name === "browser_press") return String(args.key ?? "")
  if (name === "ask_chatbot") return `${args.site ?? "chatgpt"} ← ${String(args.prompt ?? "").slice(0, 90)}`
  if (name === "use_skill") return String(args.name ?? "")
  if (name === "open_external") return String(args.url ?? "")
  if (name === "browser_set_zoom") return `${String(args.factor ?? 1)}x`
  if (name.startsWith("mcp_")) return name.slice(4).replace(/_/g, " ")
  if (name.startsWith("computer_")) return JSON.stringify(args).slice(0, 90)
  if (args.path) return String(args.path)
  return ""
}

function MarkdownView({ text }: { text: string }) {
  return (
    <div className="markdown">
      <Markdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children }) => (
            <a
              href={href}
              onClick={(event) => {
                event.preventDefault()
                if (href) window.desktop?.openExternal(href)
              }}
            >
              {children}
            </a>
          ),
        }}
      >
        {text}
      </Markdown>
    </div>
  )
}

function ToolCard({
  name,
  args,
  argsText,
  status,
  ok,
  result,
}: {
  name: string
  args: Record<string, unknown>
  argsText?: string
  status: "running" | "done"
  ok?: boolean
  result?: string
}) {
  // Running tools open automatically so the user can see what the agent is doing
  // instead of an empty "Working" line with hidden activity.
  const [open, setOpen] = useState(status === "running")
  const Icon = TOOL_ICONS[name] ?? (name.startsWith("mcp_") ? Plug : Wrench)
  return (
    <div className={`tool-card ${status === "running" ? "running" : ok ? "ok" : "failed"}`}>
      <button
        className="tool-head"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-label={`${name} tool details`}
      >
        <span className="tool-icon">
          <Icon size={13} />
        </span>
        <span className="tool-name">{name}</span>
        <span className="tool-summary">{toolSummary(name, args)}</span>
        {status === "running" ? (
          <Loader2 size={13} className="spin" />
        ) : ok ? (
          <Check size={13} className="ok-icon" />
        ) : (
          <AlertTriangle size={13} className="fail-icon" />
        )}
        {open ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
      </button>
      {open && (
        <>
          <pre className="tool-output" aria-label="Tool arguments">{argsText || JSON.stringify(args, null, 2)}</pre>
          {result !== undefined && <pre className="tool-output">{result || "(no output)"}</pre>}
        </>
      )}
    </div>
  )
}

function toolMessage(message: Message) {
  return (
    <ToolCard
      key={message.id}
      name={message.meta?.name ?? "tool"}
      args={(message.meta?.args as Record<string, unknown>) ?? {}}
      status="done"
      ok={message.meta?.ok}
      result={message.content}
    />
  )
}

const SUGGESTIONS = [
  { title: "Explain this codebase", prompt: "Explore this workspace and explain its structure, stack and main entry points." },
  { title: "Research on the web", prompt: "Open https://news.ycombinator.com and summarize the top 5 stories with their links." },
  { title: "Fix a bug", prompt: "Run the tests in this workspace, find the first failure, and propose a fix." },
  { title: "⚡ Slash Commands", prompt: "/help" },
  { title: "📦 Compact Context", prompt: "/compact" },
]

export default function ChatPane(props: Props) {
  const [showAllMessages, setShowAllMessages] = useState(false)
  const [text, setText] = useState("")
  const [queued, setQueued] = useState<string | null>(null)
  const queuedRef = useRef<string | null>(null)
  const [isListening, setIsListening] = useState(false)
  const [speaking, setSpeaking] = useState(false)
  const recognitionRef = useRef<any>(null)
  const endRef = useRef<HTMLDivElement>(null)
  const scrollContainerRef = useRef<HTMLDivElement>(null)
  const isAtBottomRef = useRef(true)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const toggleListening = () => {
    if (isListening) {
      recognitionRef.current?.stop()
      setIsListening(false)
      return
    }
    const SpeechRec = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
    if (!SpeechRec) {
      alert("Speech recognition is not supported in this browser.")
      return
    }
    const rec = new SpeechRec()
    rec.continuous = false
    rec.interimResults = true
    rec.lang = "en-US"
    rec.onresult = (event: any) => {
      const transcript = Array.from(event.results)
        .map((r: any) => r[0].transcript)
        .join("")
      setText(transcript)
    }
    rec.onend = () => setIsListening(false)
    rec.onerror = () => setIsListening(false)
    recognitionRef.current = rec
    try {
      rec.start()
      setIsListening(true)
    } catch {
      setIsListening(false)
    }
  }

  const toggleSpeaking = () => {
    if (!("speechSynthesis" in window)) return
    if (speaking) {
      window.speechSynthesis.cancel()
      setSpeaking(false)
      return
    }
    const lastAssistant = [...props.messages].reverse().find((m) => m.role === "assistant")
    if (!lastAssistant) return
    const cleanText = lastAssistant.content.replace(/```[\s\S]*?```/g, "Code block omitted.").replace(/[#*`_]/g, "")
    const utterance = new SpeechSynthesisUtterance(cleanText)
    const voices = window.speechSynthesis.getVoices()
    const preferred = voices.find((v) => v.lang.startsWith("en") && (v.name.includes("David") || v.name.includes("Natural") || v.name.includes("Google")))
    if (preferred) utterance.voice = preferred
    utterance.onend = () => setSpeaking(false)
    utterance.onerror = () => setSpeaking(false)
    setSpeaking(true)
    window.speechSynthesis.speak(utterance)
  }

  const handleScroll = () => {
    const el = scrollContainerRef.current
    if (!el) return
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
    isAtBottomRef.current = distanceFromBottom < 120
  }

  useEffect(() => {
    if (isAtBottomRef.current) {
      endRef.current?.scrollIntoView({ behavior: props.streaming ? "auto" : "smooth", block: "end" })
    }
  }, [props.messages, props.liveText, props.toolRuns, props.streaming])

  useEffect(() => {
    const area = textareaRef.current
    if (!area) return
    area.style.height = "auto"
    area.style.height = `${Math.min(area.scrollHeight, 200)}px`
  }, [text])

  const submit = () => {
    const value = text.trim()
    if (!value) return
    if (props.streaming) {
      // Keep chat usable while the agent works: queue the next message instead
      // of hiding the send control behind a Stop button.
      queuedRef.current = value
      setQueued(value)
      setText("")
      return
    }
    props.onSend(value, props.attachments.length ? [...props.attachments] : undefined)
    setText("")
  }

  useEffect(() => {
    if (props.streaming || !queuedRef.current) return
    const next = queuedRef.current
    queuedRef.current = null
    setQueued(null)
    props.onSend(next)
  }, [props.streaming, props.onSend])

  const empty = props.messages.length === 0 && !props.streaming

  // Intermediate one-line narration before a tool is progress, not a final answer.
  // Render it compactly so long tasks do not leave 4-5 near-empty chat bubbles.
  const progressIds = new Set(
    props.messages
      .map((message, index) => {
        const next = props.messages[index + 1]
        const isProgress =
          message.role === "assistant" &&
          (message.meta?.kind === "progress" ||
            (next?.role === "tool" && message.content.trim().length < 240))
        return isProgress ? message.id : null
      })
      .filter((id): id is number => id !== null),
  )

  const activeRun = props.toolRuns[props.toolRuns.length - 1]
  const activeSummary = activeRun ? toolSummary(activeRun.name, activeRun.args).slice(0, 90) : ""
  const activityLabel = activeRun
    ? `Working · ${activeRun.name}${activeSummary ? ` — ${activeSummary}` : ""}`
    : "Working"

  return (
    <section className="chat">
      <header className="chat-header" role="banner">
        <div>
          <h1>{props.sessionTitle}</h1>
          <div className="chat-meta">
            <span className="meta-chip">{props.workspaceName}</span>
            <span className="meta-chip model">{props.model}</span>
            <span className={`meta-chip conn ${props.wsState}`}>{props.wsState}</span>
          </div>
        </div>
        <button className="icon-button" onClick={props.onExport} title="Export transcript" aria-label="Export transcript">
          <Download size={13} />
        </button>
        <button className="icon-button" onClick={props.onOpenSettings} title="Settings" aria-label="Open settings">
          <SettingsIcon size={16} />
        </button>
      </header>

      {props.routeNotice && (
        <div className="route-banner" title="Auto-selected route for this reply" aria-live="polite">
          <Zap size={11} /> {props.routeNotice}
        </div>
      )}

      <div className="messages" ref={scrollContainerRef} onScroll={handleScroll}>
        {empty && (
          <div className="welcome">
            <div className="welcome-mark">◆</div>
            <h2>What should we build?</h2>
            <p>
              I can read and edit files, run commands, use the terminal, drive the browser and
              desktop, and consult ChatGPT or Gemini when you switch modes.
            </p>
            <div className="suggestions">
              {SUGGESTIONS.map((item) => (
                <button key={item.title} className="suggestion" onClick={() => props.onSend(item.prompt)}>
                  <span className="suggestion-title">{item.title}</span>
                  <span className="suggestion-prompt">{item.prompt}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {!showAllMessages && props.messages.length > 200 && (
          <button className="mini-button" onClick={() => setShowAllMessages(true)}>Show earlier messages ({props.messages.length - 200} hidden for performance)</button>
        )}
        {(showAllMessages ? props.messages : props.messages.slice(-200)).map((message) => {
          if (message.role === "user") {
            return (
              <div key={message.id} className="message user">
                <div className="bubble">{message.content}</div>
              </div>
            )
          }
          if (message.role === "tool") return toolMessage(message)
          if (progressIds.has(message.id)) {
            return (
              <div key={message.id} className="progress-line">
                <Wrench size={12} />
                <span>{message.content}</span>
              </div>
            )
          }
          return (
            <div key={message.id} className="message assistant">
              <div className="avatar">◆</div>
              <MarkdownView text={message.content} />
              <button className="mini-button" title="Copy message" aria-label="Copy message" onClick={() => void navigator.clipboard?.writeText(message.content)}>Copy</button>
            </div>
          )
        })}

        {props.toolRuns.map((run) => (
          <ToolCard
            key={run.id}
            name={run.name}
            args={run.args}
            argsText={run.argsText}
            status={run.status}
            ok={run.ok}
            result={run.result}
          />
        ))}

        {props.streaming && (
          <div className="message assistant live">
            <div className="avatar">◆</div>
            {props.liveText ? (
              <MarkdownView text={props.liveText} />
            ) : (
              <div className="thinking">
                <Loader2 size={14} className="spin" />
                <span className="thinking-label">{activityLabel}</span>
                <span className="dots">...</span>
              </div>
            )}
          </div>
        )}

        <div ref={endRef} />
      </div>

      <div className="composer-wrap">
        {props.approval && (
          <div className="approval">
            <div className="approval-head">
              <AlertTriangle size={14} />
              Command approval
            </div>
            <code>{props.approval.command}</code>
            <div className="approval-actions">
              <button className="btn allow" onClick={() => props.onApprove(true)}>
                Allow
              </button>
              <button
                className="btn allow"
                onClick={() => props.onApprove(true, true)}
                title="Approve and auto-allow future shell/desktop commands"
              >
                Always allow
              </button>
              <button className="btn deny" onClick={() => props.onApprove(false)}>
                Deny
              </button>
            </div>
          </div>
        )}

        <div className="mode-row">
          <div className="mode-group">
            {MODES.map((item) => {
              const Icon = item.icon
              return (
                <button
                  key={item.id}
                  className={`mode-chip ${props.mode === item.id ? "active" : ""}`}
                  title={item.title}
                  onClick={() => props.onModeChange(item.id)}
                >
                  <Icon size={11} /> {item.label}
                </button>
              )
            })}
          </div>
          <span className="mode-hint">
            {props.mode === "auto"
              ? props.autoHint
              : props.mode === "saved"
                ? props.model
                : `${props.mode === "gemini" ? "Gemini" : "ChatGPT"} · built-in browser`}
          </span>
        </div>

        {props.attachments.length > 0 && (
          <div className="attachments">
            {props.attachments.map((attachment) => (
              <span key={attachment.id} className="chip attachment">
                <FileText size={11} />
                <span className="chip-label" title={attachment.name}>
                  {attachment.name}
                </span>
                <button
                  className="chip-remove"
                  onClick={() => props.onRemoveAttachment(attachment.id)}
                  title="Remove attachment"
                  aria-label={`Remove attachment ${attachment.name}`}
                >
                  <X size={10} />
                </button>
              </span>
            ))}
          </div>
        )}

        <div className="composer">
          <input
            ref={fileInputRef}
            type="file"
            className="hidden"
            multiple
            onChange={(event) => props.onFilesSelected(event.target.files)}
          />
          <button
            type="button"
            className="send attach"
            title="Attach files"
            aria-label="Attach files"
            disabled={props.streaming}
            onClick={() => fileInputRef.current?.click()}
          >
            <Paperclip size={15} />
          </button>
          <button
            type="button"
            className={`send mic ${isListening ? "listening active" : ""}`}
            title={isListening ? "Listening... (click to stop)" : "Voice input (Speak to AgentDesk)"}
            aria-label={isListening ? "Stop voice input" : "Start voice input"}
            aria-pressed={isListening}
            disabled={props.streaming}
            onClick={toggleListening}
          >
            <Mic size={15} />
          </button>
          <textarea
            ref={textareaRef}
            rows={1}
            value={text}
            aria-label="Message AgentDesk"
            placeholder={isListening ? "Listening to your voice..." : "Ask AgentDesk to build, fix, research…"}
            onChange={(event) => setText(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
                event.preventDefault()
                submit()
              }
            }}
          />
          <button
            type="button"
            className={`send speaker ${speaking ? "speaking active" : ""}`}
            title={speaking ? "Stop voice playback" : "Read response aloud"}
            aria-label={speaking ? "Stop reading response aloud" : "Read response aloud"}
            aria-pressed={speaking}
            onClick={toggleSpeaking}
          >
            <Volume2 size={15} />
          </button>
          {props.streaming ? (
            <>
              <button className="send stop" onClick={props.onStop} title="Stop current run" aria-label="Stop current run">
                <Square size={15} />
              </button>
              <button
                className="send queue"
                onClick={submit}
                disabled={!text.trim()}
                title="Queue this message for when the current run finishes"
                aria-label="Queue message for after the current run"
              >
                <Send size={15} />
              </button>
            </>
          ) : (
            <button className="send" onClick={submit} disabled={!text.trim()} title={t("send")} aria-label={t("send")}>
              <Send size={15} />
            </button>
          )}
        </div>
        <div className="composer-hint">
          {queued ? (
            <span className="queued-note" title={queued}>
              <Send size={11} /> Queued: {queued.slice(0, 48)}
            </span>
          ) : (
            <span>
              <FileText size={11} /> Enter to send · Shift+Enter for a new line
            </span>
          )}
          <span className="composer-model">
            {props.mode === "auto"
              ? "local → gateways → browser"
              : props.mode === "saved"
                ? props.model
                : `${props.mode === "gemini" ? "Gemini" : "ChatGPT"} web chat`}
          </span>
        </div>
      </div>
    </section>
  )
}
