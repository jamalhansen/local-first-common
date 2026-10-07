"""Utilities for working with pydantic-ai."""

import os
from typing import Any

PROVIDER_DEFAULTS: dict[str, str] = {
    "ollama": "phi4-mini",
    "local": "phi4-mini",
    "anthropic": "claude-haiku-4-5-20251001",
    "groq": "llama-3.3-70b-versatile",
    "deepseek": "deepseek-chat",
    "gemini": "gemini-2.0-flash",
    "mock": "test-model",
}

VALID_PROVIDERS = list(PROVIDER_DEFAULTS.keys())


def build_model(
    provider: str,
    model_name: str | None = None,
    tier: str | None = None,
) -> Any:
    """Return a pydantic-ai Model object for the given provider, optional model name, or tier."""
    if provider not in PROVIDER_DEFAULTS:
        valid = ", ".join(VALID_PROVIDERS)
        raise ValueError(f"Unknown provider '{provider}'. Valid options: {valid}")

    if not model_name and tier:
        from .tiering import get_tier_model

        model = get_tier_model(tier, provider)
    else:
        model = model_name or PROVIDER_DEFAULTS[provider]

    if provider in ("ollama", "local"):
        from pydantic_ai.models.openai import OpenAIChatModel  # pyright: ignore[reportMissingImports]  # optional extra
        from pydantic_ai.providers.openai import (  # pyright: ignore[reportMissingImports]  # optional extra
            OpenAIProvider,
        )

        return OpenAIChatModel(
            model,
            provider=OpenAIProvider(
                base_url="http://localhost:11434/v1",
                api_key="ollama",
            ),
        )

    if provider == "anthropic":
        from pydantic_ai.models.anthropic import (  # pyright: ignore[reportMissingImports]  # optional extra
            AnthropicModel,
        )

        return AnthropicModel(model)

    if provider == "groq":
        from pydantic_ai.models.groq import GroqModel  # pyright: ignore[reportMissingImports]  # optional extra

        return GroqModel(model)

    if provider == "deepseek":
        from pydantic_ai.models.openai import OpenAIChatModel  # pyright: ignore[reportMissingImports]  # optional extra
        from pydantic_ai.providers.openai import (  # pyright: ignore[reportMissingImports]  # optional extra
            OpenAIProvider,
        )

        return OpenAIChatModel(
            model,
            provider=OpenAIProvider(
                base_url="https://api.deepseek.com/v1",
                api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
            ),
        )

    if provider == "gemini":
        from pydantic_ai.models.google import GoogleModel  # pyright: ignore[reportMissingImports]  # optional extra

        return GoogleModel(model)

    if provider == "mock":
        from pydantic_ai.models.test import TestModel  # pyright: ignore[reportMissingImports]  # optional extra

        return TestModel()

    raise ValueError(f"Unknown provider '{provider}'")
