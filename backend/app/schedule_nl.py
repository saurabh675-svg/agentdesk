"""Natural-language schedule parsing — ported from Hermas (MIT).

Parses “every weekday at 8:30”, “daily 09:00”, “every 15m”, “in 2h” into a
schedule dict. AgentDesk stores interval_minutes in SQLite, so callers map
``daily`` → 1440, ``weekday``/``weekly`` → 1440 with ``next_run`` computed
from the clock fields, and ``once`` → a single fire time.
"""

from __future__ import annotations

import datetime as dt
import re

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def parse_schedule(text: str) -> dict | None:
    """Best-effort NL → schedule spec. Returns None if nothing recognizable."""
    t = (text or "").lower().strip()
    m = re.search(r"in (\d+)\s*(s|sec|secs|second|seconds|m|min|mins|minute|minutes|h|hr|hrs|hour|hours)\b", t)
    if m:
        n, unit = int(m.group(1)), m.group(2)[0]
        secs = n * 3600 if unit == "h" else (n * 60 if unit == "m" else n)
        if secs >= 5:
            return {"kind": "once", "at": (dt.datetime.now() + dt.timedelta(seconds=secs)).isoformat(timespec="seconds")}
    m = re.search(r"every\s+(\d+)\s*(s|sec|secs|second|seconds|m|min|mins|minute|minutes|h|hr|hrs|hour|hours)\b", t)
    if m:
        n, unit = int(m.group(1)), m.group(2)[0]
        secs = n * 3600 if unit == "h" else (n * 60 if unit == "m" else n)
        if secs >= 10:
            return {"kind": "interval", "seconds": secs}
    m = re.search(
        r"(?:every day|daily|every weekday|weekdays|every\s+(" + "|".join(WEEKDAYS) + r"s?))"
        r"(?:\s+(?:at\s+|@\s*)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?)?",
        t,
    )
    if m:
        day = m.group(1)
        hour = int(m.group(2) or 8)
        minute = int(m.group(3) or 0)
        ap = m.group(4)
        if ap == "pm" and hour < 12:
            hour += 12
        if ap == "am" and hour == 12:
            hour = 0
        if "weekday" in t:
            return {"kind": "weekday", "hour": hour, "minute": minute}
        if day:
            day = day.rstrip("s")
            if day in WEEKDAYS:
                return {"kind": "weekly", "weekday": WEEKDAYS.index(day), "hour": hour, "minute": minute}
        return {"kind": "daily", "hour": hour, "minute": minute}
    return None


def compute_next(spec: dict, now: dt.datetime | None = None) -> str | None:
    """Next fire ISO time for a parsed spec (Hermas `_compute_next`)."""
    now = now or dt.datetime.now()
    k = spec.get("kind")
    if k == "interval":
        return (now + dt.timedelta(seconds=int(spec["seconds"]))).isoformat(timespec="seconds")
    if k == "once":
        return spec.get("at")
    if k == "daily":
        n = now.replace(hour=int(spec["hour"]), minute=int(spec["minute"]), second=0, microsecond=0)
        if n <= now:
            n += dt.timedelta(days=1)
        return n.isoformat(timespec="seconds")
    if k == "weekday":
        n = now.replace(hour=int(spec["hour"]), minute=int(spec["minute"]), second=0, microsecond=0)
        while n <= now or n.weekday() >= 5:
            n += dt.timedelta(days=1)
        return n.isoformat(timespec="seconds")
    if k == "weekly":
        n = now.replace(hour=int(spec["hour"]), minute=int(spec["minute"]), second=0, microsecond=0)
        while n <= now or n.weekday() != int(spec["weekday"]):
            n += dt.timedelta(days=1)
        return n.isoformat(timespec="seconds")
    return None


def to_interval_minutes(spec: dict) -> int:
    """Map a spec to AgentDesk's ``interval_minutes`` (SQLite schema)."""
    kind = spec.get("kind")
    if kind == "interval":
        return max(5, min(14400, int(spec["seconds"]) // 60 or 5))
    if kind in ("daily", "weekday", "weekly"):
        return 1440
    return 5
