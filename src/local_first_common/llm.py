"""LLM response parsing utilities.

For use by callers that invoke llm.complete() without response_model= and
need to parse the raw string themselves.  This is distinct from
BaseProvider._parse_json_response, which is coupled to response_model and
_clean_json and operates inside the provider layer.
"""

import json
from typing import Any


def strip_json_fences(raw: str) -> str:
    """Strip markdown code fences from an LLM response.

    Handles ```json ... ``` and ``` ... ``` wrappers.
    Returns the inner text unchanged if no fences are present.
    """
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        inner = []
        for line in lines[1:]:
            if line.strip() == "```":
                break
            inner.append(line)
        return "\n".join(inner).strip()
    return text


def parse_json_response(raw: str) -> dict[str, Any]:
    """Strip markdown fences and parse JSON from an LLM response.

    Raises json.JSONDecodeError if the content is not valid JSON
    after fence stripping.
    """
    return json.loads(strip_json_fences(raw))
