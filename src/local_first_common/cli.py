"""Typer CLI helpers for consistent provider/model/flag patterns across tools."""

import logging
import os
from typing import Any

import typer

from .logging import setup_logging

logger = logging.getLogger(__name__)

# Opt-in delegation to llm-gateway-service instead of instantiating a
# provider's own SDK client in-process. Unset by default -- see
# providers/gateway.py's GatewayProvider for what this does and doesn't
# support.
LLM_GATEWAY_URL = os.environ.get("LLM_GATEWAY_URL") or None

app = typer.Typer(name="local-first", help="Local-first AI tools management.")


@app.callback()
def main() -> None:
    """Entry callback so `local-first --help` is always valid."""
    return


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


def json_option() -> Any:
    """Return a Typer Option for JSON output."""
    return typer.Option(
        "--json",
        "-j",
        help="Output results as JSON for programmatic consumption and piping.",
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
        "--init-config/--no-init-config",
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
    model: str | None = None,
    debug: bool = False,
    verbose: bool = False,
    no_llm: bool = False,
    fallback: bool = True,
    fallback_provider: str | None = None,
    fallback_model: str | None = None,
    tool_name: str | None = None,
    use_gateway: bool = True,
):
    """Instantiate the named provider, with validation, helpful error on unknown name,
    and automatic local-to-cloud failover when Ollama is unavailable.

    tool_name, if given, attributes a failed primary-provider attempt to that
    tool in processing_log when a fallback fires -- see FallbackProvider.

    use_gateway=False forces real, direct provider instantiation even when
    LLM_GATEWAY_URL is set -- required by llm-gateway-service's OWN internal
    call (it inherits LLM_GATEWAY_URL from the same shell env as everything
    else). Found live 2026-09-20: without this, the gateway's own resolve_provider()
    call took the gateway branch and built a GatewayProvider pointed at
    itself -- every request the gateway received for the same target_provider
    recursed into another HTTP call to itself, unbounded, until the process
    ran out of file descriptors. use_gateway=False still gets real fallback
    protection (FallbackProvider wrapping real provider instances, not a
    self-referential proxy) via the direct-instantiation branch below.
    """
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
    else:
        setup_logging(level=logging.WARNING)

    if provider_name not in providers:
        valid = ", ".join(providers.keys())
        raise typer.BadParameter(
            f"Unknown provider '{provider_name}'. Valid options: {valid}"
        )

    if LLM_GATEWAY_URL and use_gateway:
        # The gateway calls resolve_provider() itself server-side (same
        # function, running inside its own process) for CONNECTIVITY
        # fallback (Ollama down/unreachable) -- but the gateway never parses
        # or validates the response against a schema (schema-awareness stays
        # entirely client-side, see GatewayProvider), so it can't catch "the
        # model responded with malformed JSON" the way a direct FallbackProvider
        # can. Wire real client-side fallback here too when requested, using
        # a second GatewayProvider (same target_provider mechanism, just a
        # different provider name) rather than instantiating a real SDK
        # client -- keeps both legs going through the gateway's auth/logging.
        from .providers.gateway import GatewayProvider

        primary = GatewayProvider(LLM_GATEWAY_URL, provider_name, model, debug=debug)

        if fallback and provider_name in ("ollama", "local"):
            from .providers.fallback import FallbackProvider
            from .tiering import resolve_fallback_target

            target = resolve_fallback_target(fallback_provider, fallback_model)
            if target:
                fb_prov_name, fb_model_name = target
                if fb_prov_name in providers and fb_prov_name not in ("ollama", "local"):
                    fb_instance = GatewayProvider(LLM_GATEWAY_URL, fb_prov_name, fb_model_name, debug=debug)
                    return FallbackProvider(primary, fb_instance, debug=debug, tool_name=tool_name)

        return primary

    cls = providers[provider_name]
    kwargs = {"model": model}
    if debug:
        kwargs["debug"] = True
    try:
        primary = cls(**kwargs)
    except TypeError:
        primary = cls(model=model)

    if fallback and provider_name in ("ollama", "local"):
        from .providers.fallback import FallbackProvider
        from .tiering import resolve_fallback_target

        target = resolve_fallback_target(fallback_provider, fallback_model)
        if target:
            fb_prov_name, fb_model_name = target
            if fb_prov_name in providers and fb_prov_name not in ("ollama", "local"):
                try:
                    fb_cls = providers[fb_prov_name]
                    fb_kwargs = {"model": fb_model_name}
                    if debug:
                        fb_kwargs["debug"] = True
                    try:
                        fb_instance = fb_cls(**fb_kwargs)
                    except TypeError:
                        fb_instance = fb_cls(model=fb_model_name)
                    return FallbackProvider(primary, fb_instance, debug=debug, tool_name=tool_name)
                except Exception as e:  # noqa: BLE001 - fallback setup is opportunistic; any failure here should just leave the primary provider in place
                    logger.debug("Fallback provider setup failed, using primary only: %s", e)

    return primary


