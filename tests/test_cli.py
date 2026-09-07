"""Tests for cli.py's Typer option helpers.

Regression coverage for a bug shipped 2026-09-04: `init_config_option`
passed no leading `default` to `typer.Option(...)`, so the `"--init-config"`
flag string itself was consumed as the positional `default` value instead of
a param declaration. Since the parameter is typed `bool`, this crashed every
call to any command using it with "Invalid value for '--init-config':
'--init-config' is not a valid boolean" -- not just --init-config itself.
"""
import typer
from typer.testing import CliRunner

from local_first_common.cli import init_config_option

runner = CliRunner()


def _make_app():
    app = typer.Typer()

    @app.command()
    def run(
        init_config: bool = init_config_option("test-tool", {"provider": "local"}),
    ):
        typer.echo("ran normally")

    return app


class TestInitConfigOption:
    def test_normal_invocation_does_not_crash(self):
        result = runner.invoke(_make_app(), [])
        assert result.exit_code == 0, result.output
        assert "ran normally" in result.output

    def test_flag_triggers_callback_and_exits(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "local_first_common.config.init_config",
            lambda tool_name, defaults: str(tmp_path / "config.toml"),
        )
        result = runner.invoke(_make_app(), ["--init-config"])
        assert result.exit_code == 0, result.output
        assert "Created default config at" in result.output

    def test_omitting_flag_does_not_trigger_callback(self, monkeypatch):
        called = False

        def fake_init_config(tool_name, defaults):
            nonlocal called
            called = True
            return "unused"

        monkeypatch.setattr("local_first_common.config.init_config", fake_init_config)
        result = runner.invoke(_make_app(), [])
        assert result.exit_code == 0, result.output
        assert called is False
