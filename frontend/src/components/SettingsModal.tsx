import { useEffect, useState } from "react"
import {
  Bot,
  Check,
  Cog,
  Download,
  FolderInput,
  Globe,
  Loader2,
  Pencil,
  Plus,
  Puzzle,
  RefreshCw,
  Search,
  Server,
  Sparkles,
  Trash2,
  X,
  Zap,
} from "lucide-react"
import { api } from "../api"
import { getLocale, setLocale } from "../i18n"
import type { Automation, MCPPreset, MCPServer, OpenRouterModel, Settings, SkillInfo } from "../types"
import LocalModelsTab from "./LocalModelsTab"
import AgentsTab from "./AgentsTab"

interface Props {
  settings: Settings
  onClose: () => void
  onSave: (patch: Partial<Settings>) => Promise<void>
  onSettingsChanged: (settings: Settings) => void
}

type Tab = "general" | "model" | "models" | "agents" | "browser" | "skills" | "mcp"

type Preset = {
  provider: string
  base_url?: string
  model?: string
  api_key?: string
  disable_thinking: boolean
  webchat_site?: string
}

const LOCAL_PRESET: Preset = {
  provider: "local",
  base_url: "http://127.0.0.1:11435/v1",
  model: "",
  disable_thinking: true,
}

const PRESETS: Record<string, Preset> = {
  local: LOCAL_PRESET,
  openrouter: {
    provider: "openrouter",
    base_url: "https://openrouter.ai/api/v1",
    model: "nvidia/nemotron-3-ultra-550b-a55b:free",
    disable_thinking: false,
  },
  keyless: {
    provider: "keyless",
    base_url: "https://api.apillmfree.com/v1",
    model: "free-ai",
    disable_thinking: false,
  },
  vercel: {
    provider: "openrouter",
    base_url: "https://ai-gateway.vercel.app/v1",
    model: "openai/gpt-5",
    disable_thinking: false,
  },
  unorouter: {
    provider: "openrouter",
    base_url: "https://api.unorouter.com/v1",
    model: "claude-opus-4-7-thinking",
    disable_thinking: false,
  },
  opencode: {
    provider: "opencode",
    base_url: "https://opencode.ai/inference/openai/v1",
    model: "mimo-v2.6-flash-free",
    disable_thinking: false,
  },
  pollinations: {
    provider: "openrouter",
    base_url: "https://gen.pollinations.ai/v1",
    model: "openai/gpt-5.4-nano",
    disable_thinking: false,
  },
  openai: {
    provider: "openai",
    base_url: "https://api.openai.com/v1",
    model: "gpt-4o-mini",
    disable_thinking: false,
  },
  chatgpt: { provider: "webchat", webchat_site: "chatgpt", disable_thinking: false },
  gemini: { provider: "webchat", webchat_site: "gemini", disable_thinking: false },
  custom: { provider: "custom", base_url: "http://127.0.0.1:1234/v1", model: "", disable_thinking: false },
}

// Gateways every user can activate at any time; each has its own saved key.
const GATEWAYS = ["local", "keyless", "openrouter", "freeai", "vercel", "unorouter", "opencode", "pollinations", "openai"]

function statusClass(status?: string): string {
  if (status === "ready") return "ready"
  if (status === "error") return "error"
  if (status === "needs_setup") return "needs-setup"
  if (status === "disabled") return "disabled"
  return "connecting"
}

