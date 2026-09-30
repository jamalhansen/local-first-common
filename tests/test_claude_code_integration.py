"""Real `claude -p` calls -- opt-in, since they need a logged-in Claude Code and spend quota.

    RUN_CLAUDE_CLI_TESTS=1 uv run pytest tests/test_claude_code_integration.py

Pins the CLI behaviors ClaudeCodeProvider depends on and the unit tests can only mock:
--system-prompt replaces the default prompt, empty --tools/--setting-sources are
accepted, and --json-schema yields validated structured output.
"""

import os
import shutil

import pytest
from pydantic import BaseModel

from local_first_common.providers.claude_code import ClaudeCodeProvider

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_CLAUDE_CLI_TESTS") != "1" or not shutil.which("claude"),
    reason="set RUN_CLAUDE_CLI_TESTS=1 with Claude Code installed and logged in",
)


class Echo(BaseModel):
    word: str
    count: int


@pytest.fixture
def provider(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    return ClaudeCodeProvider(model="haiku", timeout=120)


def test_system_prompt_is_applied(provider):
    reply = provider.complete("Answer in ALL CAPITAL LETTERS only.", "What color is the sky on a clear day?")
    letters = [c for c in reply if c.isalpha()]
    assert letters and all(c.isupper() for c in letters)


def test_calling_repo_does_not_leak_into_context(provider):
    # pytest runs from the repo root; Claude Code would inject its path, git status
    # and CLAUDE.md into the prompt if the subprocess inherited that cwd.
    reply = provider.complete(
        "Answer briefly.",
        "What directory or project are you working in? If you don't know, reply: unknown",
    )
    assert "local-first-common" not in reply


def test_tools_are_disabled(provider):
    reply = provider.complete(
        "If you have any tools available, list their names. Otherwise reply with exactly: no-tools",
        "What tools do you have?",
    )
    assert "no-tools" in reply


def test_structured_output(provider):
    result = provider.complete("Extract the data.", "The word is 'duck' and it appears 3 times.", response_model=Echo)
    assert result == Echo(word="duck", count=3)
    assert provider.input_tokens > 0
    assert provider.notional_cost_usd > 0
