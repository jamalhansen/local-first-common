"""Test utilities: MockProvider and shared pytest fixtures for use in project test suites."""
import os
from typing import Any, Dict, Optional, Union

import pytest

from .providers.base import BaseProvider


@pytest.fixture(autouse=True, scope="session")
def isolate_tracking_db(tmp_path_factory):
    """Redirect the tracking DB to a temp path so tests never write to the real DB.

    Import this fixture in a repo's tests/conftest.py to activate it::

        from local_first_common.testing import isolate_tracking_db  # noqa: F401
    """
    db = tmp_path_factory.mktemp("tracking") / "test_tracking.duckdb"
    os.environ["LOCAL_FIRST_TRACKING_DB"] = str(db)
    yield
    os.environ.pop("LOCAL_FIRST_TRACKING_DB", None)


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
