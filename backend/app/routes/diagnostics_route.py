"""Diagnostics routes: the redacted snapshot, Prometheus metrics, spans and
the native-accelerator status.

`GET /api/diagnostics` returns a redacted snapshot (no API keys ever leave the
process); the other endpoints report telemetry and which native components are
live.
"""

from fastapi import APIRouter, Response

from .. import telemetry
from ..diagnostics import agentdesk_snapshot

router = APIRouter()


@router.get("")
def snapshot_endpoint() -> dict:
    """Redacted diagnostics snapshot (providers, local model, browser, MCP…)."""
    return agentdesk_snapshot()


@router.get("/metrics")
def metrics_endpoint() -> Response:
    """Prometheus text exposition format for AgentDesk."""
    return Response(content=telemetry.prometheus_metrics(), media_type="text/plain; version=0.0.4; charset=utf-8")


@router.get("/spans")
def spans_endpoint(limit: int = 100) -> dict:
    """Recent OTLP-shaped spans (route -> plan -> tool call -> stream)."""
    return {"spans": telemetry.recent_spans(max(1, min(limit, 500)))}


@router.get("/native")
def native_endpoint() -> dict:
    """Which native accelerators are live (Rust core) and which sidecars exist."""
    info: dict = {"languages": {}}
    try:
        from .. import native_core

        info["languages"]["rust_core"] = native_core.backend_info()
    except Exception as exc:
        info["languages"]["rust_core"] = {"backend": "unavailable", "error": str(exc)[:200]}
    try:
        from .. import win_sidecar

        info["languages"]["dotnet_sidecar"] = win_sidecar.sidecar.status()
    except Exception as exc:
        info["languages"]["dotnet_sidecar"] = {"available": False, "error": str(exc)[:200]}
    try:
        from pathlib import Path

        here = Path(__file__).resolve()
        candidates = [
            here.parents[3] / "native" / "cdp_helper" / "cdp_helper.exe",  # installed: resources/native/...
            here.parents[4] / "native" / "cdp_helper" / "cdp_helper.exe",  # repo root
            here.parents[2] / "native" / "cdp_helper" / "cdp_helper.exe",
        ]
        helper = next((c for c in candidates if c.exists()), candidates[0])
        info["languages"]["cpp_cdp_helper"] = {
            "available": helper.exists(),
            "path": str(helper),
        }
    except Exception:
        info["languages"]["cpp_cdp_helper"] = {"available": False}
    return info


@router.get("/openapi.json")
def openapi_endpoint() -> dict:
    """The live OpenAPI 3.1 contract (also written to docs/openapi.json)."""
    from ..main import app

    return app.openapi()
