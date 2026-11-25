# AgentDesk 0.3.1 handoff

This release updates the existing Windows x64 Electron, React, and FastAPI app. The installer bundles the CPU model, Python runtime, and Chromium. Docker is not required.

## Quick start

Run `release\AgentDesk-Setup-0.3.1.exe`, review the install destination and confirm the installation yourself. Start AgentDesk from its desktop or Start menu shortcut. The setup uses the existing per-user install path and existing data profile. Keep the 0.3.0 installer for rollback.

Use Saved mode with Local selected for offline chat. Hard mode attempts local inference first and can use OpenRouter free inference when a compatible local response is unavailable and an OpenRouter key is saved. Web chat is optional and requires confirmation before it receives chat context. Windows may show a publisher prompt because the installer is unsigned.

## Integrations

Set a dedicated `AGENTDESK_GATEWAY_TOKEN` in the environment of the process that starts AgentDesk. Close existing AgentDesk tray instances before restarting it with that environment. Use a randomly generated secret from a password manager and pass it only to trusted local clients.

```powershell
$env:AGENTDESK_GATEWAY_TOKEN = [System.Net.NetworkCredential]::new('', (Read-Host 'Integration token' -AsSecureString)).Password
Start-Process (Join-Path $env:LOCALAPPDATA 'Programs/AgentDesk/AgentDesk.exe')
```

The integration accepts bearer-authenticated requests from local native clients with no browser Origin.

- Base URL `http://127.0.0.1:8756/v1`
- Endpoints `GET /models` and `POST /chat/completions`
- Models `agentdesk-local` and `agentdesk-hard`
- Python SDK `sdk-py/agentdesk_client.py`
- TypeScript SDK `sdk-ts/agentdesk-client.ts`

```python
import os
from agentdesk_client import AgentDeskClient

client = AgentDeskClient(os.environ["AGENTDESK_GATEWAY_TOKEN"])
response = client.complete([{"role": "user", "content": "Hello"}])
print(response["choices"][0]["message"]["content"])
```

```typescript
import { AgentDeskClient } from "./agentdesk-client.js";
const client = new AgentDeskClient(process.env.AGENTDESK_GATEWAY_TOKEN!);
for await (const chunk of client.stream([{ role: "user", content: "Hello" }])) {
  process.stdout.write(chunk.choices[0].delta.content ?? "");
}
```

The local API serves basic chat. Tool-call requests can use the configured OpenRouter free route in Hard mode. The API returns tool calls to the client for handling. It has no access to desktop actions or the app's stored workspace context. The upstream provider may see any prompts you send through the Hard cloud route. If a streaming integration already received part of a reply, it gets an explicit stream error on interruption. The desktop can switch providers before any action runs, and never restarts a turn after an action has already executed.

## Development

Use `npm run typecheck` and `backend\.venv\Scripts\python.exe scripts\verify_release.py --in-process` for local regression verification. Use `scripts\package-windows.ps1` to create the versioned setup with the cached Windows build tools and staged runtime. Use the included executable's `--verify` switch to verify the embedded payload without installing.

See `RELIABILITY.md` for the broader roadmap. The scope here is the existing Windows app and local integration clients.

## Test results

- Frontend and TypeScript SDK passed type checking.
- Backend regressions passed for authentication, approval denial, truncated streams, and fallback with a simulated local outage.
- The bundled CPU runtime rejected an unauthorized request and streamed a successful response on an isolated loopback port.
- The Python client passed live model listing, JSON completion, and streaming.
- The TypeScript client passed authenticated HTTP and split-frame streaming tests against a local fixture.
- Windows 0.3.1 install verified from the packaged build: desktop/Start-menu shortcuts launch the app, `/api/health` reports 0.3.1, the always-on local model is listening on 11435, per-gateway OpenRouter settings survive upgrade, and local sandbox commands execute successfully. Auth-gated MCP servers (notion, drive, sentry, askui) still require their credentials.

OpenRouter documentation checked 23 November 2026. The free router uses an account API key and is subject to the provider's quotas. See the [Free Models Router](https://openrouter.ai/openrouter/free) and [Free AI Models](https://openrouter.ai/collections/free-models).
