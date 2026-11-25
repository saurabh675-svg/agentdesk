"""AUTO-GENERATED — do not edit.

Source: docs/openapi.json  ·  Regenerate: python scripts/export_openapi.py
"""


from __future__ import annotations

import json
from typing import Any


BASE_URL = "http://127.0.0.1:8756"


class AgentDeskError(RuntimeError):
    def __init__(self, status: int, detail: str) -> None:
        super().__init__(f"HTTP {status}: {detail}")
        self.status = status
        self.detail = detail


class AgentDeskClient:
    """Typed loopback client for the AgentDesk API (generated)."""

    def __init__(self, token: str, base_url: str = BASE_URL, timeout: float = 60.0) -> None:
        self._token = token
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def _request(self, method: str, path: str, **params: Any) -> Any:
        import urllib.parse, urllib.request

        url = self._base_url + path
        query = {k: v for k, v in params.items() if v is not None and k != "body"}
        if query:
            url += "?" + urllib.parse.urlencode({k: str(v) for k, v in query.items()})
        body = params.get("body")
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", f"Bearer {self._token}")
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                raw = resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", "replace")
            try:
                detail = json.loads(raw).get("detail", raw)
            except Exception:
                detail = raw
            raise AgentDeskError(exc.code, str(detail)) from exc
        except urllib.error.URLError as exc:
            raise AgentDeskError(0, str(exc.reason)) from exc
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return raw

    def get_api_approvals(self, limit=None, session_id=None) -> Any:
        return self._request("GET", "/api/approvals", limit=limit, session_id=session_id)

    def get_api_automations(self) -> Any:
        return self._request("GET", "/api/automations")

    def post_api_automations(self, body=None) -> Any:
        return self._request("POST", "/api/automations", body=body)

    def post_api_automations_nl(self, body=None) -> Any:
        return self._request("POST", "/api/automations/nl", body=body)

    def post_api_automations_job_id_cancel(self, job_id=None) -> Any:
        return self._request("POST", "/api/automations/{job_id}/cancel", job_id=job_id)

    def post_api_backup_create(self) -> Any:
        return self._request("POST", "/api/backup/create")

    def get_api_backup_download_name(self, name=None) -> Any:
        return self._request("GET", "/api/backup/download/{name}", name=name)

    def get_api_brain(self) -> Any:
        return self._request("GET", "/api/brain")

    def post_api_brain(self, body=None) -> Any:
        return self._request("POST", "/api/brain", body=body)

    def get_api_brain_search(self, query=None, limit=None) -> Any:
        return self._request("GET", "/api/brain/search", query=query, limit=limit)

    def get_api_brain_search_hybrid(self, q=None, limit=None) -> Any:
        return self._request("GET", "/api/brain/search/hybrid", q=q, limit=limit)

    def post_api_browser_action(self, body=None) -> Any:
        return self._request("POST", "/api/browser/action", body=body)

    def get_api_browser_challenge(self) -> Any:
        return self._request("GET", "/api/browser/challenge")

    def post_api_browser_challenge_wait(self, body=None) -> Any:
        return self._request("POST", "/api/browser/challenge/wait", body=body)

    def get_api_browser_drivers(self) -> Any:
        return self._request("GET", "/api/browser/drivers")

    def post_api_browser_sdk_act(self, body=None) -> Any:
        return self._request("POST", "/api/browser/sdk/act", body=body)

    def get_api_browser_sdk_info(self) -> Any:
        return self._request("GET", "/api/browser/sdk/info")

    def post_api_browser_sdk_navigate(self, body=None) -> Any:
        return self._request("POST", "/api/browser/sdk/navigate", body=body)

    def get_api_browser_sdk_screenshot(self, fmt=None, quality=None) -> Any:
        return self._request("GET", "/api/browser/sdk/screenshot", fmt=fmt, quality=quality)

    def get_api_browser_sdk_snapshot(self, limit=None) -> Any:
        return self._request("GET", "/api/browser/sdk/snapshot", limit=limit)

    def get_api_browser_sdk_tabs(self) -> Any:
        return self._request("GET", "/api/browser/sdk/tabs")

    def get_api_browser_state(self) -> Any:
        return self._request("GET", "/api/browser/state")

    def post_api_computer_capture(self) -> Any:
        return self._request("POST", "/api/computer/capture")

    def get_api_computer_size(self) -> Any:
        return self._request("GET", "/api/computer/size")

    def get_api_computer_state(self) -> Any:
        return self._request("GET", "/api/computer/state")

    def get_api_diagnostics(self) -> Any:
        return self._request("GET", "/api/diagnostics")

    def get_api_diagnostics_metrics(self) -> Any:
        return self._request("GET", "/api/diagnostics/metrics")

    def get_api_diagnostics_native(self) -> Any:
        return self._request("GET", "/api/diagnostics/native")

    def get_api_diagnostics_openapi_json(self) -> Any:
        return self._request("GET", "/api/diagnostics/openapi.json")

    def get_api_diagnostics_spans(self, limit=None) -> Any:
        return self._request("GET", "/api/diagnostics/spans", limit=limit)

    def post_api_earnings_autopilot_tick(self) -> Any:
        return self._request("POST", "/api/earnings/autopilot/tick")

    def get_api_earnings_brief(self, venture_id=None) -> Any:
        return self._request("GET", "/api/earnings/brief", venture_id=venture_id)

    def get_api_earnings_income(self) -> Any:
        return self._request("GET", "/api/earnings/income")

    def post_api_earnings_income(self, body=None) -> Any:
        return self._request("POST", "/api/earnings/income", body=body)

    def post_api_earnings_income_import_csv(self, body=None) -> Any:
        return self._request("POST", "/api/earnings/income/import-csv", body=body)

    def post_api_earnings_launch(self, body=None) -> Any:
        return self._request("POST", "/api/earnings/launch", body=body)

    def get_api_earnings_learning(self, limit=None) -> Any:
        return self._request("GET", "/api/earnings/learning", limit=limit)

    def post_api_earnings_learning(self, body=None) -> Any:
        return self._request("POST", "/api/earnings/learning", body=body)

    def get_api_earnings_opportunities(self, query=None, category=None, limit=None) -> Any:
        return self._request("GET", "/api/earnings/opportunities", query=query, category=category, limit=limit)

    def get_api_earnings_overview(self) -> Any:
        return self._request("GET", "/api/earnings/overview")

    def post_api_earnings_radar(self, Body=None) -> Any:
        return self._request("POST", "/api/earnings/radar", Body=Body)

    def get_api_earnings_radar_last(self) -> Any:
        return self._request("GET", "/api/earnings/radar/last")

    def get_api_earnings_settings(self) -> Any:
        return self._request("GET", "/api/earnings/settings")

    def put_api_earnings_settings(self, body=None) -> Any:
        return self._request("PUT", "/api/earnings/settings", body=body)

    def get_api_earnings_ventures(self) -> Any:
        return self._request("GET", "/api/earnings/ventures")

    def get_api_earnings_ventures_venture_id(self, venture_id=None) -> Any:
        return self._request("GET", "/api/earnings/ventures/{venture_id}", venture_id=venture_id)

    def post_api_earnings_ventures_venture_id_tasks_task_id_complete(self, venture_id=None, task_id=None, Body=None) -> Any:
        return self._request("POST", "/api/earnings/ventures/{venture_id}/tasks/{task_id}/complete", venture_id=venture_id, task_id=task_id, Body=Body)

    def get_api_extensions_mcp_presets(self) -> Any:
        return self._request("GET", "/api/extensions/mcp/presets")

    def get_api_extensions_mcp_servers(self) -> Any:
        return self._request("GET", "/api/extensions/mcp/servers")

    def put_api_extensions_mcp_servers(self, body=None) -> Any:
        return self._request("PUT", "/api/extensions/mcp/servers", body=body)

    def put_api_extensions_mcp_servers_server_id(self, server_id=None, body=None) -> Any:
        return self._request("PUT", "/api/extensions/mcp/servers/{server_id}", server_id=server_id, body=body)

    def post_api_extensions_mcp_servers_server_id_reconnect(self, server_id=None) -> Any:
        return self._request("POST", "/api/extensions/mcp/servers/{server_id}/reconnect", server_id=server_id)

    def get_api_extensions_skills(self) -> Any:
        return self._request("GET", "/api/extensions/skills")

    def post_api_extensions_skills(self, body=None) -> Any:
        return self._request("POST", "/api/extensions/skills", body=body)

    def get_api_extensions_skills_bundled(self) -> Any:
        return self._request("GET", "/api/extensions/skills/bundled")

    def get_api_extensions_skills_evolution(self) -> Any:
        return self._request("GET", "/api/extensions/skills/evolution")

    def post_api_extensions_skills_evolution_propose(self, body=None) -> Any:
        return self._request("POST", "/api/extensions/skills/evolution/propose", body=body)

    def post_api_extensions_skills_evolution_skill_id_approve(self, skill_id=None) -> Any:
        return self._request("POST", "/api/extensions/skills/evolution/{skill_id}/approve", skill_id=skill_id)

    def post_api_extensions_skills_evolution_skill_id_reject(self, skill_id=None, body=None) -> Any:
        return self._request("POST", "/api/extensions/skills/evolution/{skill_id}/reject", skill_id=skill_id, body=body)

    def post_api_extensions_skills_evolution_skill_id_rollback(self, skill_id=None) -> Any:
        return self._request("POST", "/api/extensions/skills/evolution/{skill_id}/rollback", skill_id=skill_id)

    def post_api_extensions_skills_import(self, body=None) -> Any:
        return self._request("POST", "/api/extensions/skills/import", body=body)

    def post_api_extensions_skills_install(self, body=None) -> Any:
        return self._request("POST", "/api/extensions/skills/install", body=body)

    def get_api_extensions_skills_scan(self, path=None) -> Any:
        return self._request("GET", "/api/extensions/skills/scan", path=path)

    def delete_api_extensions_skills_slug_name(self, slug_name=None) -> Any:
        return self._request("DELETE", "/api/extensions/skills/{slug_name}", slug_name=slug_name)

    def get_api_health(self) -> Any:
        return self._request("GET", "/api/health")

    def post_api_mcp_server_call(self, Body=None) -> Any:
        return self._request("POST", "/api/mcp-server/call", Body=Body)

    def get_api_mcp_server_capabilities(self) -> Any:
        return self._request("GET", "/api/mcp-server/capabilities")

    def get_api_memory(self) -> Any:
        return self._request("GET", "/api/memory")

    def post_api_memory(self, body=None) -> Any:
        return self._request("POST", "/api/memory", body=body)

    def get_api_memory_projects(self) -> Any:
        return self._request("GET", "/api/memory/projects")

    def post_api_memory_projects(self, body=None) -> Any:
        return self._request("POST", "/api/memory/projects", body=body)

    def get_api_missions(self) -> Any:
        return self._request("GET", "/api/missions")

    def post_api_missions(self, body=None) -> Any:
        return self._request("POST", "/api/missions", body=body)

    def delete_api_missions_mission_id(self, mission_id=None) -> Any:
        return self._request("DELETE", "/api/missions/{mission_id}", mission_id=mission_id)

    def post_api_missions_mission_id_run(self, mission_id=None) -> Any:
        return self._request("POST", "/api/missions/{mission_id}/run", mission_id=mission_id)

    def get_api_models(self) -> Any:
        return self._request("GET", "/api/models")

    def post_api_models_activate(self, body=None) -> Any:
        return self._request("POST", "/api/models/activate", body=body)

    def get_api_models_backend(self) -> Any:
        return self._request("GET", "/api/models/backend")

    def post_api_models_backend(self, body=None) -> Any:
        return self._request("POST", "/api/models/backend", body=body)

    def post_api_models_download(self, body=None) -> Any:
        return self._request("POST", "/api/models/download", body=body)

    def get_api_models_status(self) -> Any:
        return self._request("GET", "/api/models/status")

    def delete_api_models_name(self, name=None) -> Any:
        return self._request("DELETE", "/api/models/{name}", name=name)

    def get_api_openrouter_models(self, refresh=None) -> Any:
        return self._request("GET", "/api/openrouter/models", refresh=refresh)

    def get_api_openrouter_recommended(self, preferred=None) -> Any:
        return self._request("GET", "/api/openrouter/recommended", preferred=preferred)

    def post_api_pet_ask(self, body=None) -> Any:
        return self._request("POST", "/api/pet/ask", body=body)

    def post_api_pet_expert(self, body=None) -> Any:
        return self._request("POST", "/api/pet/expert", body=body)

    def get_api_pet_expert_brief(self) -> Any:
        return self._request("GET", "/api/pet/expert/brief")

    def get_api_pet_expert_capabilities(self) -> Any:
        return self._request("GET", "/api/pet/expert/capabilities")

    def post_api_pet_sleep(self) -> Any:
        return self._request("POST", "/api/pet/sleep")

    def get_api_pet_status(self) -> Any:
        return self._request("GET", "/api/pet/status")

    def post_api_pet_toggle(self) -> Any:
        return self._request("POST", "/api/pet/toggle")

    def get_api_provider_health(self) -> Any:
        return self._request("GET", "/api/provider-health")

    def get_api_provider_health_metrics(self) -> Any:
        return self._request("GET", "/api/provider-health/metrics")

    def post_api_sandbox_run(self, body=None) -> Any:
        return self._request("POST", "/api/sandbox/run", body=body)

    def get_api_sandbox_session(self) -> Any:
        return self._request("GET", "/api/sandbox/session")

    def get_api_sessions(self) -> Any:
        return self._request("GET", "/api/sessions")

    def post_api_sessions(self, body=None) -> Any:
        return self._request("POST", "/api/sessions", body=body)

    def post_api_sessions_subagents(self, body=None) -> Any:
        return self._request("POST", "/api/sessions/subagents", body=body)

    def get_api_sessions_subagents_session_id(self, session_id=None) -> Any:
        return self._request("GET", "/api/sessions/subagents/{session_id}", session_id=session_id)

    def delete_api_sessions_session_id(self, session_id=None) -> Any:
        return self._request("DELETE", "/api/sessions/{session_id}", session_id=session_id)

    def get_api_sessions_session_id(self, session_id=None) -> Any:
        return self._request("GET", "/api/sessions/{session_id}", session_id=session_id)

    def patch_api_sessions_session_id(self, session_id=None, body=None) -> Any:
        return self._request("PATCH", "/api/sessions/{session_id}", session_id=session_id, body=body)

    def post_api_sessions_session_id_compact(self, session_id=None, body=None) -> Any:
        return self._request("POST", "/api/sessions/{session_id}/compact", session_id=session_id, body=body)

    def get_api_sessions_session_id_export(self, session_id=None) -> Any:
        return self._request("GET", "/api/sessions/{session_id}/export", session_id=session_id)

    def get_api_sessions_session_id_messages(self, session_id=None) -> Any:
        return self._request("GET", "/api/sessions/{session_id}/messages", session_id=session_id)

    def post_api_sessions_session_id_rewind_to_message_id(self, session_id=None, message_id=None) -> Any:
        return self._request("POST", "/api/sessions/{session_id}/rewind-to/{message_id}", session_id=session_id, message_id=message_id)

    def get_api_settings(self) -> Any:
        return self._request("GET", "/api/settings")

    def put_api_settings(self, body=None) -> Any:
        return self._request("PUT", "/api/settings", body=body)

    def post_api_uploads_files(self, body=None) -> Any:
        return self._request("POST", "/api/uploads/files", body=body)

    def get_api_workers(self) -> Any:
        return self._request("GET", "/api/workers")

    def get_api_workers_catalog(self) -> Any:
        return self._request("GET", "/api/workers/catalog")

    def post_api_workers_cline(self, Body=None) -> Any:
        return self._request("POST", "/api/workers/cline", Body=Body)

    def post_api_workers_kiro(self, Body=None) -> Any:
        return self._request("POST", "/api/workers/kiro", Body=Body)

    def post_api_workers_opencode(self, Body=None) -> Any:
        return self._request("POST", "/api/workers/opencode", Body=Body)

    def get_api_workers_worker_type_output(self, worker_type=None) -> Any:
        return self._request("GET", "/api/workers/{worker_type}/output", worker_type=worker_type)

    def post_api_workers_worker_type_stop(self, worker_type=None) -> Any:
        return self._request("POST", "/api/workers/{worker_type}/stop", worker_type=worker_type)

    def get_api_workspace(self) -> Any:
        return self._request("GET", "/api/workspace")

    def post_api_workspace(self, body=None) -> Any:
        return self._request("POST", "/api/workspace", body=body)

    def get_api_workspace_file(self, path=None) -> Any:
        return self._request("GET", "/api/workspace/file", path=path)

    def get_api_workspace_tree(self, path=None, depth=None) -> Any:
        return self._request("GET", "/api/workspace/tree", path=path, depth=depth)

    def post_v1_chat_completions(self, body=None) -> Any:
        return self._request("POST", "/v1/chat/completions", body=body)

    def get_v1_models(self) -> Any:
        return self._request("GET", "/v1/models")
