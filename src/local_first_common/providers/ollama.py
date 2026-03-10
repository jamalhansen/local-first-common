from typing import Any, Dict, List, Optional, Union

import httpx

from .base import BaseProvider


class OllamaProvider(BaseProvider):
    default_model = "phi4-mini"
    known_models: List[str] = []  # fetched dynamically from /api/tags
    models_url = "http://localhost:11434"

    def _get_installed_models(self) -> List[str]:
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{self.models_url}/api/tags")
                response.raise_for_status()
                data = response.json()
                return [m["name"] for m in data.get("models", [])]
        except Exception:
            return []

    def complete(
        self,
        system: str,
        user: str,
        response_model: Optional[Any] = None,
    ) -> Union[str, Dict[str, Any]]:
        template = self._get_example_json(response_model) if response_model else ""
        self._debug_print_request(template, system, user)

        prompt = f"<system>\n{system}\n</system>\n\n<user>\n{user}\n</user>"
        if response_model:
            prompt += f"\n\n<instructions>\nReturn ONLY a valid JSON object. Use this exact structure:\n{template}\n</instructions>"

        payload: Dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }
        if response_model:
            payload["format"] = "json"

        try:
            with httpx.Client(timeout=120.0) as client:
                response = client.post(f"{self.models_url}/api/generate", json=payload)
                if response.status_code == 404:
                    installed = self._get_installed_models()
                    hint = f"Installed models: {installed}" if installed else "Run 'ollama list' to see installed models."
                    raise RuntimeError(
                        f"Ollama model '{self.model}' not found. Pull it with 'ollama pull {self.model}'. "
                        f"{hint}. See {self.models_url}"
                    )
                response.raise_for_status()
                content = response.json().get("response", "")
        except httpx.RequestError as exc:
            raise RuntimeError(
                f"Ollama request failed: {exc}. Is Ollama running? Try: ollama serve"
            )

        result = self._parse_json_response(content, response_model) if response_model else content
        self._debug_print_response(result)
        return result
