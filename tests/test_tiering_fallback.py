"""Tests for model tiering and local-to-cloud automatic fallback."""


from local_first_common.cli import resolve_provider
from local_first_common.providers.base import BaseProvider
from local_first_common.providers.errors import ConnectionError
from local_first_common.providers.fallback import FallbackProvider
from local_first_common.pydantic_ai_utils import build_model
from local_first_common.tiering import (
    detect_active_cloud_provider,
    get_tier_model,
    resolve_fallback_target,
)


class DummyPrimary(BaseProvider):
    provider_name = "dummy-ollama"
    default_model = "llama3.2:3b"

    def __init__(self, model=None, debug=False):
        super().__init__(model=model or self.default_model, debug=debug)
        self.call_count = 0

    def _complete(self, system, user, response_model=None, images=None):
        self.call_count += 1
        raise ConnectionError("Ollama offline")

    async def _acomplete(self, system, user, response_model=None, images=None):
        self.call_count += 1
        raise ConnectionError("Ollama offline")


class DummyWorkingPrimary(BaseProvider):
    provider_name = "dummy-ollama"
    default_model = "llama3.2:3b"

    def __init__(self, model=None, debug=False):
        super().__init__(model=model or self.default_model, debug=debug)

    def _complete(self, system, user, response_model=None, images=None):
        return "primary ok"

    async def _acomplete(self, system, user, response_model=None, images=None):
        return "primary ok async"


class DummyFallback(BaseProvider):
    provider_name = "dummy-anthropic"
    default_model = "claude-sonnet-5"

    def __init__(self, model=None, debug=False):
        super().__init__(model=model or self.default_model, debug=debug)
        self.call_count = 0
        self.input_tokens = 12
        self.output_tokens = 24

    def _complete(self, system, user, response_model=None, images=None):
        self.call_count += 1
        return "fallback ok"

    async def _acomplete(self, system, user, response_model=None, images=None):
        self.call_count += 1
        return "fallback ok async"


def test_get_tier_model():
    assert get_tier_model("fast", "ollama") == "llama3.2:3b"
    assert get_tier_model("classification", "anthropic") == "claude-haiku-4-5-20251001"
    assert get_tier_model("reasoning", "anthropic") == "claude-sonnet-5"
    assert get_tier_model("frontier", "gemini") == "gemini-2.5-pro"
    assert get_tier_model("unknown_tier", "anthropic") == "claude-haiku-4-5-20251001"


