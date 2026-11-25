import { useCallback, useEffect, useState } from "react"
import {
  ArrowUpRight,
  Briefcase,
  Check,
  CheckCircle2,
  CircleDollarSign,
  Coins,
  Copy,
  Globe,
  Loader2,
  RefreshCw,
  Rocket,
  Sparkles,
  Target,
  TrendingUp,
} from "lucide-react"
import { api } from "../api"
import type {
  EarningBrief,
  EarningOpportunity,
  EarningOverview,
  EarningRadar,
  EarningVenture,
} from "../types"

interface Props {
  agentBusy: boolean
  onAskAgent: (prompt: string) => void
  onOpenBrowser?: (url: string) => void
}

function money(amount: number, currency: string): string {
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency: currency || "USD",
      maximumFractionDigits: 2,
    }).format(amount)
  } catch {
    return `${currency} ${amount.toFixed(2)}`
  }
}

function dateLabel(seconds: number): string {
  return new Date(seconds * 1000).toLocaleDateString(undefined, { month: "short", day: "numeric" })
}

export default function EarnPane({ agentBusy, onAskAgent, onOpenBrowser }: Props) {
  const [overview, setOverview] = useState<EarningOverview | null>(null)
  const [opps, setOpps] = useState<EarningOpportunity[]>([])
  const [category, setCategory] = useState("All")
  const [query, setQuery] = useState("")
  const [scanning, setScanning] = useState(false)
  const [radar, setRadar] = useState<EarningRadar | null>(null)
  const [selected, setSelected] = useState<number | null>(null)
  const [brief, setBrief] = useState<EarningBrief | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [copied, setCopied] = useState<string | null>(null)
  const [lesson, setLesson] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [results, setResults] = useState<Record<number, string>>({})
  const [incomeInputs, setIncomeInputs] = useState<Record<number, string>>({})
  const [currency, setCurrency] = useState("USD")
  const [skills, setSkills] = useState("")
  const [showTune, setShowTune] = useState(false)

  const load = useCallback(async () => {
    const data = await api.get<EarningOverview>("/api/earnings/overview")
    setOverview(data)
    if (category === "All") setOpps(data.best_opportunities)
    setCurrency(data.settings.currency)
    setSkills(data.settings.skills.join(", "))
    return data
  }, [category])

  useEffect(() => {
    load().catch((err) => setError(err instanceof Error ? err.message : String(err)))
  }, [load])

  const openVenture = useCallback(async (ventureId: number, url?: string) => {
    setSelected(ventureId)
    try {
      const data = await api.get<EarningBrief>(`/api/earnings/brief?venture_id=${ventureId}`)
      setBrief(data)
      if (url && onOpenBrowser) onOpenBrowser(url)
      else if (!url) setError("This venture has no site URL to open in the browser.")
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }, [onOpenBrowser])

  const activeVentures = overview?.active_ventures ?? []
  const selectedVenture: EarningVenture | undefined =
    activeVentures.find((venture) => venture.id === selected) ?? activeVentures[0]
  const activeBrief = selectedVenture && brief ? brief : null

  useEffect(() => {
    if (!selected && activeVentures.length > 0) {
      const first = activeVentures[0].id
      setSelected(first)
      api
        .get<EarningBrief>(`/api/earnings/brief?venture_id=${first}`)
        .then(setBrief)
        .catch(() => undefined)
    }
  }, [activeVentures, selected])

  const totalEarned = Object.values(overview?.income ?? {}).reduce((sum, value) => sum + value, 0)
  const incomeEvents = overview?.income_events ?? []
  const incomeChart = (() => {
    if (incomeEvents.length < 2) return null
    const sorted = [...incomeEvents].sort((a, b) => a.created_at - b.created_at)
    const max = Math.max(...sorted.map((e) => e.amount), 1)
    const pts = sorted.map((e, i) => `${(i / Math.max(1, sorted.length - 1)) * 100},${100 - (e.amount / max) * 90}`).join(" ")
    return (<svg viewBox="0 0 100 100" preserveAspectRatio="none" style={{ width: "100%", height: 80 }} aria-label="Income over time"><polyline points={pts} fill="none" stroke="#4ade80" strokeWidth="2" vectorEffect="non-scaling-stroke" /></svg>)
  })()

  const doScan = async () => {
    setScanning(true)
    setError(null)
    try {
      const result = await api.post<EarningRadar>("/api/earnings/radar", {
        query: query.trim() || undefined,
        category: category === "All" ? undefined : category,
        limit: 8,
      })
      setRadar(result)
      setOpps(result.opportunities)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setScanning(false)
    }
  }

  const pickCategory = async (next: string) => {
    setCategory(next)
    setRadar(null)
    try {
      if (next === "All") {
        setOpps(overview?.best_opportunities ?? [])
      } else {
        setOpps(
          await api.get<EarningOpportunity[]>(
            `/api/earnings/opportunities?category=${encodeURIComponent(next)}&limit=24`,
          ),
        )
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  const launch = async (opportunityId: string) => {
    setBusy(`launch-${opportunityId}`)
    setError(null)
    try {
      const venture = await api.post<EarningVenture>("/api/earnings/launch", {
        opportunity_id: opportunityId,
      })
      await load()
      await openVenture(venture.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(null)
    }
  }

  const complete = async (ventureId: number, taskId: number) => {
    setBusy(`task-${taskId}`)
    setError(null)
    try {
      const income = Number(incomeInputs[taskId] || 0)
      await api.post(`/api/earnings/ventures/${ventureId}/tasks/${taskId}/complete`, {
        result: results[taskId] || "Completed from the Earn tab.",
        income: Number.isFinite(income) ? income : 0,
      })
      setResults((current) => ({ ...current, [taskId]: "" }))
      setIncomeInputs((current) => ({ ...current, [taskId]: "" }))
      await load()
      await openVenture(ventureId)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(null)
    }
  }

  const toggleAutopilot = async () => {
    if (!overview) return
    setBusy("autopilot")
    try {
      await api.put("/api/earnings/settings", { autopilot: !overview.autopilot })
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(null)
    }
  }

  const saveTuning = async () => {
    setBusy("tune")
    try {
      await api.put("/api/earnings/settings", {
        currency,
        skills: skills
          .split(",")
          .map((skill) => skill.trim())
          .filter(Boolean),
      })
      await load()
      setShowTune(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(null)
    }
  }

  const saveLesson = async () => {
    if (!lesson.trim()) return
    setBusy("lesson")
    try {
      await api.post("/api/earnings/learning", { lesson: lesson.trim() })
      setLesson("")
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(null)
    }
  }

  const copy = (key: string, text: string) => {
    navigator.clipboard.writeText(text).catch(() => undefined)
    setCopied(key)
    window.setTimeout(() => setCopied(null), 1600)
  }

  return (
    <div className="earn-view">
      <div className="earn-hero">
        <div className="earn-hero-top">
          <div>
            <span className="earn-kicker">
              <TrendingUp size={11} /> Global earnings · founder OS
            </span>
            <h2>Company brain</h2>
          </div>
          <span className={`earn-live ${agentBusy ? "busy" : ""}`} title="Agent activity">
            {agentBusy ? <Loader2 size={12} className="spin" /> : <Sparkles size={12} />}
            {agentBusy ? "agent working" : "ready"}
          </span>
        </div>
        <p className="earn-lede">
          Finds realistic ways to earn, ranks the free-first ones, turns the best into a 30-day
          company plan, drafts the work, tracks income and learns from every result.
          {incomeChart && <div style={{ marginTop: 8 }}>{incomeChart}<div style={{ fontSize: 11, opacity: 0.7 }}>Income over time (recent events)</div></div>}
        </p>
        <div className="earn-stats">
          <div>
            <span>Earned</span>
            <strong>{money(totalEarned, overview?.currency ?? "USD")}</strong>
          </div>
          <div>
            <span>Ventures</span>
            <strong>{overview?.ventures_count ?? 0}</strong>
          </div>
          <div>
            <span>Open tasks</span>
            <strong>{overview?.tasks_pending ?? 0}</strong>
          </div>
          <div>
            <span>Done</span>
            <strong>{overview?.tasks_done ?? 0}</strong>
          </div>
        </div>
        <div className="earn-controls">
          <button
            className={`earn-toggle ${overview?.autopilot ? "on" : ""}`}
            onClick={toggleAutopilot}
            disabled={busy === "autopilot"}
            title="Autopilot drafts local assets only; it never sends or spends"
          >
            <span className="earn-toggle-track">
              <span />
            </span>
            Autopilot {overview?.autopilot ? "on" : "off"}
          </button>
          <button className="earn-link" onClick={() => setShowTune((value) => !value)}>
            <Target size={11} /> Tune profile
          </button>
          <button className="earn-link" onClick={() => load().catch(() => undefined)}>
            <RefreshCw size={11} /> Refresh
          </button>
        </div>
        {showTune && (
          <div className="earn-tune">
            <label>
              Currency
              <select value={currency} onChange={(event) => setCurrency(event.target.value)}>
                {["USD", "INR", "EUR", "GBP", "AED", "SGD"].map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Skills (comma separated)
              <input value={skills} onChange={(event) => setSkills(event.target.value)} />
            </label>
            <button className="earn-launch small" onClick={saveTuning} disabled={busy === "tune"}>
              {busy === "tune" ? <Loader2 size={12} className="spin" /> : <Check size={12} />} Save
            </button>
          </div>
        )}
      </div>

      {error && (
        <div className="earn-error" onClick={() => setError(null)}>
          {error}
        </div>
      )}

      <section className="earn-section">
        <div className="earn-section-head">
          <div>
            <CircleDollarSign size={13} /> Opportunity radar
            <span className="earn-count">{opps.length}</span>
          </div>
          {radar?.live_search && <span className="earn-live-badge">live web</span>}
        </div>
        <div className="earn-scan">
          <input
            value={query}
            placeholder="Search a field, e.g. AI automation, data annotation, design…"
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") doScan().catch(() => undefined)
            }}
          />
          <button onClick={doScan} disabled={scanning}>
            {scanning ? <Loader2 size={12} className="spin" /> : <Sparkles size={12} />}
            {scanning ? "Scanning" : "Scan"}
          </button>
        </div>
        <div className="earn-cats">
          {["All", ...(overview?.categories ?? [])].map((item) => (
            <button
              key={item}
              className={`earn-cat ${category === item ? "active" : ""}`}
              onClick={() => pickCategory(item)}
            >
              {item}
            </button>
          ))}
        </div>
        <div className="earn-opps">
          {opps.map((opp) => {
            const launchedVenture = activeVentures.find((item) => item.opportunity_id === opp.id)
            return (
            <div className="earn-opp" key={opp.id}>
              <div className="earn-opp-top">
                <span className="earn-score">{opp.score}</span>
                <div className="earn-opp-title">
                  <strong>{opp.title}</strong>
                  <span>
                    {opp.category} · {opp.platforms.slice(0, 2).join(" / ")}
                  </span>
                </div>
                <button
                  className="earn-launch small"
                  disabled={busy === `launch-${opp.id}` || Boolean(opp.launched)}
                  onClick={() => launch(opp.id)}
                >
                  {busy === `launch-${opp.id}` ? (
                    <Loader2 size={11} className="spin" />
                  ) : opp.launched ? (
                    <Check size={11} />
                  ) : (
                    <Rocket size={11} />
                  )}
                  {opp.launched ? "Running" : "Launch"}
                </button>
              </div>
              <p>{opp.summary}</p>
              <div className="earn-opp-meta">
                <span>{opp.startup_cost <= 0 ? "free start" : `$${opp.startup_cost} start`}</span>
                <span>{opp.time_to_cash_days}d to cash</span>
                <span>{opp.automation}% auto</span>
                <span>{opp.pricing}</span>
              </div>
              <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", marginTop: "8px" }}>
                {opp.url && onOpenBrowser && (
                  <button
                    className="earn-open"
                    onClick={() => onOpenBrowser(opp.url!)}
                    title="Open in in-built stealth browser"
                  >
                    <Globe size={11} /> Open in Browser
                  </button>
                )}
                {opp.url && (
                  <button
                    className="earn-open"
                    onClick={() =>
                      onAskAgent(
                        `Inspect this live opportunity at ${opp.url}: Extract all requirements, verify feasibility, and draft a high-quality deliverable in our workspace.`
                      )
                    }
                    title="Ask agent to research and automate"
                  >
                    <Sparkles size={11} /> Automate with Agent
                  </button>
                )}
                {opp.launched && launchedVenture && (
                  <button
                    className="earn-open"
                    title="Open this venture's site in the inbuilt browser"
                    onClick={() => openVenture(launchedVenture.id, launchedVenture.opportunity?.url || opp.url)}
                  >
                    Open venture <ArrowUpRight size={11} />
                  </button>
                )}
              </div>
            </div>
            )
          })}
        </div>
        {radar?.signals && radar.signals.length > 0 && (
          <div className="earn-signals">
            <div className="earn-signals-head">
              <Globe size={13} /> Live signals
            </div>
            {radar.signals.slice(0, 6).map((signal) => (
              <div
                key={`${signal.url}-${signal.title}`}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: "8px",
                  padding: "4px 0",
                  borderBottom: "1px solid var(--border-soft)",
                }}
              >
                <span
                  style={{
                    fontSize: "11px",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                    maxWidth: "60%",
                  }}
                  title={signal.title}
                >
                  {signal.title}
                </span>
                <div style={{ display: "flex", gap: "4px" }}>
                  {signal.url && onOpenBrowser && (
                    <button
                      className="earn-open"
                      style={{ padding: "2px 6px", fontSize: "10px" }}
                      onClick={() => onOpenBrowser(signal.url)}
                      title="Open in in-built browser"
                    >
                      <Globe size={10} /> Browser
                    </button>
                  )}
                  {signal.url && (
                    <button
                      className="earn-open"
                      style={{ padding: "2px 6px", fontSize: "10px" }}
                      onClick={() =>
                        onAskAgent(`Investigate this opportunity at ${signal.url} and prepare a solution.`)
                      }
                      title="Ask agent to automate"
                    >
                      <Sparkles size={10} /> Automate
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="earn-section">
        <div className="earn-section-head">
          <div>
            <Briefcase size={13} /> Ventures
            <span className="earn-count">{activeVentures.length}</span>
          </div>
          {selectedVenture && (
            <span className="earn-progress-label">
              {selectedVenture.progress.done}/{selectedVenture.progress.total} tasks
            </span>
          )}
        </div>
        {activeVentures.length === 0 ? (
          <div className="earn-empty">
            Launch one opportunity above. The engine creates a 30-day plan with roles, tasks,
            drafts and a learning loop.
          </div>
        ) : (
          <>
            <div className="earn-venture-tabs">
              {activeVentures.map((venture) => (
                <button
                  key={venture.id}
                  className={`earn-venture-tab ${selectedVenture?.id === venture.id ? "active" : ""}`}
                  onClick={() => openVenture(venture.id)}
                >
                  <span>{venture.name}</span>
                  <em>
                    {venture.progress.done}/{venture.progress.total}
                  </em>
                </button>
              ))}
            </div>
            {selectedVenture && (
              <div className="earn-venture">
                <div className="earn-venture-head">
                  <div>
                    <strong>{selectedVenture.name}</strong>
                    <span>{selectedVenture.opportunity?.category ?? "venture"}</span>
                  </div>
                  <div className="earn-venture-tools">
                    {selectedVenture.opportunity?.url && onOpenBrowser && (
                      <button
                        className="earn-open"
                        title="Open venture site in the inbuilt browser"
                        onClick={() => onOpenBrowser(selectedVenture.opportunity!.url!)}
                      >
                        <Globe size={11} /> Open site
                      </button>
                    )}
                    <div className="earn-venture-money">
                      {Object.entries(selectedVenture.income).length === 0
                        ? money(0, selectedVenture.currency)
                        : Object.entries(selectedVenture.income)
                            .map(([cur, amount]) => money(amount, cur))
                            .join(" · ")}
                    </div>
                  </div>
                </div>
                <p className="earn-mission">{selectedVenture.mission}</p>
                <div className="earn-bar">
                  <span
                    style={{
                      width: `${
                        selectedVenture.progress.total
                          ? (selectedVenture.progress.done / selectedVenture.progress.total) * 100
                          : 0
                      }%`,
                    }}
                  />
                </div>

                <div className="earn-actions">
                  <div className="earn-subhead">
                    <Coins size={12} /> Next best actions
                  </div>
                  {(activeBrief?.actions ?? []).slice(0, 3).map((action) => (
                    <div className="earn-action" key={action.task_id}>
                      <div className="earn-action-head">
                        <span className={`earn-role role-${action.role.toLowerCase()}`}>{action.role}</span>
                        <strong>{action.title}</strong>
                        <span className="earn-min">{action.estimate_min}m</span>
                      </div>
                      <div className="earn-action-accept">Done when: {action.acceptance}</div>
                      <pre className="earn-draft">{action.draft}</pre>
                      <div className="earn-action-row">
                        <input
                          className="earn-result"
                          placeholder="What did you produce? (optional)"
                          value={results[action.task_id] ?? ""}
                          onChange={(event) =>
                            setResults((current) => ({ ...current, [action.task_id]: event.target.value }))
                          }
                        />
                        <input
                          className="earn-income"
                          placeholder="income"
                          inputMode="decimal"
                          value={incomeInputs[action.task_id] ?? ""}
                          onChange={(event) =>
                            setIncomeInputs((current) => ({ ...current, [action.task_id]: event.target.value }))
                          }
                        />
                      </div>
                      <div className="earn-action-row wrap">
                        <button
                          className="earn-ghost"
                          onClick={() => copy(`draft-${action.task_id}`, action.draft)}
                        >
                          {copied === `draft-${action.task_id}` ? <Check size={11} /> : <Copy size={11} />}
                          {copied === `draft-${action.task_id}` ? "Copied" : "Copy draft"}
                        </button>
                        <button
                          className="earn-ghost"
                          onClick={() =>
                            onAskAgent(
                              `Help me execute this Earn task in venture "${action.venture}" (task #${action.task_id}): ${action.title}.\n\nAcceptance: ${action.acceptance}\n\nDraft:\n${action.draft}\n\nDo the work, then tell me exactly what changed and what I should approve next.`,
                            )
                          }
                        >
                          <Sparkles size={11} /> Work on this
                        </button>
                        <button
                          className="earn-done"
                          disabled={busy === `task-${action.task_id}`}
                          onClick={() => complete(selectedVenture.id, action.task_id)}
                        >
                          {busy === `task-${action.task_id}` ? (
                            <Loader2 size={11} className="spin" />
                          ) : (
                            <CheckCircle2 size={11} />
                          )}
                          Mark done
                        </button>
                      </div>
                    </div>
                  ))}
                  {(activeBrief?.actions ?? []).length === 0 && (
                    <div className="earn-empty">All current tasks are done. Review KPIs and write a lesson.</div>
                  )}
                </div>

                <details className="earn-all-tasks">
                  <summary>All 30-day tasks</summary>
                  {["Validate", "Launch", "Deliver", "Scale"].map((phase) => {
                    const tasks = selectedVenture.tasks.filter((task) => task.phase === phase)
                    if (tasks.length === 0) return null
                    return (
                      <div className="earn-phase" key={phase}>
                        <div className="earn-phase-name">{phase}</div>
                        {tasks.map((task) => (
                          <div className={`earn-task ${task.status === "done" ? "done" : ""}`} key={task.id}>
                            <span className="earn-check">{task.status === "done" && <Check size={10} />}</span>
                            <div>
                              <strong>{task.title}</strong>
                              <span>
                                {task.role} · {task.estimate_min}m · priority {task.priority}
                              </span>
                            </div>
                            {task.status !== "done" && (
                              <button
                                className="earn-ghost tiny"
                                onClick={() => complete(selectedVenture.id, task.id)}
                                disabled={busy === `task-${task.id}`}
                              >
                                <Check size={10} />
                              </button>
                            )}
                          </div>
                        ))}
                      </div>
                    )
                  })}
                </details>
              </div>
            )}
          </>
        )}
      </section>

      <section className="earn-section">
        <div className="earn-section-head">
          <div>
            <Sparkles size={13} /> Recursive learning
            <span className="earn-count">{overview?.learning.length ?? 0}</span>
          </div>
          <span className="earn-progress-label">feeds every plan</span>
        </div>
        <div className="earn-learning">
          {(overview?.learning ?? []).map((item) => (
            <div className="earn-lesson" key={item.id}>
              <span className="earn-lesson-date">{dateLabel(item.created_at)}</span>
              <p>{item.lesson}</p>
              {item.tags && <span className="earn-tag">{item.tags}</span>}
            </div>
          ))}
          {(overview?.learning ?? []).length === 0 && (
            <div className="earn-empty">No lessons yet. Finish a task or save one below.</div>
          )}
        </div>
        <div className="earn-lesson-add">
          <input
            value={lesson}
            placeholder="Lesson learned — what should the next plan do differently?"
            onChange={(event) => setLesson(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") saveLesson().catch(() => undefined)
            }}
          />
          <button onClick={saveLesson} disabled={busy === "lesson" || !lesson.trim()}>
            {busy === "lesson" ? <Loader2 size={12} className="spin" /> : <Check size={12} />} Save
          </button>
        </div>
      </section>

      <div className="earn-guardrail">{overview?.guardrail}</div>
    </div>
  )
}

function GlobeIcon() {
  return <ArrowUpRight size={11} />
}
