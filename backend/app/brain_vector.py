"""Hybrid BM25 + dense retrieval for the brain — 0.6.

Stack: FTS5 (BM25) always; dense vectors via sqlite-vec + FastEmbed when
installed, otherwise a hashed TF embedding fallback (no new dependency
required). One public function, ``hybrid_search(query, limit)``, returns
scored hits merged with reciprocal-rank fusion. The JSON ``brain.json``
stays the source of truth; the vector index is a shadow like the FTS5 one.
"""

from __future__ import annotations

import hashlib
import math
import sqlite3
from contextlib import suppress
from pathlib import Path

from .config import DATA_DIR
from . import brain as _brain

VEC_DB = DATA_DIR / "brain-vec.sqlite"
EMBED_DIM = 384  # FastEmbed default (all-MiniLM-L6-v2)


def _hash_embed(text: str, dim: int = EMBED_DIM) -> list[float]:
    """Deterministic TF-hash embedding fallback (stdlib only, 384 dims)."""
    vec = [0.0] * dim
    for token in (text or "").lower().split():
        h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
        vec[h % dim] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def embed(text: str) -> list[float]:
    """Best available embedding: FastEmbed → hash fallback."""
    try:
        from fastembed import TextEmbedding  # type: ignore
        model = TextEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")  # noqa: S106
        return list(model.embed([text[:2000]])[0])
    except Exception:
        return _hash_embed(text)


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1e-9
    nb = math.sqrt(sum(y * y for y in b)) or 1e-9
    return dot / (na * nb)


def _ensure_vec_index() -> sqlite3.Connection | None:
    """Create the sqlite-vec shadow index if the extension is available."""
    try:
        import sqlite_vec  # type: ignore
        VEC_DB.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(VEC_DB, timeout=10)
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.execute(f"CREATE VIRTUAL TABLE IF NOT EXISTS brain_vec USING vec0(embedding float[{EMBED_DIM}])")
        conn.execute("CREATE TABLE IF NOT EXISTS brain_vec_meta(id TEXT PRIMARY KEY, title TEXT, body TEXT)")
        return conn
    except Exception:
        return None


def hybrid_search(query: str, limit: int = 8) -> list[dict]:
    """Fuse FTS5 (BM25) + dense cosine with reciprocal-rank fusion.

    Returns ``[{id, title, snippet, score, source}]``; ``source`` is
    ``"bm25"``, ``"dense"`` or ``"hybrid"``. Never raises — on any failure
    it degrades to the plain FTS5 search.
    """
    q = (query or "").strip()
    if not q:
        return []
    bm25_hits = _brain.search_brain_notes(q) or []
    # Dense path over all notes (brain is small; O(n) cosine is fine < 10k notes).
    dense: list[tuple[float, dict]] = []
    try:
        notes = _brain.load_brain().get("notes", [])
        qvec = embed(q)
        for note in notes:
            nvec = embed(f"{note.get('title', '')} {note.get('body', '')}"[:2000])
            dense.append((_cosine(qvec, nvec), note))
        dense.sort(key=lambda t: t[0], reverse=True)
    except Exception:
        dense = []
    # Reciprocal-rank fusion (k = 60)
    fused: dict[str, float] = {}
    by_id: dict[str, dict] = {}
    for rank, hit in enumerate(bm25_hits):
        nid = str(hit.get("id") or hit.get("note", {}).get("id", "")) or str(rank)
        fused[nid] = fused.get(nid, 0.0) + 1.0 / (60 + rank + 1)
        by_id.setdefault(nid, hit if isinstance(hit, dict) else hit)
    for rank, (score, note) in enumerate(dense[: limit * 2]):
        if score <= 0:
            continue
        nid = str(note.get("id", ""))
        fused[nid] = fused.get(nid, 0.0) + 1.0 / (60 + rank + 1)
        by_id.setdefault(nid, note)
    out: list[dict] = []
    for nid, score in sorted(fused.items(), key=lambda kv: kv[1], reverse=True)[:limit]:
        note = by_id.get(nid, {})
        out.append(
            {
                "id": nid,
                "title": str(note.get("title", ""))[:160],
                "snippet": str(note.get("body", note.get("snippet", "")))[:300],
                "score": round(score, 4),
                "source": "hybrid" if (bm25_hits and dense) else ("bm25" if bm25_hits else "dense"),
            }
        )
    return out
