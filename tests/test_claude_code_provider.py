import asyncio
import json
import subprocess
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from local_first_common.providers.claude_code import ClaudeCodeError, ClaudeCodeProvider


class Score(BaseModel):
    score: int
    reason: str


def _envelope(**overrides):
    base = {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "result": "pong",
        "total_cost_usd": 0.0012,
        "usage": {
            "input_tokens": 400,
            "cache_read_input_tokens": 20,
            "cache_creation_input_tokens": 5,
            "output_tokens": 40,
        },
    }
    base.update(overrides)
    return json.dumps(base)


def _proc(stdout, returncode=0, stderr=""):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


@pytest.fixture
def provider():
    return ClaudeCodeProvider(binary="/usr/bin/claude")


class TestConstruction:
    def test_missing_binary_raises(self, monkeypatch):
        monkeypatch.delenv("CLAUDE_CODE_BINARY", raising=False)
        with patch("local_first_common.providers.claude_code.shutil.which", return_value=None), pytest.raises(RuntimeError, match="claude CLI not found"):
            ClaudeCodeProvider()

    def test_binary_from_env(self, monkeypatch):
        monkeypatch.setenv("CLAUDE_CODE_BINARY", "/opt/claude")
        assert ClaudeCodeProvider().binary == "/opt/claude"

    def test_default_model_is_haiku_alias(self, provider):
        assert provider.model == "haiku"


class TestArgs:
    def test_locked_down_plain_completion(self, provider):
        args = provider._build_args("sys", None)
        assert args[:2] == ["/usr/bin/claude", "-p"]
        assert "--bare" not in args  # --bare disables subscription OAuth
        for flag in ("--strict-mcp-config", "--disable-slash-commands", "--no-session-persistence"):
            assert flag in args
        assert args[args.index("--tools") + 1] == ""
        assert args[args.index("--setting-sources") + 1] == ""
        assert args[args.index("--system-prompt") + 1] == "sys"
        assert "--json-schema" not in args

    def test_response_model_becomes_json_schema(self, provider):
        args = provider._build_args("sys", Score)
        schema = json.loads(args[args.index("--json-schema") + 1])
        assert set(schema["required"]) == {"score", "reason"}

    def test_env_strips_api_key_but_keeps_oauth_token(self, provider, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "oauth-test")
        env = provider._env()
        assert "ANTHROPIC_API_KEY" not in env
        assert env["CLAUDE_CODE_OAUTH_TOKEN"] == "oauth-test"


class TestComplete:
    def test_runs_from_neutral_workdir_not_callers_repo(self, provider):
        with patch("subprocess.run", return_value=_proc(_envelope())) as run:
            provider.complete("sys", "ping")
        assert run.call_args.kwargs["cwd"] == provider.workdir
        assert provider.workdir.name == "claude-code-provider"

    def test_plain_text_and_usage_accounting(self, provider):
        with patch("subprocess.run", return_value=_proc(_envelope())) as run:
            assert provider.complete("sys", "ping") == "pong"
        assert run.call_args.kwargs["input"] == "ping"
        assert provider.input_tokens == 400  # uncached only, matching AnthropicProvider
        assert provider.output_tokens == 40
        assert provider.notional_cost_usd == pytest.approx(0.0012)

    def test_structured_output_preferred(self, provider):
        out = _envelope(result="ignored", structured_output={"score": 7, "reason": "ok"})
        with patch("subprocess.run", return_value=_proc(out)):
            result = provider.complete("sys", "rate", response_model=Score)
        assert result == Score(score=7, reason="ok")

    def test_falls_back_to_parsing_result_text(self, provider):
        out = _envelope(result='Here: {"score": 3, "reason": "meh"}')
        with patch("subprocess.run", return_value=_proc(out)):
            result = provider.complete("sys", "rate", response_model=Score)
        assert result.score == 3

    def test_is_error_raises_without_429(self, provider):
        out = _envelope(is_error=True, result="Claude AI usage limit reached", api_error_status=429)
        with patch("subprocess.run", return_value=_proc(out, returncode=1)), pytest.raises(RuntimeError) as exc:
            provider._complete("sys", "x")
        assert "usage limit" in str(exc.value)
        assert not provider._is_rate_limit_error(exc.value)

    def test_limit_message_with_429_in_epoch_is_not_retried(self, provider):
        out = _envelope(is_error=True, result="Claude AI usage limit reached|1759429000")
        with patch("subprocess.run", return_value=_proc(out, returncode=1)) as run, pytest.raises(ClaudeCodeError):
            provider.complete("sys", "x")
        assert run.call_count == 2  # schema retry only, no rate-limit backoff loop

    def test_non_json_output_raises(self, provider):
        with patch("subprocess.run", return_value=_proc("", returncode=1, stderr="not logged in")), pytest.raises(RuntimeError, match="not logged in"):
            provider._complete("sys", "x")

    def test_timeout_raises(self, provider):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="claude", timeout=1)), pytest.raises(RuntimeError, match="timed out"):
            provider._complete("sys", "x")

    def test_images_rejected(self, provider):
        with pytest.raises(RuntimeError, match="does not support images"):
            provider._complete("sys", "x", images=["abc"])


class TestAcompleteCancellation:
    def test_cancelled_call_kills_the_subprocess(self, provider):
        proc = MagicMock()
        proc.returncode = None
        proc.communicate = AsyncMock(side_effect=asyncio.CancelledError)
        proc.wait = AsyncMock()
        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)), pytest.raises(asyncio.CancelledError):
            asyncio.run(provider._acomplete("sys", "x"))
        proc.kill.assert_called_once()


class TestAcomplete:
    def test_async_path(self, provider):
        proc = MagicMock()
        proc.communicate = AsyncMock(return_value=(_envelope().encode(), b""))
        proc.returncode = 0
        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)) as spawn:
            result = asyncio.run(provider.acomplete("sys", "ping"))
        assert result == "pong"
        assert spawn.call_args.args[0] == "/usr/bin/claude"
        proc.communicate.assert_awaited_once_with(b"ping")
