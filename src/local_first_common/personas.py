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
    """Load a single persona by name (checking .yaml then .md in a specific dir)."""
    directory = _personas_dir(personas_dir)
    yaml_path = directory / f"{name.lower()}.yaml"
    md_path = directory / f"{name.lower()}.md"
    
    # Also check case-sensitive if lowercase fails
    if not yaml_path.exists():
        yaml_path = directory / f"{name}.yaml"
    if not md_path.exists():
        md_path = directory / f"{name}.md"

    if yaml_path.exists():
        return load_any_persona(yaml_path)
    if md_path.exists():
        return load_any_persona(md_path)
        
    available = []
    if directory.exists():
        available = sorted(p.stem for p in directory.glob("*") if p.suffix in (".yaml", ".md"))
    hint = f"Available: {', '.join(available)}" if available else "No personas found."
    raise FileNotFoundError(f"Persona '{name}' not found at {directory}. {hint}")


def get_persona(
    name: str, 
    category: str, 
    vault_path: Optional[Path] = None, 
    config_dir: Optional[Path] = None
) -> BasePersona:
    """Load a single persona by name and category. 
    
    Search order:
    1. Obsidian vault: personas/{category}/{name}.md
    2. Config dir: personas/{category}/{name}.yaml or .md
    """
    from .obsidian import find_vault_root
    
    # 1. Check Vault
    try:
        root = vault_path or find_vault_root()
        vault_file = root / "personas" / category / f"{name}.md"
        if not vault_file.exists():
             # Try lowercase
             vault_file = root / "personas" / category / f"{name.lower()}.md"
        
        if vault_file.exists():
            return load_obsidian_persona(vault_file)
    except Exception:
        pass
        
    # 2. Check Config Fallback
    base_config = config_dir or DEFAULT_PERSONAS_DIR
    try:
        return load_persona(name, personas_dir=base_config / category)
    except FileNotFoundError:
        # Try root of config as a secondary fallback
        try:
            return load_persona(name, personas_dir=base_config)
        except FileNotFoundError:
            raise FileNotFoundError(f"Persona '{name}' not found in vault or config for category '{category}'.")


def list_personas(
    category: Optional[str] = None, 
    vault_path: Optional[Path] = None, 
    config_dir: Optional[Path] = None
) -> list[BasePersona]:
    """Return all persona cards from vault and config directory, sorted by name.
    
    If category is provided, searches in personas/{category}/ subfolders.
    Otherwise, searches in the root of the personas directory (Legacy/Flat mode).
    """
    from .obsidian import find_vault_root
    
    personas_dict = {}
    
    # 1. Check Vault
    try:
        root = vault_path or find_vault_root()
        vault_dir = root / "personas"
        if category:
            vault_dir = vault_dir / category
            
        if vault_dir.exists():
            for md_file in vault_dir.glob("*.md"):
                try:
                    p = load_obsidian_persona(md_file)
                    # If category is specified, we might want to filter by frontmatter too
                    if category:
                        # User specified category: "[[Persona]]" check
                        cat_field = p.metadata.get("category", "")
                        # Handle both string and list/link formats
                        if isinstance(cat_field, str):
                             if "[[Persona]]" not in cat_field and cat_field != "Persona":
                                 # For some categories we might be more lenient, 
                                 # but if they are in the folder, they are likely personas.
                                 pass 
                    
                    personas_dict[p.name.lower()] = p
                except Exception:
                    pass
    except Exception:
        pass
        
    # 2. Check Config Fallback
    base_config = config_dir or DEFAULT_PERSONAS_DIR
    config_search_dir = base_config
    if category:
        config_search_dir = base_config / category
        
    if config_search_dir.exists():
        # Load YAMLs
        for yaml_file in config_search_dir.glob("*.yaml"):
            try:
                p = load_any_persona(yaml_file)
                name_key = p.name.lower()
                if name_key not in personas_dict:
                    personas_dict[name_key] = p
            except Exception:
                pass
                
        # Load MDs
        for md_file in config_search_dir.glob("*.md"):
            try:
                p = load_any_persona(md_file)
                name_key = p.name.lower()
                if name_key not in personas_dict:
                    personas_dict[name_key] = p
            except Exception:
                pass
                
    return sorted(personas_dict.values(), key=lambda p: p.name.lower())


def load_obsidian_persona(path: Path) -> BasePersona:
    """Parse an Obsidian persona markdown file using frontmatter."""
    try:
        post = frontmatter.load(path)
        content = post.content
        fm = post.metadata
    except Exception as e:
        logger.warning(f"Failed to load frontmatter from {path}: {e}")
        # Fallback to simple read
        content = path.read_text(encoding="utf-8")
        fm = {}
    
    # Extract Name from filename or fm or H1
    name = fm.get("name") or path.stem
    h1_match = re.search(r"^# (.*)$", content, re.MULTILINE)
    if h1_match and not fm.get("name"):
        name = h1_match.group(1).strip()
        
    # Extract Archetype
    archetype = fm.get("archetype") or "General Reader"
    archetype_match = re.search(r"\*\*Archetype:\*\* (.*)$", content, re.MULTILINE)
    if archetype_match and not fm.get("archetype"):
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

    metadata = {"path": str(path), "source": "obsidian"}
    metadata.update(fm)

    return BasePersona(
        name=name,
        archetype=archetype,
        system_prompt=system_prompt,
        domain=fm.get("domain", ""),
        metadata=metadata
    )


def list_vault_personas(category: str, vault_path: Optional[Path] = None) -> list[BasePersona]:
    """List all personas in a specific obsidian category (under personas/{category})."""
    return list_personas(category=category, vault_path=vault_path)


def list_obsidian_personas(category: str = "brand", vault_path: Optional[Path] = None) -> list[BasePersona]:
    """List all personas in a specific obsidian category. Legacy alias for list_vault_personas."""
    return list_vault_personas(category, vault_path)
