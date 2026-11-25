export const API_BASE = "http://127.0.0.1:8756"

export const socketProtocols = () => ["agentdesk", `token.${window.desktop?.apiToken || "missing"}`]

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers)
  headers.set("Authorization", `Bearer ${window.desktop?.apiToken || ""}`)
  if (typeof init?.body === "string") headers.set("Content-Type", "application/json")
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
  })
  if (!response.ok) {
    let detail = response.statusText
    try {
      const body = await response.json()
      detail = body.detail || detail
    } catch {
      // ignore
    }
    throw new Error(detail)
  }
  return response.json() as Promise<T>
}

export const api = {
  upload: <T>(path: string, body: FormData) => request<T>(path, { method: "POST", body }),
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: JSON.stringify(body ?? {}) }),
  put: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "PUT", body: JSON.stringify(body) }),
  patch: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
}

export const wsUrl = (sessionId: number) => `ws://127.0.0.1:8756/ws/chat/${sessionId}`

export const terminalUrl = (sessionId: number) =>
  `ws://127.0.0.1:8756/ws/terminal/${sessionId}`
