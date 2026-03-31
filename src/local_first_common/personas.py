"""Persona store: load YAML persona files into structured PersonaCard models."""
import os
import re
from pathlib import Path
from typing import Optional

import yaml
import frontmatter
from pydantic import BaseModel, Field

DEFAULT_PERSONAS_DIR = Path(
    os.environ.get("LOCAL_FIRST_PERSONAS_DIR", "~/.config/local-first/personas")
).expanduser()


class ObsidianPersona(BaseModel):
    name: str
    archetype: str
    system_prompt: str
    metadata: dict = Field(default_factory=dict)


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


def load_obsidian_persona(path: Path) -> ObsidianPersona:
    """Parse an Obsidian persona markdown file."""
    content = path.read_text(encoding="utf-8")
    
    # Extract Name from filename or H1
    name = path.stem
    h1_match = re.search(r"^# (.*)$", content, re.MULTILINE)
    if h1_match:
        name = h1_match.group(1).strip()
        
    # Extract Archetype
    archetype = "General Reader"
    archetype_match = re.search(r"\*\*Archetype:\*\* (.*)$", content, re.MULTILINE)
    if archetype_match:
        archetype = archetype_match.group(1).strip()
        
    # Extract System Prompt Seed
    system_prompt = ""
    # Look for the blockquote under "System Prompt Seed"
    seed_match = re.search(
        r"## System Prompt Seed\s*\n+>\s*(.*?)(?=\n\n|\n#|$)", 
        content, 
        re.DOTALL | re.IGNORECASE
    )
    if seed_match:
        system_prompt = seed_match.group(1).strip().replace("\n> ", " ")
    else:
        # Fallback: use the "Lens" or "Identity" if seed is missing
        lens_match = re.search(r"## Lens\s*\n+(.*?)(?=\n##|$)", content, re.DOTALL)
        if lens_match:
            system_prompt = f"You are {name}, {archetype}. {lens_match.group(1).strip()}"
        else:
            system_prompt = f"You are {name}, {archetype}."

    return ObsidianPersona(
        name=name,
        archetype=archetype,
        system_prompt=system_prompt,
        metadata={"path": str(path)}
    )


def list_obsidian_personas(category: str = "brand", vault_path: Optional[Path] = None) -> list[ObsidianPersona]:
    """List all personas in a specific obsidian category."""
    if vault_path is None:
        vault_path = Path(os.environ.get("OBSIDIAN_VAULT_PATH", ""))
        
    if not vault_path or not vault_path.exists():
        return []
        
    persona_dir = vault_path / "personas" / category
    if not persona_dir.exists():
        return []
        
    personas = []
    for md_file in persona_dir.glob("*.md"):
        try:
            personas.append(load_obsidian_persona(md_file))
        except Exception as e:
            # Using print is fine here as it's a utility function
            print(f"Warning: Failed to load persona {md_file}: {e}")
            
    return sorted(personas, key=lambda p: p.name)
