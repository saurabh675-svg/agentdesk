"""Nous Hermes-style self-learning and reflection engine.

1. Trajectory Distillation: Analyzes successful multi-step tool executions and compiles
   them into reusable SKILL.md procedures.
2. Episodic Reflection: Records error-and-recovery patterns to avoid repeating mistakes.
3. Progressive Retrieval: Returns relevant learned lessons for prompt injection.
"""

from __future__ import annotations

import json
import re
import sqlite3
import time
from pathlib import Path
from typing import Any

from .config import DATA_DIR
from .skills import save_skill, slugify

LEARNING_DB = DATA_DIR / "memory.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS reflections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    goal TEXT NOT NULL,
    error_pattern TEXT NOT NULL,
    resolution TEXT NOT NULL,
    tags TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reflections_goal ON reflections(goal);
"""


def _conn() -> sqlite3.Connection:
    LEARNING_DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(LEARNING_DB, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    return con


def init_db() -> None:
    con = _conn()
    con.executescript(SCHEMA)
    con.commit()
    con.close()


def record_reflection(goal: str, error_pattern: str, resolution: str, tags: list[str] | None = None) -> None:
    """Store an episodic lesson when an error is resolved so future runs avoid it."""
    init_db()
    con = _conn()
    now = time.time()
    tag_str = ",".join(tags or [])
    con.execute(
        "INSERT INTO reflections (goal, error_pattern, resolution, tags, created_at) VALUES (?, ?, ?, ?, ?)",
        (goal[:500], error_pattern[:1000], resolution[:1500], tag_str[:200], now),
    )
    con.commit()
    con.close()


import math
from collections import Counter


def _vectorize_text(text: str) -> dict[str, float]:
    """Generate a lightweight character 3-gram + word token TF vector for semantic comparison."""
    clean = re.sub(r"[^\w\s]", " ", text.lower())
    words = [w for w in clean.split() if len(w) > 2]
    # Word unigrams
    counts = Counter(words)
    # Character trigrams for morphological and typo tolerance
    for w in words:
        if len(w) >= 3:
            for i in range(len(w) - 2):
                counts[w[i : i + 3]] += 0.5
    # Normalize length
    norm = math.sqrt(sum(v * v for v in counts.values())) or 1.0
    return {k: v / norm for k, v in counts.items()}


def _cosine_similarity(vec_a: dict[str, float], vec_b: dict[str, float]) -> float:
    """Calculate cosine similarity between two normalized sparse vectors."""
    if not vec_a or not vec_b:
        return 0.0
    # Iterate over smaller vector
    small, large = (vec_a, vec_b) if len(vec_a) < len(vec_b) else (vec_b, vec_a)
    return sum(val * large.get(key, 0.0) for key, val in small.items())


def relevant_reflections(query: str, limit: int = 3) -> list[dict[str, Any]]:
    """Retrieve top learned lessons using dual hybrid semantic vector + keyword scoring."""
    init_db()
    con = _conn()
    now = time.time()
    # Fetch recent reflections for hybrid ranking (up to 100 candidate reflections)
    rows = con.execute("SELECT * FROM reflections ORDER BY id DESC LIMIT 100").fetchall()
    con.close()
    if not rows:
        return []

    query_vec = _vectorize_text(query)
    query_words = set(re.findall(r"\b[a-zA-Z]{3,}\b", query.lower()))

    scored: list[tuple[float, dict[str, Any]]] = []
    for r in rows:
        item = dict(r)
        # Composite text of the reflection
        composite = f"{item.get('goal', '')} {item.get('error_pattern', '')} {item.get('resolution', '')} {item.get('tags', '')}"
        target_vec = _vectorize_text(composite)
        vec_sim = _cosine_similarity(query_vec, target_vec)

        # Exact keyword overlap
        target_words = set(re.findall(r"\b[a-zA-Z]{3,}\b", composite.lower()))
        kw_sim = (len(query_words & target_words) / (len(query_words) or 1)) if query_words else 0.0

        # Recency boost (halves every 7 days)
        age_days = (now - item.get("created_at", now)) / 86400.0
        recency = math.exp(-0.1 * min(age_days, 30))

        # Hybrid score
        score = (0.60 * vec_sim) + (0.25 * min(kw_sim, 1.0)) + (0.15 * recency)
        item["similarity_score"] = round(score, 3)
        scored.append((score, item))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored[:limit]]


def distill_skill_from_trajectory(goal: str, steps: list[dict[str, Any]], summary: str = "") -> dict[str, Any] | None:
    """Analyze a multi-step execution trajectory and synthesize a new persistent skill."""
    if len(steps) < 2:
        return None  # Only compile non-trivial workflows

    slug = slugify(goal[:40])
    description = f"Autonomous workflow for: {goal[:100]}"
    
    # Format steps into reproducible markdown instructions
    step_lines = []
    for idx, s in enumerate(steps, 1):
        tool = s.get("tool", "action")
        args_str = json.dumps(s.get("args", {}))[:120]
        step_lines.append(f"{idx}. Call `{tool}` with `{args_str}`")

    body = f"""# {goal.title()}

## When to use
Use this skill when asked to perform: {goal}.

## Verified Step-by-Step Execution
{chr(10).join(step_lines)}

## Key Takeaways
{summary or 'Execution completed and verified successfully.'}
"""

    saved = save_skill(slug, description, body, source="self_learned")
    return saved
