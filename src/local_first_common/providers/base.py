import json
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Union, get_args, get_origin


class BaseProvider(ABC):
    default_model: str
    known_models: list
    models_url: str

    def __init__(self, model: Optional[str] = None, debug: bool = False):
        self.model = model or self.default_model
        self.debug = debug

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

    def complete(
        self,
        system: str,
        user: str,
        response_model: Optional[Any] = None,
        images: Optional[list[str]] = None,
        max_retries: int = 1,
    ) -> Union[str, Dict[str, Any]]:
        """Call the LLM with optional retry on JSON/validation failure.
        
        max_retries=1 means 2 total attempts (initial + 1 retry).
        """
        current_user = user
        
        for attempt in range(max_retries + 1):
            try:
                result = self._complete(system, current_user, response_model=response_model, images=images)
                
                if response_model and hasattr(response_model, "model_validate"):
                    response_model.model_validate(result)
                
                return result
            except Exception as e:
                if attempt < max_retries:
                    current_user = user + f"\n\nERROR FROM PREVIOUS ATTEMPT:\n{e}\n\nPlease fix the response to match the schema exactly."
                    continue
                raise

    async def acomplete(
        self,
        system: str,
        user: str,
        response_model: Optional[Any] = None,
        images: Optional[list[str]] = None,
        max_retries: int = 1,
    ) -> Union[str, Dict[str, Any]]:
        """Call the LLM with optional retry on JSON/validation failure (async).
        
        max_retries=1 means 2 total attempts (initial + 1 retry).
        """
        current_user = user
        
        for attempt in range(max_retries + 1):
            try:
                result = await self._acomplete(system, current_user, response_model=response_model, images=images)
                
                if response_model and hasattr(response_model, "model_validate"):
                    response_model.model_validate(result)
                
                return result
            except Exception as e:
                if attempt < max_retries:
                    current_user = user + f"\n\nERROR FROM PREVIOUS ATTEMPT:\n{e}\n\nPlease fix the response to match the schema exactly."
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
                result = json.loads(match.group())
                return self._clean_json(result, response_model)
            raise

    def _debug_print_request(self, template: str, system: str, user: str) -> None:
        if not self.debug:
            return
        print("\n" + "=" * 20 + " DEBUG: PROMPT " + "=" * 20)
        print(f"PROVIDER: {self.__class__.__name__}")
        print(f"MODEL: {self.model}")
        print(f"SYSTEM: {system}")
        print(f"USER: {user}")
        if template:
            print(f"TEMPLATE:\n{template}")
        print("=" * 55 + "\n")

    def _debug_print_response(self, result: Any) -> None:
        if not self.debug:
            return
        print("\n" + "=" * 20 + " DEBUG: RESPONSE " + "=" * 20)
        print(result)
        print("=" * 57 + "\n")
