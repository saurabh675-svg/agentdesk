# AgentDesk — Security notes

This document describes AgentDesk's current trust model, mitigations, and the
known gaps. It is intentionally short; the long-form research is in
`RELIABILITY.md`.

## Threat model

AgentDesk is a **single-user, local application**. It runs on a Windows PC
owned by the user. The user trusts:
- their own machine.
- the providers they have configured (OpenRouter, Firecrawl, OpenAI, etc.).
- ChatGPT/Gemini web sessions they sign in to.

The user does **not** trust:
- random web pages.
- prompts inward from email/clipboard/SDR/voice tools.
- tool-bridged text that the model might be tricked into following.

## Authentication

### Local API
- HTTP and WebSocket endpoints are protected by `LocalAccessMiddleware`
  (`backend/app/security.py`).
- A 32-byte token is generated per process start in `electron/main.js` and
  passed to the renderer as `window.desktop.apiToken`.
- The WebSocket authenticates via the `agentdesk` subprotocol + a `token.*`
  subprotocol carrying the bearer.
- Allowed Origin allowlist: `null`, `file://`, `http://127.0.0.1:5173`,
  `http://localhost:5173`. Anything else is dropped with 403.
- `/v1/*` integration endpoints additionally require `AGENTDESK_GATEWAY_TOKEN`
  in the environment.

### Filesystem
- Tools (`fs.py`, `workspace.py`) reject paths outside the configured
  workspace via a `safe_path` helper that resolves and bounds the request.
- Browser and `computer_*` tools are gated by approval when auto-approve is
  off (the default).

### MCP servers
- MCP servers run with **OS permissions** of the AgentDesk Python process.
  They can therefore read any file the Python user can.
- New MCP presets log the exact required env vars (`needs_setup`) when auth
  is missing. Server start is refused until credentials are added.

## Credential storage
- API keys are encrypted with **Windows DPAPI** (`credentials.protect`) and
  persisted to `data\settings.json`. `AGENTDESK_API_TOKEN` and the llama.cpp
  server key are stored separately in `data\llama.key`.
- The local browser login profile for ChatGPT/Gemini lives in
  `data\browser-profile` (Chromium persistent context). Nothing is sent to a
  remote by AgentDesk itself; the user signs in themselves.

## Sandbox boundaries
- Electron uses `contextIsolation: true`, `sandbox: true`,
  `nodeIntegration: false`. CSP is injected from Vite + dev-only removal.
- Shell commands inherit a minimal environment (Python env vars are cleared
  in the packaged install).
- Desktop automation requires explicit user approval per call.

## Known limitations
- The installer is **unsigned**; SmartScreen shows a "More info → Run anyway"
  prompt on a clean Windows machine.
- The bundled llama.cpp server is reachable only on loopback, but the
  persistent auth key in `data\llama.key` is shared across process
  restarts.
- Tools that read external text (browser, web search) treat that text as
  **untrusted**. `agent.system_prompt` instructs the model not to follow
  embedded instructions, but this is a layered mitigation only — not a
  guaranteed defence.
- Approval is per-action, not per-effect. A single approved `run_command`
  cannot be replayed, but its action may have lasting side effects.
- Worker subprocesses (MCP, scheduler) inherit the parent's environment
  unless explicitly constrained.

## Reporting

Security issues can be reported by opening a private issue on the source
repository. Include reproduction steps, observed behaviour, and suspected
impact. Do **not** include real keys or credentials.

## Cadence

This document is reviewed before each minor release and the
`AGENTDESK_UPGRADE_PLAN.md` is consulted for new mitigations planned
(SQLite automation claims, scoped approvals, Windows Job Object process
isolation, signer acquisition).
