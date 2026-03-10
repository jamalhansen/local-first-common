import os
from typing import Any, Dict, List, Optional, Union

from .base import BaseProvider


class GeminiProvider(BaseProvider):
    default_model = "gemini-2.0-flash"
    known_models: List[str] = [
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-1.5-pro",
        "gemini-1.5-flash",
    ]
    models_url = "https://ai.google.dev/gemini-api/docs/models"

    def __init__(self, model: Optional[str] = None, debug: bool = False, api_key: Optional[str] = None):
        super().__init__(model=model, debug=debug)
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is required. Set it as an environment variable."
            )

    def complete(
        self,
        system: str,
        user: str,
        response_model: Optional[Any] = None,
    ) -> Union[str, Dict[str, Any]]:
        try:
            from google import genai
            from google.genai import types
        except ImportError:
            raise RuntimeError(
                "google-genai package is required for GeminiProvider. Install it with: uv add google-genai"
            )

        template = self._get_example_json(response_model) if response_model else ""
        self._debug_print_request(template, system, user)

        try:
            client = genai.Client(api_key=self.api_key)
            config = types.GenerateContentConfig(system_instruction=system)

            prompt = user
            if response_model:
                prompt += f"\n\nReturn a valid JSON object matching this structure:\n{template}"
                config.response_mime_type = "application/json"

            response = client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config,
            )
            content = response.text
        except Exception as e:
            err = str(e)
            if "not found" in err.lower() or "invalid" in err.lower():
                raise RuntimeError(
                    f"Gemini model '{self.model}' not found. "
                    f"Known models: {self.known_models}. See {self.models_url}"
                )
            raise RuntimeError(f"Gemini API error: {e}")

        result = self._parse_json_response(content, response_model) if response_model else content
        self._debug_print_response(result)
        return result
