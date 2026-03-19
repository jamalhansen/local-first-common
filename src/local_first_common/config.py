"""Centralized configuration for local-first AI tools."""
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LocalFirstSettings(BaseSettings):
    """Global settings for all local-first tools.

    Values are loaded from environment variables or a .env file.
    Priority: ENV VAR > .env file > Default value.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # LLM Defaults
    model_provider: str = Field(default="ollama", validation_alias="MODEL_PROVIDER")
    model_name: Optional[str] = Field(default=None, validation_alias="MODEL_NAME")

    # API Keys
    anthropic_api_key: Optional[str] = Field(default=None, validation_alias="ANTHROPIC_API_KEY")
    google_api_key: Optional[str] = Field(default=None, validation_alias="GOOGLE_API_KEY")
    gemini_api_key: Optional[str] = Field(default=None, validation_alias="GEMINI_API_KEY")
    groq_api_key: Optional[str] = Field(default=None, validation_alias="GROQ_API_KEY")
    deepseek_api_key: Optional[str] = Field(default=None, validation_alias="DEEPSEEK_API_KEY")

    # Obsidian
    obsidian_vault_path: Optional[str] = Field(default=None, validation_alias="OBSIDIAN_VAULT_PATH")

    # Content Discovery
    content_discovery_db_path: Optional[str] = Field(default=None, validation_alias="CONTENT_DISCOVERY_DB_PATH")

    # Personas
    personas_dir: Path = Field(
        default=Path("~/.config/local-first/personas").expanduser(),
        validation_alias="LOCAL_FIRST_PERSONAS_DIR"
    )
    brand_voice_path: Optional[Path] = Field(default=None, validation_alias="BRAND_VOICE_PATH")

    # Data Storage
    data_dir: Path = Field(
        default=Path("~/.local/share/local-ai-tools").expanduser(),
        validation_alias="LOCAL_FIRST_DATA_DIR"
    )

    @property
    def total_ram_gb(self) -> float:
        """Return total system RAM in GB."""
        import os
        try:
            # macOS / Linux
            return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / (1024**3)
        except (AttributeError, ValueError):
            return 8.0 # Safe fallback

    @property
    def is_powerful_machine(self) -> bool:
        """Heuristic to determine if the machine can handle larger models (>= 16GB RAM)."""
        return self.total_ram_gb >= 15.5

    @property
    def vault_root(self) -> Path:
        """Resolve and return the Obsidian vault root path."""
        from .obsidian import find_vault_root
        return find_vault_root(env_var="OBSIDIAN_VAULT_PATH")

    def get_db_path(self, tool_name: str, db_name: str = "data.db") -> Path:
        """Get a standardized path for a tool's SQLite database."""
        path = self.data_dir / tool_name / db_name
        path.parent.mkdir(parents=True, exist_ok=True)
        return path


# Global settings instance
settings = LocalFirstSettings()
