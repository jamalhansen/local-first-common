from typing import Any, Dict, List, Optional, Union
import logging

import httpx

from .base import BaseProvider

logger = logging.getLogger(__name__)


class OllamaProvider(BaseProvider):
    default_model = "phi4-mini"
    known_models: List[str] = []  # fetched dynamically from /api/tags
    models_url = "http://localhost:11434"

    def __init__(self, model: Optional[str] = None, debug: bool = False):
        # We handle model resolution in resolve_provider, but for direct usage:
        super().__init__(model=model, debug=debug)
        self._installed_models_cache: Optional[List[Dict[str, Any]]] = None

    def _get_model_info(self) -> List[Dict[str, Any]]:
        """Fetch full model metadata from Ollama."""
        if self._installed_models_cache is not None:
            return self._installed_models_cache
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{self.models_url}/api/tags")
                response.raise_for_status()
                data = response.json()
                self._installed_models_cache = data.get("models", [])
                return self._installed_models_cache
        except Exception as e:
            logger.warning(f"Could not fetch Ollama models: {e}")
            return []

    def _get_installed_model_names(self) -> List[str]:
        return [m["name"] for m in self._get_model_info()]

    def recommend_model(self, intent: str = "text") -> str:
        """Recommend the best installed model for a given intent.
        
        Intents:
            - 'text': Best general text model for this machine.
            - 'fast': Lowest latency model.
            - 'vision': Best model with vision capabilities.
            - 'encoding': Best model for embeddings/encoding.
        """
        from ..config import settings
        
        models = self._get_model_info()
        names = [m["name"] for m in models]
        
        if not names:
            return self.default_model

        powerful = settings.is_powerful_machine

        # 1. Vision Logic
        if intent == "vision":
            # Priority for vision
            for pref in ["llama3.2-vision", "llava", "moondream"]:
                for name in names:
                    if pref in name.lower():
                        return name
            return names[0] # Fallback to first available

        # 2. Fast / Encoding Logic
        if intent in ("fast", "encoding"):
            for pref in ["phi4-mini", "llama3.2:1b", "llama3.2:3b", "phi3"]:
                for name in names:
                    if pref in name.lower():
                        return name
            return names[0]

        # 3. Best General Text Logic
        if powerful:
            # Prefer larger/better models on powerful machines
            for pref in ["phi4", "llama3.3", "llama3.1:70b", "mistral-large"]:
                for name in names:
                    if pref in name.lower():
                        return name
        
        # Standard machine or no heavy models found
        for pref in ["phi4-mini", "llama3.1:8b", "llama3.2:3b", "mistral"]:
            for name in names:
                if pref in name.lower():
                    return name

        return names[0]

    def _build_prompt(self, system: str, user: str, template: str) -> str:
        prompt = f"<system>\n{system}\n</system>\n\n<user>\n{user}\n</user>"
        if template:
            prompt += f"\n\n<instructions>\nReturn ONLY a valid JSON object. Use this exact structure:\n{template}\n</instructions>"
        return prompt

    def _build_payload(self, prompt: str, is_json: bool, images: Optional[list[str]] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }
        if is_json:
            payload["format"] = "json"
        if images:
            payload["images"] = images
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

        prompt = self._build_prompt(system, user, template)
        payload = self._build_payload(prompt, bool(response_model), images=images)

        try:
            with httpx.Client(timeout=120.0) as client:
                response = client.post(f"{self.models_url}/api/generate", json=payload)
                if response.status_code == 404:
                    installed = self._get_installed_model_names()
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

    async def acomplete(
        self,
        system: str,
        user: str,
        response_model: Optional[Any] = None,
        images: Optional[list[str]] = None,
    ) -> Union[str, Dict[str, Any]]:
        template = self._get_example_json(response_model) if response_model else ""
        self._debug_print_request(template, system, user)

        prompt = self._build_prompt(system, user, template)
        payload = self._build_payload(prompt, bool(response_model), images=images)

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(f"{self.models_url}/api/generate", json=payload)
                if response.status_code == 404:
                    installed = self._get_installed_model_names()
                    hint = f"Installed models: {installed}" if installed else "Run 'ollama list' to see installed models."
                    raise RuntimeError(
                        f"Ollama model '{self.model}' not found. Pull it with 'ollama pull {self.model}'. "
                        f"{hint}. See {self.models_url}"
                    )
                response.raise_for_status()
                data = response.json()
                content = data.get("response", "")
        except httpx.RequestError as exc:
            raise RuntimeError(
                f"Ollama request failed: {exc}. Is Ollama running? Try: ollama serve"
            )

        result = self._parse_json_response(content, response_model) if response_model else content
        self._debug_print_response(result)
        return result
