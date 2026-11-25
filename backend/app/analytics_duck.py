"""DuckDB analytics over earnings/usage — 0.6.

DuckDB crunches Parquet/CSV with SQL and is ~10× faster than Python loops
for the dashboards. Optional dependency: when ``duckdb`` is missing we fall
back to the SQLite aggregates in ``earnings.py`` (same shape, slower).
"""

from __future__ import annotations

from pathlib import Path


def _duckdb():
    try:
        import duckdb  # type: ignore
        return duckdb
    except Exception:
        return None


def earnings_summary(earnings_file: Path | None = None) -> dict:
    """Daily earnings aggregated with DuckDB when available, SQLite else."""
    from . import earnings
    # Fast path: use the existing SQLite aggregates (always correct).
    base = earnings.summary() if hasattr(earnings, "summary") else {"total_missions": 0}
    duck = _duckdb()
    if duck is None:
        return {**base, "engine": "sqlite-fallback"}
    try:
        import sqlite3
        from .config import DATA_DIR
        db_path = DATA_DIR / "earnings.sqlite"
        if db_path.exists():
            con = duck.connect()
            rows = con.execute(
                f"SELECT date(created_at) AS day, COUNT(*) AS n, COALESCE(SUM(amount),0) AS earned "
                f"FROM read_sqlite('{db_path.as_posix()}') GROUP BY 1 ORDER BY 1 LIMIT 90"
            ).fetchall()
            con.close()
            return {**base, "engine": "duckdb", "daily": [{"day": str(r[0]), "n": int(r[1]), "earned": float(r[2] or 0)} for r in rows]}
    except Exception:
        pass
    return {**base, "engine": "duckdb-available-sqlite-fallback"}
