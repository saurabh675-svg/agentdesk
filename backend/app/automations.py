"""Global, persisted automation jobs backed by SQLite.

Jobs repeat the same AgentDesk prompt on a fixed interval, are run through the normal
agent loop, and update their status after every run. The scheduler is owned by the backend
process: jobs still run while their app is running, and they persist so a restart picks up
the next due job.

All state is stored in SQLite (agentdesk.db) with WAL mode. Each run gets a unique run_key
for idempotency, so a crash before/during/after an action can be reconciled without
duplicating external side effects.
"""

import json
import time
import uuid

from . import db
from .config import DATA_DIR

MIN_INTERVAL_MINUTES = 5
MAX_INTERVAL_MINUTES = 14_400
LEGACY_FILE = DATA_DIR / "automations.json"


def migrate_legacy_json() -> None:
    """One-time import of pre-0.3.1 JSON automations into SQLite.

    The JSON file is renamed instead of deleted so a failed migration can be
    inspected or retried; runs are not duplicated thanks to INSERT OR IGNORE.
    """
    if not LEGACY_FILE.exists():
        return
    try:
        payload = json.loads(LEGACY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return
    jobs = payload.get("automations") if isinstance(payload, dict) else None
    if not isinstance(jobs, list):
        return
    con = db.get_conn()
    try:
        for job in jobs:
            if not isinstance(job, dict) or not job.get("id") or not job.get("prompt"):
                continue
            now = time.time()
            con.execute(
                """INSERT OR IGNORE INTO automations
                   (id, name, prompt, interval_minutes, workspace, status,
                    last_run_at, next_run, last_status, last_summary, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(job["id"]),
                    str(job.get("name") or "Automation"),
                    str(job["prompt"]),
                    int(_clamp_interval(job.get("interval_minutes", 15))),
                    job.get("workspace"),
                    str(job.get("status") or "active"),
                    job.get("last_run_at"),
                    float(job.get("next_run") or now),
                    job.get("last_status"),
                    job.get("last_summary"),
                    float(job.get("created_at") or now),
                    float(job.get("updated_at") or now),
                ),
            )
        con.commit()
    finally:
        con.close()
    try:
        LEGACY_FILE.replace(LEGACY_FILE.with_suffix(".json.migrated"))
    except OSError:
        pass


def _clamp_interval(minutes: float) -> float:
    try:
        value = float(minutes or 15)
    except (TypeError, ValueError):
        value = 15.0
    return max(float(MIN_INTERVAL_MINUTES), min(float(MAX_INTERVAL_MINUTES), value))


def list_automations() -> list[dict]:
    now = time.time()
    con = db.get_conn()
    try:
        rows = con.execute(
            "SELECT * FROM automations ORDER BY next_run ASC"
        ).fetchall()
    finally:
        con.close()
    out = []
    for row in rows:
        item = dict(row)
        item.setdefault("status", "active")
        next_run = item.get("next_run")
        item["next_run"] = float(next_run) if next_run else 0.0
        item["overdue"] = item["next_run"] > 0 and item["next_run"] <= now
        out.append(item)
    return out

def get_automation(job_id: str) -> dict | None:
    con = db.get_conn()
    row = con.execute(
        "SELECT * FROM automations WHERE id = ?", (job_id,)
    ).fetchone()
    con.close()
    return dict(row) if row else None


def create_automation(name: str, prompt: str, interval_minutes: float, workspace: str | None = None) -> dict:
    job_id = uuid.uuid4().hex[:12]
    now = time.time()
    interval = int(_clamp_interval(interval_minutes))
    job = {
        "id": job_id,
        "name": (name or "Automation").strip() or "Automation",
        "prompt": prompt.strip(),
        "interval_minutes": interval,
        "workspace": workspace,
        "status": "active",
        "last_run_at": None,
        "next_run": now + interval * 60,
        "created_at": now,
        "updated_at": now,
    }
    con = db.get_conn()
    con.execute(
        """INSERT INTO automations
           (id, name, prompt, interval_minutes, workspace, status,
            last_run_at, next_run, last_status, last_summary, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            job["id"], job["name"], job["prompt"], job["interval_minutes"],
            job["workspace"], job["status"], job["last_run_at"],
            job["next_run"], None, None, job["created_at"], job["updated_at"],
        ),
    )
    con.commit()
    con.close()
    return job


def create_automation_nl(name: str, prompt: str, schedule_text: str, workspace: str | None = None) -> dict:
    """Create an automation from natural language ("every weekday at 8:30", "in 2h")."""
    import datetime as _dt
    from .schedule_nl import compute_next, parse_schedule, to_interval_minutes
    spec = parse_schedule(schedule_text or "")
    if spec is None:
        raise ValueError(f"Could not parse schedule: {schedule_text!r}. Try 'every 30m', 'daily 09:00', 'in 2h'.")
    interval = to_interval_minutes(spec)
    job = create_automation(name, prompt, interval, workspace)
    nxt = compute_next(spec, _dt.datetime.now())
    if nxt:
        import datetime as _dt2
        ts = _dt2.datetime.fromisoformat(nxt).timestamp()
        con = db.get_conn()
        con.execute("UPDATE automations SET next_run = ? WHERE id = ?", (ts, job["id"]))
        con.commit()
        con.close()
        job["next_run"] = ts
    job["schedule_spec"] = spec
    return job


def cancel_automation(job_id: str) -> dict:
    con = db.get_conn()
    row = con.execute(
        "SELECT id FROM automations WHERE id = ?", (job_id,)
    ).fetchone()
    if not row:
        con.close()
        return {"ok": False, "error": "automation not found"}
    con.execute(
        "UPDATE automations SET status = 'cancelled', updated_at = ? WHERE id = ?",
        (time.time(), job_id),
    )
    con.commit()
    con.close()
    return {"ok": True}


def mark_run(job_id: str, result: dict) -> None:
    now = time.time()
    con = db.get_conn()
    row = con.execute(
        "SELECT interval_minutes FROM automations WHERE id = ?", (job_id,)
    ).fetchone()
    if not row:
        con.close()
        return
    interval = int(row["interval_minutes"])
    con.execute(
        """UPDATE automations
           SET last_run_at = ?, next_run = ?, last_status = ?,
               last_summary = ?, updated_at = ?
           WHERE id = ?""",
        (
            now,
            now + interval * 60,
            result.get("status", "completed"),
            (result.get("summary") or "")[:500],
            now,
            job_id,
        ),
    )
    con.commit()
    con.close()


def due_automations(limit: int = 1) -> list[dict]:
    now = time.time()
    con = db.get_conn()
    rows = con.execute(
        """SELECT * FROM automations
           WHERE status = 'active' AND next_run IS NOT NULL AND next_run <= ?
           ORDER BY next_run ASC LIMIT ?""",
        (now, limit),
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def claim_run(job_id: str, run_key: str) -> bool:
    """Atomically claim a run for an automation. Returns True if this process won the claim.

    Prevents duplicate execution when the scheduler fires while a previous run is still
    in progress, or after a restart where the previous run's outcome is uncertain.
    """
    now = time.time()
    con = db.get_conn()
    try:
        con.execute("BEGIN IMMEDIATE")
        existing = con.execute(
            "SELECT id FROM automation_runs WHERE run_key = ?", (run_key,)
        ).fetchone()
        if existing:
            con.rollback()
            con.close()
            return False
        con.execute(
            """INSERT INTO automation_runs
               (automation_id, status, started_at, run_key)
               VALUES (?, 'pending', ?, ?)""",
            (job_id, now, run_key),
        )
        con.commit()
        return True
    except Exception:
        try:
            con.rollback()
        except Exception:
            pass
        con.close()
        return False


def complete_run(run_key: str, status: str, summary: str | None = None, seconds: float | None = None) -> None:
    """Mark a claimed run as finished with its outcome."""
    now = time.time()
    con = db.get_conn()
    con.execute(
        """UPDATE automation_runs
           SET status = ?, summary = ?, seconds = ?, finished_at = ?
           WHERE run_key = ?""",
        (status, summary, seconds, now, run_key),
    )
    con.commit()
    con.close()


def get_run_state(run_key: str) -> dict | None:
    """Return the current state of a run for crash recovery reconciliation."""
    con = db.get_conn()
    row = con.execute(
        "SELECT * FROM automation_runs WHERE run_key = ?", (run_key,)
    ).fetchone()
    con.close()
    return dict(row) if row else None

def seed_scheduled_jobs() -> list[dict]:
    """Idempotently create the built-in scheduled jobs.

    These keep the new subsystems honest without the user having to remember:
    a daily expert briefing, and a periodic self-check of the browser control
    plane, pet expert and MCP skills.
    """
    seeds = [
        {
            "name": "Daily DeskPet briefing",
            "interval_minutes": 1440,
            "prompt": (
                "Write my daily briefing. Use web search for anything that changed in the last "
                "24 hours that touches my projects, check your memory database for notes I left, "
                "and list which MCP skills could help most today. End with three concrete "
                "next actions, each one line long."
            ),
        },
        {
            "name": "AgentDesk self-check",
            "interval_minutes": 360,
            "prompt": (
                "Run a health check of AgentDesk and report only what is broken. Verify: "
                "(1) the browser control plane: GET http://127.0.0.1:8756/api/browser/sdk/info "
                "with the SDK token from the browser-sdk.token file, (2) the Chrome DevTools "
                "endpoint on http://127.0.0.1:9333/json/version, (3) the pet expert: POST "
                "/api/pet/expert with a short question, (4) MCP servers via GET /api/mcp/status. "
                "If everything is healthy reply with a single line: all green."
            ),
        },
    ]
    created: list[dict] = []
    try:
        existing = {str(job.get("name") or "") for job in list_automations()}
    except Exception:
        existing = set()
    for seed in seeds:
        if seed["name"] in existing:
            continue
        try:
            created.append(create_automation(seed["name"], seed["prompt"], seed["interval_minutes"]))
        except Exception:
            continue
    return created
