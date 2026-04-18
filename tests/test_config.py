import toml
from local_first_common.config import get_setting, init_config


def test_precedence(tmp_path, monkeypatch):
    mock_config_dir = tmp_path / "config"
    mock_config_dir.mkdir()
    monkeypatch.setattr("local_first_common.config.CONFIG_DIR", mock_config_dir)

    tool_name = "test-tool"
    config_file = mock_config_dir / f"{tool_name}.toml"

    assert get_setting(tool_name, "provider", default="ollama") == "ollama"

    config_file.write_text('provider = "anthropic"')
    assert get_setting(tool_name, "provider", default="ollama") == "anthropic"

    monkeypatch.setenv("TEST_PROVIDER", "groq")
    assert (
        get_setting(tool_name, "provider", env_var="TEST_PROVIDER", default="ollama")
        == "groq"
    )

    assert (
        get_setting(
            tool_name,
            "provider",
            cli_val="openai",
            env_var="TEST_PROVIDER",
            default="ollama",
        )
        == "openai"
    )


def test_init_config(tmp_path, monkeypatch):
    mock_config_dir = tmp_path / "config"
    monkeypatch.setattr("local_first_common.config.CONFIG_DIR", mock_config_dir)

    tool_name = "init-tool"
    defaults = {"provider": "ollama", "max_dim": 1200}

    path = init_config(tool_name, defaults)
    assert path.exists()

    data = toml.load(path)
    assert data["provider"] == "ollama"
    assert data["max_dim"] == 1200


def test_load_config_returns_empty_dict_on_parse_error(tmp_path, monkeypatch, capsys):
    mock_config_dir = tmp_path / "config"
    mock_config_dir.mkdir()
    monkeypatch.setattr("local_first_common.config.CONFIG_DIR", mock_config_dir)

    tool_name = "broken-tool"
    config_file = mock_config_dir / f"{tool_name}.toml"
    config_file.write_text("not=valid=toml")

    value = get_setting(tool_name, "provider", default="ollama")
    captured = capsys.readouterr()

    assert value == "ollama"
    assert "Warning: Failed to load config" in captured.err
