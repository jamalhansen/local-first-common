"""Test utilities: MockProvider for use in project test suites."""
from typing import Any, Dict, Optional, Union

from .providers.base import BaseProvider


class MockProvider(BaseProvider):
    """A deterministic provider for use in tests. Records calls and returns preset responses."""

    default_model = "mock"
    known_models: list = ["mock"]
    models_url = "https://example.com"

    def __init__(
        self,
        response: str = "Default mock response",
        model: Optional[str] = None,
        raise_error: Optional[str] = None,
    ):
        super().__init__(model=model or self.default_model)
        self._response = response
        self._raise_error = raise_error
        self.calls: list[tuple[str, str]] = []

    def complete(
        self,
        system: str,
        user: str,
        response_model: Optional[Any] = None,
        images: Optional[list[str]] = None,
    ) -> Union[str, Dict[str, Any]]:
        self.calls.append((system, user))
        if self._raise_error:
            raise RuntimeError(self._raise_error)
        if response_model:
            return self._parse_json_response(self._response, response_model)
        return self._response

    async def acomplete(
        self,
        system: str,
        user: str,
        response_model: Optional[Any] = None,
        images: Optional[list[str]] = None,
    ) -> Union[str, Dict[str, Any]]:
        return self.complete(system, user, response_model, images=images)
