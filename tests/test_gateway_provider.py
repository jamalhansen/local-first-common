"""Tests for GatewayProvider, and for resolve_provider()'s delegation to it."""
import json
from unittest.mock import patch

import pytest
from pydantic import BaseModel

from local_first_common.cli import resolve_provider
from local_first_common.providers.gateway import GatewayError, GatewayProvider


class Answer(BaseModel):
    score: float
    label: str


class _FakeResponse:
    def __init__(self, status_code: int, json_body: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._json_body = json_body or {}
        self.text = text or json.dumps(self._json_body)

    def json(self):
        return self._json_body


class TestGatewayProviderProviderName:
    def test_provider_name_reflects_target_provider(self):
        provider = GatewayProvider("http://127.0.0.1:8788", "anthropic")
        assert provider.provider_name == "anthropic"


class TestGatewayProviderComplete:
    def test_returns_plain_text_when_no_response_model(self):
        response = _FakeResponse(200, {"text": "a real answer", "input_tokens": 10, "output_tokens": 3})
        with patch("httpx.post", return_value=response) as mock_post:
            provider = GatewayProvider("http://127.0.0.1:8788", "anthropic", "claude-haiku")
            result = provider.complete("system prompt", "user prompt")
        assert result == "a real answer"
        assert provider.input_tokens == 10
        assert provider.output_tokens == 3
        sent = mock_post.call_args.kwargs["json"]
        assert sent["provider"] == "anthropic"
        assert sent["system"] == "system prompt"
        assert sent["user"] == "user prompt"

    def test_no_model_given_does_not_send_the_provider_alias_as_the_model(self):
        """Regression test: model must never fall back to target_provider --
        "local"/"anthropic" are provider aliases, not real model names. Found
        live: discover save with no --model sent {"model": "local"} to the
        gateway, which then failed trying to pull an Ollama model called
        "local". The server's own resolve_provider() must see an empty
        model so it applies that provider's real default.
        """
        response = _FakeResponse(200, {"text": "ok"})
        with patch("httpx.post", return_value=response) as mock_post:
            provider = GatewayProvider("http://127.0.0.1:8788", "local")
            provider.complete("s", "u")
        assert provider.model != "local"
        sent = mock_post.call_args.kwargs["json"]
        assert sent["model"] != "local"

    def test_response_model_embeds_json_template_and_parses_result(self):
        response = _FakeResponse(200, {"text": json.dumps({"score": 0.8, "label": "good"})})
        with patch("httpx.post", return_value=response) as mock_post:
            provider = GatewayProvider("http://127.0.0.1:8788", "anthropic")
            result = provider.complete("system prompt", "user prompt", response_model=Answer)
        assert result == Answer(score=0.8, label="good")
        sent = mock_post.call_args.kwargs["json"]
        assert "JSON object matching this structure" in sent["system"]
        assert '"score"' in sent["system"]

    def test_gateway_never_receives_a_schema_in_the_payload(self):
        """The gateway is a dumb text transport -- schema-awareness stays entirely client-side."""
        response = _FakeResponse(200, {"text": json.dumps({"score": 1.0, "label": "x"})})
        with patch("httpx.post", return_value=response) as mock_post:
            GatewayProvider("http://127.0.0.1:8788", "anthropic").complete(
                "s", "u", response_model=Answer
            )
        sent = mock_post.call_args.kwargs["json"]
        assert set(sent.keys()) == {"provider", "model", "system", "user"}

    def test_sends_bearer_token_when_api_key_set(self, monkeypatch):
        monkeypatch.setenv("LLM_GATEWAY_API_KEY", "the-secret")
        response = _FakeResponse(200, {"text": "ok"})
        with patch("httpx.post", return_value=response) as mock_post:
            GatewayProvider("http://127.0.0.1:8788", "anthropic").complete("s", "u")
        assert mock_post.call_args.kwargs["headers"]["Authorization"] == "Bearer the-secret"

    def test_no_auth_header_when_api_key_unset(self, monkeypatch):
        monkeypatch.delenv("LLM_GATEWAY_API_KEY", raising=False)
        response = _FakeResponse(200, {"text": "ok"})
        with patch("httpx.post", return_value=response) as mock_post:
            GatewayProvider("http://127.0.0.1:8788", "anthropic").complete("s", "u")
        assert "Authorization" not in mock_post.call_args.kwargs["headers"]

    def test_non_200_raises_gateway_error(self):
        response = _FakeResponse(502, text="upstream failed")
        with patch("httpx.post", return_value=response), pytest.raises(GatewayError, match="502"):
            GatewayProvider("http://127.0.0.1:8788", "anthropic").complete("s", "u")

    def test_request_failure_raises_gateway_error(self):
        import httpx

        with (
            patch("httpx.post", side_effect=httpx.ConnectError("connection refused")),
            pytest.raises(GatewayError, match="request failed"),
        ):
            GatewayProvider("http://127.0.0.1:8788", "anthropic").complete("s", "u")

    def test_images_are_forwarded_in_the_payload(self):
        response = _FakeResponse(200, {"text": "I see a cat"})
        with patch("httpx.post", return_value=response) as mock_post:
            result = GatewayProvider("http://127.0.0.1:8788", "anthropic").complete(
                "s", "u", images=["base64imagedata"]
            )
        assert result == "I see a cat"
        assert mock_post.call_args.kwargs["json"]["images"] == ["base64imagedata"]

    def test_no_images_key_in_payload_when_none_given(self):
        response = _FakeResponse(200, {"text": "ok"})
        with patch("httpx.post", return_value=response) as mock_post:
            GatewayProvider("http://127.0.0.1:8788", "anthropic").complete("s", "u")
        assert "images" not in mock_post.call_args.kwargs["json"]


class TestGatewayProviderAcomplete:
    @pytest.mark.asyncio
    async def test_async_returns_plain_text(self):
        response = _FakeResponse(200, {"text": "async answer"})

        class FakeAsyncClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def post(self, *args, **kwargs):
                return response

        with patch("httpx.AsyncClient", return_value=FakeAsyncClient()):
            provider = GatewayProvider("http://127.0.0.1:8788", "anthropic")
            result = await provider.acomplete("s", "u")
        assert result == "async answer"

    @pytest.mark.asyncio
    async def test_async_images_are_forwarded_in_the_payload(self):
        response = _FakeResponse(200, {"text": "I see a cat"})
        captured = {}

        class FakeAsyncClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def post(self, *args, **kwargs):
                captured.update(kwargs)
                return response

        with patch("httpx.AsyncClient", return_value=FakeAsyncClient()):
            result = await GatewayProvider("http://127.0.0.1:8788", "anthropic").acomplete(
                "s", "u", images=["base64imagedata"]
            )
        assert result == "I see a cat"
        assert captured["json"]["images"] == ["base64imagedata"]


class TestResolveProviderGatewayDelegation:
    def test_no_gateway_url_uses_real_provider(self, monkeypatch):
        monkeypatch.delenv("LLM_GATEWAY_URL", raising=False)
        provider = resolve_provider(provider_name="mock")
        assert not isinstance(provider, GatewayProvider)

    def test_use_gateway_false_bypasses_gateway_routing_even_with_url_set(self, monkeypatch):
        """Regression for the 2026-09-20 incident: llm-gateway-service's own
        internal resolve_provider() call inherits LLM_GATEWAY_URL from the
        same shell env as every other tool. Without use_gateway=False, that
        call would build a GatewayProvider pointed at the gateway itself --
        every request it served would recurse into another HTTP call to
        itself, unbounded, until the process ran out of file descriptors."""
        from local_first_common.testing import MockProvider

        with patch("local_first_common.cli.LLM_GATEWAY_URL", "http://127.0.0.1:8788"):
            provider = resolve_provider(
                {"ollama": MockProvider}, provider_name="ollama", use_gateway=False, fallback=False
            )
        assert not isinstance(provider, GatewayProvider)
        assert isinstance(provider, MockProvider)

    def test_gateway_url_set_returns_gateway_provider(self, monkeypatch):
        with patch("local_first_common.cli.LLM_GATEWAY_URL", "http://127.0.0.1:8788"):
            provider = resolve_provider(provider_name="anthropic", model="claude-haiku")
        assert isinstance(provider, GatewayProvider)
        assert provider.target_provider == "anthropic"
        assert provider.model == "claude-haiku"

    def test_gateway_url_set_still_validates_unknown_provider(self, monkeypatch):
        import typer

        with (
            patch("local_first_common.cli.LLM_GATEWAY_URL", "http://127.0.0.1:8788"),
            pytest.raises(typer.BadParameter),
        ):
            resolve_provider(provider_name="not-a-real-provider")

    def test_no_llm_still_returns_mock_even_with_gateway_url_set(self):
        from local_first_common.testing import MockProvider

        with patch("local_first_common.cli.LLM_GATEWAY_URL", "http://127.0.0.1:8788"):
            provider = resolve_provider(no_llm=True)
        assert isinstance(provider, MockProvider)

    def test_gateway_url_set_with_fallback_wraps_two_gateway_providers(self):
        """Found live 2026-09-20: routing through the gateway used to skip
        client-side fallback-wrapping entirely (the gateway's own server-side
        fallback only catches connectivity, not a malformed-JSON response,
        since the gateway never parses the schema) -- every gateway-routed
        tool had zero protection against that failure mode. Both legs should
        still go through the gateway (same auth/logging), just as two
        different target_provider values."""
        from local_first_common.providers.fallback import FallbackProvider

        with patch("local_first_common.cli.LLM_GATEWAY_URL", "http://127.0.0.1:8788"):
            provider = resolve_provider(
                provider_name="ollama", fallback=True, fallback_provider="deepseek", tool_name="my-tool"
            )
        assert isinstance(provider, FallbackProvider)
        assert isinstance(provider.primary, GatewayProvider)
        assert provider.primary.target_provider == "ollama"
        assert isinstance(provider.fallback, GatewayProvider)
        assert provider.fallback.target_provider == "deepseek"
        assert provider.tool_name == "my-tool"

    def test_gateway_url_set_non_ollama_provider_skips_fallback_wrapping(self):
        """Fallback is an ollama/local-only concept (there's nothing to fail
        over *from* for a cloud provider) -- confirms that path is untouched."""
        from local_first_common.providers.fallback import FallbackProvider

        with patch("local_first_common.cli.LLM_GATEWAY_URL", "http://127.0.0.1:8788"):
            provider = resolve_provider(provider_name="anthropic", fallback=True, fallback_provider="deepseek")
        assert isinstance(provider, GatewayProvider)
        assert not isinstance(provider, FallbackProvider)
