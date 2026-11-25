import { useEffect, useRef, useState } from "react"
import { Terminal as XTerm } from "@xterm/xterm"
import { FitAddon } from "@xterm/addon-fit"
import "@xterm/xterm/css/xterm.css"
import { RefreshCw, RotateCw, Terminal as TerminalIcon } from "lucide-react"
import { socketProtocols, terminalUrl } from "../api"

interface Props {
  sessionId: number
}

export default function TerminalView({ sessionId }: Props) {
  const hostRef = useRef<HTMLDivElement>(null)
  const socketRef = useRef<WebSocket | null>(null)
  const fitRef = useRef<FitAddon | null>(null)
  const termRef = useRef<XTerm | null>(null)
  const [state, setState] = useState<"connecting" | "open" | "closed">("connecting")
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const host = hostRef.current
    if (!host) return

    const term = new XTerm({
      fontFamily: '"Cascadia Code", "JetBrains Mono", Consolas, monospace',
      fontSize: 12,
      lineHeight: 1.25,
      cursorBlink: true,
      allowProposedApi: true,
      theme: {
        background: "#0a0e16",
        foreground: "#c3cbdc",
        cursor: "#7c9cff",
        selectionBackground: "rgba(124,156,255,0.28)",
        black: "#0a0e16",
        red: "#e07a86",
        green: "#63d29a",
        yellow: "#e0b15c",
        blue: "#7c9cff",
        magenta: "#c39bff",
        cyan: "#6fd0cf",
        white: "#d7dce6",
        brightBlack: "#5f6a7e",
        brightRed: "#f08b97",
        brightGreen: "#7fe3b0",
        brightYellow: "#f0c477",
        brightBlue: "#9db6ff",
        brightMagenta: "#d4b3ff",
        brightCyan: "#8fe4e3",
        brightWhite: "#eef2fa",
      },
    })
    const fit = new FitAddon()
    term.loadAddon(fit)
    term.open(host)
    termRef.current = term
    fitRef.current = fit
    try {
      fit.fit()
    } catch {
      // container may not be measured yet
    }

    let disposed = false
    const socket = new WebSocket(terminalUrl(sessionId), socketProtocols())
    socketRef.current = socket
    setState("connecting")
    setError(null)
    term.writeln("\x1b[38;5;61mAgentDesk terminal\x1b[0m — PowerShell session")

    socket.onopen = () => {
      if (disposed) return
      setState("open")
      socket.send(JSON.stringify({ type: "resize", rows: term.rows, cols: term.cols }))
    }
    socket.onmessage = (event) => {
      if (disposed) return
      try {
        const message = JSON.parse(event.data)
        if (message.type === "ready") {
          if (message.error) {
            setError(message.error)
            term.writeln(`\x1b[31mterminal unavailable: ${message.error}\x1b[0m`)
          } else if (message.buffer) {
            term.write(message.buffer)
          }
        } else if (message.type === "output") {
          term.write(message.data)
        } else if (message.type === "cleared") {
          term.reset()
        }
      } catch {
        // ignore malformed frames
      }
    }
    socket.onclose = () => {
      if (!disposed) setState("closed")
    }
    socket.onerror = () => socket.close()

    const dataDisposable = term.onData((data) => {
      if (socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ type: "input", data }))
      }
    })

    const observer = new ResizeObserver(() => {
      try {
        fit.fit()
      } catch {
        return
      }
      if (socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ type: "resize", rows: term.rows, cols: term.cols }))
      }
    })
    observer.observe(host)
    const focusTimer = window.setTimeout(() => term.focus(), 120)

    return () => {
      disposed = true
      window.clearTimeout(focusTimer)
      observer.disconnect()
      dataDisposable.dispose()
      socket.close()
      term.dispose()
      socketRef.current = null
      termRef.current = null
      fitRef.current = null
    }
  }, [sessionId])

  const restart = () => {
    const socket = socketRef.current
    if (socket?.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: "restart" }))
    }
  }

  return (
    <div className="terminal-view">
      <div className="terminal-toolbar">
        <TerminalIcon size={13} />
        <span className="terminal-title">PowerShell</span>
        <span className={`terminal-state ${state}`}>{state}</span>
        {error && <span className="terminal-error">{error}</span>}
        <span className="right-spacer" />
        <button aria-label="Restart terminal" className="mini-button" onClick={restart} title="Restart terminal">
          <RotateCw size={11} /> restart
        </button>
      </div>
      <div className="terminal-host" ref={hostRef} />
      <div className="terminal-hint">
        <RefreshCw size={10} /> The agent can run commands here with your approval — you can also type
        directly.
      </div>
    </div>
  )
}
