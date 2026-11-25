"""Import skill packs from folders, zips and the bundled packs.

AgentDesk skills are folders that contain a ``SKILL.md`` file with YAML
frontmatter (``name``, ``description``). That is exactly the layout used by
the OpenHands and deepagents skill packs, so those repositories can be
imported as-is - including straight from a zip file the user already has on
disk, without unpacking it first.

Plain-markdown skills (GenAgent style: a single ``.md`` file with a
``## When to use`` section) are converted into the same layout on import.
"""

from __future__ import annotations

import re
import shutil
import zipfile
from pathlib import Path

from .config import DATA_DIR
from .skills import SKILLS_DIR, parse_skill, slugify, validate_skill

BUNDLED_DIR = Path(__file__).parent / "skills_bundled"
PLAIN_SKILL_FILENAMES = re.compile(r"^[a-z0-9][a-z0-9._-]*\.md$", re.IGNORECASE)
# Documentation files live next to skills but are not skills themselves.
NOT_A_SKILL = {"readme", "changelog", "license", "license_md", "contributing", "security", "code_of_conduct"}
MAX_SCAN_DEPTH = 6


# --------------------------------------------------------------------------- helpers

def _skill_from_markdown(path: Path) -> tuple[str, str, str]:
    """Convert a plain-markdown skill into (name, description, body)."""
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    name = path.stem.replace("_", " ").replace("-", " ").strip()
    description = ""
    match = re.search(r"^#+\s*Skill:\s*(.+)$", text, re.MULTILINE)
    if match:
        name = match.group(1).strip()
    match = re.search(r"^##\s*When to use\s*$(.*?)(?=^##\s|\Z)", text, re.MULTILINE | re.DOTALL)
    if match:
        description = " ".join(match.group(1).split())[:400]
    if not description:
        match = re.search(r"^description:\s*(.+)$", text, re.MULTILINE)
        if match:
            description = match.group(1).strip()[:400]
    if not description:
        first = next((line.strip() for line in text.splitlines()[1:] if line.strip()), "")
        description = first[:400] or f"Imported skill: {name}"
    return name, description, text


def _read_skill_md(path: Path) -> tuple[str, str, str, dict]:
    """Return (name, description, body, meta) for a SKILL.md file."""
    text = path.read_text(encoding="utf-8", errors="replace")
    meta, body = parse_skill(text)
    name = str(meta.get("name") or path.parent.name.replace("_", " ").replace("-", " ").strip())
    description = str(meta.get("description") or "").strip()
    if not description:
        first = body.splitlines()[0] if body else ""
        description = first[:400]
    return name, description, body, meta


def _pack_source_label(root: Path) -> str:
    parts = [p for p in root.parts if p not in ("/", "\\")]
    for marker in (".agents", "skills", "bundled"):
        if marker in parts:
            idx = parts.index(marker)
            if idx > 0:
                return parts[idx - 1]
    return root.name


# --------------------------------------------------------------------------- scanning

def scan_folder(root: Path, pack_label: str | None = None) -> list[dict]:
    """Find importable skills in a folder (recursively, shallow)."""
    root = Path(root)
    if not root.is_dir():
        return []
    label = pack_label or _pack_source_label(root)
    found: list[dict] = []

    for skill_file in sorted(root.rglob("SKILL.md")):
        if len(skill_file.relative_to(root).parts) > MAX_SCAN_DEPTH:
            continue
        try:
            name, description, body, meta = _read_skill_md(skill_file)
        except OSError:
            continue
        found.append(
            {
                "name": name,
                "description": description,
                "slug": slugify(name),
                "kind": "skill-md",
                "source": label,
                "path": str(skill_file),
                "size": len(body),
                "license": str(meta.get("license") or ""),
            }
        )

    if not found:
        for md_file in sorted(root.glob("*.md")):
            if not PLAIN_SKILL_FILENAMES.match(md_file.name):
                continue
            if md_file.stem.lower().replace("-", "_") in NOT_A_SKILL:
                continue
            try:
                name, description, body = _skill_from_markdown(md_file)
            except OSError:
                continue
            found.append(
                {
                    "name": name,
                    "description": description,
                    "slug": slugify(name),
                    "kind": "markdown",
                    "source": label,
                    "path": str(md_file),
                    "size": len(body),
                    "license": "",
                }
            )
    return found


