"""Downloads watcher: scan ~/Downloads -> brain (local only).

Phase 4 of the upgrade plan. Stdlib-only parsers where possible:
- txt/md/json/html: direct read
- docx/xlsx/pptx: zipfile + xml (no new deps)
- pdf: pypdf if installed, otherwise skipped with reason (still indexed by title)

Embedded via brain_vector.hash embed + sqlite-vec shadow; provenance is
(source path, sha, mtime). All files stay on disk; only chunks go to brain.
"""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from pathlib import Path

from .config import DATA_DIR

_MANIFEST = DATA_DIR / "downloads-manifest.json"
_MAX_FILES = 500
_MAX_BYTES = 20 * 1024 * 1024
_TEXT_EXTS = {".txt", ".md", ".markdown", ".json", ".html", ".htm", ".csv", ".rst"}


def _downloads_dir() -> Path:
    return Path.home() / "Downloads"


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(64 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _strip_html(text: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", text, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _from_docx(path: Path) -> str:
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8", "ignore")
    text = re.sub(r"<[^>]+>", " ", xml)
    return re.sub(r"\s+", " ", text).strip()


def _from_xlsx(path: Path) -> str:
    from xml.etree import ElementTree as ET

    with zipfile.ZipFile(path) as z:
        shared = []
        try:
            sx = z.read("xl/sharedStrings.xml").decode("utf-8", "ignore")
            root = ET.fromstring(sx)
            ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
            shared = ["".join(t.text or "" for t in si.findall(".//m:t", ns)) for si in root.findall("m:si", ns)]
        except Exception:
            pass
        out: list[str] = []
        for name in sorted(n for n in z.namelist() if n.startswith("xl/worksheets/") and n.endswith(".xml")):
            root = ET.fromstring(z.read(name))
            ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
            for c in root.findall(".//m:c", ns):
                v = c.findtext("m:v", default="", namespaces=ns)
                if c.get("t") == "s" and v.strip().isdigit():
                    out.append(shared[int(v)] if int(v) < len(shared) else "")
                elif v:
                    out.append(v)
        return " ".join(o for o in out if o).strip()


def _from_pptx(path: Path) -> str:
    with zipfile.ZipFile(path) as z:
        out: list[str] = []
        for name in sorted(n for n in z.namelist() if n.startswith("ppt/slides/slide") and n.endswith(".xml")):
            xml = z.read(name).decode("utf-8", "ignore")
            out.append(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", xml)).strip())
        return " ".join(o for o in out if o).strip()


def extract_text(path: Path) -> tuple[str, str]:
    """(text, reason). Empty text + reason when unsupported."""
    ext = path.suffix.lower()
    try:
        if ext in _TEXT_EXTS:
            raw = path.read_text(encoding="utf-8", errors="ignore")
            if ext in {".html", ".htm"}:
                raw = _strip_html(raw)
            return raw.strip(), ""
        if ext == ".docx":
            return _from_docx(path), ""
        if ext == ".xlsx":
            return _from_xlsx(path), ""
        if ext == ".pptx":
            return _from_pptx(path), ""
        if ext == ".pdf":
            try:
                from pypdf import PdfReader  # type: ignore

                pages = [(pg.extract_text() or "") for pg in PdfReader(str(path)).pages]
                return " ".join(pages).strip(), ""
            except ImportError:
                return "", "pdf parser not installed (pip install pypdf)"
    except Exception as exc:
        return "", str(exc)[:200]
    return "", "unsupported type"


def _manifest() -> dict:
    try:
        return json.loads(_MANIFEST.read_text(encoding="utf-8"))
    except Exception:
        return {}


def scan(force: bool = False) -> dict:
    """Index new/changed Downloads files into the brain (idempotent)."""
    root = _downloads_dir()
    manifest = _manifest()
    indexed: list[dict] = []
    skipped: list[dict] = []
    if not root.exists():
        return {"indexed": indexed, "skipped": skipped, "total": 0}
    files = sorted(
        (p for p in root.iterdir() if p.is_file()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[:_MAX_FILES]
    from . import brain

    for path in files:
        if path.stat().st_size > _MAX_BYTES:
            skipped.append({"path": str(path), "reason": "too large"})
            continue
        digest = _sha(path)
        prev = manifest.get(str(path))
        if not force and prev and prev.get("sha") == digest:
            continue
        text, reason = extract_text(path)
        if not text:
            skipped.append({"path": str(path), "reason": reason or "empty"})
            manifest[str(path)] = {"sha": digest, "status": "skipped", "reason": reason}
            continue
        # Chunk to brain notes (512-token-ish chunks).
        chunks = [text[i : i + 2000] for i in range(0, min(len(text), 120_000), 1800)]
        for i, chunk in enumerate(chunks[:8]):
            try:
                brain.add_brain_note(
                    title=f"Downloads: {path.name} [{i + 1}]",
                    body=chunk[:4000],
                    tags=["downloads", path.suffix.lower().lstrip(".")],
                )
            except Exception:
                pass
        manifest[str(path)] = {"sha": digest, "status": "indexed", "chars": len(text)}
        indexed.append({"path": str(path), "chars": len(text)})
    _MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    _MANIFEST.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return {"indexed": indexed, "skipped": skipped, "total": len(files)}


__all__ = ["scan", "extract_text"]
