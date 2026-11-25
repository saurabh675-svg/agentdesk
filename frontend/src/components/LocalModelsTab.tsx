import { useCallback, useEffect, useRef, useState } from "react"
import { Check, Download, Loader2, Play, RefreshCw, Trash2 } from "lucide-react"
import { api } from "../api"
import type { ModelsPayload, Settings } from "../types"

interface Props {
  onError: (message: string | null) => void
  onNotice: (message: string | null) => void
  onActivated: (settings: Settings) => void
}

function formatSize(bytes: number): string {
  if (!bytes) return "—"
  const gb = bytes / 1_000_000_000
  if (gb >= 1) return `${gb.toFixed(2)} GB`
  return `${Math.round(bytes / 1_000_000)} MB`
}

export default function LocalModelsTab({ onError, onNotice, onActivated }: Props) {
  const [data, setData] = useState<ModelsPayload | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [customUrl, setCustomUrl] = useState("")
  const [customName, setCustomName] = useState("")
  const [backendChoice, setBackendChoice] = useState("auto")
  const [backendBusy, setBackendBusy] = useState(false)
  const timer = useRef<number | null>(null)

  const load = useCallback(async () => {
    try {
      setData(await api.get<ModelsPayload>("/api/models"))
    } catch (err) {
      onError(err instanceof Error ? err.message : String(err))
    }
  }, [onError])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    if (data?.backend?.selected) setBackendChoice(data.backend.selected)
  }, [data?.backend?.selected])

  const applyBackend = async () => {
    setBackendBusy(true)
    onError(null)
    try {
      await api.post("/api/models/backend", { backend: backendChoice })
      onNotice("Local inference backend switched and llama.cpp restarted.")
      await load()
    } catch (err) {
      onError(err instanceof Error ? err.message : String(err))
    } finally {
      setBackendBusy(false)
    }
  }

  // Poll progress while a download is active.
  useEffect(() => {
    const active = data?.download?.active
    if (active) {
      timer.current = window.setInterval(load, 1500)
    }
    return () => {
      if (timer.current) window.clearInterval(timer.current)
      timer.current = null
    }
  }, [data?.download?.active, load])

  const download = async (modelId?: string, url?: string, filename?: string) => {
    setBusy(modelId || url || "custom")
    onError(null)
    try {
      await api.post("/api/models/download", { model_id: modelId, url: url || "", filename })
      onNotice("Model downloaded. Activate it to use it locally.")
      await load()
    } catch (err) {
      onError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(null)
    }
  }

  const activate = async (path: string) => {
    setBusy(path)
    onError(null)
    try {
      await api.post("/api/models/activate", { path })
      const settings = await api.get<Settings>("/api/settings")
      onActivated(settings)
      onNotice("Local model activated and llama.cpp restarted.")
      await load()
    } catch (err) {
      onError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(null)
    }
  }

  const remove = async (path: string) => {
    const isActiveModel = (data?.local || []).some((m) => m.path === path && m.active)
    if (isActiveModel) { onError("Cannot delete the active model while it is in use. Activate another model first."); return }
    if (dl?.active) { onError("Cannot delete a model while a download is in progress."); return }
    setBusy(path)
    try {
      await api.delete(`/api/models/${encodeURIComponent(path)}`)
      onNotice("Model removed.")
      await load()
    } catch (err) {
      onError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(null)
    }
  }

  const dl = data?.download
  const progress = dl?.total ? Math.min(100, Math.round(((dl.downloaded || 0) / dl.total) * 100)) : 0

  return (
    <div className="local-models">
      <div className="section-head">
        <h3>Local llama.cpp models</h3>
        <button className="mini-button" onClick={load} title="Refresh">
          <RefreshCw size={11} />
        </button>
      </div>
      <p className="tab-hint">
        Download GGUF models and run them fully offline through the bundled llama.cpp server.
        Models are stored in <code>{data?.models_dir || "…"}</code>.
      </p>

      <div className="model-row">
        <div className="model-row-main">
          <span className="model-name">Inference backend</span>
          <span className="model-meta">
            Active: {data?.backend?.active === "vulkan" ? "Vulkan GPU" : "CPU"}
            {data?.backend?.available ? " · Vulkan runtime bundled" : " · Vulkan binary not found"}
            {data?.backend?.active === "vulkan" ? ` · ${data?.backend?.gpu_layers} GPU layers` : ""}
          </span>
        </div>
        <div className="model-row-actions">
          <select value={backendChoice} onChange={(event) => setBackendChoice(event.target.value)} disabled={backendBusy}>
            <option value="auto">Auto (Vulkan if available)</option>
            <option value="vulkan" disabled={!data?.backend?.available}>Vulkan GPU</option>
            <option value="cpu">CPU</option>
          </select>
          <button
            className="mini-button"
            disabled={backendBusy || backendChoice === data?.backend?.selected}
            onClick={applyBackend}
          >
            Apply
          </button>
        </div>
      </div>

      {dl?.active && (
        <div className="download-progress">
          <div className="download-progress-label">
            <Loader2 size={11} className="spin" /> Downloading {dl.filename} · {formatSize(dl.downloaded || 0)}
            {dl.total ? ` / ${formatSize(dl.total)}` : ""}
          </div>
          <div className="progress-track">
            <div className="progress-fill" style={{ width: `${progress}%` }} />
          </div>
        </div>
      )}

      <h4>Installed</h4>
      <div className="model-list">
        {(data?.local || []).map((model) => (
          <div key={model.path} className={`model-row ${model.active ? "active" : ""}`}>
            <div className="model-row-main">
              <span className="model-name">{model.name}</span>
              <span className="model-meta">
                {formatSize(model.size_bytes)}
                {model.builtin ? " · bundled" : ""}
                {model.active ? " · active" : ""}
              </span>
            </div>
            <div className="model-row-actions">
              {model.active ? (
                <span className="model-active-badge"><Check size={11} /> active</span>
              ) : (
                <button className="mini-button" disabled={busy === model.path} onClick={() => activate(model.path)}>
                  {busy === model.path ? <Loader2 size={11} className="spin" /> : <Play size={11} />} Activate
                </button>
              )}
              {!model.builtin && (
                <button className="mini-button danger" disabled={busy === model.path} onClick={() => remove(model.path)}>
                  <Trash2 size={11} />
                </button>
              )}
            </div>
          </div>
        ))}
        {data && data.local.length === 0 && <p className="tab-hint">No local models found yet.</p>}
      </div>

      <h4>Download a model</h4>
      <div className="model-list">
        {(data?.catalog || []).map((model) => (
          <div key={model.id} className="model-row">
            <div className="model-row-main">
              <span className="model-name">{model.name}</span>
              <span className="model-meta">{formatSize(model.size_bytes)} · {Math.round(model.context / 1000)}k ctx — {model.description}</span>
            </div>
            <div className="model-row-actions">
              {model.downloaded ? (
                <span className="model-active-badge"><Check size={11} /> downloaded</span>
              ) : (
                <button className="mini-button" disabled={Boolean(dl?.active) || busy === model.id} onClick={() => download(model.id)}>
                  {busy === model.id ? <Loader2 size={11} className="spin" /> : <Download size={11} />} Download
                </button>
              )}
            </div>
          </div>
        ))}
      </div>

      <h4>Custom GGUF URL</h4>
      <div className="custom-model-form">
        <input value={customUrl} onChange={(e) => setCustomUrl(e.target.value)} placeholder="https://huggingface.co/…/resolve/main/model.gguf" spellCheck={false} />
        <input value={customName} onChange={(e) => setCustomName(e.target.value)} placeholder="filename.gguf (optional)" spellCheck={false} />
        <button
          className="mini-button"
          disabled={!customUrl.trim() || Boolean(dl?.active)}
          onClick={() => download(undefined, customUrl.trim(), customName.trim() || undefined)}
        >
          <Download size={11} /> Download
        </button>
      </div>
    </div>
  )
}