def scan_zip(zip_path: Path) -> list[dict]:
    """Find importable skills inside a zip archive without extracting it."""
    zip_path = Path(zip_path)
    if not zip_path.is_file() or zip_path.suffix.lower() != ".zip":
        return []
    found: list[dict] = []
    label = zip_path.stem
    try:
        with zipfile.ZipFile(zip_path) as archive:
            names = [n for n in archive.namelist() if not n.endswith("/")]
            skill_files = [n for n in names if n.rsplit("/", 1)[-1] == "SKILL.md"]
            if skill_files:
                for name in skill_files:
                    try:
                        text = archive.read(name).decode("utf-8", errors="replace")
                    except KeyError:
                        continue
                    meta, body = parse_skill(text)
                    skill_name = str(meta.get("name") or name.split("/")[-2])
                    description = str(meta.get("description") or "").strip()
                    if not description:
                        description = (body.splitlines() or [""])[0][:400]
                    found.append(
                        {
                            "name": skill_name,
                            "description": description,
                            "slug": slugify(skill_name),
                            "kind": "skill-md",
                            "source": label,
                            "path": f"{zip_path.name}!/{name}",
                            "size": len(body),
                            "license": str(meta.get("license") or ""),
                        }
                    )
            else:
                # Plain markdown skills inside the archive.
                for name in names:
                    candidate = name.rsplit("/", 1)[-1]
                    if not PLAIN_SKILL_FILENAMES.match(candidate):
                        continue
                    if candidate[:-3].lower().replace("-", "_") in NOT_A_SKILL:
                        continue
                    try:
                        text = archive.read(name).decode("utf-8", errors="replace")
                    except KeyError:
                        continue
                    found.append(
                        {
                            "name": candidate[:-3].replace("_", " "),
                            "description": " ".join(text.split())[:400],
                            "slug": slugify(candidate[:-3]),
                            "kind": "markdown",
                            "source": label,
                            "path": f"{zip_path.name}!/{name}",
                            "size": len(text),
                            "license": "",
                        }
                    )
    except (zipfile.BadZipFile, OSError):
        return []
    return found


def scan(path: str | Path) -> list[dict]:
    """Scan a folder or zip archive for skills."""
    target = Path(str(path).strip().strip('"'))
    if target.suffix.lower() == ".zip":
        return scan_zip(target)
    return scan_folder(target)


# --------------------------------------------------------------------------- importing

def _install_skill(slug: str, name: str, description: str, body: str, source: str, extras: dict[str, bytes] | None = None) -> dict:
    errors = validate_skill(name, description, body)
    if errors:
        raise ValueError(f"{name}: " + "; ".join(errors))
    folder = SKILLS_DIR / slug
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True, exist_ok=True)
    front = (
        f"---\nname: {slug}\ndescription: {description.strip()}\n"
        f"source: {source}\n---\n\n{body.strip()}\n"
    )
    (folder / "SKILL.md").write_text(front, encoding="utf-8")
    for extra_name, extra_bytes in (extras or {}).items():
        target = folder / extra_name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(extra_bytes)
    return {"name": name, "slug": slug, "description": description, "source": source}


def import_path(path: str | Path, overwrite: bool = True, limit: int = 60) -> dict:
    """Import every skill found in a folder or zip archive."""
    target = Path(str(path).strip().strip('"'))
    if not target.exists():
        raise ValueError(f"Path not found: {target}")
    if target.suffix.lower() == ".zip":
        return _import_zip(target, overwrite=overwrite, limit=limit)
    return _import_folder(target, overwrite=overwrite, limit=limit)


def _import_folder(root: Path, overwrite: bool, limit: int) -> dict:
    candidates = scan_folder(root)
    imported: list[dict] = []
    skipped: list[dict] = []
    errors: list[str] = []
    for candidate in candidates[:limit]:
        slug = candidate["slug"]
        if (SKILLS_DIR / slug).exists() and not overwrite:
            skipped.append({"name": candidate["name"], "reason": "already installed"})
            continue
        source_file = Path(candidate["path"])
        try:
            name, description, body, _meta = _read_skill_md(source_file)
            extras = {
                str(p.relative_to(source_file.parent)): p.read_bytes()
                for p in source_file.parent.rglob("*")
                if p.is_file() and p.name != "SKILL.md"
            }
            imported.append(_install_skill(slug, name, description, body, candidate["source"], extras))
        except Exception as exc:
            errors.append(f"{candidate['name']}: {exc}")
    return {
        "imported": imported,
        "skipped": skipped,
        "errors": errors,
        "found": len(candidates),
    }


