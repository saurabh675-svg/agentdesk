# AgentDesk Browser — multi-language clients

One real browser (the one the agent drives, with **your** signed-in sessions)
exposed to any language through three façades.

| Façade | Best for | Endpoint |
|---|---|---|
| **REST + WebSocket** | everything, zero dependencies | `http://127.0.0.1:8756/api/browser/sdk` |
| **Chrome DevTools Protocol** | C++, Go, Rust, Node/Puppeteer, Selenium | `http://127.0.0.1:9333` |
| **WebDriver BiDi** | C#/.NET, Java, Selenium 4, Playwright .NET | `ws://127.0.0.1:8756/api/browser/bidi/ws` |

All three drive the **same Chromium instance**, so cookies, logins and the
visible window are shared with the agent.

## Auth

```powershell
# stable token for external clients (created on first use)
type "$env:APPDATA%\AgentDesk\data\browser-sdk.token"
```

Send it as `Authorization: Bearer <token>` (or `?token=<token>` for the
WebSocket handshake). The CDP port is loopback-only and unauthenticated —
treat local machine access as full browser control.

## C++ — raw CDP over WebSocket

`cpp/cdp_client.cpp` — zero external deps beyond a websocket library
(libwebsockets / Boost.Beast / websocketpp). Talks raw CDP:
`Target.createTarget`, `Page.navigate`, `Runtime.evaluate`, `Input.dispatchMouseEvent`.

```bash
g++ -std=c++17 -O2 cpp/cdp_client.cpp -o cdp_client   # add your ws lib flags
```

## C# — Selenium 4 or Playwright for .NET

`csharp/Program.cs` — uses **WebDriver BiDi** (no extra browser download):

```bash
dotnet new console -o csharp && cd csharp
dotnet add package Selenium.WebDriver
dotnet run
```

Or with Playwright for .NET against the CDP port:
`Microsoft.Playwright` + `ConnectAsync` equivalents.

## JavaScript — Puppeteer (or plain fetch)

`js/puppeteer_client.mjs` — connects to the existing browser, no Chromium
download needed:

```bash
npm i puppeteer-core
node js/puppeteer_client.mjs
```

`js/rest_client.mjs` — pure `fetch`, no dependencies at all.

## Python

`sdk-py/agentdesk_client.py` already exists for the chat API; the browser
control plane is plain REST:

```python
import requests
TOKEN = open(r"%APPDATA%\AgentDesk\data\browser-sdk.token").read().strip()
requests.post("http://127.0.0.1:8756/api/browser/sdk/navigate",
              headers={"Authorization": f"Bearer {TOKEN}"},
              json={"url": "https://kaggle.com"})
```

## REST reference (the universal API)

| Method | Path | Body | Notes |
|---|---|---|---|
| GET | `/api/browser/sdk/info` | – | endpoints + capabilities + CDP status |
| GET | `/api/browser/sdk/tabs` | – | open tabs |
| POST | `/api/browser/sdk/navigate` | `{"url"}` | |
| POST | `/api/browser/sdk/act` | see below | one input action |
| GET | `/api/browser/sdk/snapshot` | – | URL, title, text, links, indexed elements |
| GET | `/api/browser/sdk/screenshot` | – | base64 frame |
| WS | `/api/browser/sdk/events` | – | live frames + state |

`/act` actions: `click` (selector), `click_at` (x,y), `double_click_at`,
`type` (selector+text), `key` (name — arrows, chords like `Control+K`),
`hover` (x,y), `drag` (x,y → to_x,to_y), `scroll` (delta_y/delta_x),
`scroll_to` (selector), `select` (selector+value), `wait_for`,
`upload` (selector+path), `back`, `forward`, `reload`.

## Enabling / disabling CDP

Settings → Browser → **CDP port** (`browser_cdp_port`, default `9333`,
`0` = disabled). Restart the browser afterwards.
