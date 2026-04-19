import asyncio
import json
import logging
import re
import time
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Optional, Union, get_args, get_origin

logger = logging.getLogger(__name__)


class BaseProvider(ABC):
    default_model: str
    known_models: list
    models_url: str

    def __init__(
        self,
        model: Optional[str] = None,
        debug: bool = False,
        report_callback: Optional[Callable[[str], None]] = None,
        interactive_output: bool = True,
    ):
        self.model = model or self.default_model
        self.debug = debug
        self.report_callback = report_callback
        self.interactive_output = interactive_output

    def _emit_status(self, message: str) -> None:
        """Emit status text via callback or stdout when enabled.

        This preserves existing interactive behavior by default while allowing
        non-interactive callers to disable terminal writes.
        """
        if self.report_callback:
            self.report_callback(message)
            return
        if self.interactive_output:
            print(message, flush=True)

    @abstractmethod
    def _complete(
        self,
        system: str,
        user: str,
        response_model: Optional[Any] = None,
        images: Optional[list[str]] = None,
    ) -> Union[str, Dict[str, Any]]: ...

    @abstractmethod
    async def _acomplete(
        self,
        system: str,
        user: str,
        response_model: Optional[Any] = None,
        images: Optional[list[str]] = None,
    ) -> Union[str, Dict[str, Any]]: ...

    @staticmethod
    def _is_rate_limit_error(e: Exception) -> bool:
        """Return True if the exception indicates a 429 Too Many Requests response."""
        return "429" in str(e)

    def _complete_with_backoff(
        self,
        system: str,
        user: str,
        response_model: Optional[Any],
        images: Optional[list[str]],
        rate_limit_retries: int,
    ) -> Union[str, Dict[str, Any]]:
        """Call _complete with exponential backoff on 429 rate-limit errors.

        Waits 5s, 10s, 20s, ... between retries (doubles each time).
        """
        for attempt in range(rate_limit_retries + 1):
            try:
                return self._complete(
                    system, user, response_model=response_model, images=images
                )
            except Exception as e:
                if self._is_rate_limit_error(e) and attempt < rate_limit_retries:
                    wait = 5 * (2**attempt)
                    logger.warning(
                        "Rate limited (429). Waiting %ds before retry %d/%d.",
                        wait,
                        attempt + 1,
                        rate_limit_retries,
                        extra={
                            "run_context": "provider_rate_limit_retry",
                            "source_location": self.model,
                        },
                    )
                    self._emit_status(
                        f"  Rate limited — waiting {wait}s before retry {attempt + 1}/{rate_limit_retries}...",
                    )
                    time.sleep(wait)
                    continue
                raise

    async def _acomplete_with_backoff(
        self,
        system: str,
        user: str,
        response_model: Optional[Any],
        images: Optional[list[str]],
        rate_limit_retries: int,
    ) -> Union[str, Dict[str, Any]]:
        """Async version of _complete_with_backoff."""
        for attempt in range(rate_limit_retries + 1):
            try:
                return await self._acomplete(
                    system, user, response_model=response_model, images=images
                )
            except Exception as e:
                if self._is_rate_limit_error(e) and attempt < rate_limit_retries:
                    wait = 5 * (2**attempt)
                    logger.warning(
                        "Rate limited (429). Waiting %ds before retry %d/%d.",
                        wait,
                        attempt + 1,
                        rate_limit_retries,
                        extra={
                            "run_context": "provider_rate_limit_retry_async",
                            "source_location": self.model,
                        },
                    )
                    self._emit_status(
                        f"  Rate limited — waiting {wait}s before retry {attempt + 1}/{rate_limit_retries}...",
                    )
                    await asyncio.sleep(wait)
                    continue
                raise

    def complete(
        self,
        system: str,
        user: str,
        response_model: Optional[Any] = None,
        images: Optional[list[str]] = None,
        max_retries: int = 1,
        rate_limit_retries: int = 3,
    ) -> Union[str, Dict[str, Any]]:
        """Call the LLM with retry on JSON/validation failure and 429 rate limits.

        max_retries controls retries on bad responses (error injected into prompt).
        rate_limit_retries controls retries on 429s with exponential backoff (5s, 10s, 20s).
        """
        current_user = user

        for attempt in range(max_retries + 1):
            try:
                result = self._complete_with_backoff(
                    system, current_user, response_model, images, rate_limit_retries
                )

                if response_model and hasattr(response_model, "model_validate"):
                    response_model.model_validate(result)

                return result
            except Exception as e:
                if attempt < max_retries and not self._is_rate_limit_error(e):
                    logger.warning(
                        "Provider response failed validation/parse on attempt %d/%d; retrying.",
                        attempt + 1,
                        max_retries + 1,
                        extra={
                            "run_context": "provider_schema_retry",
                            "source_location": self.model,
                        },
                    )
                    current_user = (
                        user
                        + f"\n\nERROR FROM PREVIOUS ATTEMPT:\n{e}\n\nPlease fix the response to match the schema exactly."
                    )
                    continue
                raise

    async def acomplete(
        self,
        system: str,
        user: str,
        response_model: Optional[Any] = None,
        images: Optional[list[str]] = None,
        max_retries: int = 1,
        rate_limit_retries: int = 3,
    ) -> Union[str, Dict[str, Any]]:
        """Async version of complete(). Same retry behaviour."""
        current_user = user

        for attempt in range(max_retries + 1):
            try:
                result = await self._acomplete_with_backoff(
                    system, current_user, response_model, images, rate_limit_retries
                )

                if response_model and hasattr(response_model, "model_validate"):
                    response_model.model_validate(result)

                return result
            except Exception as e:
                if attempt < max_retries and not self._is_rate_limit_error(e):
                    logger.warning(
                        "Provider response failed validation/parse on attempt %d/%d; retrying.",
                        attempt + 1,
                        max_retries + 1,
                        extra={
                            "run_context": "provider_schema_retry_async",
                            "source_location": self.model,
                        },
                    )
                    current_user = (
                        user
                        + f"\n\nERROR FROM PREVIOUS ATTEMPT:\n{e}\n\nPlease fix the response to match the schema exactly."
                    )
                    continue
                raise

    def _get_example_json(self, model: Any) -> str:
        if not model or not hasattr(model, "model_fields"):
            return "{}"
        example = {}
        for name, field in model.model_fields.items():
            annotation = field.annotation
            origin = get_origin(annotation)
            args = get_args(annotation)
            if origin is Union:
                annotation = args[0]
                origin = get_origin(annotation)
                args = get_args(annotation)
            if origin is list:
                item_type = args[0]
                if hasattr(item_type, "model_fields"):
                    example[name] = [json.loads(self._get_example_json(item_type))]
                else:
                    example[name] = ["example item"]
            elif hasattr(annotation, "model_fields"):
                example[name] = json.loads(self._get_example_json(annotation))
            elif annotation is int:
                example[name] = 0
            elif annotation is bool:
                example[name] = True
            else:
                example[name] = "string"
        return json.dumps(example, indent=2)

    def _clean_json(self, data: Any, model: Any) -> Any:
        if not isinstance(data, dict):
            return data
        for field_name, field_info in model.model_fields.items():
            is_list = get_origin(field_info.annotation) is list
            if is_list and field_name in data and isinstance(data[field_name], dict):
                data[field_name] = [data[field_name]]
        return data

    def _parse_json_response(self, content: str, response_model: Any) -> Dict[str, Any]:
        try:
            result = json.loads(content)
            return self._clean_json(result, response_model)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                try:
                    result = json.loads(match.group())
                    return self._clean_json(result, response_model)
                except json.JSONDecodeError as e:
                    logger.warning(
                        "JSON parse failed even after extracting object from provider response.",
                        extra={
                            "run_context": "provider_json_parse_fallback_failed",
                            "source_location": self.model,
                        },
                    )
                    raise e
            logger.warning(
                "JSON parse failed and no object payload could be extracted from provider response.",
                extra={
                    "run_context": "provider_json_parse_failed",
                    "source_location": self.model,
                },
            )
            raise

    def _debug_print_request(self, template: str, system: str, user: str) -> None:
        if not self.debug:
            return
        logger.debug("Provider prompt debug emitted for %s", self.__class__.__name__)
        self._emit_status("\n" + "=" * 20 + " DEBUG: PROMPT " + "=" * 20)
        self._emit_status(f"PROVIDER: {self.__class__.__name__}")
        self._emit_status(f"MODEL: {self.model}")
        self._emit_status(f"SYSTEM: {system}")
        self._emit_status(f"USER: {user}")
        if template:
            self._emit_status(f"TEMPLATE:\n{template}")
        self._emit_status("=" * 55 + "\n")

    def _debug_print_response(self, result: Any) -> None:
        if not self.debug:
            return
        logger.debug("Provider response debug emitted for %s", self.__class__.__name__)
        self._emit_status("\n" + "=" * 20 + " DEBUG: RESPONSE " + "=" * 20)
        self._emit_status(str(result))
        self._emit_status("=" * 57 + "\n")
