from .anthropic import AnthropicProvider
from .base import BaseProvider
from .deepseek import DeepSeekProvider
from .fallback import FallbackProvider
from .gemini import GeminiProvider
from .groq import GroqProvider
from .ollama import OllamaProvider

PROVIDERS = {
    "ollama": OllamaProvider,
    "local": OllamaProvider,  # alias for Ollama (backward compat)
    "anthropic": AnthropicProvider,
    "gemini": GeminiProvider,
    "groq": GroqProvider,
    "deepseek": DeepSeekProvider,
}

__all__ = [
    "PROVIDERS",
    "BaseProvider",
    "FallbackProvider",
    "OllamaProvider",
    "AnthropicProvider",
    "GeminiProvider",
    "GroqProvider",
    "DeepSeekProvider",
]

