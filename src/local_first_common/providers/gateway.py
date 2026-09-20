"""Routes LLM calls through llm-gateway-service instead of calling a
provider's own SDK directly in-process.

Reuses BaseProvider._get_example_json()/_parse_json_response() unchanged --
both are defined on the base class, not duplicated per-provider, so
response_model handling works exactly the way every other provider already
does it: the JSON-schema instruction is built and embedded into the prompt
client-side, sent as plain text, and the raw response is parsed client-side
after it comes back. The gateway itself never sees a schema; it's a dumb
text-in/text-out transport. This is why no gateway API change was needed to
support response_model.

Vision/image calls (2026-09-19): the gateway's /complete endpoint now
accepts an `images` field (base64-encoded, no data-URI prefix -- the same
convention BaseProvider's own `images` parameter already uses), forwarded
through to whichever real provider handles the request server-side.
"""
import logging
import os
from typing import Any, ClassVar

import httpx

from .base import BaseProvider

logger = logging.getLogger(__name__)


class GatewayError(RuntimeError):
    """Raised when llm-gateway-service is unreachable or returns an error."""


class GatewayProvider(BaseProvider):
    default_model = ""
    known_models: ClassVar[list[str]] = []
    models_url = ""

    def __init__(
        self,
        gateway_url: str,
        target_provider: str,
        model: str | None = None,
        debug: bool = False,
        timeout: float = 120.0,
    ):
        self.target_provider = target_provider
        self._gateway_url = gateway_url.rstrip("/")
        self._timeout = timeout
        # Deliberately NOT `model or target_provider` -- target_provider is a
        # provider alias ("local", "anthropic"), never a real model name.
        # Passing an empty model through (BaseProvider's own `model or
        # self.default_model` leaves self.model == "" since default_model
        # is "" here) lets the gateway's own server-side resolve_provider()
        # call apply that provider's actual default model, the same way it
        # would for any other caller that omits --model.
        super().__init__(model=model, debug=debug)
        self.input_tokens: int | None = None
        self.output_tokens: int | None = None

    @property
    def provider_name(self) -> str:
        return self.target_provider

    def _headers(self) -> dict[str, str]:
        headers = {}
        api_key = os.environ.get("LLM_GATEWAY_API_KEY")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    def _build_system(self, system: str, response_model: Any | None) -> str:
        if not response_model:
            return system
        template = self._get_example_json(response_model)
        return (
            f"{system}\n\nYou MUST return a valid JSON object matching this "
            f"structure:\n{template}\nDO NOT include any other text."
        )

    def _payload(
        self, system: str, user: str, response_model: Any | None, images: list[str] | None
    ) -> dict:
        payload = {
            "provider": self.target_provider,
            "model": self.model,
            "system": self._build_system(system, response_model),
            "user": user,
        }
        if images:
            payload["images"] = images
        return payload

    def _handle_response(self, response: httpx.Response, response_model: Any | None) -> str | dict[str, Any]:
        if response.status_code != 200:
            raise GatewayError(f"llm-gateway-service returned {response.status_code}: {response.text}")
        data = response.json()
        self.input_tokens = data.get("input_tokens")
        self.output_tokens = data.get("output_tokens")
        content = data["text"]
        return self._parse_json_response(content, response_model) if response_model else content

    def _complete(
        self,
        system: str,
        user: str,
        response_model: Any | None = None,
        images: list[str] | None = None,
    ) -> str | dict[str, Any]:
        template = self._get_example_json(response_model) if response_model else ""
        self._debug_print_request(template, system, user)
        payload = self._payload(system, user, response_model, images)
        try:
            response = httpx.post(
                f"{self._gateway_url}/complete", json=payload, headers=self._headers(), timeout=self._timeout
            )
        except httpx.HTTPError as e:
            raise GatewayError(f"llm-gateway-service request failed: {type(e).__name__}: {e}") from e
        result = self._handle_response(response, response_model)
        self._debug_print_response(result)
        return result

    async def _acomplete(
        self,
        system: str,
        user: str,
        response_model: Any | None = None,
        images: list[str] | None = None,
    ) -> str | dict[str, Any]:
        template = self._get_example_json(response_model) if response_model else ""
        self._debug_print_request(template, system, user)
        payload = self._payload(system, user, response_model, images)
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self._gateway_url}/complete", json=payload, headers=self._headers(), timeout=self._timeout
                )
        except httpx.HTTPError as e:
            raise GatewayError(f"llm-gateway-service request failed: {type(e).__name__}: {e}") from e
        result = self._handle_response(response, response_model)
        self._debug_print_response(result)
        return result
