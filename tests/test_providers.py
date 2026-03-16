import json
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

from local_first_common.providers import PROVIDERS
from local_first_common.providers.base import BaseProvider
from local_first_common.providers.ollama import OllamaProvider
from local_first_common.providers.anthropic import AnthropicProvider
from local_first_common.providers.groq import GroqProvider
from local_first_common.providers.deepseek import DeepSeekProvider
from local_first_common.providers.gemini import GeminiProvider


class SampleOutput(BaseModel):
    title: str
    score: int
    tags: list[str]


SAMPLE_JSON = json.dumps({"title": "Test", "score": 8, "tags": ["a", "b"]})


class TestProvidersDict:
    def test_all_providers_registered(self):
        assert set(PROVIDERS.keys()) == {"ollama", "local", "anthropic", "gemini", "groq", "deepseek"}

    def test_local_alias_is_ollama(self):
        assert PROVIDERS["local"] is OllamaProvider

    def test_each_value_is_base_provider_subclass(self):
        for name, cls in PROVIDERS.items():
            assert issubclass(cls, BaseProvider), f"{name} is not a BaseProvider subclass"


class TestBaseProvider:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            BaseProvider()

    def test_default_model_used_when_no_model_given(self):
        class Concrete(BaseProvider):
            default_model = "my-model"
            known_models = []
            models_url = "http://example.com"
            def complete(self, system, user, response_model=None):
                return ""

        p = Concrete()
        assert p.model == "my-model"

    def test_custom_model_overrides_default(self):
        class Concrete(BaseProvider):
            default_model = "my-model"
            known_models = []
            models_url = "http://example.com"
            def complete(self, system, user, response_model=None):
                return ""

        p = Concrete(model="custom")
        assert p.model == "custom"

    def test_get_example_json_produces_valid_json(self):
        class Concrete(BaseProvider):
            default_model = "x"
            known_models = []
            models_url = "http://example.com"
            def complete(self, system, user, response_model=None):
                return ""

        p = Concrete()
        result = p._get_example_json(SampleOutput)
        parsed = json.loads(result)
        assert "title" in parsed
        assert "score" in parsed
        assert "tags" in parsed
        assert isinstance(parsed["tags"], list)

    def test_parse_json_response_clean_json(self):
        class Concrete(BaseProvider):
            default_model = "x"
            known_models = []
            models_url = "http://example.com"
            def complete(self, system, user, response_model=None):
                return ""

        p = Concrete()
        result = p._parse_json_response(SAMPLE_JSON, SampleOutput)
        assert result["title"] == "Test"

    def test_parse_json_response_extracts_from_prose(self):
        class Concrete(BaseProvider):
            default_model = "x"
            known_models = []
            models_url = "http://example.com"
            def complete(self, system, user, response_model=None):
                return ""

        p = Concrete()
        wrapped = f"Here is the output:\n{SAMPLE_JSON}\nHope that helps."
        result = p._parse_json_response(wrapped, SampleOutput)
        assert result["score"] == 8


class TestOllamaProvider:
    def test_default_model(self):
        p = OllamaProvider()
        assert p.model == "phi4-mini"

    def test_custom_model(self):
        p = OllamaProvider(model="llama3")
        assert p.model == "llama3"

    def test_complete_returns_string_without_response_model(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"response": "hello world"}

        with patch("local_first_common.providers.ollama.httpx.Client") as mock_cls:
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=ctx)
            ctx.__exit__ = MagicMock(return_value=False)
            ctx.post.return_value = mock_resp
            mock_cls.return_value = ctx

            result = OllamaProvider().complete("sys", "usr")

        assert result == "hello world"

    def test_complete_returns_dict_with_response_model(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"response": SAMPLE_JSON}

        with patch("local_first_common.providers.ollama.httpx.Client") as mock_cls:
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=ctx)
            ctx.__exit__ = MagicMock(return_value=False)
            ctx.post.return_value = mock_resp
            mock_cls.return_value = ctx

            result = OllamaProvider().complete("sys", "usr", response_model=SampleOutput)

        assert isinstance(result, dict)
        assert result["title"] == "Test"

    def test_model_not_found_raises_runtime_error(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 404

        with patch("local_first_common.providers.ollama.httpx.Client") as mock_cls:
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=ctx)
            ctx.__exit__ = MagicMock(return_value=False)
            ctx.post.return_value = mock_resp
            mock_cls.return_value = ctx

            p = OllamaProvider(model="no-such-model")
            p._get_installed_models = MagicMock(return_value=["llama3"])

            with pytest.raises(RuntimeError, match="not found"):
                p.complete("sys", "usr")


class TestAnthropicProvider:
    def test_missing_api_key_raises(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
            AnthropicProvider(api_key=None)

    def test_default_model(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        p = AnthropicProvider()
        assert p.model == AnthropicProvider.default_model

    def test_complete_returns_string(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        mock_content = MagicMock()
        mock_content.text = "hello"
        mock_message = MagicMock()
        mock_message.content = [mock_content]

        with patch("local_first_common.providers.anthropic._Anthropic") as mock_cls:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = mock_message
            mock_cls.return_value = mock_client

            result = AnthropicProvider().complete("sys", "usr")

        assert result == "hello"

    def test_complete_returns_dict_with_response_model(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        mock_content = MagicMock()
        mock_content.text = SAMPLE_JSON
        mock_message = MagicMock()
        mock_message.content = [mock_content]

        with patch("local_first_common.providers.anthropic._Anthropic") as mock_cls:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = mock_message
            mock_cls.return_value = mock_client

            result = AnthropicProvider().complete("sys", "usr", response_model=SampleOutput)

        assert result["title"] == "Test"


class TestGroqProvider:
    def test_missing_api_key_raises(self, monkeypatch):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
            GroqProvider(api_key=None)

    def test_default_model(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        p = GroqProvider()
        assert p.model == GroqProvider.default_model

    def test_complete_returns_dict_with_response_model(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"choices": [{"message": {"content": SAMPLE_JSON}}]}

        with patch("local_first_common.providers.groq.httpx.Client") as mock_cls:
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=ctx)
            ctx.__exit__ = MagicMock(return_value=False)
            ctx.post.return_value = mock_resp
            mock_cls.return_value = ctx

            result = GroqProvider().complete("sys", "usr", response_model=SampleOutput)

        assert result["score"] == 8


class TestDeepSeekProvider:
    def test_missing_api_key_raises(self, monkeypatch):
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
            DeepSeekProvider(api_key=None)

    def test_default_model(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
        p = DeepSeekProvider()
        assert p.model == "deepseek-chat"


class TestGeminiProvider:
    def test_missing_api_key_raises(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
            GeminiProvider(api_key=None)

    def test_default_model(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        p = GeminiProvider()
        assert p.model == "gemini-2.0-flash"
