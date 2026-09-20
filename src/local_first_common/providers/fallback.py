"""Fallback provider wrapper for automatic local-to-cloud failover."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from .base import BaseProvider
from .errors import ConnectionError

logger = logging.getLogger(__name__)

# What triggers failover: connectivity failures (the original scope) plus a
# response that doesn't parse as the requested schema. The latter matters
# specifically for small local models -- confirmed live 2026-09-20:
# phi4-mini occasionally returns malformed JSON for a structured request,
# which used to propagate as a raw 500 with no path to recovery.
_FAILOVER_EXCEPTIONS = (ConnectionError, httpx.RequestError, OSError, json.JSONDecodeError)


class FallbackProvider(BaseProvider):
    """Wraps a primary (local) provider with an automatic fallback (cloud) provider.

    Fails over to the fallback provider on a connection error, connection
    refused, timeout, or a response that fails to parse against the
    requested schema.
    """

    # Empty, not a real model name -- matches GatewayProvider's own precedent.
    # A primary with no explicit model (the normal case: let the server apply
    # its real default) has primary.model == "", and BaseProvider.__init__'s
    # `model or self.default_model` would otherwise crash here with no
    # default_model attribute at all. Found live 2026-09-20 wrapping a
    # GatewayProvider primary.
    default_model = ""

    def __init__(
        self,
        primary: BaseProvider,
        fallback: BaseProvider,
        debug: bool = False,
        tool_name: str | None = None,
    ):
        self.primary = primary
        self.fallback = fallback
        self.tool_name = tool_name
        self._active = primary
        super().__init__(model=primary.model, debug=debug)

    def _log_primary_failure(self, exc: Exception) -> None:
        """Record the failed primary attempt to processing_log -- not just a
        log line -- so a fallback that silently "worked" is still visible in
        the same place tool activity/model-choice reporting reads from."""
        try:
            from ..tracking import log_run

            log_run(
                self.tool_name or f"{self.primary.__class__.__name__}(unattributed)",
                self.primary.model,
                success=False,
                error_message=f"fallback triggered: {exc}"[:500],
            )
        except Exception:
            logger.debug("Failed to log primary-provider failure for diagnostics", exc_info=True)

    @property
    def model(self) -> str:
        return self._active.model

    @model.setter
    def model(self, value: str) -> None:
        self.primary.model = value

    @property
    def input_tokens(self) -> int | None:
        return getattr(self._active, "input_tokens", None)

    @property
    def output_tokens(self) -> int | None:
        return getattr(self._active, "output_tokens", None)

    def _complete(
        self,
        system: str,
        user: str,
        response_model: Any | None = None,
        images: list[str] | None = None,
    ) -> str | dict[str, Any]:
        try:
            result = self.primary._complete(
                system, user, response_model=response_model, images=images
            )
            self._active = self.primary
            return result
        except _FAILOVER_EXCEPTIONS as exc:
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
            self._log_primary_failure(exc)
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
        response_model: Any | None = None,
        images: list[str] | None = None,
    ) -> str | dict[str, Any]:
        try:
            result = await self.primary._acomplete(
                system, user, response_model=response_model, images=images
            )
            self._active = self.primary
            return result
        except _FAILOVER_EXCEPTIONS as exc:
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
            self._log_primary_failure(exc)
            self._emit_status(
                f"  [fallback] Local model failed ({exc}). Failing over to {self.fallback.__class__.__name__} ({self.fallback.model})..."
            )
            result = await self.fallback._acomplete(
                system, user, response_model=response_model, images=images
            )
            self._active = self.fallback
            return result
