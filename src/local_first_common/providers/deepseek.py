import os
from typing import Any, Dict, List, Optional, Union

import httpx

from .base import BaseProvider


class DeepSeekProvider(BaseProvider):
    default_model = "deepseek-chat"
    known_models: List[str] = [
        "deepseek-chat",
        "deepseek-reasoner",
    ]
    models_url = "https://api-docs.deepseek.com/quick_start/pricing"
    _api_url = "https://api.deepseek.com/chat/completions"

    def __init__(self, model: Optional[str] = None, debug: bool = False, api_key: Optional[str] = None):
        super().__init__(model=model, debug=debug)
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "DEEPSEEK_API_KEY is required. Set it as an environment variable."
            )

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

    def complete(
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
                content = response.json()["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as e:
            err = str(e)
            if "model" in err.lower():
                raise RuntimeError(
                    f"DeepSeek model '{self.model}' not found. "
                    f"Known models: {self.known_models}. See {self.models_url}"
                )
            raise RuntimeError(f"DeepSeek API error: {e}")
        except Exception as e:
            raise RuntimeError(f"DeepSeek request failed: {e}")

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
        template = self._get_example_json(response_model) if response_model else ""
        self._debug_print_request(template, system, user)

        payload = self._build_payload(system, user, template, bool(response_model))
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(self._api_url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as e:
            err = str(e)
            if "model" in err.lower():
                raise RuntimeError(
                    f"DeepSeek model '{self.model}' not found. "
                    f"Known models: {self.known_models}. See {self.models_url}"
                )
            raise RuntimeError(f"DeepSeek API error: {e}")
        except Exception as e:
            raise RuntimeError(f"DeepSeek request failed: {e}")

        result = self._parse_json_response(content, response_model) if response_model else content
        self._debug_print_response(result)
        return result
