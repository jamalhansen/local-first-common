"""Shared utilities for reading and writing Obsidian markdown vaults."""
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Iterator, Optional

import frontmatter


def find_vault_root(env_var: str = "OBSIDIAN_VAULT_PATH") -> Path:
    """Return vault root from env var, or discover via .obsidian dir, or fall back to cwd."""
    import os

    vault_path = os.environ.get(env_var)
    if vault_path:
        return Path(vault_path).expanduser()

    current = Path.cwd()
    for parent in [current, *current.parents]:
        if (parent / ".obsidian").is_dir():
            return parent

    return current


def get_daily_note_path(vault_root: Path, note_date: date, subdir: Optional[str] = None) -> Path:
    """Return the path for a daily note. Optionally nested under subdir."""
    base = vault_root / subdir if subdir else vault_root
    return base / f"{note_date.isoformat()}.md"


def get_week_dates(date_in_week: date) -> list[date]:
    """Return the 7 dates (Mon–Sun) for the ISO week containing date_in_week."""
    monday = date_in_week - timedelta(days=date_in_week.weekday())
    return [monday + timedelta(days=i) for i in range(7)]


def render_obsidian_template(template: str, note_date: date) -> str:
    """Replace Obsidian template variables ({{date:...}}, {{yesterday}}, {{tomorrow}})."""
    yesterday = note_date - timedelta(days=1)
    tomorrow = note_date + timedelta(days=1)

    def replace_date_format(m: re.Match) -> str:
        fmt = m.group(1).strip()
        fmt = fmt.replace("YYYY", "%G")
        fmt = fmt.replace("MM", "%m")
        fmt = fmt.replace("DD", "%d")
        fmt = re.sub(r"\[W\]W", "W%V", fmt)
        return note_date.strftime(fmt)

    result = re.sub(r"\{\{date:([^}]+)\}\}", replace_date_format, template)
    result = re.sub(r"\{\{\s*yesterday\s*\}\}", yesterday.isoformat(), result)
    result = re.sub(r"\{\{\s*tomorrow\s*\}\}", tomorrow.isoformat(), result)
    return result


def append_to_daily_note(
    note_path: Path,
    content: str,
    template_path: Optional[Path] = None,
) -> None:
    """
    Append content to an existing or new daily note.

    If the note exists, inserts a --- separator then appends.
    If the note does not exist, renders template (if provided) or writes minimal frontmatter.
    """
    note_path.parent.mkdir(parents=True, exist_ok=True)

    if note_path.exists():
        existing = note_path.read_text(encoding="utf-8")
        separator = "\n\n---\n\n" if existing.strip() else ""
        note_path.write_text(existing.rstrip() + separator + content + "\n", encoding="utf-8")
    else:
        base = _new_note_base(note_path, template_path)
        note_path.write_text(base + content + "\n", encoding="utf-8")


def _new_note_base(note_path: Path, template_path: Optional[Path]) -> str:
    if template_path and template_path.exists():
        try:
            note_date = date.fromisoformat(note_path.stem[:10])
        except ValueError:
            note_date = date.today()
        rendered = render_obsidian_template(template_path.read_text(encoding="utf-8"), note_date)
        return rendered.rstrip() + "\n\n---\n\n"
    return f"---\ndate: {date.today().isoformat()}\n---\n\n"


def load_daily_notes_for_week(
    vault_root: Path,
    dates: list[date],
    subdir: Optional[str] = None,
) -> list[dict]:
    """Load daily notes for a list of dates. Returns [{date, content, path}] for found files."""
    notes = []
    for d in dates:
        path = get_daily_note_path(vault_root, d, subdir=subdir)
        if path.is_file():
            try:
                post = frontmatter.load(str(path))
                notes.append({"date": d, "content": post.content, "path": path})
            except Exception as e:
                print(f"Warning: could not load {path}: {e}")
    return notes


def iter_daily_notes(
    vault_root: Path,
    subdir: Optional[str] = None,
) -> Iterator[dict]:
    """Yield all daily notes (newest first) as {date, content, path} dicts."""
    base = vault_root / subdir if subdir else vault_root
    for path in sorted(base.glob("????-??-??.md"), reverse=True):
        try:
            note_date = date.fromisoformat(path.stem)
            post = frontmatter.load(str(path))
            yield {"date": note_date, "content": post.content, "path": path}
        except Exception:
            continue


def format_notes_for_llm(notes: list[dict]) -> str:
    """Combine notes into a single string for use in an LLM prompt."""
    parts = []
    for note in notes:
        parts.append(f"## DATE: {note['date'].isoformat()}")
        parts.append(note["content"])
        parts.append("\n---\n")
    return "\n".join(parts)
