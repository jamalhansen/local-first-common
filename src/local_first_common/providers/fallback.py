"""Fallback provider wrapper for automatic local-to-cloud failover."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Union

import httpx

from .base import BaseProvider
from .errors import ConnectionError

logger = logging.getLogger(__name__)


class FallbackProvider(BaseProvider):
    """Wraps a primary (local) provider with an automatic fallback (cloud) provider.

    If the primary provider experiences a connection error, connection refused,
    or timeout, the call is automatically rerouted to the fallback provider.
    """

    def __init__(
        self,
        primary: BaseProvider,
        fallback: BaseProvider,
        debug: bool = False,
    ):
        self.primary = primary
        self.fallback = fallback
        self._active = primary
        super().__init__(model=primary.model, debug=debug)

    @property
    def model(self) -> str:
        return self._active.model

    @model.setter
    def model(self, value: str) -> None:
        self.primary.model = value

    @property
    def input_tokens(self) -> Optional[int]:
        return getattr(self._active, "input_tokens", None)

    @property
    def output_tokens(self) -> Optional[int]:
        return getattr(self._active, "output_tokens", None)

    def _complete(
        self,
        system: str,
        user: str,
        response_model: Optional[Any] = None,
        images: Optional[list[str]] = None,
    ) -> Union[str, Dict[str, Any]]:
        try:
            result = self.primary._complete(
                system, user, response_model=response_model, images=images
            )
            self._active = self.primary
            return result
        except (ConnectionError, httpx.RequestError, OSError) as exc:
            logger.warning(
                "[fallback] Primary provider %s failed: %s. Failing over to %s (%s).",
                self.primary.__class__.__name__,
                exc,
                self.fallback.__class__.__name__,
                self.fallback.model,
                extra={
                    "run_context": "local_to_cloud_fallback",
                    "source_location": self.fallback.model,
                },
            )
            self._emit_status(
                f"  [fallback] Local model failed ({exc}). Failing over to {self.fallback.__class__.__name__} ({self.fallback.model})..."
            )
            result = self.fallback._complete(
                system, user, response_model=response_model, images=images
            )
            self._active = self.fallback
            return result

    async def _acomplete(
        self,
        system: str,
        user: str,
        response_model: Optional[Any] = None,
        images: Optional[list[str]] = None,
    ) -> Union[str, Dict[str, Any]]:
        try:
            result = await self.primary._acomplete(
                system, user, response_model=response_model, images=images
            )
            self._active = self.primary
            return result
        except (ConnectionError, httpx.RequestError, OSError) as exc:
            logger.warning(
                "[fallback] Primary provider %s failed in async complete: %s. Failing over to %s (%s).",
                self.primary.__class__.__name__,
                exc,
                self.fallback.__class__.__name__,
                self.fallback.model,
                extra={
                    "run_context": "local_to_cloud_fallback_async",
                    "source_location": self.fallback.model,
                },
            )
            self._emit_status(
                f"  [fallback] Local model failed ({exc}). Failing over to {self.fallback.__class__.__name__} ({self.fallback.model})..."
            )
            result = await self.fallback._acomplete(
                system, user, response_model=response_model, images=images
            )
            self._active = self.fallback
            return result
