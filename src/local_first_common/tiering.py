"""Model tiering and automated local-to-cloud fallback definitions."""

from __future__ import annotations

import os

__all__ = [
    "FAST_TIER_MODELS",
    "REASONING_TIER_MODELS",
    "detect_active_cloud_provider",
    "get_tier_model",
    "resolve_fallback_target",
]

# Tier 1: Fast Local Tier (3B–8B SLMs)
# Target: Low latency (< 1s), $0 token cost, ideal for deterministic classification,
# frontmatter parsing, tag suggestions, and voice extraction.
FAST_TIER_MODELS: dict[str, str] = {
    "ollama": "llama3.2:3b",
    "local": "llama3.2:3b",
    "anthropic": "claude-haiku-4-5-20251001",
    "gemini": "gemini-2.0-flash",
    "groq": "llama-3.1-8b-instant",
    "deepseek": "deepseek-chat",
    "mock": "test-model",
}

# Tier 2: High-Reasoning Cloud Tier
# Target: Deep multi-perspective synthesis, adversarial critique, complex analysis.
REASONING_TIER_MODELS: dict[str, str] = {
    "anthropic": "claude-3-7-sonnet-latest",
    "gemini": "gemini-2.5-pro",
    "groq": "llama-3.3-70b-versatile",
    "deepseek": "deepseek-reasoner",
    "ollama": "llama3.3:70b",
    "local": "llama3.3:70b",
    "mock": "test-model",
}


def get_tier_model(tier: str, provider: str) -> str:
    """Return recommended model for a given tier and provider."""
    normalized_tier = tier.strip().lower()
    normalized_provider = provider.strip().lower()

    if (
        normalized_tier in ("fast", "slm", "classification", "tagging")
        and normalized_provider in FAST_TIER_MODELS
    ):
        return FAST_TIER_MODELS[normalized_provider]
    elif (
        normalized_tier in ("reasoning", "cloud", "frontier", "critique")
        and normalized_provider in REASONING_TIER_MODELS
    ):
        return REASONING_TIER_MODELS[normalized_provider]

    # Fallback to provider default if tier unknown
    from .pydantic_ai_utils import PROVIDER_DEFAULTS

    return PROVIDER_DEFAULTS.get(normalized_provider, "unknown")


def detect_active_cloud_provider() -> tuple[str, str] | None:
    """Detect available cloud provider from active environment API keys.

    Returns (provider_name, model_name) or None if no cloud keys are set.
    Priority order: Anthropic > Gemini > Groq > DeepSeek.
    """
    if os.environ.get("ANTHROPIC_API_KEY"):
        return ("anthropic", REASONING_TIER_MODELS["anthropic"])
    if os.environ.get("GEMINI_API_KEY"):
        return ("gemini", REASONING_TIER_MODELS["gemini"])
    if os.environ.get("GROQ_API_KEY"):
        return ("groq", REASONING_TIER_MODELS["groq"])
    if os.environ.get("DEEPSEEK_API_KEY"):
        return ("deepseek", REASONING_TIER_MODELS["deepseek"])
    return None


def resolve_fallback_target(
    requested_provider: str | None = None,
    requested_model: str | None = None,
) -> tuple[str, str] | None:
    """Resolve the target provider and model for automatic fallback.

    Checks:
    1. Explicit parameters passed to function
    2. LOCAL_FIRST_FALLBACK_PROVIDER / FALLBACK_PROVIDER environment variables
    3. Auto-detected cloud provider with configured API key
    """
    prov = (
        requested_provider
        or os.environ.get("LOCAL_FIRST_FALLBACK_PROVIDER")
        or os.environ.get("FALLBACK_PROVIDER")
    )
    mod = (
        requested_model
        or os.environ.get("LOCAL_FIRST_FALLBACK_MODEL")
        or os.environ.get("FALLBACK_MODEL")
    )

    if prov:
        prov = prov.strip().lower()
        target_model = mod or REASONING_TIER_MODELS.get(prov) or FAST_TIER_MODELS.get(prov, "default")
        return (prov, target_model)

    return detect_active_cloud_provider()