export default function SettingsModal(props: Props) {
  const [form, setForm] = useState<Settings>(props.settings)
  const [tab, setTab] = useState<Tab>("model")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const [skills, setSkills] = useState<SkillInfo[]>([])
  const [skillUrl, setSkillUrl] = useState("")
  const [skillPackPath, setSkillPackPath] = useState("")
  const [skillPackPreview, setSkillPackPreview] = useState<{ name: string; description: string }[]>([])
  const [skillName, setSkillName] = useState("")
  const [skillDescription, setSkillDescription] = useState("")
  const [skillContent, setSkillContent] = useState("")

  const [mcpServers, setMcpServers] = useState<MCPServer[]>([])
  const [mcpPresets, setMcpPresets] = useState<MCPPreset[]>([])
  const [mcpDirty, setMcpDirty] = useState(false)
  const [editingServerId, setEditingServerId] = useState<string | null>(null)
  const [editEnvText, setEditEnvText] = useState("")
  const [mcpBusy, setMcpBusy] = useState<string | null>(null)
  const [customName, setCustomName] = useState("")
  const [customCommand, setCustomCommand] = useState("npx")
  const [customArgs, setCustomArgs] = useState("")

  const [settingsSearch, setSettingsSearch] = useState("")
  const [testResult, setTestResult] = useState<string | null>(null)
  const [freeModels, setFreeModels] = useState<OpenRouterModel[]>([])
  const [freeBusy, setFreeBusy] = useState(false)

  const [automations, setAutomations] = useState<Automation[]>([])
  const [automationBusy, setAutomationBusy] = useState(false)
  const [newAutomationName, setNewAutomationName] = useState("")
  const [newAutomationPrompt, setNewAutomationPrompt] = useState("")
  const [newAutomationInterval, setNewAutomationInterval] = useState(15)
  const [policyJson, setPolicyJson] = useState("{}")

  useEffect(() => {
    setPolicyJson(JSON.stringify(form.policies || {}, null, 2))
  }, [form])

  const loadAutomations = async () => {
    try {
      setAutomations(await api.get<Automation[]>("/api/automations"))
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  const createAutomation = async () => {
    if (!newAutomationName.trim() || !newAutomationPrompt.trim()) return
    setAutomationBusy(true)
    setError(null)
    try {
      await api.post("/api/automations", {
        name: newAutomationName,
        prompt: newAutomationPrompt,
        interval_minutes: Math.max(5, newAutomationInterval),
      })
      setNewAutomationName("")
      setNewAutomationPrompt("")
      await loadAutomations()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setAutomationBusy(false)
    }
  }

  const cancelAutomation = async (id: string) => {
    setAutomationBusy(true)
    try {
      await api.post(`/api/automations/${id}/cancel`)
      await loadAutomations()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setAutomationBusy(false)
    }
  }

  useEffect(() => {
    setForm(props.settings)
    setError(null)
  }, [props.settings])

  const loadFreeModels = async (refresh = false) => {
    setFreeBusy(true)
    try {
      setFreeModels(
        await api.get<OpenRouterModel[]>(`/api/openrouter/models${refresh ? "?refresh=true" : ""}`),
      )
    } catch {
      // the backend falls back to a known free model; leave the list empty
    } finally {
      setFreeBusy(false)
    }
  }

  useEffect(() => {
    loadFreeModels()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const set = <K extends keyof Settings>(key: K, value: Settings[K]) =>
    setForm((current) => ({ ...current, [key]: value }))

  const applyPreset = (name: keyof typeof PRESETS) => {
    const preset = PRESETS[name]
    const savedKey = form.keys?.[name] ?? preset.api_key ?? ""
    setForm((current) => ({
      ...current,
      ...preset,
      gateway: name,
      // Activate any LLM any time: reuse that gateway's saved key.
      api_key: savedKey,
    }))
  }

  const setKeys = (updater: (current: Record<string, string> | undefined) => Record<string, string>) =>
    setForm((current) => ({ ...current, keys: updater(current.keys) }))

  const save = async () => {
    setBusy(true)
    setError(null)
    try {
      await props.onSave(form)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  const applyPolicies = async () => {
    setBusy(true)
    setError(null)
    try {
      const policies = JSON.parse(policyJson || "{}")
      await props.onSave({ ...form, policies })
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  const loadSkills = async () => {
    try {
      setSkills(await api.get<SkillInfo[]>("/api/extensions/skills"))
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  const scanSkillPack = async () => {
    if (!skillPackPath.trim()) return
    setBusy(true)
    setError(null)
    try {
      const result = await api.get<{ skills: { name: string; description: string }[] }>(
        `/api/extensions/skills/scan?path=${encodeURIComponent(skillPackPath.trim())}`,
      )
      setSkillPackPreview(result.skills)
      setNotice(
        result.skills.length
          ? `Found ${result.skills.length} skill${result.skills.length === 1 ? "" : "s"} in that path`
          : "No skills found in that path",
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  const importSkillPack = async () => {
    if (!skillPackPath.trim()) return
    setBusy(true)
    setError(null)
    try {
      const result = await api.post<{
        imported: { name: string }[]
        skipped: { name: string }[]
        errors: string[]
      }>("/api/extensions/skills/import", { path: skillPackPath.trim(), overwrite: true })
      setNotice(
        `Imported ${result.imported.length} skill${result.imported.length === 1 ? "" : "s"}` +
          (result.skipped.length ? `, ${result.skipped.length} skipped` : "") +
          (result.errors.length ? `, ${result.errors.length} failed` : ""),
      )
      setSkillPackPath("")
      setSkillPackPreview([])
      await loadSkills()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  const loadMcp = async () => {
    try {
      const [servers, presets] = await Promise.all([
        api.get<MCPServer[]>("/api/extensions/mcp/servers"),
        api.get<MCPPreset[]>("/api/extensions/mcp/presets"),
      ])
      setMcpServers(servers)
      setMcpPresets(presets)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  useEffect(() => {
    if (tab === "general") loadAutomations()
    if (tab === "skills") loadSkills()
    if (tab === "mcp") loadMcp()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab])

  useEffect(() => {
    if (!notice) return
    const timer = setTimeout(() => setNotice(null), 9500)
    return () => clearTimeout(timer)
  }, [notice])

  const installSkill = async () => {
    if (!skillUrl.trim()) return
    setBusy(true)
    setError(null)
    try {
      const installed = await api.post<SkillInfo>("/api/extensions/skills/install", {
        url: skillUrl.trim(),
      })
      setSkillUrl("")
      setNotice(`Installed skill “${installed.name}”`)
      await loadSkills()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  const addSkill = async () => {
    if (!skillName.trim() || !skillContent.trim()) {
      setError("A skill needs a name and content.")
      return
    }
    setBusy(true)
    setError(null)
    try {
      await api.post("/api/extensions/skills", {
        name: skillName.trim(),
        description: skillDescription.trim(),
        content: skillContent.trim(),
      })
      setSkillName("")
      setSkillDescription("")
      setSkillContent("")
      setNotice("Skill saved")
      await loadSkills()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  const removeSkill = async (slug: string) => {
    setBusy(true)
    try {
      await api.delete(`/api/extensions/skills/${slug}`)
      await loadSkills()
      setNotice("Skill removed")
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  const addPreset = (preset: MCPPreset) => {
    if (mcpServers.some((server) => server.id === preset.id)) {
      setNotice(`${preset.name} is already in the list`)
      return
    }
    setMcpServers((current) => [
      ...current,
      {
        id: preset.id,
        name: preset.name,
        command: preset.command,
        args: preset.args,
        env: {},
        enabled: true,
        status: "stopped",
      },
    ])
    setMcpDirty(true)
  }

  const addCustomMcp = () => {
    if (!customName.trim() || !customCommand.trim()) {
      setError("A custom MCP server needs a name and a command.")
      return
    }
    const id = customName.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-")
    setMcpServers((current) => [
      ...current,
      {
        id,
        name: customName.trim(),
        command: customCommand.trim(),
        args: customArgs
          .split(/\s+/)
          .map((part) => part.trim())
          .filter(Boolean),
        env: {},
        enabled: true,
        status: "stopped",
      },
    ])
    setCustomName("")
    setCustomArgs("")
    setMcpDirty(true)
  }

  const applyMcp = async () => {
    setBusy(true)
    setError(null)
    try {
      const payload = mcpServers.map((server) => ({
        id: server.id,
        name: server.name,
        command: server.command,
        args: server.args,
        env: server.env ?? {},
        enabled: server.enabled,
      }))
      const statuses = await api.put<MCPServer[]>("/api/extensions/mcp/servers", {
        servers: payload,
      })
      setMcpServers(statuses)
      setMcpDirty(false)
      setNotice("MCP servers updated — connecting in the background")
      window.setTimeout(() => {
        api
          .get<MCPServer[]>("/api/extensions/mcp/servers")
          .then(setMcpServers)
          .catch(() => undefined)
      }, 4000)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  const toggleMcp = (id: string, enabled: boolean) => {
    setMcpServers((current) =>
      current.map((server) => (server.id === id ? { ...server, enabled } : server)),
    )
    setMcpDirty(true)
  }

  const removeMcp = (id: string) => {
    setMcpServers((current) => current.filter((server) => server.id !== id))
    setMcpDirty(true)
  }

  const reconnectMcp = async (id: string) => {
    setMcpBusy("mcp_reconnect")
    setError(null)
    try {
      await api.post(`/api/extensions/mcp/servers/${id}/reconnect`)
      await loadMcp()
      setNotice("Reconnected")
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setMcpBusy(null)
    }
  }

  const editServerEnv = (server: MCPServer) => {
    setEditingServerId(server.id)
    setEditEnvText(JSON.stringify(server.env ?? {}, null, 2))
  }

  const saveServerEnv = async (server: MCPServer) => {
    setMcpBusy("mcp_env")
    setError(null)
    try {
      let env: Record<string, string> = {}
      try {
        const parsed = JSON.parse(editEnvText || "{}")
        env = parsed && typeof parsed === "object" ? parsed : {}
      } catch {
        setError("Env must be a JSON object, e.g. {\"NOTION_TOKEN\": \"...\"}")
        return
      }
      await api.put(`/api/extensions/mcp/servers/${server.id}`, { env })
      setEditingServerId(null)
      await loadMcp()
      setNotice("Saved — server reconnected")
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setMcpBusy(null)
    }
  }

  const openChatSite = async (site: "chatgpt" | "gemini") => {
    setBusy(true)
    setError(null)
    try {
      const updated = await api.put<Settings>("/api/settings", {
        ...form,
        provider: form.provider,
        webchat_site: site,
        browser_headless: false,
      })
      setForm(updated)
      props.onSettingsChanged(updated)
      await api.post("/api/browser/action", {
        action: "navigate",
        url: site === "chatgpt" ? "https://chatgpt.com/" : "https://gemini.google.com/app",
      })
      setNotice(
        `A Chromium window opened. Sign in to ${site === "chatgpt" ? "ChatGPT" : "Gemini"}, then select the preset in Model.`,
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  const openGoogleLogin = async (site: "drive" | "gmail" | "calendar") => {
    const url =
      site === "drive" ? "https://drive.google.com/"
      : site === "gmail" ? "https://mail.google.com/"
      : "https://calendar.google.com/"
    const label = site === "drive" ? "Google Drive" : site === "gmail" ? "Gmail" : "Google Calendar"
    setBusy(true)
    setError(null)
    try {
      const updated = await api.put<Settings>("/api/settings", {
        ...form,
        provider: form.provider,
        webchat_site: site,
        browser_headless: false,
      })
      setForm(updated)
      props.onSettingsChanged(updated)
      await api.post("/api/browser/action", { action: "navigate", url })
      setNotice(
        `A Chromium window opened. Sign in to ${label} and browse via the Browser panel.`,
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  const editing = tab === "model" || tab === "browser"

  return (
    <div
      className="modal-backdrop"
      onMouseDown={(event) => event.target === event.currentTarget && props.onClose()}
    >
      <div className="modal wide">
        <div className="modal-head">
          <h2>Settings</h2>
          <button className="icon-button" onClick={props.onClose} aria-label="Close settings">
            <X size={16} />
          </button>
        </div>

        <input className="file-filter-input" placeholder="Search settings…" value={settingsSearch} onChange={(e) => setSettingsSearch(e.target.value)} aria-label="Search settings tabs" style={{ margin: "8px 0" }} />
        {testResult && <div className="notice" role="status">{testResult}</div>}
        <div className="preset-row wrap">
          <button className="preset" onClick={async () => { try { await api.get("/api/diagnostics"); setTestResult("Config test passed: backend reachable, diagnostics OK.") } catch (err) { setTestResult(`Config test failed: ${err instanceof Error ? err.message : String(err)}`) } }}>Test my config</button>
          <button className="preset" onClick={() => { if (window.confirm("Reset all settings to defaults?")) setForm({ ...form, temperature: 0.2, max_steps: 32, browser_headless: true }) }}>Reset to defaults</button>
        </div>
        <details><summary>Effective config (read-only)</summary><pre style={{ maxHeight: 160, overflow: "auto", fontSize: 11 }}>{JSON.stringify({ provider: form.provider, model: form.model, gateway: form.gateway, auto_gateways: form.auto_gateways, active_agent: form.active_agent }, null, 2)}</pre></details>
        <div className="modal-tabs">
          {(!settingsSearch || "general model browser".includes(settingsSearch.toLowerCase())) && <button className={tab === "general" ? "active" : ""} onClick={() => setTab("general")}>
            <Cog size={13} /> General
          </button>}
          {(!settingsSearch || "model provider gateway key auto".includes(settingsSearch.toLowerCase())) && <button className={tab === "model" ? "active" : ""} onClick={() => setTab("model")}>
            <Bot size={13} /> Model
          </button>}
          {(!settingsSearch || "local models gguf download".includes(settingsSearch.toLowerCase())) && <button className={tab === "models" ? "active" : ""} onClick={() => setTab("models")}>
            <Download size={13} /> Local Models
          </button>}
          <button className={tab === "agents" ? "active" : ""} onClick={() => setTab("agents")}>
            <Sparkles size={13} /> Agents
          </button>
          <button className={tab === "browser" ? "active" : ""} onClick={() => setTab("browser")}>
            <Globe size={13} /> Browser
          </button>
          <button className={tab === "skills" ? "active" : ""} onClick={() => setTab("skills")}>
            <Puzzle size={13} /> Skills
          </button>
          {(!settingsSearch || "mcp servers tools".includes(settingsSearch.toLowerCase())) && <button className={tab === "mcp" ? "active" : ""} onClick={() => setTab("mcp")}>
            <Server size={13} /> MCP
          </button>}
        </div>

        {tab === "model" && (
          <>
            <div className="preset-row wrap">
              <button className="preset" onClick={() => applyPreset("local")}>
                Local (llama.cpp)
              </button>
              <button className="preset" onClick={() => applyPreset("keyless")}>
                Keyless (no signup)
              </button>
              <button className="preset" onClick={() => applyPreset("openrouter")}>
                OpenRouter (free)
              </button>
              <button className="preset" onClick={() => applyPreset("vercel")}>
                Vercel Gateway
              </button>
              <button className="preset" onClick={() => applyPreset("unorouter")}>
                UnoRouter
              </button>
              <button className="preset" onClick={() => applyPreset("opencode")}>
                OpenCode AI
              </button>
              <button className="preset" onClick={() => applyPreset("pollinations")}>
                Pollinations (free multimodal)
              </button>
              <button className="preset" onClick={() => applyPreset("openai")}>
                OpenAI
              </button>
              <button className="preset" onClick={() => applyPreset("chatgpt")}>
                ChatGPT (browser)
              </button>
              <button className="preset" onClick={() => applyPreset("gemini")}>
                Gemini (browser)
              </button>
              <button className="preset" onClick={() => applyPreset("custom")}>
                Custom
              </button>
            </div>

            <p className="tab-hint">
              <strong>OpenRouter free models</strong> need a free key from{" "}
              <code>openrouter.ai/keys</code>. <strong>ChatGPT / Gemini browser</strong> modes drive
              the signed-in web UI through the built-in browser — use the Browser tab to sign in
              first.
            </p>

            <label className="field">
              <span>Base URL (OpenAI-compatible)</span>
              <input
                value={form.base_url}
                onChange={(event) => set("base_url", event.target.value)}
                spellCheck={false}
              />
            </label>

            <div className="field-row">
              <label className="field grow">
                <span>Model</span>
                <input
                  value={form.model}
                  onChange={(event) => set("model", event.target.value)}
                  spellCheck={false}
                />
              </label>
              <label className="field grow">
                <span>API key</span>
                <input
                  type="password"
                  value={form.api_key}
                  onChange={(event) => {
                    const value = event.target.value
                    set("api_key", value)
                    // Every gateway saves its own key, so it is never lost.
                    setKeys((current) => ({ ...(current || {}), [form.gateway || "local"]: value }))
                  }}
                  placeholder={form.gateway === "local" ? "local model needs no key" : "sk-…"}
                />
              </label>
            </div>

            {form.gateway === "local" && (
              <label className="field">
                <span>Local GGUF model path</span>
                <input
                  value={form.local_model_path || ""}
                  onChange={(event) => set("local_model_path", event.target.value)}
                  placeholder="auto — picks the largest in ~/.llama or the bundled model"
                  spellCheck={false}
                />
              </label>
            )}

            <div className="gateway-keys">
              <div className="gateway-keys-head">
                <h4>Saved API keys (per gateway)</h4>
                <p className="tab-hint">
                  Keys are saved per gateway. Activate any LLM any time; every key stays available.
                </p>
              </div>
              <div className="gateway-keys-grid">
                {GATEWAYS.map((gw) => (
                  <label key={gw} className="gateway-key-field">
                    <span>{gw}</span>
                    <input
                      type="password"
                      value={form.keys?.[gw] ?? ""}
                      placeholder={gw === "local" ? "—" : "sk-…"}
                      onChange={(event) =>
                        setKeys((current) => ({ ...(current || {}), [gw]: event.target.value }))
                      }
                    />
                  </label>
                ))}
              </div>
            </div>

            <div className="field-row">
              <label className="field">
                <span>Temperature</span>
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  max="2"
                  value={form.temperature}
                  onChange={(event) => set("temperature", Number(event.target.value))}
                />
              </label>
              <label className="field">
                <span>Max steps</span>
                <input
                  type="number"
                  min="1"
                  max="100"
                  value={form.max_steps}
                  onChange={(event) => set("max_steps", Number(event.target.value))}
                />
              </label>
              <label className="field">
                <span>Language / Idioma / भाषा</span>
                <select value={getLocale()} onChange={(e) => setLocale(e.target.value as "en" | "es" | "hi")}>
                  <option value="en">English</option>
                  <option value="es">Español</option>
                  <option value="hi">हिन्दी</option>
                </select>
              </label>
              <label className="field">
                <span>Provider</span>
                <select value={form.provider} onChange={(event) => set("provider", event.target.value)}>
                  <option value="local">local (llama.cpp)</option>
                  <option value="keyless">keyless (no API key)</option>
                  <option value="openrouter">openrouter</option>
                  <option value="vercel">vercel (gateway)</option>
                  <option value="unorouter">unorouter</option>
                  <option value="opencode">opencode</option>
                  <option value="pollinations">pollinations</option>
                  <option value="openai">openai</option>
                  <option value="webchat">webchat</option>
                  <option value="custom">custom</option>
                </select>
              </label>
            </div>

            <label className="check">
              <input
                type="checkbox"
                checked={form.disable_thinking}
                onChange={(event) => set("disable_thinking", event.target.checked)}
              />
              <span>
                Disable model thinking <em>(local/llama.cpp: faster replies)</em>
              </span>
            </label>

            <label className="check">
              <input
                type="checkbox"
                checked={form.auto_approve_commands}
                onChange={(event) => set("auto_approve_commands", event.target.checked)}
              />
              <span>Auto-approve shell commands and desktop control</span>
            </label>

            <div className="hard-section">
              <div className="hard-head">
                <Zap size={13} />
                Auto route
                <span className="hard-badge">local → gateways → browser</span>
              </div>
              <p className="tab-hint">
                Auto mode tries the local llama.cpp model first, then every gateway below that has a
                saved key (in order), and finally the signed-in ChatGPT/Gemini browser tab. No single
                provider is hardcoded — activate whichever models you want.
              </p>

              <label className="check-field">
                <input type="checkbox" checked={form.allow_cloud_fallback} onChange={(event) => set("allow_cloud_fallback", event.target.checked)} />
                Allow Saved mode to also try other configured providers
              </label>
              <label className="check-field">
                <input type="checkbox" checked={form.allow_webchat_fallback} onChange={(event) => set("allow_webchat_fallback", event.target.checked)} />
                Allow Auto mode to fall back to a ChatGPT/Gemini browser tab
              </label>
              <label className="check-field">
                <input type="checkbox" checked={form.learn_workflows} onChange={(event) => set("learn_workflows", event.target.checked)} />
                Save successful tool sequences as reusable skills
              </label>
              <label className="check-field">
                <input type="checkbox" checked={Boolean((form as any).rubric_enabled)} onChange={(event) => set("rubric_enabled", event.target.checked)} />
                Rubric verify: grade work before finishing (deepagents-style)
              </label>
              {(form as any).rubric_enabled ? (
                <>
                  <label className="field">
                    <span>Rubric (blank = auto-inferred)</span>
                    <input value={(form as any).rubric_text ?? ""} onChange={(event) => set("rubric_text", event.target.value)} placeholder="Every file change is named; tests were run and reported..." />
                  </label>
                  <label className="field">
                    <span>Rubric max revisions</span>
                    <input type="number" min={1} max={5} value={(form as any).rubric_max_iterations ?? 2} onChange={(event) => set("rubric_max_iterations", Number(event.target.value))} />
                  </label>
                </>
              ) : null}

              <div className="auto-gateways">
                <h4>Gateway order &amp; models</h4>
                <p className="tab-hint">Toggle a gateway to include it in Auto mode; set a model override or leave blank for the gateway default.</p>
                {GATEWAYS.filter((gw) => gw !== "local").map((gw) => {
                  const enabled = (form.auto_gateways || []).includes(gw)
                  const hasKey = Boolean(form.keys?.[gw])
                  return (
                    <div key={gw} className="auto-gateway-row">
                      <label className="check">
                        <input
                          type="checkbox"
                          checked={enabled}
                          onChange={(event) => {
                            const current = form.auto_gateways || []
                            set("auto_gateways", event.target.checked ? [...current, gw] : current.filter((g) => g !== gw))
                          }}
                        />
                        <span>{gw}{gw === "keyless" ? " · no key needed" : hasKey ? "" : " · no key"}</span>
                      </label>
                      <input
                        className="auto-gateway-model"
                        value={form.gateway_models?.[gw] ?? ""}
                        placeholder="default model"
                        spellCheck={false}
                        onChange={(event) =>
                          setForm((current) => ({
                            ...current,
                            gateway_models: { ...(current.gateway_models || {}), [gw]: event.target.value },
                          }))
                        }
                      />
                    </div>
                  )
                })}
              </div>

              <label className="field">
                <span>Browser fallback site</span>
                <select
                  value={form.hard_fallback_site}
                  onChange={(event) => set("hard_fallback_site", event.target.value)}
                >
                  <option value="chatgpt">ChatGPT</option>
                  <option value="gemini">Gemini</option>
                </select>
              </label>
            </div>
          </>
        )}

        {tab === "models" && (
          <LocalModelsTab
            onError={setError}
            onNotice={setNotice}
            onActivated={(settings) => {
              setForm(settings)
              props.onSettingsChanged(settings)
            }}
          />
        )}

        {tab === "agents" && (
          <AgentsTab
            form={form}
            setForm={setForm}
            onSave={props.onSave}
            onSettingsChanged={props.onSettingsChanged}
            onError={setError}
            onNotice={setNotice}
          />
        )}

        {tab === "general" && (
          <>
            <section className="settings-section">
              <div className="section-head">
                <div className="section-title">
                  <svg />
                </div>
                <h3>Automations</h3>
                <span className="section-subtitle">
                  Repeated tasks the agent re-runs automatically (global persistence, while AgentDesk is open).
                </span>
              </div>
              <p className="tab-hint">
                Create a job and it runs as an AgentDesk session when due. Prompts, tools and shell/file access run the same as a chat.
              </p>
              <div className="automation-form">
                <input
                  value={newAutomationName}
                  onChange={(event) => setNewAutomationName(event.target.value)}
                  placeholder="Daily status digest"
                  spellCheck={false}
                />
                <input
                  value={newAutomationPrompt}
                  onChange={(event) => setNewAutomationPrompt(event.target.value)}
                  placeholder="Summarize the git log of this workspace..."
                  spellCheck={false}
                />
                <label className="field tiny">
                  <span>Every</span>
                  <select
                    value={newAutomationInterval}
                    onChange={(event) => setNewAutomationInterval(Number(event.target.value))}
                  >
                    <option value={5}>5 min</option>
                    <option value={15}>15 min</option>
                    <option value={30}>30 min</option>
                    <option value={60}>1 hour</option>
                    <option value={360}>6 hours</option>
                    <option value={720}>12 hours</option>
                    <option value={1440}>1 day</option>
                  </select>
                </label>
                <button
                  className="btn allow"
                  onClick={createAutomation}
                  disabled={automationBusy || !newAutomationName.trim() || !newAutomationPrompt.trim()}
                >
                  {automationBusy ? <Loader2 size={10} className="spin" /> : <Plus size={12} />} Add
                </button>
              </div>

              <div className="automation-list">
                {automations.length === 0 && <div className="empty-hint">No automations yet.</div>}
                {automations.map((automation) => (
                  <div className="automation-row" key={automation.id}>
                    <div className="automation-main">
                      <div className="automation-name">
                        {automation.status === "active" && <span className="status-dot active" />}
                        {automation.name}
                        <span className="automation-status">{automation.status}</span>
                      </div>
                      <div className="automation-meta">
                        every {automation.interval_minutes} min · {automation.prompt.slice(0, 120)}
                        {automation.last_status && ` · last: ${automation.last_status}`}
                      </div>
                    </div>
                    <button
                      className="icon-button tiny cancel"
                      title="Cancel"
                      disabled={automationBusy}
                      onClick={() => cancelAutomation(automation.id)}
                    >
                      <Trash2 size={12} />
                    </button>
                  </div>
                ))}
              </div>
            </section>

            <section className="settings-section">
              <h3>Global search</h3>
              <p className="tab-hint">
                Use <code>web_search</code> when you need fresh facts. Firecrawl is paid after a free tier;
                a key is required.
              </p>
              <label className="field">
                <span>Free.ai GPU API key <a href="https://free.ai/gpu/" target="_blank" rel="noreferrer" style={{fontSize:"0.75em",opacity:0.7}}>↗ 30K free tokens/day</a></span>
                <input
                  type="password"
                  value={(form as any).freeai_api_key || ""}
                  onChange={(event) => set("freeai_api_key" as any, event.target.value)}
                  placeholder="sk-free-..."
                />
              </label>

              <label className="field">
                <span>Firecrawl API key</span>
                <input
                  type="password"
                  value={form.firecrawl_api_key}
                  onChange={(event) => set("firecrawl_api_key", event.target.value)}
                  placeholder="fc-..."
                />
              </label>
              <label className="field">
                <span>GitHub token</span>
                <input
                  type="password"
                  value={form.github_token}
                  onChange={(event) => set("github_token", event.target.value)}
                  placeholder="ghp_..."
                />
              </label>

              <label className="field">
                <span>Vercel Gateway API key</span>
                <input
                  type="password"
                  value={form.gateway_api_key}
                  onChange={(event) => set("gateway_api_key", event.target.value)}
                  placeholder="vck_..."
                />
              </label>

              <label className="field">
                <span>OpenCode AI API key</span>
                <input
                  type="password"
                  value={form.api_key || ""}
                  onChange={(event) => set("api_key", event.target.value)}
                  placeholder="OpenCode account token"
                />
              </label>

              <label className="check">
                <input
                  type="checkbox"
                  checked={form.auto_approve_commands}
                  onChange={(event) => set("auto_approve_commands", event.target.checked)}
                />
                <span>Allow all shell commands (skip manual approvals)</span>
              </label>

              <label className="field">
                <span>Action policies JSON</span>
                <textarea
                  value={policyJson}
                  onChange={(event) => setPolicyJson(event.target.value)}
                  rows={7}
                  spellCheck={false}
                  placeholder='{"run_command": "ask", "browser_navigate": "allow", "mcp_playwright_browser_click": "deny"}'
                />
              </label>
              <div className="inline-actions">
                <button className="btn allow" onClick={applyPolicies} disabled={busy}>
                  Apply policies
                </button>
              </div>
            </section>
          </>
        )}

        {tab === "browser" && (
          <>
            <p className="tab-hint">
              The browser is a real Chromium managed by Playwright. It keeps a persistent profile, so
              ChatGPT and Gemini logins survive restarts.
            </p>

            <label className="check">
              <input
                type="checkbox"
                checked={form.browser_headless}
                onChange={(event) => set("browser_headless", event.target.checked)}
              />
              <span>
                Run browser headless <em>(turn off to see the Chromium window and sign in)</em>
              </span>
            </label>

            <label className="field">
              <span>
                DevTools / CDP port <em>(lets C++, C#, JavaScript tools attach to this browser)</em>
              </span>
              <input
                type="number"
                min={0}
                max={65535}
                value={form.browser_cdp_port ?? 9333}
                onChange={(event) => set("browser_cdp_port", Number(event.target.value) || 0)}
              />
            </label>
            <p className="tab-hint">
              Port 9333 exposes the Chrome DevTools Protocol on 127.0.0.1 — Puppeteer,
              Selenium, Playwright and raw CDP clients attach to the <em>same</em> browser
              (and your sign-ins). Set 0 to disable. Restart the browser to apply.
              The stable SDK token for REST/BiDi clients lives in
              <code> data\browser-sdk.token</code>.
            </p>

            <label className="field">
              <span>Web chatbot used by the “webchat” provider</span>
              <select value={form.webchat_site} onChange={(event) => set("webchat_site", event.target.value)}>
                <option value="chatgpt">ChatGPT (chatgpt.com)</option>
                <option value="gemini">Gemini (gemini.google.com)</option>
                <option value="drive">Google Drive</option>
                <option value="gmail">Gmail</option>
                <option value="calendar">Google Calendar</option>
              </select>
            </label>

            <div className="inline-actions">
              <button className="btn allow" onClick={() => openChatSite("chatgpt")} disabled={busy}>
                {busy ? <Loader2 size={13} className="spin" /> : <Globe size={13} />} Open ChatGPT login
              </button>
              <button className="btn allow" onClick={() => openChatSite("gemini")} disabled={busy}>
                {busy ? <Loader2 size={13} className="spin" /> : <Globe size={13} />} Open Gemini login
              </button>
              <button className="btn allow" onClick={() => openGoogleLogin("drive")} disabled={busy}>
                {busy ? <Loader2 size={13} className="spin" /> : <Globe size={13} />} Open Drive login
              </button>
              <button className="btn allow" onClick={() => openGoogleLogin("gmail")} disabled={busy}>
                {busy ? <Loader2 size={13} className="spin" /> : <Globe size={13} />} Open Gmail login
              </button>
              <button className="btn allow" onClick={() => openGoogleLogin("calendar")} disabled={busy}>
                {busy ? <Loader2 size={13} className="spin" /> : <Globe size={13} />} Open Calendar login
              </button>
            </div>

            <p className="modal-note">
              Workspace: <code>{form.workspace}</code>
            </p>
          </>
        )}

        {tab === "skills" && (
          <div className="settings-section">
            <p className="tab-hint">
              Skills are Markdown playbooks the agent loads on demand with <code>use_skill</code>.
              Install one from any raw URL (GitHub <code>blob</code> links are converted
              automatically), or write your own.
            </p>

            <div className="inline-form">
              <input
                value={skillUrl}
                onChange={(event) => setSkillUrl(event.target.value)}
                placeholder="https://raw.githubusercontent.com/…/SKILL.md"
                spellCheck={false}
              />
              <button className="btn allow" onClick={installSkill} disabled={busy || !skillUrl.trim()} aria-label="Install skill">
                <Download size={13} /> Install from URL
              </button>
            </div>

            <div className="skill-import">
              <div className="skill-import-head">
                <FolderInput size={13} />
                <span>Import a skill pack</span>
              </div>
              <p className="tab-hint">
                Point at a folder or a <code>.zip</code> that contains <code>SKILL.md</code> files
                (OpenHands, deepagents and GenAgent packs work as-is) and AgentDesk installs
                every skill it finds.
              </p>
              <div className="inline-form">
                <input
                  value={skillPackPath}
                  onChange={(event) => {
                    setSkillPackPath(event.target.value)
                    setSkillPackPreview([])
                  }}
                  placeholder="C:\Users\you\Downloads\OpenHands-1.43.0.zip"
                  spellCheck={false}
                />
                <button
                  className="btn" aria-label="Scan skill pack"
                  onClick={scanSkillPack}
                  disabled={busy || !skillPackPath.trim()}
                >
                  <Search size={13} /> Scan
                </button>
                <button
                  className="btn allow" aria-label="Import skill pack"
                  onClick={importSkillPack}
                  disabled={busy || !skillPackPath.trim()}
                >
                  <Download size={13} /> Import
                </button>
              </div>
              {skillPackPreview.length > 0 && (
                <div className="skill-preview">
                  {skillPackPreview.slice(0, 8).map((item) => (
                    <div className="skill-preview-row" key={item.name}>
                      <Puzzle size={11} />
                      <span className="skill-preview-name">{item.name}</span>
                      <span className="skill-preview-desc">{item.description.slice(0, 90)}</span>
                    </div>
                  ))}
                  {skillPackPreview.length > 8 && (
                    <div className="skill-preview-more">+{skillPackPreview.length - 8} more</div>
                  )}
                </div>
              )}
            </div>

            <div className="skill-list">
              {skills.map((skill) => (
                <div className="skill-row" key={skill.slug}>
                  <Puzzle size={13} className="skill-icon" />
                  <div className="skill-main">
                    <div className="skill-name">{skill.name}</div>
                    <div className="skill-desc">{skill.description || "No description"}</div>
                    <div className="skill-source" title={skill.source}>
                      {skill.source.startsWith("http") ? skill.source : skill.source || "local"}
                    </div>
                  </div>
                  <button
                    className="icon-button tiny"
                    title="Delete skill"
                    onClick={() => removeSkill(skill.slug)}
                  >
                    <Trash2 size={12} />
                  </button>
                </div>
              ))}
              {skills.length === 0 && <div className="empty-hint">No skills installed yet.</div>}
            </div>

            <details className="skill-new">
              <summary>
                <Plus size={12} /> Write a new skill
              </summary>
              <div className="skill-form">
                <div className="field-row">
                  <label className="field grow">
                    <span>Name</span>
                    <input value={skillName} onChange={(event) => setSkillName(event.target.value)} />
                  </label>
                  <label className="field grow">
                    <span>Description</span>
                    <input
                      value={skillDescription}
                      onChange={(event) => setSkillDescription(event.target.value)}
                    />
                  </label>
                </div>
                <label className="field">
                  <span>Instructions (Markdown)</span>
                  <textarea
                    rows={5}
                    value={skillContent}
                    onChange={(event) => setSkillContent(event.target.value)}
                    placeholder="When to use this skill, the exact steps, checks, and output format…"
                  />
                </label>
                <div className="inline-actions end">
                  <button className="btn allow" aria-label="Add skill" onClick={addSkill} disabled={busy}>
                    <Check size={13} /> Save skill
                  </button>
                </div>
              </div>
            </details>
          </div>
        )}

        {tab === "mcp" && (
          <div className="settings-section">
            <p className="tab-hint">
              MCP servers add tools to the agent. Adding a preset runs it with <code>npx -y</code> or{" "}
              <code>uvx</code>, which downloads the package automatically on first use.
            </p>

            <div className="mcp-presets">
              {mcpPresets.map((preset) => {
                const added = mcpServers.some((server) => server.id === preset.id)
                return (
                  <div className="mcp-preset" key={preset.id}>
                    <div className="mcp-preset-main">
                      <div className="skill-name">{preset.name}</div>
                      <div className="skill-desc">{preset.description}</div>
                    </div>
                    <button className="mini-button" onClick={() => addPreset(preset)} disabled={added}>
                      {added ? "added" : <><Plus size={10} /> add</>}
                    </button>
                  </div>
                )
              })}
            </div>

            <div className="section-label mcp-list-label">
              Configured servers
              <button className="icon-button tiny" onClick={loadMcp} title="Refresh status" aria-label="Refresh status">
                <RefreshCw size={11} />
              </button>
            </div>

            <div className="mcp-list">
              {mcpServers.map((server) => (
                <div className="mcp-row" key={server.id}>
                  <label className="check mcp-check">
                    <input
                      type="checkbox"
                      checked={server.enabled}
                      onChange={(event) => toggleMcp(server.id, event.target.checked)}
                    />
                  </label>
                  <div className="skill-main">
                    <div className="skill-name">
                      {server.name}
                      <span className={`mcp-status ${statusClass(server.status)}`}>
                        {server.status ?? "new"}
                      </span>
                    </div>
                    <div className="mcp-command">
                      {server.command} {server.args.join(" ")}
                    </div>
                    {server.error && <div className="mcp-error">{server.error}</div>}
                    {server.tools && server.tools.length > 0 && (
                      <div className="mcp-tools">
                        {server.tools.length} tools: {server.tools.map((tool) => tool.original).join(", ")}
                      </div>
                    )}
                    {editingServerId === server.id && (
                      <textarea
                        className="mcp-env-textarea"
                        rows={3}
                        spellCheck={false}
                        value={editEnvText}
                        onChange={(event) => setEditEnvText(event.target.value)}
                        placeholder='Env JSON, e.g. {"NOTION_TOKEN": "..."}'
                      />
                    )}
                  </div>
                  <button
                    className="icon-button tiny"
                    onClick={() => (editingServerId === server.id ? (setEditingServerId(null)) : editServerEnv(server))}
                    title={editingServerId === server.id ? "Cancel env edit" : "Edit env"}
                  >
                    <Pencil size={11} />
                  </button>
                  <button className="icon-button tiny" onClick={() => reconnectMcp(server.id)} title="Reconnect">
                    <RefreshCw size={11} />
                  </button>
                  <button className="icon-button tiny" onClick={() => removeMcp(server.id)} title="Remove">
                    <Trash2 size={12} />
                  </button>
                  {editingServerId === server.id && (
                    <button className="btn allow tiny" onClick={() => saveServerEnv(server)}>
                      Save env
                    </button>
                  )}
                </div>
              ))}
              {mcpServers.length === 0 && (
                <div className="empty-hint">Add a preset above, or a custom server below.</div>
              )}
            </div>

            <details className="skill-new">
              <summary>
                <Plus size={12} /> Custom stdio server
              </summary>
              <div className="skill-form">
                <div className="field-row">
                  <label className="field grow">
                    <span>Name</span>
                    <input value={customName} onChange={(event) => setCustomName(event.target.value)} />
                  </label>
                  <label className="field">
                    <span>Command</span>
                    <input
                      value={customCommand}
                      onChange={(event) => setCustomCommand(event.target.value)}
                    />
                  </label>
                </div>
                <label className="field">
                  <span>Arguments (space separated)</span>
                  <input value={customArgs} onChange={(event) => setCustomArgs(event.target.value)} />
                </label>
                <div className="inline-actions end">
                  <button className="btn allow" aria-label="Add custom MCP server" onClick={addCustomMcp}>
                    <Plus size={13} /> Add server
                  </button>
                </div>
              </div>
            </details>

            <div className="inline-actions end mcp-apply">
              {mcpDirty && <span className="dirty-hint">unsaved changes</span>}
              <button className="btn allow" onClick={applyMcp} disabled={busy || !mcpDirty}>
                {busy ? <Loader2 size={13} className="spin" /> : <Server size={13} />} Apply &amp; connect
              </button>
            </div>
          </div>
        )}

        {notice && (
          <div className="modal-notice">
            <Check size={13} /> {notice}
          </div>
        )}
        {error && <div className="modal-error">{error}</div>}

        <div className="modal-actions">
          <button className="btn deny" onClick={props.onClose}>
            {editing ? "Cancel" : "Close"}
          </button>
          {editing && (
            <button className="btn allow" onClick={save} disabled={busy}>
              {busy ? "Saving…" : "Save settings"}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
