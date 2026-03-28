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


def try_xml_parse(raw: str, fields: list[str]) -> dict[str, str] | None:
    """Extract field values from XML-style tags in an LLM response.

    Tries re.search for each tag in ``fields``.  Returns a dict mapping
    field name → extracted text if ALL fields are found, or None if any
    field is missing.  Values are stripped of leading/trailing whitespace.

    Useful as a fallback when JSON parsing fails for local models that
    struggle with strict JSON syntax under token-pressure.

    Example::

        raw = "<score>0.8</score><summary>Great post</summary>"
        result = try_xml_parse(raw, ["score", "summary"])
        # {"score": "0.8", "summary": "Great post"}
    """
    import re
    result: dict[str, str] = {}
    for field in fields:
        match = re.search(rf"<{field}>(.*?)</{field}>", raw, re.DOTALL)
        if not match:
            return None
        result[field] = match.group(1).strip()
    return result
