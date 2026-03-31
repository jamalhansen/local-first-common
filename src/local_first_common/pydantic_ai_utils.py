"""Utilities for working with pydantic-ai."""
import os
from typing import Any

PROVIDER_DEFAULTS: dict[str, str] = {
    "ollama": "phi4-mini",
    "anthropic": "claude-haiku-4-5-20251001",
    "groq": "llama-3.3-70b-versatile",
    "deepseek": "deepseek-chat",
    "gemini": "gemini-2.0-flash",
    "mock": "test-model",
}

VALID_PROVIDERS = list(PROVIDER_DEFAULTS.keys())


def build_model(provider: str, model_name: str | None) -> Any:
    """Return a pydantic-ai Model object for the given provider and optional model name."""
    if provider not in PROVIDER_DEFAULTS:
        valid = ", ".join(VALID_PROVIDERS)
        raise ValueError(f"Unknown provider '{provider}'. Valid options: {valid}")

    model = model_name or PROVIDER_DEFAULTS[provider]

    if provider == "ollama":
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider

        return OpenAIChatModel(
            model,
            provider=OpenAIProvider(
                base_url="http://localhost:11434/v1",
                api_key="ollama",
            ),
        )

    if provider == "anthropic":
        from pydantic_ai.models.anthropic import AnthropicModel

        return AnthropicModel(model)

    if provider == "groq":
        from pydantic_ai.models.groq import GroqModel

        return GroqModel(model)

    if provider == "deepseek":
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider

        return OpenAIChatModel(
            model,
            provider=OpenAIProvider(
                base_url="https://api.deepseek.com/v1",
                api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
            ),
        )

    if provider == "gemini":
        from pydantic_ai.models.google import GoogleModel

        return GoogleModel(model)

    if provider == "mock":
        from pydantic_ai.models.test import TestModel

        return TestModel()

    raise ValueError(f"Unknown provider '{provider}'")
