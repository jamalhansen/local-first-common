"""Persona store: load YAML or Markdown persona files into a unified BasePersona model."""
import logging
import os
import re
from pathlib import Path
from typing import Optional

import yaml
import frontmatter
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

DEFAULT_PERSONAS_DIR = Path(
    os.environ.get("LOCAL_FIRST_PERSONAS_DIR", "~/.config/local-first/personas")
).expanduser()


class BasePersona(BaseModel):
    """A unified persona model that works across YAML and Obsidian Markdown sources."""
    name: str
    archetype: str
    system_prompt: str
    metadata: dict = Field(default_factory=dict)
    domain: str = ""  # For PersonaCard compatibility


class ObsidianPersona(BasePersona):
    """Legacy model for Obsidian personas — now just an alias for BasePersona."""
    pass


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

    def to_base(self) -> BasePersona:
        """Convert a legacy PersonaCard to the unified BasePersona."""
        return BasePersona(
            name=self.name,
            archetype=self.archetype,
            system_prompt=self.system_prompt,
            domain=self.domain,
            metadata={"source": "yaml"}
        )


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


def load_any_persona(path: Path) -> BasePersona:
    """Load a persona from either .yaml or .md format."""
    if path.suffix.lower() == ".yaml":
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        card = PersonaCard(**data)
        return card.to_base()
    elif path.suffix.lower() == ".md":
        return load_obsidian_persona(path)
    else:
        raise ValueError(f"Unsupported persona format: {path.suffix}")


def load_persona(name: str, personas_dir: Optional[Path] = None) -> BasePersona:
    """Load a single persona by name (checking .yaml then .md). Raises FileNotFoundError if not found."""
    directory = _personas_dir(personas_dir)
    yaml_path = directory / f"{name.lower()}.yaml"
    md_path = directory / f"{name.lower()}.md"
    
    if yaml_path.exists():
        return load_any_persona(yaml_path)
    if md_path.exists():
        return load_any_persona(md_path)
        
    available = []
    if directory.exists():
        available = sorted(p.stem for p in directory.glob("*") if p.suffix in (".yaml", ".md"))
    hint = f"Available: {', '.join(available)}" if available else "No personas found."
    raise FileNotFoundError(f"Persona '{name}' not found at {directory}. {hint}")


def list_personas(personas_dir: Optional[Path] = None) -> list[BasePersona]:
    """Return all persona cards (.yaml and .md) from the personas directory, sorted by name."""
    directory = _personas_dir(personas_dir)
    if not directory.exists():
        return []
    
    personas = []
    # Load YAMLs
    for yaml_file in directory.glob("*.yaml"):
        try:
            personas.append(load_any_persona(yaml_file))
        except Exception:
            pass
            
    # Load MDs
    for md_file in directory.glob("*.md"):
        try:
            personas.append(load_any_persona(md_file))
        except Exception:
            pass
            
    return sorted(personas, key=lambda p: p.name.lower())


def load_obsidian_persona(path: Path) -> BasePersona:
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

    return BasePersona(
        name=name,
        archetype=archetype,
        system_prompt=system_prompt,
        metadata={"path": str(path), "source": "obsidian"}
    )


def list_vault_personas(category: str, vault_path: Optional[Path] = None) -> list[BasePersona]:
    """List all personas in a specific obsidian category (under personas/{category})."""
    from .obsidian import find_vault_root
    
    root = vault_path or find_vault_root()
    persona_dir = root / "personas" / category
    if not persona_dir.exists():
        return []
        
    personas = []
    for md_file in persona_dir.glob("*.md"):
        try:
            personas.append(load_obsidian_persona(md_file))
        except Exception as e:
            logger.warning("Failed to load persona %s: %s", md_file, e)
            
    return sorted(personas, key=lambda p: p.name.lower())


def list_obsidian_personas(category: str = "brand", vault_path: Optional[Path] = None) -> list[BasePersona]:
    """List all personas in a specific obsidian category. Legacy alias for list_vault_personas."""
    return list_vault_personas(category, vault_path)
