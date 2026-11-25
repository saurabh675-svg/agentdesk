"""Working-memory SQLite with FTS5 — persistent cross-session facts, procedural memory."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from .config import DATA_DIR

MEMORY_DB = DATA_DIR / "agent_memory.db"


def _init() -> None:
    MEMORY_DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(MEMORY_DB, timeout=30)
    con.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(id, kind, content, created_at, tokenize='porter')"
    )
    con.execute(
        "CREATE TABLE IF NOT EXISTS memory_meta (id TEXT PRIMARY KEY, kind TEXT, hits INTEGER DEFAULT 0, last_used REAL, created_at REAL NOT NULL)"
    )
    con.commit()
    con.close()


def add_fact(text: str, kind: str = "fact") -> dict:
    _init()
    text = (text or "").strip()
    if not text:
        return {"kind": kind, "text": ""}
    fact_id = int(time.time() * 1000)
    con = sqlite3.connect(MEMORY_DB, timeout=30)
    con.execute(
        "INSERT INTO memory_fts (id, kind, content, created_at) VALUES (?,?,?,?)",
        (fact_id, kind, text[:4000], time.time()),
    )
    con.execute(
        "INSERT INTO memory_meta (id, kind, hits, last_used, created_at) VALUES (?,?,?,?,?)",
        (fact_id, kind, 0, time.time(), time.time()),
    )
    con.commit()
    con.close()
    return {"id": fact_id, "kind": kind, "text": text[:500]}


def search_memory(query: str, kind: str | None = None, limit: int = 10) -> list[dict]:
    _init()
    query = (query or "").strip()
    if not query:
        return []
    con = sqlite3.connect(MEMORY_DB, timeout=30)
    sql = "SELECT id, kind, content, bm25(memory_fts) AS score FROM memory_fts WHERE memory_fts MATCH ?"
    params: list = [query]
    if kind:
        sql += " AND kind = ?"
        params.append(kind)
    sql += " ORDER BY score LIMIT ?"
    params.append(max(1, int(limit)))
    try:
        rows = con.execute(sql, params).fetchall()
    except sqlite3.OperationalError:
        # Fall back to substring search if MATCH syntax fails.
        base = "SELECT id, kind, content FROM memory_fts"
        if kind:
            base += " WHERE kind = ?"
            rows = con.execute(base, (kind,)).fetchall()
        else:
            rows = con.execute(base).fetchall()
        q = query.lower()
        rows = [(r[0], r[1], r[2], 1.0) for r in rows if q in str(r[2]).lower()][:limit]
    for row in rows:
        try:
            con.execute("UPDATE memory_meta SET hits = hits + 1, last_used = ? WHERE id = ?", (time.time(), row[0]))
        except Exception:
            pass
    con.commit()
    con.close()
    return [{"id": r[0], "kind": r[1], "content": str(r[2])[:1500], "score": round(float(r[3]), 4)} for r in rows]


def forget(fact_id: str) -> bool:
    _init()
    con = sqlite3.connect(MEMORY_DB, timeout=30)
    con.execute("DELETE FROM memory_fts WHERE id = ?", (fact_id,))
    con.execute("DELETE FROM memory_meta WHERE id = ?", (fact_id,))
    con.commit()
    changed = con.total_changes > 0
    con.close()
    return changed


def stats() -> dict:
    _init()
    con = sqlite3.connect(MEMORY_DB, timeout=30)
    counts = dict(con.execute("SELECT kind, COUNT(*) FROM memory_fts GROUP BY kind").fetchall())
    total = con.execute("SELECT COUNT(*) FROM memory_fts").fetchone()[0]
    con.close()
    return {"db": str(MEMORY_DB), "total": total, "kinds": counts}