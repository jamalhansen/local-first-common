import json
import pytest

from local_first_common.llm import strip_json_fences, parse_json_response


SAMPLE = {"title": "Test", "score": 8, "tags": ["a", "b"]}
SAMPLE_JSON = json.dumps(SAMPLE)


class TestStripJsonFences:
    def test_no_fences_unchanged(self):
        assert strip_json_fences(SAMPLE_JSON) == SAMPLE_JSON

    def test_json_fence(self):
        raw = f"```json\n{SAMPLE_JSON}\n```"
        assert strip_json_fences(raw) == SAMPLE_JSON

    def test_bare_fence(self):
        raw = f"```\n{SAMPLE_JSON}\n```"
        assert strip_json_fences(raw) == SAMPLE_JSON

    def test_preserves_inner_backticks(self):
        payload = '{"code": "x = `foo`"}'
        raw = f"```json\n{payload}\n```"
        assert strip_json_fences(raw) == payload

    def test_strips_surrounding_whitespace(self):
        raw = f"  ```json\n{SAMPLE_JSON}\n```  "
        assert strip_json_fences(raw) == SAMPLE_JSON


class TestParseJsonResponse:
    def test_plain_json(self):
        result = parse_json_response(SAMPLE_JSON)
        assert result == SAMPLE

    def test_json_fence(self):
        raw = f"```json\n{SAMPLE_JSON}\n```"
        assert parse_json_response(raw) == SAMPLE

    def test_bare_fence(self):
        raw = f"```\n{SAMPLE_JSON}\n```"
        assert parse_json_response(raw) == SAMPLE

    def test_invalid_raises(self):
        with pytest.raises(json.JSONDecodeError):
            parse_json_response("not json")

    def test_trailing_text_after_fence(self):
        # Some models add text after the closing fence — inner content is still valid
        raw = f"```json\n{SAMPLE_JSON}\n```\nHere is your JSON."
        # strip_json_fences stops at the first closing ```, so inner JSON is clean
        assert parse_json_response(raw) == SAMPLE