def _import_zip(zip_path: Path, overwrite: bool, limit: int) -> dict:
    imported: list[dict] = []
    skipped: list[dict] = []
    errors: list[str] = []
    label = zip_path.stem
    with zipfile.ZipFile(zip_path) as archive:
        names = [n for n in archive.namelist() if not n.endswith("/")]
        skill_files = [n for n in names if n.rsplit("/", 1)[-1] == "SKILL.md"]
        if skill_files:
            for entry in skill_files[:limit]:
                try:
                    text = archive.read(entry).decode("utf-8", errors="replace")
                except KeyError:
                    continue
                meta, body = parse_skill(text)
                name = str(meta.get("name") or entry.split("/")[-2])
                description = str(meta.get("description") or "").strip()
                if not description:
                    description = (body.splitlines() or [""])[0][:400]
                slug = slugify(name)
                if (SKILLS_DIR / slug).exists() and not overwrite:
                    skipped.append({"name": name, "reason": "already installed"})
                    continue
                # keep sibling reference files (e.g. references/guide.md)
                base = entry.rsplit("/", 1)[0]
                extras: dict[str, bytes] = {}
                for other in names:
                    if other.startswith(base + "/") and other != entry:
                        extras[other[len(base) + 1 :]] = archive.read(other)
                try:
                    imported.append(_install_skill(slug, name, description, body, label, extras))
                except Exception as exc:
                    errors.append(f"{name}: {exc}")
        else:
            for entry in names[:limit]:
                candidate = entry.rsplit("/", 1)[-1]
                if not PLAIN_SKILL_FILENAMES.match(candidate):
                    continue
                try:
                    text = archive.read(entry).decode("utf-8", errors="replace")
                    name, description, body = _skill_from_markdown(Path(candidate))
                except Exception:
                    continue
                slug = slugify(name)
                if (SKILLS_DIR / slug).exists() and not overwrite:
                    skipped.append({"name": name, "reason": "already installed"})
                    continue
                try:
                    imported.append(_install_skill(slug, name, description, body, label))
                except Exception as exc:
                    errors.append(f"{name}: {exc}")
    return {
        "imported": imported,
        "skipped": skipped,
        "errors": errors,
        "found": len(imported) + len(skipped) + len(errors),
    }


# --------------------------------------------------------------------------- bundled packs

BUNDLED_PACKS = {
    "openhands": "OpenHands (MIT)",
    "deepagents": "deepagents (MIT)",
    "genagent": "GenAgent (MIT)",
}


def bundled_skills() -> list[dict]:
    """Skills that ship with AgentDesk."""
    found: list[dict] = []
    if not BUNDLED_DIR.is_dir():
        return found
    for pack, label in BUNDLED_PACKS.items():
        pack_dir = BUNDLED_DIR / pack
        if not pack_dir.is_dir():
            continue
        for item in scan_folder(pack_dir, pack_label=label):
            item["source"] = label
            found.append(item)
    return found


def seed_bundled_skills(overwrite: bool = False) -> dict:
    """Install the bundled skill packs on first run.

    Existing user skills are never overwritten unless ``overwrite`` is set.
    """
    imported: list[dict] = []
    skipped: list[dict] = []
    errors: list[str] = []
    for pack, label in BUNDLED_PACKS.items():
        pack_dir = BUNDLED_DIR / pack
        if not pack_dir.is_dir():
            continue
        for candidate in scan_folder(pack_dir, pack_label=label):
            slug = candidate["slug"]
            if (SKILLS_DIR / slug).exists() and not overwrite:
                skipped.append({"name": candidate["name"], "reason": "already installed"})
                continue
            source_file = Path(candidate["path"])
            try:
                name, description, body, _meta = _read_skill_md(source_file)
                extras = {
                    str(p.relative_to(source_file.parent)): p.read_bytes()
                    for p in source_file.parent.rglob("*")
                    if p.is_file() and p.name != "SKILL.md"
                }
                imported.append(_install_skill(slug, name, description, body, label, extras))
            except Exception as exc:
                errors.append(f"{candidate['name']}: {exc}")
    return {"imported": imported, "skipped": skipped, "errors": errors}


def skills_data_dir() -> Path:
    """Where imported skills live (kept for diagnostics)."""
    return DATA_DIR / "skills"
