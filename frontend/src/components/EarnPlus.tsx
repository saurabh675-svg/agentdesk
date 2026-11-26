import { useEffect, useState } from "react"
import { Trophy, HandCoins, Users } from "lucide-react"
import { api } from "../api"

type SubTab = "competitions" | "funds"

export default function EarnPlus() {
  const [tab, setTab] = useState<SubTab>("competitions")
  const [comps, setComps] = useState<Record<string, unknown>[]>([])
  const [funds, setFunds] = useState<Record<string, unknown>[]>([])
  const [owner, setOwner] = useState("Student")
  const [team, setTeam] = useState<string>("")
  const [msg, setMsg] = useState("")

  const load = async () => {
    try {
      setComps(await api.get("/api/competitions"))
    } catch {}
    try {
      setFunds(await api.get(`/api/earnings-plus/funds?owner=${encodeURIComponent(owner)}`))
    } catch {}
  }
  useEffect(() => {
    load()
  }, [owner])

  const showTeam = async (name: string) => {
    try {
      const r = await api.get<{ team: { role: string; task: string }[] }>(`/api/competitions/${encodeURIComponent(name)}/team`)
      setTeam(`${name}\n` + r.team.map((t) => `• ${t.role}: ${t.task}`).join("\n"))
    } catch (e) {
      setMsg(String(e))
    }
  }

  const toggleCheck = async (name: string, stage: string) => {
    try {
      const r = await api.post<{ checklist: Record<string, boolean> }>(`/api/competitions/${encodeURIComponent(name)}/checklist`, { stage, done: true })
      setMsg(`${name} [${stage}] → ${JSON.stringify(r.checklist)}`)
    } catch (e) {
      setMsg(String(e))
    }
  }

  const guidance = async (name: string) => {
    try {
      const r = await api.get(`/api/earnings-plus/funds/${encodeURIComponent(name)}/guidance?owner=${encodeURIComponent(owner)}`)
      setMsg(JSON.stringify(r).slice(0, 400))
    } catch (e) {
      setMsg(String(e))
    }
  }

  return (
    <section className="earn-section" aria-label="Global opportunities">
      <div className="earn-section-head">
        <h3>
          <Trophy size={13} /> Global · Competitions & Funds
        </h3>
        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          <select value={owner} onChange={(e) => setOwner(e.target.value)} aria-label="Owner type">
            {["Student", "Professional", "Researcher", "NGO", "Startup"].map((o) => (
              <option key={o}>{o}</option>
            ))}
          </select>
          <button className={`earn-link ${tab === "competitions" ? "active" : ""}`} onClick={() => setTab("competitions")}>
            <Trophy size={11} /> Competitions
          </button>
          <button className={`earn-link ${tab === "funds" ? "active" : ""}`} onClick={() => setTab("funds")}>
            <HandCoins size={11} /> Funds
          </button>
        </div>
      </div>
      {msg && (
        <p className="earn-note" style={{ whiteSpace: "pre-wrap" }}>
          {msg}
        </p>
      )}
      {tab === "competitions" ? (
        <div className="earn-grid">
          {comps.map((c) => (
            <article key={String(c.name)} className="earn-card">
              <h4>{String(c.name)}</h4>
              <p>
                {String(c.prize ?? "")} · due {String(c.deadline ?? "")}
              </p>
              <p className="earn-note">{(c as { eligibility?: string[] }).eligibility?.join(", ")}</p>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                <button className="earn-link" onClick={() => showTeam(String(c.name))}>
                  <Users size={11} /> Team plan
                </button>
                <button className="earn-link" onClick={() => toggleCheck(String(c.name), "rules")}>
                  Mark rules read
                </button>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className="earn-grid">
          {funds.map((f) => (
            <article key={String(f.name)} className="earn-card">
              <h4>{String(f.name)}</h4>
              <p>
                {String(f.sector ?? "")} · {String(f.ticket ?? "")} · due {String(f.deadline ?? "")}
              </p>
              <p className="earn-note">
                Owner ({owner}): {String(f.fit ?? "")}
              </p>
              <button className="earn-link" onClick={() => guidance(String(f.name))}>
                Next steps
              </button>
            </article>
          ))}
        </div>
      )}
      {team && (
        <pre className="earn-pre" style={{ whiteSpace: "pre-wrap" }}>
          {team}
        </pre>
      )}
    </section>
  )
}
