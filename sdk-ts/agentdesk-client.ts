export type Message = { role: string; content: string | null }
export type CompletionOptions = { model?: "agentdesk-local" | "agentdesk-hard"; max_tokens?: number; temperature?: number; tools?: object[]; tool_choice?: string | object; response_format?: object; seed?: number }

export class AgentDeskError extends Error {
  constructor(message: string, public status?: number) { super(message); this.name = "AgentDeskError" }
}
export type Completion = { choices: { message: { role: string; content: string | null; tool_calls?: object[] }; finish_reason: string }[] }
export type StreamChunk = { choices: { delta: { content?: string; tool_calls?: object[] }; finish_reason: string | null }[] }

export class AgentDeskClient {
  constructor(private token: string, private baseUrl = "http://127.0.0.1:8756/v1") {}

  private async request(path: string, body?: object) {
    const response = await fetch(this.baseUrl.replace(/\/$/, "") + path, {
      method: body ? "POST" : "GET",
      headers: { Authorization: `Bearer ${this.token}`, "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
    })
    if (!response.ok) {
      const text = await response.text().catch(() => "")
      throw new AgentDeskError(`AgentDesk returned HTTP ${response.status}: ${text.slice(0, 500)}`, response.status)
    }
    return response
  }

  async models() {
    return (await this.request("/models")).json()
  }

  async complete(messages: Message[], options: CompletionOptions = {}): Promise<Completion> {
    return (await this.request("/chat/completions", { ...options, messages, stream: false })).json()
  }

  async *stream(messages: Message[], options: CompletionOptions = {}): AsyncGenerator<StreamChunk> {
    const response = await this.request("/chat/completions", { ...options, messages, stream: true })
    const reader = response.body?.pipeThrough(new TextDecoderStream()).getReader()
    if (!reader) throw new Error("AgentDesk returned no response stream")
    let buffer = ""
    try {
      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += value
        let boundary = buffer.indexOf("\n\n")
        while (boundary >= 0) {
          const frame = buffer.slice(0, boundary)
          buffer = buffer.slice(boundary + 2)
          if (frame.startsWith("data: ")) {
            const payload = frame.slice(6)
            if (payload === "[DONE]") return
            const event = JSON.parse(payload)
            if (event.error) throw new Error(event.error.message)
            yield event
          }
          boundary = buffer.indexOf("\n\n")
        }
      }
      throw new Error("The AgentDesk stream ended unexpectedly")
    } finally {
      await reader.cancel().catch(() => undefined)
      reader.releaseLock()
    }
  }
}
