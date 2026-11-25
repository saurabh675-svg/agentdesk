import { useState } from "react"
import { Check, Loader2, Plus, Trash2, Zap } from "lucide-react"
import type { AgentProfile, Settings } from "../types"

interface Props {
  form: Settings
  setForm: React.Dispatch<React.SetStateAction<Settings>>
  onSave: (patch: Partial<Settings>) => Promise<void>
  onSettingsChanged: (settings: Settings) => void
  onError: (message: string | null) => void
  onNotice: (message: string | null) => void
}

const PROVIDERS = ["local", "keyless", "openrouter", "freeai", "vercel", "unorouter", "opencode", "pollinations", "openai", "custom", "webchat"]

export default function AgentsTab({ form, setForm, onSave, onSettingsChanged, onError, onNotice }: Props) {
  const [busy, setBusy] = useState(false)
  const [name, setName] = useState("")
  const [provider, setProvider] = useState("openrouter")
  const [model, setModel] = useState("")
  const [baseUrl, setBaseUrl] = useState("")
  const [apiKey, setApiKey] = useState("")

  const agents = form.agents || []

  const persist = async (nextAgents: AgentProfile[], activeAgent: string) => {
    setBusy(true)
    onError(null)
    try {
      const patch = { ...form, agents: nextAgents, active_agent: activeAgent }
      await onSave(patch)
      setForm(patch)
      onSettingsChanged(patch)
    } catch (err) {
      onError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  const addAgent = async () => {
    if (!name.trim()) {
      onError("Give the agent a name.")
      return
    }
    const agent: AgentProfile = {
      id: `agent-${Date.now().toString(36)}`,
      name: name.trim(),
      provider,
      gateway: provider,
      model: model.trim(),
      base_url: baseUrl.trim() || undefined,
      api_key: apiKey.trim() || undefined,
    }
    await persist([...agents, agent], form.active_agent || "")
    setName("")
    setModel("")
    setBaseUrl("")
    setApiKey("")
    onNotice(`Agent “${agent.name}” created.`)
  }

  const activate = async (id: string) => {
    await persist(agents, id)
    onNotice("Agent activated. New chats use its model and key.")
  }

  const deactivate = async () => {
    await persist(agents, "")
    onNotice("Agent cleared. Using the main Model settings.")
  }

  const remove = async (id: string) => {
    await persist(agents.filter((a) => a.id !== id), form.active_agent === id ? "" : form.active_agent || "")
  }

  return (
    <div className="agents-tab">
      <div className="section-head">
        <h3>Agent profiles</h3>
      </div>
      <p className="tab-hint">
        Each agent pins a provider, model and key. Activate one to make it the default for new chats,
        or leave none active to use the main Model settings. Keys are saved per gateway and never lost.
      </p>

      <div className="model-list">
        {agents.map((agent) => {
          const active = form.active_agent === agent.id
          return (
            <div key={agent.id} className={`model-row ${active ? "active" : ""}`}>
              <div className="model-row-main">
                <span className="model-name">{agent.name}</span>
                <span className="model-meta">{agent.provider}{agent.model ? ` · ${agent.model}` : ""}{active ? " · active" : ""}</span>
              </div>
              <div className="model-row-actions">
                {active ? (
                  <button className="mini-button" disabled={busy} onClick={deactivate}>
                    <Check size={11} /> active — clear
                  </button>
                ) : (
                  <button className="mini-button" disabled={busy} onClick={() => activate(agent.id)}>
                    <Zap size={11} /> Activate
                  </button>
                )}
                <button className="mini-button danger" disabled={busy} onClick={() => remove(agent.id)}>
                  <Trash2 size={11} />
                </button>
              </div>
            </div>
          )
        })}
        {agents.length === 0 && <p className="tab-hint">No agent profiles yet. Create one below.</p>}
      </div>

      <h4>New agent</h4>
      <div className="agent-form">
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Name (e.g. Coder, Researcher)" spellCheck={false} />
        <select value={provider} onChange={(e) => setProvider(e.target.value)}>
          {PROVIDERS.map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
        <input value={model} onChange={(e) => setModel(e.target.value)} placeholder="Model id (blank = gateway default)" spellCheck={false} />
        <input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder="Base URL (optional)" spellCheck={false} />
        <input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="API key (optional; uses saved gateway key)" />
        <button className="mini-button" disabled={busy} onClick={addAgent}>
          {busy ? <Loader2 size={11} className="spin" /> : <Plus size={11} />} Add agent
        </button>
      </div>
    </div>
  )
}
