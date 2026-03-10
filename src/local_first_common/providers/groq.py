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

    def complete(
        self,
        system: str,
        user: str,
        response_model: Optional[Any] = None,
    ) -> Union[str, Dict[str, Any]]:
        template = self._get_example_json(response_model) if response_model else ""
        self._debug_print_request(template, system, user)

        actual_system = system
        if response_model:
            actual_system += f"\n\nYou MUST return a valid JSON object matching this structure:\n{template}\nDO NOT include any other text."

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": actual_system},
                {"role": "user", "content": user},
            ],
        }
        if response_model:
            payload["response_format"] = {"type": "json_object"}

        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        try:
            with httpx.Client(timeout=120.0) as client:
                response = client.post(self._api_url, json=payload, headers=headers)
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
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
