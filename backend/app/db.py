import json
import sqlite3
import time

from .config import DB_PATH, PROJECTS_DIR

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL DEFAULT 'New chat',
    workspace TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    meta TEXT,
    created_at REAL NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, id);
CREATE TABLE IF NOT EXISTS transcript_archive (
    session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    compacted_at REAL NOT NULL,
    snapshot TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    root TEXT,
    user_id TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    UNIQUE(name, root)
);
CREATE TABLE IF NOT EXISTS memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER,
    scope TEXT DEFAULT 'project',
    key TEXT NOT NULL,
    value TEXT NOT NULL DEFAULT '',
    score REAL DEFAULT 1.0,
    created_at REAL NOT NULL,
    UNIQUE(project_id, scope, key)
);
CREATE TABLE IF NOT EXISTS approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER,
    tool TEXT NOT NULL,
    action TEXT NOT NULL,
    level TEXT NOT NULL DEFAULT 'caution',
    approved INTEGER NOT NULL DEFAULT 0,
    auto INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL
);


CREATE TABLE IF NOT EXISTS automations (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    prompt TEXT NOT NULL,
    interval_minutes INTEGER NOT NULL DEFAULT 15,
    workspace TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    last_run_at REAL,
    next_run REAL,
    last_status TEXT,
    last_summary TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_automations_next_run ON automations(next_run, status);
CREATE INDEX IF NOT EXISTS idx_automations_status ON automations(status);

CREATE TABLE IF NOT EXISTS automation_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    automation_id TEXT NOT NULL,
    status TEXT NOT NULL,
    summary TEXT,
    seconds REAL,
    started_at REAL NOT NULL,
    finished_at REAL,
    run_key TEXT NOT NULL UNIQUE,
    FOREIGN KEY (automation_id) REFERENCES automations(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_automation_runs_automation ON automation_runs(automation_id, started_at);
CREATE INDEX IF NOT EXISTS idx_automation_runs_run_key ON automation_runs(run_key);

CREATE INDEX IF NOT EXISTS idx_approvals_created ON approvals(created_at DESC);
"""


def get_conn() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    return con


def init_db() -> None:
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    con = get_conn()
    con.executescript(SCHEMA)
    con.commit()
    con.close()


def _row_to_session(row: sqlite3.Row) -> dict:
    return dict(row)


def create_session(title: str = "New chat", workspace: str | None = None) -> dict:
    now = time.time()
    con = get_conn()
    cur = con.execute(
        "INSERT INTO sessions (title, workspace, created_at, updated_at) VALUES (?, ?, ?, ?)",
        (title, workspace, now, now),
    )
    con.commit()
    row = con.execute("SELECT * FROM sessions WHERE id = ?", (cur.lastrowid,)).fetchone()
    con.close()
    return _row_to_session(row)


def list_sessions() -> list[dict]:
    con = get_conn()
    rows = con.execute("SELECT * FROM sessions ORDER BY updated_at DESC").fetchall()
    con.close()
    return [_row_to_session(r) for r in rows]


def get_session(session_id: int) -> dict | None:
    con = get_conn()
    row = con.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    con.close()
    return _row_to_session(row) if row else None


def update_session(session_id: int, **fields) -> dict | None:
    allowed = {"title", "workspace"}
    fields = {k: v for k, v in fields.items() if k in allowed}
    if not fields:
        return get_session(session_id)
    fields["updated_at"] = time.time()
    sets = ", ".join(f"{k} = ?" for k in fields)
    con = get_conn()
    con.execute(f"UPDATE sessions SET {sets} WHERE id = ?", (*fields.values(), session_id))
    con.commit()
    row = con.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    con.close()
    return _row_to_session(row) if row else None


def delete_session(session_id: int) -> None:
    con = get_conn()
    con.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
    con.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    con.commit()
    con.close()


def touch_session(session_id: int) -> None:
    con = get_conn()
    con.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (time.time(), session_id))
    con.commit()
    con.close()


def compact_session(session_id: int, summary: str) -> dict:
    """Replace all messages in a session with a single compacted summary message.

    Returns a synthetic message dict representing the compact entry.
    """
    now = time.time()
    con = get_conn()
    con.execute("BEGIN IMMEDIATE")
    snapshot = [dict(row) for row in con.execute("SELECT * FROM messages WHERE session_id = ? ORDER BY id", (session_id,))]
    con.execute("INSERT INTO transcript_archive VALUES (?, ?, ?)", (session_id, now, json.dumps(snapshot)))
    con.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
    cur = con.execute(
        "INSERT INTO messages (session_id, role, content, meta, created_at) VALUES (?, ?, ?, ?, ?)",
        (session_id, "assistant", summary, json.dumps({"compact": True}), now),
    )
    con.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (now, session_id))
    con.commit()
    row = con.execute("SELECT * FROM messages WHERE id = ?", (cur.lastrowid,)).fetchone()
    con.close()
    data = dict(row)
    data["meta"] = json.loads(data["meta"]) if data.get("meta") else None
    return data


def list_transcript_archives(session_id: int) -> list[dict]:
    con = get_conn()
    try:
        rows = con.execute("SELECT compacted_at, snapshot FROM transcript_archive WHERE session_id = ? ORDER BY compacted_at", (session_id,)).fetchall()
        return [{"compacted_at": row["compacted_at"], "messages": json.loads(row["snapshot"])} for row in rows]
    finally:
        con.close()


def add_message(session_id: int, role: str, content: str, meta: dict | None = None) -> dict:
    now = time.time()
    con = get_conn()
    cur = con.execute(
        "INSERT INTO messages (session_id, role, content, meta, created_at) VALUES (?, ?, ?, ?, ?)",
        (session_id, role, content, json.dumps(meta) if meta else None, now),
    )
    con.commit()
    row = con.execute("SELECT * FROM messages WHERE id = ?", (cur.lastrowid,)).fetchone()
    con.close()
    data = dict(row)
    data["meta"] = json.loads(data["meta"]) if data.get("meta") else None
    return data


def list_messages(session_id: int) -> list[dict]:
    con = get_conn()
    rows = con.execute(
        "SELECT * FROM messages WHERE session_id = ? ORDER BY id ASC", (session_id,)
    ).fetchall()
    con.close()
    out = []
    for row in rows:
        data = dict(row)
        data["meta"] = json.loads(data["meta"]) if data.get("meta") else None
        out.append(data)
    return out


def rewind_session(session_id: int, message_id: int) -> int:
    con = get_conn()
    cur = con.execute(
        "DELETE FROM messages WHERE session_id = ? AND id > ?", (session_id, message_id)
    )
    deleted = cur.rowcount
    con.commit()
    con.close()
    return deleted


def create_project(name: str, root: str | None = None, user_id: str | None = None) -> dict:
    now = time.time()
    con = get_conn()
    cur = con.execute(
        "INSERT OR IGNORE INTO projects (name, root, user_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (name, root, user_id, now, now),
    )
    row = con.execute("SELECT * FROM projects WHERE id = ?", (cur.lastrowid,)).fetchone()
    if row is None:
        row = con.execute("SELECT * FROM projects WHERE name = ? LIMIT 1", (name,)).fetchone()
    con.commit()
    con.close()
    return _row_to_session(row) if row else {"id": None, "name": name, "root": root, "user_id": user_id, "created_at": now, "updated_at": now}


def list_projects() -> list[dict]:
    con = get_conn()
    rows = con.execute("SELECT * FROM projects ORDER BY updated_at DESC").fetchall()
    con.close()
    return [_row_to_session(r) for r in rows]


def get_project_by_name(name: str) -> dict | None:
    con = get_conn()
    row = con.execute("SELECT * FROM projects WHERE name = ? LIMIT 1", (name,)).fetchone()
    con.close()
    return _row_to_session(row) if row else None


def save_memory(key: str, value: str, project_id: int | None = None, scope: str = "project") -> dict:
    now = time.time()
    con = get_conn()
    if project_id is not None:
        con.execute(
            "UPDATE memory SET value = ?, score = min(score + 0.5, 10.0), created_at = ? WHERE project_id = ? AND scope = ? AND key = ?",
            (value, now, project_id, scope, key),
        )
        if con.execute("SELECT changes()").fetchone()[0] == 0:
            con.execute(
                "INSERT INTO memory (project_id, scope, key, value, score, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (project_id, scope, key, value, 1.0, now),
            )
    else:
        con.execute(
            "INSERT INTO memory (project_id, scope, key, value, score, created_at) VALUES (NULL, ?, ?, ?, ?, ?)",
            (scope, key, value, 1.0, now),
        )
    con.commit()
    con.close()
    con = get_conn()
    row = con.execute("SELECT * FROM memory WHERE key = ? ORDER BY created_at DESC LIMIT 1", (key,)).fetchone()
    con.close()
    return _row_to_session(row) if row else {"key": key, "value": value, "project_id": project_id, "scope": scope, "created_at": now}


def get_memory(key: str, project_id: int | None = None) -> str | None:
    con = get_conn()
    row = con.execute(
        "SELECT value FROM memory WHERE key = ? AND (project_id = ? OR project_id IS NULL) ORDER BY score DESC LIMIT 1",
        (key, project_id),
    ).fetchone()
    con.close()
    return row["value"] if row else None


def list_memories(project_id: int | None = None, scope: str = "project", limit: int = 50) -> list[dict]:
    sql = "SELECT * FROM memory"
    params = []
    if project_id is not None:
        sql += " WHERE project_id = ?"
        params.append(project_id)
    if scope:
        sql += " WHERE scope = ?" if project_id is None else " AND scope = ?"
        params.append(scope)
    sql += " ORDER BY score DESC, created_at DESC LIMIT ?"
    params.append(limit)
    con = get_conn()
    rows = con.execute(sql, params).fetchall()
    con.close()
    return [dict(r) for r in rows]

def log_approval(session_id, tool, action, level="caution", approved=False, auto=False):
    con = get_conn()
    cur = con.execute(
        "INSERT INTO approvals (session_id, tool, action, level, approved, auto, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (session_id, tool, action[:2000], level, 1 if approved else 0, 1 if auto else 0, time.time()),
    )
    con.commit()
    row = con.execute("SELECT * FROM approvals WHERE id = ?", (cur.lastrowid,)).fetchone()
    con.close()
    return dict(row) if row else None


def list_approvals(limit=100, session_id=None):
    con = get_conn()
    if session_id:
        rows = con.execute(
            "SELECT * FROM approvals WHERE session_id = ? ORDER BY created_at DESC LIMIT ?",
            (session_id, int(limit)),
        ).fetchall()
    else:
        rows = con.execute(
            "SELECT * FROM approvals ORDER BY created_at DESC LIMIT ?", (int(limit),)
        ).fetchall()
    con.close()
    return [dict(r) for r in rows]
