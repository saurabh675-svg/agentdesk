/**
 * AUTO-GENERATED — do not edit.
 * Source: docs/openapi.json  ·  Regenerate: python scripts/export_openapi.py
 */


export const BASE_URL = 'http://127.0.0.1:8756';

export class AgentDeskHttpError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

export interface RequestOptions {
  method: string;
  path: string;
  query?: Record<string, unknown>;
  body?: unknown;
}

export function createClient(token: string, baseUrl = BASE_URL) {
  const request = async (opts: RequestOptions) => {
    const url = new URL(opts.path, baseUrl);
    if (opts.query) Object.entries(opts.query).forEach(([k, v]) => url.searchParams.set(k, String(v)));
    const res = await fetch(url.toString(), {
      method: opts.method,
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
    });
    const text = await res.text();
    const data = text ? JSON.parse(text) : null;
    if (!res.ok) throw new AgentDeskHttpError(res.status, data?.detail ?? text);
    return data;
  };

  const client = {
  "GET /api/approvals": (args: any = {}) => request({ method: "GET", path: `/api/approvals`, query: { limit: args["limit"], session_id: args["session_id"] } }),
  "GET /api/automations": (args: any = {}) => request({ method: "GET", path: `/api/automations` }),
  "POST /api/automations": (args: any = {}) => request({ method: "POST", path: `/api/automations`, body: args.body }),
  "POST /api/automations/nl": (args: any = {}) => request({ method: "POST", path: `/api/automations/nl`, body: args.body }),
  "POST /api/automations/{job_id}/cancel": (args: any = {}) => request({ method: "POST", path: `/api/automations/${encodeURIComponent(String(args["job_id"]))}/cancel` }),
  "POST /api/backup/create": (args: any = {}) => request({ method: "POST", path: `/api/backup/create` }),
  "GET /api/backup/download/{name}": (args: any = {}) => request({ method: "GET", path: `/api/backup/download/${encodeURIComponent(String(args["name"]))}` }),
  "GET /api/brain": (args: any = {}) => request({ method: "GET", path: `/api/brain` }),
  "POST /api/brain": (args: any = {}) => request({ method: "POST", path: `/api/brain`, body: args.body }),
  "GET /api/brain/search": (args: any = {}) => request({ method: "GET", path: `/api/brain/search`, query: { query: args["query"], limit: args["limit"] } }),
  "GET /api/brain/search/hybrid": (args: any = {}) => request({ method: "GET", path: `/api/brain/search/hybrid`, query: { q: args["q"], limit: args["limit"] } }),
  "POST /api/browser/action": (args: any = {}) => request({ method: "POST", path: `/api/browser/action`, body: args.body }),
  "GET /api/browser/challenge": (args: any = {}) => request({ method: "GET", path: `/api/browser/challenge` }),
  "POST /api/browser/challenge/wait": (args: any = {}) => request({ method: "POST", path: `/api/browser/challenge/wait`, body: args.body }),
  "GET /api/browser/drivers": (args: any = {}) => request({ method: "GET", path: `/api/browser/drivers` }),
  "POST /api/browser/sdk/act": (args: any = {}) => request({ method: "POST", path: `/api/browser/sdk/act`, body: args.body }),
  "GET /api/browser/sdk/info": (args: any = {}) => request({ method: "GET", path: `/api/browser/sdk/info` }),
  "POST /api/browser/sdk/navigate": (args: any = {}) => request({ method: "POST", path: `/api/browser/sdk/navigate`, body: args.body }),
  "GET /api/browser/sdk/screenshot": (args: any = {}) => request({ method: "GET", path: `/api/browser/sdk/screenshot`, query: { fmt: args["fmt"], quality: args["quality"] } }),
  "GET /api/browser/sdk/snapshot": (args: any = {}) => request({ method: "GET", path: `/api/browser/sdk/snapshot`, query: { limit: args["limit"] } }),
  "GET /api/browser/sdk/tabs": (args: any = {}) => request({ method: "GET", path: `/api/browser/sdk/tabs` }),
  "GET /api/browser/state": (args: any = {}) => request({ method: "GET", path: `/api/browser/state` }),
  "GET /api/competitions": (args: any = {}) => request({ method: "GET", path: `/api/competitions` }),
  "POST /api/competitions": (args: any = {}) => request({ method: "POST", path: `/api/competitions`, query: { Body: args["Body"] } }),
  "POST /api/competitions/{name}/checklist": (args: any = {}) => request({ method: "POST", path: `/api/competitions/${encodeURIComponent(String(args["name"]))}/checklist`, query: { Body: args["Body"] } }),
  "GET /api/competitions/{name}/team": (args: any = {}) => request({ method: "GET", path: `/api/competitions/${encodeURIComponent(String(args["name"]))}/team` }),
  "POST /api/computer/capture": (args: any = {}) => request({ method: "POST", path: `/api/computer/capture` }),
  "GET /api/computer/size": (args: any = {}) => request({ method: "GET", path: `/api/computer/size` }),
  "GET /api/computer/state": (args: any = {}) => request({ method: "GET", path: `/api/computer/state` }),
  "GET /api/diagnostics": (args: any = {}) => request({ method: "GET", path: `/api/diagnostics` }),
  "GET /api/diagnostics/metrics": (args: any = {}) => request({ method: "GET", path: `/api/diagnostics/metrics` }),
  "GET /api/diagnostics/native": (args: any = {}) => request({ method: "GET", path: `/api/diagnostics/native` }),
  "GET /api/diagnostics/openapi.json": (args: any = {}) => request({ method: "GET", path: `/api/diagnostics/openapi.json` }),
  "GET /api/diagnostics/spans": (args: any = {}) => request({ method: "GET", path: `/api/diagnostics/spans`, query: { limit: args["limit"] } }),
  "POST /api/downloads/scan": (args: any = {}) => request({ method: "POST", path: `/api/downloads/scan`, query: { force: args["force"] } }),
  "POST /api/earnings-plus/export-doc": (args: any = {}) => request({ method: "POST", path: `/api/earnings-plus/export-doc`, query: { Body: args["Body"] } }),
  "GET /api/earnings-plus/funds": (args: any = {}) => request({ method: "GET", path: `/api/earnings-plus/funds`, query: { owner: args["owner"] } }),
  "GET /api/earnings-plus/funds/{name}/guidance": (args: any = {}) => request({ method: "GET", path: `/api/earnings-plus/funds/${encodeURIComponent(String(args["name"]))}/guidance`, query: { owner: args["owner"] } }),
  "GET /api/earnings-plus/projects": (args: any = {}) => request({ method: "GET", path: `/api/earnings-plus/projects` }),
  "POST /api/earnings-plus/projects": (args: any = {}) => request({ method: "POST", path: `/api/earnings-plus/projects`, query: { Body: args["Body"] } }),
  "POST /api/earnings/autopilot/tick": (args: any = {}) => request({ method: "POST", path: `/api/earnings/autopilot/tick` }),
  "GET /api/earnings/brief": (args: any = {}) => request({ method: "GET", path: `/api/earnings/brief`, query: { venture_id: args["venture_id"] } }),
  "GET /api/earnings/income": (args: any = {}) => request({ method: "GET", path: `/api/earnings/income` }),
  "POST /api/earnings/income": (args: any = {}) => request({ method: "POST", path: `/api/earnings/income`, body: args.body }),
  "POST /api/earnings/income/import-csv": (args: any = {}) => request({ method: "POST", path: `/api/earnings/income/import-csv`, body: args.body }),
  "POST /api/earnings/launch": (args: any = {}) => request({ method: "POST", path: `/api/earnings/launch`, body: args.body }),
  "GET /api/earnings/learning": (args: any = {}) => request({ method: "GET", path: `/api/earnings/learning`, query: { limit: args["limit"] } }),
  "POST /api/earnings/learning": (args: any = {}) => request({ method: "POST", path: `/api/earnings/learning`, body: args.body }),
  "GET /api/earnings/opportunities": (args: any = {}) => request({ method: "GET", path: `/api/earnings/opportunities`, query: { query: args["query"], category: args["category"], limit: args["limit"] } }),
  "GET /api/earnings/overview": (args: any = {}) => request({ method: "GET", path: `/api/earnings/overview` }),
  "POST /api/earnings/radar": (args: any = {}) => request({ method: "POST", path: `/api/earnings/radar`, query: { Body: args["Body"] } }),
  "GET /api/earnings/radar/last": (args: any = {}) => request({ method: "GET", path: `/api/earnings/radar/last` }),
  "GET /api/earnings/settings": (args: any = {}) => request({ method: "GET", path: `/api/earnings/settings` }),
  "PUT /api/earnings/settings": (args: any = {}) => request({ method: "PUT", path: `/api/earnings/settings`, body: args.body }),
  "GET /api/earnings/ventures": (args: any = {}) => request({ method: "GET", path: `/api/earnings/ventures` }),
  "GET /api/earnings/ventures/{venture_id}": (args: any = {}) => request({ method: "GET", path: `/api/earnings/ventures/${encodeURIComponent(String(args["venture_id"]))}` }),
  "POST /api/earnings/ventures/{venture_id}/tasks/{task_id}/complete": (args: any = {}) => request({ method: "POST", path: `/api/earnings/ventures/${encodeURIComponent(String(args["venture_id"]))}/tasks/${encodeURIComponent(String(args["task_id"]))}/complete`, query: { Body: args["Body"] } }),
  "GET /api/extensions/mcp/presets": (args: any = {}) => request({ method: "GET", path: `/api/extensions/mcp/presets` }),
  "GET /api/extensions/mcp/servers": (args: any = {}) => request({ method: "GET", path: `/api/extensions/mcp/servers` }),
  "PUT /api/extensions/mcp/servers": (args: any = {}) => request({ method: "PUT", path: `/api/extensions/mcp/servers`, body: args.body }),
  "PUT /api/extensions/mcp/servers/{server_id}": (args: any = {}) => request({ method: "PUT", path: `/api/extensions/mcp/servers/${encodeURIComponent(String(args["server_id"]))}`, body: args.body }),
  "POST /api/extensions/mcp/servers/{server_id}/reconnect": (args: any = {}) => request({ method: "POST", path: `/api/extensions/mcp/servers/${encodeURIComponent(String(args["server_id"]))}/reconnect` }),
  "GET /api/extensions/skills": (args: any = {}) => request({ method: "GET", path: `/api/extensions/skills` }),
  "POST /api/extensions/skills": (args: any = {}) => request({ method: "POST", path: `/api/extensions/skills`, body: args.body }),
  "GET /api/extensions/skills/bundled": (args: any = {}) => request({ method: "GET", path: `/api/extensions/skills/bundled` }),
  "GET /api/extensions/skills/evolution": (args: any = {}) => request({ method: "GET", path: `/api/extensions/skills/evolution` }),
  "POST /api/extensions/skills/evolution/propose": (args: any = {}) => request({ method: "POST", path: `/api/extensions/skills/evolution/propose`, body: args.body }),
  "POST /api/extensions/skills/evolution/{skill_id}/approve": (args: any = {}) => request({ method: "POST", path: `/api/extensions/skills/evolution/${encodeURIComponent(String(args["skill_id"]))}/approve` }),
  "POST /api/extensions/skills/evolution/{skill_id}/reject": (args: any = {}) => request({ method: "POST", path: `/api/extensions/skills/evolution/${encodeURIComponent(String(args["skill_id"]))}/reject`, body: args.body }),
  "POST /api/extensions/skills/evolution/{skill_id}/rollback": (args: any = {}) => request({ method: "POST", path: `/api/extensions/skills/evolution/${encodeURIComponent(String(args["skill_id"]))}/rollback` }),
  "POST /api/extensions/skills/import": (args: any = {}) => request({ method: "POST", path: `/api/extensions/skills/import`, body: args.body }),
  "POST /api/extensions/skills/install": (args: any = {}) => request({ method: "POST", path: `/api/extensions/skills/install`, body: args.body }),
  "GET /api/extensions/skills/scan": (args: any = {}) => request({ method: "GET", path: `/api/extensions/skills/scan`, query: { path: args["path"] } }),
  "DELETE /api/extensions/skills/{slug_name}": (args: any = {}) => request({ method: "DELETE", path: `/api/extensions/skills/${encodeURIComponent(String(args["slug_name"]))}` }),
  "GET /api/health": (args: any = {}) => request({ method: "GET", path: `/api/health` }),
  "POST /api/mcp-server/call": (args: any = {}) => request({ method: "POST", path: `/api/mcp-server/call`, query: { Body: args["Body"] } }),
  "GET /api/mcp-server/capabilities": (args: any = {}) => request({ method: "GET", path: `/api/mcp-server/capabilities` }),
  "GET /api/memory": (args: any = {}) => request({ method: "GET", path: `/api/memory` }),
  "POST /api/memory": (args: any = {}) => request({ method: "POST", path: `/api/memory`, body: args.body }),
  "GET /api/memory/projects": (args: any = {}) => request({ method: "GET", path: `/api/memory/projects` }),
  "POST /api/memory/projects": (args: any = {}) => request({ method: "POST", path: `/api/memory/projects`, body: args.body }),
  "GET /api/missions": (args: any = {}) => request({ method: "GET", path: `/api/missions` }),
  "POST /api/missions": (args: any = {}) => request({ method: "POST", path: `/api/missions`, body: args.body }),
  "DELETE /api/missions/{mission_id}": (args: any = {}) => request({ method: "DELETE", path: `/api/missions/${encodeURIComponent(String(args["mission_id"]))}` }),
  "POST /api/missions/{mission_id}/run": (args: any = {}) => request({ method: "POST", path: `/api/missions/${encodeURIComponent(String(args["mission_id"]))}/run` }),
  "GET /api/models": (args: any = {}) => request({ method: "GET", path: `/api/models` }),
  "POST /api/models/activate": (args: any = {}) => request({ method: "POST", path: `/api/models/activate`, body: args.body }),
  "GET /api/models/backend": (args: any = {}) => request({ method: "GET", path: `/api/models/backend` }),
  "POST /api/models/backend": (args: any = {}) => request({ method: "POST", path: `/api/models/backend`, body: args.body }),
  "POST /api/models/download": (args: any = {}) => request({ method: "POST", path: `/api/models/download`, body: args.body }),
  "GET /api/models/status": (args: any = {}) => request({ method: "GET", path: `/api/models/status` }),
  "DELETE /api/models/{name}": (args: any = {}) => request({ method: "DELETE", path: `/api/models/${encodeURIComponent(String(args["name"]))}` }),
  "GET /api/openrouter/models": (args: any = {}) => request({ method: "GET", path: `/api/openrouter/models`, query: { refresh: args["refresh"] } }),
  "GET /api/openrouter/recommended": (args: any = {}) => request({ method: "GET", path: `/api/openrouter/recommended`, query: { preferred: args["preferred"] } }),
  "POST /api/pet/ask": (args: any = {}) => request({ method: "POST", path: `/api/pet/ask`, body: args.body }),
  "POST /api/pet/expert": (args: any = {}) => request({ method: "POST", path: `/api/pet/expert`, body: args.body }),
  "GET /api/pet/expert/brief": (args: any = {}) => request({ method: "GET", path: `/api/pet/expert/brief` }),
  "GET /api/pet/expert/capabilities": (args: any = {}) => request({ method: "GET", path: `/api/pet/expert/capabilities` }),
  "POST /api/pet/sleep": (args: any = {}) => request({ method: "POST", path: `/api/pet/sleep` }),
  "GET /api/pet/status": (args: any = {}) => request({ method: "GET", path: `/api/pet/status` }),
  "POST /api/pet/toggle": (args: any = {}) => request({ method: "POST", path: `/api/pet/toggle` }),
  "GET /api/provider-health": (args: any = {}) => request({ method: "GET", path: `/api/provider-health` }),
  "GET /api/provider-health/metrics": (args: any = {}) => request({ method: "GET", path: `/api/provider-health/metrics` }),
  "POST /api/sandbox/run": (args: any = {}) => request({ method: "POST", path: `/api/sandbox/run`, body: args.body }),
  "GET /api/sandbox/session": (args: any = {}) => request({ method: "GET", path: `/api/sandbox/session` }),
  "GET /api/sessions": (args: any = {}) => request({ method: "GET", path: `/api/sessions` }),
  "POST /api/sessions": (args: any = {}) => request({ method: "POST", path: `/api/sessions`, body: args.body }),
  "POST /api/sessions/subagents": (args: any = {}) => request({ method: "POST", path: `/api/sessions/subagents`, body: args.body }),
  "GET /api/sessions/subagents/{session_id}": (args: any = {}) => request({ method: "GET", path: `/api/sessions/subagents/${encodeURIComponent(String(args["session_id"]))}` }),
  "DELETE /api/sessions/{session_id}": (args: any = {}) => request({ method: "DELETE", path: `/api/sessions/${encodeURIComponent(String(args["session_id"]))}` }),
  "GET /api/sessions/{session_id}": (args: any = {}) => request({ method: "GET", path: `/api/sessions/${encodeURIComponent(String(args["session_id"]))}` }),
  "PATCH /api/sessions/{session_id}": (args: any = {}) => request({ method: "PATCH", path: `/api/sessions/${encodeURIComponent(String(args["session_id"]))}`, body: args.body }),
  "POST /api/sessions/{session_id}/compact": (args: any = {}) => request({ method: "POST", path: `/api/sessions/${encodeURIComponent(String(args["session_id"]))}/compact`, body: args.body }),
  "GET /api/sessions/{session_id}/export": (args: any = {}) => request({ method: "GET", path: `/api/sessions/${encodeURIComponent(String(args["session_id"]))}/export` }),
  "GET /api/sessions/{session_id}/messages": (args: any = {}) => request({ method: "GET", path: `/api/sessions/${encodeURIComponent(String(args["session_id"]))}/messages` }),
  "POST /api/sessions/{session_id}/rewind-to/{message_id}": (args: any = {}) => request({ method: "POST", path: `/api/sessions/${encodeURIComponent(String(args["session_id"]))}/rewind-to/${encodeURIComponent(String(args["message_id"]))}` }),
  "GET /api/settings": (args: any = {}) => request({ method: "GET", path: `/api/settings` }),
  "PUT /api/settings": (args: any = {}) => request({ method: "PUT", path: `/api/settings`, body: args.body }),
  "POST /api/uploads/files": (args: any = {}) => request({ method: "POST", path: `/api/uploads/files`, body: args.body }),
  "GET /api/workers": (args: any = {}) => request({ method: "GET", path: `/api/workers` }),
  "GET /api/workers/catalog": (args: any = {}) => request({ method: "GET", path: `/api/workers/catalog` }),
  "POST /api/workers/cline": (args: any = {}) => request({ method: "POST", path: `/api/workers/cline`, query: { Body: args["Body"] } }),
  "POST /api/workers/kiro": (args: any = {}) => request({ method: "POST", path: `/api/workers/kiro`, query: { Body: args["Body"] } }),
  "POST /api/workers/opencode": (args: any = {}) => request({ method: "POST", path: `/api/workers/opencode`, query: { Body: args["Body"] } }),
  "GET /api/workers/{worker_type}/output": (args: any = {}) => request({ method: "GET", path: `/api/workers/${encodeURIComponent(String(args["worker_type"]))}/output` }),
  "POST /api/workers/{worker_type}/stop": (args: any = {}) => request({ method: "POST", path: `/api/workers/${encodeURIComponent(String(args["worker_type"]))}/stop` }),
  "GET /api/workspace": (args: any = {}) => request({ method: "GET", path: `/api/workspace` }),
  "POST /api/workspace": (args: any = {}) => request({ method: "POST", path: `/api/workspace`, body: args.body }),
  "GET /api/workspace/file": (args: any = {}) => request({ method: "GET", path: `/api/workspace/file`, query: { path: args["path"] } }),
  "GET /api/workspace/tree": (args: any = {}) => request({ method: "GET", path: `/api/workspace/tree`, query: { path: args["path"], depth: args["depth"] } }),
  "POST /v1/chat/completions": (args: any = {}) => request({ method: "POST", path: `/v1/chat/completions`, body: args.body }),
  "GET /v1/models": (args: any = {}) => request({ method: "GET", path: `/v1/models` }),
  } as const;

  return client;
}
