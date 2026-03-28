import json
import pytest

from local_first_common.llm import strip_json_fences, parse_json_response, try_xml_parse


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


class TestTryXmlParse:
    def test_all_fields_returns_dict(self):
        raw = "<score>0.8</score><summary>Great article</summary>"
        result = try_xml_parse(raw, ["score", "summary"])
        assert result == {"score": "0.8", "summary": "Great article"}

    def test_missing_field_returns_none(self):
        raw = "<score>0.8</score>"
        result = try_xml_parse(raw, ["score", "summary"])
        assert result is None

    def test_xml_embedded_in_json_blob(self):
        raw = '{"ignored": true}\n<score>0.7</score><summary>Test</summary>'
        result = try_xml_parse(raw, ["score", "summary"])
        assert result == {"score": "0.7", "summary": "Test"}

    def test_empty_string_returns_none(self):
        result = try_xml_parse("", ["score"])
        assert result is None

    def test_multiline_value_stripped(self):
        raw = "<summary>\n  Line one\n  Line two\n</summary><score>0.5</score>"
        result = try_xml_parse(raw, ["summary", "score"])
        assert result is not None
        assert "Line one" in result["summary"]
        assert result["score"] == "0.5"

    def test_single_field_list(self):
        raw = "<language>en</language>"
        result = try_xml_parse(raw, ["language"])
        assert result == {"language": "en"}

    def test_empty_fields_list_returns_empty_dict(self):
        result = try_xml_parse("<score>0.5</score>", [])
        assert result == {}
