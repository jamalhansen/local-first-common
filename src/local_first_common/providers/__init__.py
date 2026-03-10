from .anthropic import AnthropicProvider
from .base import BaseProvider
from .deepseek import DeepSeekProvider
from .gemini import GeminiProvider
from .groq import GroqProvider
from .ollama import OllamaProvider

PROVIDERS = {
    "ollama": OllamaProvider,
    "anthropic": AnthropicProvider,
    "gemini": GeminiProvider,
    "groq": GroqProvider,
    "deepseek": DeepSeekProvider,
}

__all__ = [
    "PROVIDERS",
    "BaseProvider",
    "OllamaProvider",
    "AnthropicProvider",
    "GeminiProvider",
    "GroqProvider",
    "DeepSeekProvider",
]
