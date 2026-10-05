import asyncio
import json
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, ClassVar

from .base import BaseProvider

logger = logging.getLogger(__name__)


class ClaudeCodeError(RuntimeError):
    """A failed `claude -p` call, carrying the envelope's structured status."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class ClaudeCodeProvider(BaseProvider):
    """Claude via the headless `claude -p` CLI, billed to a Claude Pro/Max subscription.

    Anthropic scopes subscription auth to Claude Code / the Agent SDK, so this
    goes *through* Claude Code rather than lifting its OAuth token into the
    `anthropic` SDK. Interactive shells use the logged-in session; cron/launchd
    jobs need CLAUDE_CODE_OAUTH_TOKEN from `claude setup-token`.
    """

    provider_name = "claude-code"
    default_model = "haiku"
    known_models: ClassVar[list[str]] = [
        "haiku",
        "sonnet",
        "opus",
        "claude-haiku-4-5-20251001",
        "claude-sonnet-5",
        "claude-opus-5-5",
    ]
    models_url = "https://docs.anthropic.com/en/docs/claude-code/cli-reference"

    def __init__(
        self,
        model: str | None = None,
        debug: bool = False,
        binary: str | None = None,
        timeout: float = 300,
    ):
        super().__init__(model=model, debug=debug)
        self.binary = binary or os.environ.get("CLAUDE_CODE_BINARY") or shutil.which("claude")
        if not self.binary:
            raise RuntimeError("claude CLI not found on PATH. Install Claude Code or set CLAUDE_CODE_BINARY.")
        self.timeout = timeout
        # Claude Code injects its working directory's context (path, git status,
        # project CLAUDE.md) into the prompt, so a tool run from inside a repo
        # would leak that repo into every completion. Run from an empty dir.
        self.workdir = Path(tempfile.gettempdir()) / "claude-code-provider"
        self.workdir.mkdir(exist_ok=True)
        self.input_tokens: int = 0
        self.output_tokens: int = 0
        # What the same calls would have cost on the metered API -- not billed.
        self.notional_cost_usd: float = 0.0

    @staticmethod
    def _is_rate_limit_error(e: Exception) -> bool:
        # Subscription limits reset in hours, so BaseProvider's 5-20s backoff only
        # delays the failure. Decided on type, not text: the CLI's limit message
        # embeds a reset epoch, which can itself contain "429".
        if isinstance(e, ClaudeCodeError):
            return False
        return BaseProvider._is_rate_limit_error(e)

    def _build_args(self, system: str, response_model: Any | None) -> list[str]:
        # No --bare: it forces ANTHROPIC_API_KEY auth and disables OAuth.
        # System prompt stays in argv: --system-prompt-file is silently ignored
        # outside --bare (verified 2026-09-29), which would drop every prompt.
        # Empty --tools/--setting-sources keep this a plain completion: no tool
        # use, no user hooks or plugins, no MCP servers, nothing persisted.
        args = [
            self.binary,
            "-p",
            "--output-format",
            "json",
            "--model",
            self.model,
            "--system-prompt",
            system,
            "--tools",
            "",
            "--setting-sources",
            "",
            "--strict-mcp-config",
            "--disable-slash-commands",
            "--no-session-persistence",
        ]
        if response_model is not None and hasattr(response_model, "model_json_schema"):
            args += ["--json-schema", json.dumps(response_model.model_json_schema())]
        return args

    @staticmethod
    def _env() -> dict[str, str]:
        env = os.environ.copy()
        # With an API key present the CLI bills the API instead of the subscription.
        env.pop("ANTHROPIC_API_KEY", None)
        return env

    @staticmethod
    def _check_images(images: list[str] | None) -> None:
        if images:
            raise RuntimeError(
                "ClaudeCodeProvider does not support images yet; use --provider anthropic or ollama for vision."
            )

    def _handle_output(
        self, stdout: str, stderr: str, returncode: int, response_model: Any | None
    ) -> str | dict[str, Any]:
        try:
            envelope = json.loads(stdout)
        except json.JSONDecodeError as err:
            logger.warning(
                "claude CLI returned non-JSON output (exit %d): %s",
                returncode,
                (stderr or stdout)[:500],
                extra={"run_context": "provider_cli_bad_output", "source_location": self.model},
            )
            raise ClaudeCodeError(f"claude CLI failed (exit {returncode}): {(stderr or stdout).strip()[:500]}") from err

        # Same semantics as AnthropicProvider (uncached input only), so
        # processing_log totals stay comparable across the two.
        usage = envelope.get("usage") or {}
        self.input_tokens += usage.get("input_tokens", 0)
        self.output_tokens += usage.get("output_tokens", 0)
        self.notional_cost_usd += envelope.get("total_cost_usd") or 0.0

        if envelope.get("is_error") or returncode != 0:
            status = envelope.get("api_error_status")
            detail = envelope.get("result") or envelope.get("subtype") or stderr.strip()
            logger.warning(
                "claude CLI call failed for %s (status %s): %s",
                self.model,
                status,
                detail,
                extra={"run_context": "provider_api_error", "source_location": self.model},
            )
            label = "usage/rate limit" if status == 429 else f"status {status}"
            raise ClaudeCodeError(f"Claude Code error ({label}): {detail}", status=status)

        if response_model is not None:
            structured = envelope.get("structured_output")
            if isinstance(structured, dict):
                result: str | dict[str, Any] = self._clean_json(structured, response_model)
            else:
                result = self._parse_json_response(envelope.get("result", ""), response_model)
        else:
            result = envelope.get("result", "")

        self._debug_print_response(result)
        return result

    def _complete(
        self,
        system: str,
        user: str,
        response_model: Any | None = None,
        images: list[str] | None = None,
    ) -> str | dict[str, Any]:
        self._check_images(images)
        self._debug_print_request("", system, user)
        try:
            proc = subprocess.run(
                self._build_args(system, response_model),
                input=user,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                env=self._env(),
                cwd=self.workdir,
                check=False,
            )
        except subprocess.TimeoutExpired as err:
            raise ClaudeCodeError(f"claude CLI timed out after {self.timeout}s") from err
        return self._handle_output(proc.stdout, proc.stderr, proc.returncode, response_model)

    async def _acomplete(
        self,
        system: str,
        user: str,
        response_model: Any | None = None,
        images: list[str] | None = None,
    ) -> str | dict[str, Any]:
        self._check_images(images)
        self._debug_print_request("", system, user)
        proc = await asyncio.create_subprocess_exec(
            *self._build_args(system, response_model),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self._env(),
            cwd=self.workdir,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(user.encode()), timeout=self.timeout)
        except TimeoutError as err:
            raise ClaudeCodeError(f"claude CLI timed out after {self.timeout}s") from err
        finally:
            # Also covers cancellation: an orphaned `claude` keeps spending quota.
            if proc.returncode is None:
                proc.kill()
                await proc.wait()
        return self._handle_output(stdout.decode(), stderr.decode(), proc.returncode or 0, response_model)
