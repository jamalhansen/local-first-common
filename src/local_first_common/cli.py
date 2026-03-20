"""Typer CLI helpers for consistent provider/model/flag patterns across tools."""
import logging
import os
import re
from pathlib import Path
from typing import Any, Optional

import typer

from .logging import setup_logging

app = typer.Typer(name="local-first", help="Local-first AI tools management.")


def provider_option(providers: dict | None = None, default: str = "ollama") -> Any:
    """Return a Typer Option for --provider / -p with env var fallback."""
    if providers is None:
        from .providers import PROVIDERS
        providers = PROVIDERS
    
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
        help="Override the provider's default model. Supports aliases for Ollama (e.g. @fast, @vision, @best).",
    )


def dry_run_option() -> Any:
    """Return a Typer Option for --dry-run / -n."""
    return typer.Option(
        ...,
        "--dry-run",
        "-n",
        help="Preview output without writing files or calling LLM.",
    )


def verbose_option() -> Any:
    """Return a Typer Option for --verbose / -v."""
    return typer.Option(
        ...,
        "--verbose",
        "-v",
        help="Show extra debug output.",
    )


def debug_option() -> Any:
    """Return a Typer Option for --debug / -d (shows raw prompts and responses)."""
    return typer.Option(
        ...,
        "--debug",
        "-d",
        help="Show raw prompts and LLM responses.",
    )


def resolve_provider(
    providers: dict | None = None,
    provider_name: str = "ollama",
    model: Optional[str] = None,
    debug: bool = False,
    verbose: bool = False,
):
    """Instantiate the named provider, with validation and helpful error on unknown name."""
    if providers is None:
        from .providers import PROVIDERS
        providers = PROVIDERS
    if debug:
        setup_logging(level=logging.DEBUG)
    elif verbose:
        setup_logging(level=logging.INFO)

    if provider_name not in providers:
        valid = ", ".join(providers.keys())
        raise typer.BadParameter(f"Unknown provider '{provider_name}'. Valid options: {valid}")
    
    cls = providers[provider_name]
    
    # --- Special Logic for Ollama Model Resolution ---
    if provider_name in ("ollama", "local"):
        # Resolve aliases like @fast, @vision, @best, @auto
        if model and model.startswith("@"):
            intent = model[1:].lower()
            if intent == "auto":
                intent = "text"
            temp_llm = cls(debug=debug)
            model = temp_llm.recommend_model(intent=intent)
            if verbose:
                typer.secho(f"Resolved alias to {model}", fg=typer.colors.DIM)

    kwargs: dict = {"debug": debug} if debug else {}
    if model:
        kwargs["model"] = model
    return cls(**kwargs)


@app.command()
def recommend():
    """Show hardware stats and recommended Ollama models for this machine."""
    from .config import settings
    from .providers.ollama import OllamaProvider
    from rich.table import Table
    from rich.console import Console

    console = Console()
    
    typer.secho("\nMachine Awareness Report", fg=typer.colors.CYAN, bold=True)
    typer.echo(f"  RAM: {settings.total_ram_gb:.1f} GB")
    typer.echo(f"  Profile: {'[Powerful]' if settings.is_powerful_machine else '[Standard]'}")
    
    ollama = OllamaProvider()
    installed = ollama._get_installed_model_names()
    
    if not installed:
        typer.secho("\nNo Ollama models found. Is Ollama running?", fg=typer.colors.RED)
        return

    table = Table(title="\nIntent-based Recommendations", title_style="bold magenta")
    table.add_column("Alias", style="cyan")
    table.add_column("Intent", style="white")
    table.add_column("Recommended Model", style="green")

    table.add_row("@best", "Highest quality", ollama.recommend_model("text"))
    table.add_row("@fast", "Lowest latency", ollama.recommend_model("fast"))
    table.add_row("@vision", "Image processing", ollama.recommend_model("vision"))
    table.add_row("@encoding", "Embeddings/Search", ollama.recommend_model("encoding"))

    console.print(table)
    typer.echo("\nUsage Example:")
    typer.echo("  uv run main.py --model @best")
    typer.echo("")


@app.command(name="list")
def list_tools():
    """List all available local-first AI tools in the current workspace."""
    # Look for directories next to local-first-common that have pyproject.toml
    # and depend on local-first-common.
    current_dir = Path.cwd()
    if current_dir.name == "local-first-common":
        root = current_dir.parent
    elif (current_dir / "local-first-common").is_dir():
        root = current_dir
    else:
        # Check parents to see if we are in a tool dir
        root = current_dir.parent
        if not (root / "local-first-common").is_dir():
            root = Path.home() / "projects" / "local-first"

    if not root.exists():
        typer.echo(f"Error: Could not find workspace root at {root}")
        raise typer.Exit(1)

    typer.secho("\nLocal-First AI Tools Registry", fg=typer.colors.CYAN, bold=True)
    typer.echo("-" * 40)

    found = 0
    for d in sorted(root.iterdir()):
        if d.is_dir() and (d / "pyproject.toml").exists():
            content = (d / "pyproject.toml").read_text()
            if "local-first-common" in content:
                desc = ""
                # Try to extract description from pyproject.toml
                match = re.search(r'description\s*=\s*"([^"]+)"', content)
                if match:
                    desc = f" — {match.group(1)}"
                
                typer.echo(f"  {d.name}{desc}")
                found += 1

    if found == 0:
        typer.echo(f"No local-first tools found in {root}")
    typer.echo("")


if __name__ == "__main__":
    app()
