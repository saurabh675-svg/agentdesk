"""Lightweight telemetry for AgentDesk.

Design goals (see docs/NEXT_UPGRADES_CUTTING_EDGE.md, phase 0.7.0):

* **No new runtime dependency.** The OpenTelemetry *SDK* is not bundled, so we
  emit OTLP-shaped JSON spans ourselves and keep the exporter swappable: when
  `opentelemetry-sdk` is installed later, only ``_span_sink`` changes.
* **Prometheus text format** at ``GET /api/metrics`` so any scraper (or a
  browser tab) can read counters and latency histograms.
* **Cheap to call.** Every span is a dict append; no network in the hot path.

Metrics exposed:

* ``agentdesk_turn_total`` — agent turns by route/provider
* ``agentdesk_tool_total`` — tool calls by tool name and outcome
* ``agentdesk_tool_duration_seconds`` — histogram (buckets 5/50/250/1000/5000 ms)
* ``agentdesk_turn_duration_seconds`` — histogram
* ``agentdesk_llm_tokens_total`` — tokens by provider
* ``agentdesk_http_requests_total`` — API requests by route
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any

_lock = threading.Lock()
_spans: list[dict] = []
MAX_SPANS = 4000

_counters: dict[tuple[str, tuple[tuple[str, str], ...]], float] = {}
_histograms: dict[tuple[str, tuple[tuple[str, str], ...]], list[float]] = {}
_histogram_bounds: dict[str, list[float]] = {}


def _data_dir() -> Path:
    from .config import DATA_DIR

    return Path(DATA_DIR)


def _inc(name: str, value: float = 1.0, **labels: Any) -> None:
    key = (name, tuple(sorted((str(k), str(v)) for k, v in labels.items())))
    with _lock:
        _counters[key] = _counters.get(key, 0.0) + value


def _observe(name: str, value_ms: float, **labels: Any) -> None:
    key = (name, tuple(sorted((str(k), str(v)) for k, v in labels.items())))
    with _lock:
        _histograms.setdefault(key, []).append(float(value_ms))
        vals = _histograms[key]
        if len(vals) > 2000:
            del vals[: len(vals) - 2000]


def counter(name: str, value: float = 1.0, **labels: Any) -> None:
    """Increment a counter, e.g. ``counter('tool_calls', tool='read_file', outcome='ok')``."""
    _inc(name, value, **labels)


def observe(name: str, value_ms: float, **labels: Any) -> None:
    """Record a duration in milliseconds, e.g. ``observe('tool_duration', ms, tool='shell')``."""
    _observe(name, value_ms, **labels)


class span:
    """Context manager that records one OTLP-shaped span.

    Usage::

        with telemetry.span("agent.turn", provider="keyless") as sp:
            sp.set_attribute("route", "auto")
    """

    def __init__(self, name: str, **attributes: Any) -> None:
        self.name = name
        self.attributes: dict[str, Any] = dict(attributes)
        self.started = time.time()
        self.ended = 0.0
        self.error: str | None = None

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def __enter__(self) -> "span":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.ended = time.time()
        if exc is not None:
            self.error = f"{exc_type.__name__}: {exc}"[:400]
        self._emit()
        return False

    def _emit(self) -> None:
        payload = {
            "name": self.name,
            "trace_id": f"{int(self.started * 1e6):016x}",
            "span_id": f"{int((self.started % 1) * 1e9):016x}",
            "start_time_unix_nano": int(self.started * 1e9),
            "end_time_unix_nano": int((self.ended or time.time()) * 1e9),
            "duration_ms": round(((self.ended or time.time()) - self.started) * 1000, 2),
            "attributes": self.attributes,
            "status": {"code": "ERROR" if self.error else "OK", "message": self.error},
            "resource": {"service.name": "agentdesk", "service.version": _version()},
        }
        with _lock:
            _spans.append(payload)
            if len(_spans) > MAX_SPANS:
                del _spans[: len(_spans) - MAX_SPANS]
        self._persist(payload)

    def _persist(self, payload: dict) -> None:
        if os.environ.get("AGENTDESK_TELEMETRY_FILE", "1") != "1":
            return
        try:
            path = _data_dir() / "telemetry.jsonl"
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except Exception:
            pass


def _version() -> str:
    try:
        from .config import load_settings

        return str(load_settings().get("version") or "0.7.0")
    except Exception:
        return "0.7.0"


def recent_spans(limit: int = 100) -> list[dict]:
    with _lock:
        return _spans[-limit:][::-1]


def _bounds(name: str) -> list[float]:
    if name not in _histogram_bounds:
        _histogram_bounds[name] = [5.0, 50.0, 250.0, 1000.0, 5000.0]
    return _histogram_bounds[name]


def prometheus_metrics() -> str:
    """Render the collected metrics in Prometheus text exposition format."""
    lines: list[str] = []
    with _lock:
        counters = dict(_counters)
        histograms = {k: list(v) for k, v in _histograms.items()}

    grouped: dict[str, list[tuple[tuple[str, str], ...], float]] = {}
    for (name, labels), value in counters.items():
        grouped.setdefault(name, []).append((labels, value))
    for name, rows in sorted(grouped.items()):
        lines.append(f"# HELP {name} AgentDesk counter {name}")
        lines.append(f"# TYPE {name} counter")
        for labels, value in sorted(rows):
            lines.append(f"{name}{_labels(labels)} {value:g}")

    grouped_h: dict[str, list[tuple[tuple[str, str], ...], list[float]]] = {}
    for (name, labels), values in histograms.items():
        grouped_h.setdefault(name, []).append((labels, values))
    for name, rows in sorted(grouped_h.items()):
        bounds = _bounds(name)
        lines.append(f"# HELP {name} AgentDesk histogram {name}")
        lines.append(f"# TYPE {name} histogram")
        for labels, values in sorted(rows, key=lambda row: row[0]):
            cumulative = 0
            for bound in bounds:
                cumulative = sum(1 for v in values if v <= bound)
                lines.append(f"{name}_bucket{_labels(labels, le=str(bound))} {cumulative}")
            lines.append(f"{name}_bucket{_labels(labels, le='+Inf')} {len(values)}")
            lines.append(f"{name}_sum{_labels(labels)} {sum(values):g}")
            lines.append(f"{name}_count{_labels(labels)} {len(values)}")
    return "\n".join(lines) + "\n"


def _labels(labels: tuple[tuple[str, str], ...], **extra: Any) -> str:
    items = list(labels) + [(str(k), str(v)) for k, v in extra.items()]
    if not items:
        return ""
    body = ",".join(f'{k}="{str(v).replace(chr(92), chr(92) * 2).replace(chr(34), chr(92) + chr(34))}"' for k, v in items)
    return "{" + body + "}"


def reset() -> None:
    """Clear all telemetry (used by tests and the UI 'clear' action)."""
    with _lock:
        _counters.clear()
        _histograms.clear()
        _spans.clear()
