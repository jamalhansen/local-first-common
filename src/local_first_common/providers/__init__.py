from .anthropic import AnthropicProvider
from .base import BaseProvider
from .claude_code import ClaudeCodeProvider
from .deepseek import DeepSeekProvider
from .fallback import FallbackProvider
from .gemini import GeminiProvider
from .groq import GroqProvider
from .ollama import OllamaProvider

PROVIDERS = {
    "ollama": OllamaProvider,
    "local": OllamaProvider,  # alias for Ollama (backward compat)
    "anthropic": AnthropicProvider,
    "claude-code": ClaudeCodeProvider,
    "gemini": GeminiProvider,
    "groq": GroqProvider,
    "deepseek": DeepSeekProvider,
}

__all__ = [
    "PROVIDERS",
    "AnthropicProvider",
    "BaseProvider",
    "ClaudeCodeProvider",
    "DeepSeekProvider",
    "FallbackProvider",
    "GeminiProvider",
    "GroqProvider",
    "OllamaProvider",
]

