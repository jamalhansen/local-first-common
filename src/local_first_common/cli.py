"""Typer CLI helpers for consistent provider/model/flag patterns across tools."""

import logging
from typing import Any, Optional

import typer

from .logging import setup_logging

app = typer.Typer(name="local-first", help="Local-first AI tools management.")


@app.callback()
def main() -> None:
    """Entry callback so `local-first --help` is always valid."""
    return None


def provider_option(providers: dict | None = None) -> Any:
    """Return a Typer Option for provider metadata."""
    if providers is None:
        from .providers import PROVIDERS

        providers = PROVIDERS

    choices = list(providers.keys())
    return typer.Option(
        "--provider",
        "-p",
        help=f"LLM provider. Choices: {', '.join(choices)}",
    )


def model_option() -> Any:
    """Return a Typer Option for model metadata."""
    return typer.Option(
        "--model",
        "-m",
        help="Override the provider's default model. Supports aliases for Ollama (e.g. @fast, @vision, @best).",
    )


def dry_run_option() -> Any:
    """Return a Typer Option for dry-run metadata."""
    return typer.Option(
        "--dry-run",
        "-n",
        help="Perform the action and call the LLM, but do not write to disk/vault/DB. Print result to stdout.",
    )


def no_llm_option() -> Any:
    """Return a Typer Option for no-llm metadata."""
    return typer.Option(
        "--no-llm",
        help="Skip calling the LLM backend. Use mock responses. Implies --dry-run.",
    )


def verbose_option() -> Any:
    """Return a Typer Option for verbose metadata."""
    return typer.Option(
        "--verbose",
        "-v",
        help="Show extra debug output.",
    )


def debug_option() -> Any:
    """Return a Typer Option for debug metadata."""
    return typer.Option(
        "--debug",
        "-d",
        help="Show raw prompts and LLM responses.",
    )


def pipe_option() -> Any:
    """Return a Typer Option for pipe metadata."""
    return typer.Option(
        "--pipe",
        "-P",
        help="Read input from stdin instead of a file.",
    )


def init_config_callback(tool_name: str, defaults: dict):
    def callback(value: bool):
        if value:
            from .config import init_config

            path = init_config(tool_name, defaults)
            typer.echo(f"Created default config at {path}")
            raise typer.Exit()

    return callback


def init_config_option(tool_name: str, defaults: dict) -> Any:
    """Return a Typer Option for --init-config metadata."""
    return typer.Option(
        "--init-config",
        callback=init_config_callback(tool_name, defaults),
        is_eager=True,
        help=f"Generate a default config file for {tool_name}.",
    )


def resolve_dry_run(dry_run: bool, no_llm: bool) -> bool:
    """Standard rule: --no-llm always implies --dry-run."""
    if no_llm:
        return True
    return dry_run


def resolve_provider(
    providers: dict | None = None,
    provider_name: str = "ollama",
    model: Optional[str] = None,
    debug: bool = False,
    verbose: bool = False,
    no_llm: bool = False,
):
    """Instantiate the named provider, with validation and helpful error on unknown name."""
    if providers is None:
        from .providers import PROVIDERS

        providers = PROVIDERS

    if no_llm or provider_name == "mock":
        from .testing import MockProvider

        return MockProvider()

    if debug:
        setup_logging(level=logging.DEBUG)
    elif verbose:
        setup_logging(level=logging.INFO)

    if provider_name not in providers:
        valid = ", ".join(providers.keys())
        raise typer.BadParameter(
            f"Unknown provider '{provider_name}'. Valid options: {valid}"
        )

    cls = providers[provider_name]
    return cls(model=model)
