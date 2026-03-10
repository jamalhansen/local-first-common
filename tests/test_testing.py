import pytest
from pydantic import BaseModel

from local_first_common.testing import MockProvider


class SampleModel(BaseModel):
    answer: str
    confidence: int


class TestMockProvider:
    def test_returns_configured_string_response(self):
        p = MockProvider(response='{"answer": "yes", "confidence": 9}')
        result = p.complete("sys", "usr")
        assert result == '{"answer": "yes", "confidence": 9}'

    def test_returns_parsed_dict_with_response_model(self):
        p = MockProvider(response='{"answer": "yes", "confidence": 9}')
        result = p.complete("sys", "usr", response_model=SampleModel)
        assert isinstance(result, dict)
        assert result["answer"] == "yes"

    def test_records_calls(self):
        p = MockProvider(response="ok")
        p.complete("system one", "user one")
        p.complete("system two", "user two")
        assert len(p.calls) == 2
        assert p.calls[0] == ("system one", "user one")
        assert p.calls[1] == ("system two", "user two")

    def test_default_model(self):
        p = MockProvider(response="x")
        assert p.model == "mock"

    def test_custom_model(self):
        p = MockProvider(response="x", model="custom-mock")
        assert p.model == "custom-mock"

    def test_raises_on_demand(self):
        p = MockProvider(response="x", raise_error="boom")
        with pytest.raises(RuntimeError, match="boom"):
            p.complete("sys", "usr")
