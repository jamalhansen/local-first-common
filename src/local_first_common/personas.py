"""Persona store: load YAML persona files into structured PersonaCard models."""
import os
from pathlib import Path
from typing import Optional

import yaml
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
    principle: str
    lens: str
    bias: PersonaBias
    evaluation_questions: list[str]
    rewards: list[str]
    penalizes: list[str]
    conflict_signature: str
    system_prompt: str


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
