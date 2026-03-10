"""Typer CLI helpers for consistent provider/model/flag patterns across tools."""
import os
from typing import Any, Optional

import typer


def provider_option(providers: dict, default: str = "ollama") -> Any:
    """Return a Typer Option for --provider / -p with env var fallback."""
    choices = list(providers.keys())
    env_default = os.environ.get("MODEL_PROVIDER", default)
    return typer.Option(
        env_default,
        "--provider",
        "-p",
        help=f"LLM provider. Choices: {', '.join(choices)}",
    )


def model_option() -> Any:
    """Return a Typer Option for --model / -m."""
    return typer.Option(
        None,
        "--model",
        "-m",
        help="Override the provider's default model.",
    )


def dry_run_option() -> Any:
    """Return a Typer Option for --dry-run / -n."""
    return typer.Option(
        False,
        "--dry-run",
        "-n",
        help="Preview output without writing files or calling LLM.",
    )


def verbose_option() -> Any:
    """Return a Typer Option for --verbose / -v."""
    return typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show extra debug output.",
    )


def debug_option() -> Any:
    """Return a Typer Option for --debug / -d (shows raw prompts and responses)."""
    return typer.Option(
        False,
        "--debug",
        "-d",
        help="Show raw prompts and LLM responses.",
    )


def resolve_provider(providers: dict, provider_name: str, model: Optional[str], debug: bool = False):
    """Instantiate the named provider, with validation and helpful error on unknown name."""
    if provider_name not in providers:
        valid = ", ".join(providers.keys())
        raise typer.BadParameter(f"Unknown provider '{provider_name}'. Valid options: {valid}")
    cls = providers[provider_name]
    kwargs: dict = {"debug": debug} if debug else {}
    if model:
        kwargs["model"] = model
    return cls(**kwargs)
