"""Tests for cli.py's Typer option helpers.

Regression coverage for a bug shipped 2026-09-04: `init_config_option`
passed no leading `default` to `typer.Option(...)`, so the `"--init-config"`
flag string itself was consumed as the positional `default` value instead of
a param declaration. Since the parameter is typed `bool`, this crashed every
call to any command using it with "Invalid value for '--init-config':
'--init-config' is not a valid boolean" -- not just --init-config itself.
"""
from typing import Annotated

import typer
from typer.testing import CliRunner

from local_first_common.cli import init_config_option

runner = CliRunner()


def _make_app():
    app = typer.Typer()

    @app.command()
    def run(
        init_config: Annotated[
            bool, init_config_option("test-tool", {"provider": "local"})
        ] = False,
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

    def test_negated_flag_is_a_real_option_not_just_absent(self):
        """A missing leading `default` on typer.Option() doesn't always crash --
        it can just silently drop Typer's auto-generated --no-x form instead,
        which is exactly what happened here 2026-09-06 despite this file's
        other three tests all passing throughout. --no-init-config must exist
        and must not itself be mistaken for the positional default again."""
        result = runner.invoke(_make_app(), ["--no-init-config"])
        assert result.exit_code == 0, result.output
        assert "no such option" not in result.output.lower()
        assert "ran normally" in result.output


class TestJsonOption:
    def test_json_option_in_app(self):
        from local_first_common.cli import json_option

        app = typer.Typer()

        @app.command()
        def cmd(json_out: Annotated[bool, json_option()] = False):
            if json_out:
                typer.echo('{"status": "ok"}')
            else:
                typer.echo("status: ok")

        res1 = runner.invoke(app, [])
        assert res1.exit_code == 0
        assert "status: ok" in res1.output

        res2 = runner.invoke(app, ["--json"])
        assert res2.exit_code == 0
        assert '{"status": "ok"}' in res2.output

        res3 = runner.invoke(app, ["-j"])
        assert res3.exit_code == 0
        assert '{"status": "ok"}' in res3.output

