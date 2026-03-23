import os
from typing import Any, Dict, List, Optional, Union

import httpx

from .base import BaseProvider


class GroqProvider(BaseProvider):
    default_model = "llama-3.3-70b-versatile"
    known_models: List[str] = [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "mixtral-8x7b-32768",
    ]
    models_url = "https://console.groq.com/docs/models"
    _api_url = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self, model: Optional[str] = None, debug: bool = False, api_key: Optional[str] = None):
        super().__init__(model=model, debug=debug)
        self.api_key = api_key or os.environ.get("GROQ_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "GROQ_API_KEY is required. Set it as an environment variable."
            )
        self.input_tokens: int = 0
        self.output_tokens: int = 0

    def _build_payload(self, system: str, user: str, template: str, is_json: bool) -> Dict[str, Any]:
        actual_system = system
        if template:
            actual_system += f"\n\nYou MUST return a valid JSON object matching this structure:\n{template}\nDO NOT include any other text."

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": actual_system},
                {"role": "user", "content": user},
            ],
        }
        if is_json:
            payload["response_format"] = {"type": "json_object"}
        return payload

    def _complete(
        self,
        system: str,
        user: str,
        response_model: Optional[Any] = None,
        images: Optional[list[str]] = None,
    ) -> Union[str, Dict[str, Any]]:
        template = self._get_example_json(response_model) if response_model else ""
        self._debug_print_request(template, system, user)

        payload = self._build_payload(system, user, template, bool(response_model))
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        try:
            with httpx.Client(timeout=120.0) as client:
                response = client.post(self._api_url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                usage = data.get("usage", {})
                self.input_tokens += usage.get("prompt_tokens", 0)
                self.output_tokens += usage.get("completion_tokens", 0)
                content = data["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as e:
            err = str(e)
            if "model" in err.lower():
                raise RuntimeError(
                    f"Groq model '{self.model}' not found. "
                    f"Known models: {self.known_models}. See {self.models_url}"
                )
            raise RuntimeError(f"Groq API error: {e}")
        except Exception as e:
            raise RuntimeError(f"Groq request failed: {e}")

        result = self._parse_json_response(content, response_model) if response_model else content
        self._debug_print_response(result)
        return result

    async def _acomplete(
        self,
        system: str,
        user: str,
        response_model: Optional[Any] = None,
        images: Optional[list[str]] = None,
    ) -> Union[str, Dict[str, Any]]:
        template = self._get_example_json(response_model) if response_model else ""
        self._debug_print_request(template, system, user)

        payload = self._build_payload(system, user, template, bool(response_model))
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(self._api_url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                usage = data.get("usage", {})
                self.input_tokens += usage.get("prompt_tokens", 0)
                self.output_tokens += usage.get("completion_tokens", 0)
                content = data["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as e:
            err = str(e)
            if "model" in err.lower():
                raise RuntimeError(
                    f"Groq model '{self.model}' not found. "
                    f"Known models: {self.known_models}. See {self.models_url}"
                )
            raise RuntimeError(f"Groq API error: {e}")
        except Exception as e:
            raise RuntimeError(f"Groq request failed: {e}")

        result = self._parse_json_response(content, response_model) if response_model else content
        self._debug_print_response(result)
        return result
