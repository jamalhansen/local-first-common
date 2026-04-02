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
from local_first_common.providers.errors import ModelNotFoundError
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
            def _complete(self, system, user, response_model=None, images=None):
                return ""
            async def _acomplete(self, system, user, response_model=None, images=None):
                return ""

        p = Concrete()
        assert p.model == "my-model"

    def test_custom_model_overrides_default(self):
        class Concrete(BaseProvider):
            default_model = "my-model"
            known_models = []
            models_url = "http://example.com"
            def _complete(self, system, user, response_model=None, images=None):
                return ""
            async def _acomplete(self, system, user, response_model=None, images=None):
                return ""

        p = Concrete(model="custom")
        assert p.model == "custom"

    def test_get_example_json_produces_valid_json(self):
        class Concrete(BaseProvider):
            default_model = "x"
            known_models = []
            models_url = "http://example.com"
            def _complete(self, system, user, response_model=None, images=None):
                return ""
            async def _acomplete(self, system, user, response_model=None, images=None):
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
            def _complete(self, system, user, response_model=None, images=None):
                return ""
            async def _acomplete(self, system, user, response_model=None, images=None):
                return ""

        p = Concrete()
        result = p._parse_json_response(SAMPLE_JSON, SampleOutput)
        assert result["title"] == "Test"

    def test_parse_json_response_extracts_from_prose(self):
        class Concrete(BaseProvider):
            default_model = "x"
            known_models = []
            models_url = "http://example.com"
            def _complete(self, system, user, response_model=None, images=None):
                return ""
            async def _acomplete(self, system, user, response_model=None, images=None):
                return ""

        p = Concrete()
        wrapped = f"Here is the output:\n{SAMPLE_JSON}\nHope that helps."
        result = p._parse_json_response(wrapped, SampleOutput)
        assert result["score"] == 8


class TestBaseProviderRateLimit:
    """Rate-limit retry behaviour in BaseProvider.complete()."""

    def _make_provider(self, responses):
        """Return a concrete provider whose _complete cycles through responses."""
        call_count = {"n": 0}

        class Concrete(BaseProvider):
            default_model = "x"
            known_models = []
            models_url = "http://example.com"

            def _complete(self, system, user, response_model=None, images=None):
                resp = responses[min(call_count["n"], len(responses) - 1)]
                call_count["n"] += 1
                if isinstance(resp, Exception):
                    raise resp
                return resp

            async def _acomplete(self, system, user, response_model=None, images=None):
                return self._complete(system, user, response_model=response_model, images=images)

        return Concrete(), call_count

    def test_is_rate_limit_error_detects_429(self):
        class Concrete(BaseProvider):
            default_model = "x"
            known_models = []
            models_url = ""
            def _complete(self, *a, **kw): return ""
            async def _acomplete(self, *a, **kw): return ""

        p = Concrete()
        assert p._is_rate_limit_error(RuntimeError("429 Too Many Requests")) is True
        assert p._is_rate_limit_error(RuntimeError("500 Internal Server Error")) is False

    def test_retries_on_429_then_succeeds(self):
        rate_err = RuntimeError("429 Too Many Requests")
        provider, call_count = self._make_provider([rate_err, rate_err, "ok"])

        with patch("time.sleep"):
            result = provider.complete("sys", "usr", rate_limit_retries=3)

        assert result == "ok"
        assert call_count["n"] == 3

    def test_raises_after_exhausting_rate_limit_retries(self):
        rate_err = RuntimeError("429 Too Many Requests")
        provider, call_count = self._make_provider([rate_err, rate_err, rate_err, rate_err])

        with patch("time.sleep"):
            with pytest.raises(RuntimeError, match="429"):
                provider.complete("sys", "usr", rate_limit_retries=2)

        assert call_count["n"] == 3  # initial + 2 retries

    def test_does_not_sleep_on_non_rate_limit_error(self):
        provider, _ = self._make_provider([RuntimeError("500 Server Error")])

        with patch("time.sleep") as mock_sleep:
            with pytest.raises(RuntimeError, match="500"):
                provider.complete("sys", "usr", rate_limit_retries=3)

        mock_sleep.assert_not_called()

    def test_backoff_waits_double_each_time(self):
        rate_err = RuntimeError("429 Too Many Requests")
        provider, _ = self._make_provider([rate_err, rate_err, rate_err, "ok"])

        with patch("time.sleep") as mock_sleep:
            provider.complete("sys", "usr", rate_limit_retries=3)

        wait_times = [call.args[0] for call in mock_sleep.call_args_list]
        assert wait_times == [5, 10, 20]

    def test_rate_limit_not_retried_as_json_error(self):
        """A 429 that exhausts rate_limit_retries should not trigger max_retries injection."""
        rate_err = RuntimeError("429 Too Many Requests")
        provider, call_count = self._make_provider([rate_err] * 10)

        with patch("time.sleep"):
            with pytest.raises(RuntimeError, match="429"):
                provider.complete("sys", "usr", max_retries=2, rate_limit_retries=1)

        # rate_limit_retries=1 means 2 calls per max_retries attempt,
        # but 429 should NOT trigger the JSON-retry outer loop — just 2 calls total
        assert call_count["n"] == 2


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

            with pytest.raises(ModelNotFoundError, match="not found"):
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