def test_detect_active_cloud_provider(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    assert detect_active_cloud_provider() is None

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    assert detect_active_cloud_provider() == ("anthropic", "claude-sonnet-5")

    monkeypatch.delenv("ANTHROPIC_API_KEY")
    monkeypatch.setenv("GEMINI_API_KEY", "gm-test")
    assert detect_active_cloud_provider() == ("gemini", "gemini-2.5-pro")


def test_resolve_fallback_target_explicit():
    target = resolve_fallback_target("groq", "custom-model")
    assert target == ("groq", "custom-model")


def test_fallback_provider_success():
    primary = DummyWorkingPrimary()
    fallback = DummyFallback()
    provider = FallbackProvider(primary, fallback)

    res = provider.complete("sys", "user")
    assert res == "primary ok"
    assert fallback.call_count == 0
    assert provider.model == "llama3.2:3b"


def test_fallback_provider_failover():
    primary = DummyPrimary()
    fallback = DummyFallback()
    provider = FallbackProvider(primary, fallback)

    res = provider.complete("sys", "user")
    assert res == "fallback ok"
    assert primary.call_count == 1
    assert fallback.call_count == 1
    assert provider.model == "claude-sonnet-5"
    assert provider.input_tokens == 12
    assert provider.output_tokens == 24


def test_fallback_provider_async_failover():
    import asyncio

    primary = DummyPrimary()
    fallback = DummyFallback()
    provider = FallbackProvider(primary, fallback)

    res = asyncio.run(provider.acomplete("sys", "user"))
    assert res == "fallback ok async"
    assert fallback.call_count == 1


class DummyBadJson(BaseProvider):
    """A model that responds, but with something that doesn't parse as the
    requested schema -- the real 2026-09-20 phi4-mini failure mode, distinct
    from a connectivity failure."""

    default_model = "phi4-mini"

    def __init__(self, model=None, debug=False):
        super().__init__(model=model or self.default_model, debug=debug)
        self.call_count = 0

    def _complete(self, system, user, response_model=None, images=None):
        self.call_count += 1
        import json

        json.loads("not valid json")

    async def _acomplete(self, system, user, response_model=None, images=None):
        self.call_count += 1
        import json

        json.loads("not valid json")


def test_fallback_provider_fails_over_on_bad_json():
    primary = DummyBadJson()
    fallback = DummyFallback()
    provider = FallbackProvider(primary, fallback)

    res = provider.complete("sys", "user")
    assert res == "fallback ok"
    assert primary.call_count == 1
    assert fallback.call_count == 1


def test_fallback_provider_warns_on_primary_failure_via_plain_logging(caplog):
    """Jamal: an LLM call logged once inside the gateway -- if logs are
    needed outside the gateway, use logging like a normal developer. A
    primary-provider failure that triggers fallback never reaches the
    gateway at all (it failed before/instead of a real completion), so it
    used to get its own separate processing_log write here; now it's a
    plain logger.warning(), same as any other in-process diagnostic."""
    import logging

    primary = DummyPrimary()
    fallback = DummyFallback()
    provider = FallbackProvider(primary, fallback, tool_name="my-tool")

    with caplog.at_level(logging.WARNING):
        provider.complete("sys", "user")

    assert any("Primary provider" in r.message for r in caplog.records)


def test_fallback_provider_name_delegates_to_whichever_leg_actually_ran():
    primary = DummyPrimary()
    fallback = DummyFallback()
    provider = FallbackProvider(primary, fallback)
    assert provider.provider_name == "dummy-ollama"  # nothing has run yet -- starts on primary

    provider.complete("sys", "user")  # primary always fails in this fixture -> fails over
    assert provider.provider_name == "dummy-anthropic"


def test_fallback_provider_proxies_source_location_and_item_count_to_both_legs():
    """Set on both primary and fallback -- there's no way to know in advance
    which one will actually run, and the gateway's single database write
    needs whichever one does to have the real values."""
    primary = DummyPrimary()
    fallback = DummyFallback()
    provider = FallbackProvider(primary, fallback)

    provider.source_location = "example:あ"
    provider.item_count = 5

    assert primary.source_location == "example:あ"
    assert fallback.source_location == "example:あ"
    assert primary.item_count == 5
    assert fallback.item_count == 5


def test_resolve_provider_wires_fallback(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    mock_providers = {
        "ollama": DummyPrimary,
        "anthropic": DummyFallback,
    }

    # Should wrap in FallbackProvider
    p = resolve_provider(mock_providers, "ollama", fallback=True)
    assert isinstance(p, FallbackProvider)
    assert p.primary.model == "llama3.2:3b"

    # Should failover seamlessly when called
    res = p.complete("sys", "user")
    assert res == "fallback ok"


def test_pydantic_ai_tier_build(monkeypatch):
    import sys
    from unittest.mock import MagicMock

    mock_mod = MagicMock()
    mock_mod.models.anthropic.AnthropicModel.side_effect = lambda m: MagicMock(model_name=m)
    monkeypatch.setitem(sys.modules, "pydantic_ai", mock_mod)
    monkeypatch.setitem(sys.modules, "pydantic_ai.models.anthropic", mock_mod.models.anthropic)

    model = build_model("anthropic", tier="reasoning")
    assert hasattr(model, "model_name")
    assert "claude-sonnet-5" in getattr(model, "model_name", "")

