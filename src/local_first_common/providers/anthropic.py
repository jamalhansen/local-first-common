import os
from typing import Any, Dict, List, Optional, Union

from .base import BaseProvider

try:
    from anthropic import Anthropic as _Anthropic
except ImportError:
    _Anthropic = None  # type: ignore[assignment,misc]


class AnthropicProvider(BaseProvider):
    default_model = "claude-haiku-4-5-20251001"
    known_models: List[str] = [
        "claude-opus-4-6",
        "claude-sonnet-4-6",
        "claude-haiku-4-5-20251001",
    ]
    models_url = "https://docs.anthropic.com/en/docs/about-claude/models"

    def __init__(self, model: Optional[str] = None, debug: bool = False, api_key: Optional[str] = None):
        super().__init__(model=model, debug=debug)
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is required. Set it as an environment variable."
            )

    def complete(
        self,
        system: str,
        user: str,
        response_model: Optional[Any] = None,
    ) -> Union[str, Dict[str, Any]]:
        if _Anthropic is None:
            raise RuntimeError(
                "anthropic package is required for AnthropicProvider. Install it with: uv add anthropic"
            )

        template = self._get_example_json(response_model) if response_model else ""
        self._debug_print_request(template, system, user)

        actual_system = system
        if response_model:
            actual_system += f"\n\nYou MUST return a valid JSON object matching this structure:\n{template}\nDO NOT include any other text."

        try:
            client = _Anthropic(api_key=self.api_key)
            message = client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=actual_system,
                messages=[{"role": "user", "content": user}],
            )
            content = message.content[0].text
        except Exception as e:
            err = str(e)
            if "model" in err.lower() and ("not found" in err.lower() or "invalid" in err.lower()):
                raise RuntimeError(
                    f"Anthropic model '{self.model}' not found. "
                    f"Known models: {self.known_models}. See {self.models_url}"
                )
            raise RuntimeError(f"Anthropic API error: {e}")

        result = self._parse_json_response(content, response_model) if response_model else content
        self._debug_print_response(result)
        return result
