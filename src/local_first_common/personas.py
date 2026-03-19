"""Persona store: load YAML persona files into structured PersonaCard models."""
import os
import re
from pathlib import Path
from typing import Optional

import yaml
import frontmatter
from pydantic import BaseModel

DEFAULT_PERSONAS_DIR = Path(
    os.environ.get("LOCAL_FIRST_PERSONAS_DIR", "~/.config/local-first/personas")
).expanduser()


class PersonaBias(BaseModel):
    overweights: list[str] = []
    underweights: list[str] = []


class PersonaCard(BaseModel):
    name: str
    archetype: str
    domain: str
    princilege: str = "" # Some cards use principle, some use privileage, handle mapping if needed
    principle: str = ""
    lens: str
    bias: PersonaBias
    evaluation_questions: list[str]
    rewards: list[str]
    penalizes: list[str]
    conflict_signature: str
    system_prompt: str


def get_brand_voice(path: Optional[Path] = None) -> str:
    """Load brand voice from a file. Returns empty string if not found.
    
    This ensures personal style guides stay out of the repository.
    Optimizes by extracting 'The Short Version' or 'Writing Style' sections if they exist.
    """
    from .config import settings
    
    voice_path = path or settings.brand_voice_path
    if not voice_path or not Path(voice_path).exists():
        return ""
        
    path_obj = Path(voice_path)
    try:
        post = frontmatter.load(str(path_obj))
        content = post.content
    except Exception:
        content = path_obj.read_text(encoding="utf-8")

    # Try to find a concise section
    short_version_match = re.search(
        r"## (?:The Short Version|Writing Style)\n\n(.*?)(?=\n##|$)",
        content,
        re.DOTALL | re.IGNORECASE,
    )
    if short_version_match:
        return short_version_match.group(1).strip()

    # Fallback to full content (truncated if extreme)
    return content[:2000].strip()


def _personas_dir(override: Optional[Path] = None) -> Path:
    return override if override is not None else DEFAULT_PERSONAS_DIR


def load_persona(name: str, personas_dir: Optional[Path] = None) -> PersonaCard:
    """Load a single persona by name. Raises FileNotFoundError if not found."""
    directory = _personas_dir(personas_dir)
    path = directory / f"{name.lower()}.yaml"
    if not path.exists():
        available = sorted(p.stem for p in directory.glob("*.yaml")) if directory.exists() else []
        hint = f"Available: {', '.join(available)}" if available else "No personas found."
        raise FileNotFoundError(f"Persona '{name}' not found at {path}. {hint}")
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return PersonaCard(**data)


def list_personas(personas_dir: Optional[Path] = None) -> list[PersonaCard]:
    """Return all persona cards from the personas directory, sorted by name."""
    directory = _personas_dir(personas_dir)
    if not directory.exists():
        return []
    cards = []
    for yaml_file in sorted(directory.glob("*.yaml")):
        with open(yaml_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        cards.append(PersonaCard(**data))
    return cards
