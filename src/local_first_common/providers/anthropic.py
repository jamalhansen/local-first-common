import os
from typing import Any, Dict, List, Optional, Union

from .base import BaseProvider

try:
    from anthropic import Anthropic as _Anthropic
    from anthropic import AsyncAnthropic as _AsyncAnthropic
except ImportError:
    _Anthropic = None  # type: ignore[assignment,misc]
    _AsyncAnthropic = None  # type: ignore[assignment,misc]


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
        self.input_tokens: int = 0
        self.output_tokens: int = 0

    def _build_actual_system(self, system: str, template: str) -> str:
        actual_system = system
        if template:
            actual_system += f"\n\nYou MUST return a valid JSON object matching this structure:\n{template}\nDO NOT include any other text."
        return actual_system

    def _build_messages(self, user: str, images: Optional[list[str]] = None) -> list[dict]:
        content: list[dict] = [{"type": "text", "text": user}]
        if images:
            for img in images:
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg", # Assume JPEG for now, could detect from header if needed
                        "data": img,
                    },
                })
        return [{"role": "user", "content": content}]

    def complete(
        self,
        system: str,
        user: str,
        response_model: Optional[Any] = None,
        images: Optional[list[str]] = None,
    ) -> Union[str, Dict[str, Any]]:
        if _Anthropic is None:
            raise RuntimeError(
                "anthropic package is required for AnthropicProvider. Install it with: uv add anthropic"
            )

        template = self._get_example_json(response_model) if response_model else ""
        self._debug_print_request(template, system, user)

        actual_system = self._build_actual_system(system, template)
        messages = self._build_messages(user, images)

        try:
            client = _Anthropic(api_key=self.api_key)
            message = client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=actual_system,
                messages=messages,
            )
            self.input_tokens += message.usage.input_tokens
            self.output_tokens += message.usage.output_tokens
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

    async def acomplete(
        self,
        system: str,
        user: str,
        response_model: Optional[Any] = None,
        images: Optional[list[str]] = None,
    ) -> Union[str, Dict[str, Any]]:
        if _AsyncAnthropic is None:
            raise RuntimeError(
                "anthropic package is required for AnthropicProvider. Install it with: uv add anthropic"
            )

        template = self._get_example_json(response_model) if response_model else ""
        self._debug_print_request(template, system, user)

        actual_system = self._build_actual_system(system, template)
        messages = self._build_messages(user, images)

        try:
            client = _AsyncAnthropic(api_key=self.api_key)
            message = await client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=actual_system,
                messages=messages,
            )
            self.input_tokens += message.usage.input_tokens
            self.output_tokens += message.usage.output_tokens
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
