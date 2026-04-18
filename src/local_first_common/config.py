import os
import sys
import toml
from pathlib import Path
from typing import Any, Optional

CONFIG_DIR = Path("~/.config/local-first").expanduser()


def load_config(tool_name: str) -> dict[str, Any]:
    """Load configuration from ~/.config/local-first/{tool_name}.toml."""
    config_path = CONFIG_DIR / f"{tool_name}.toml"
    if not config_path.exists():
        return {}
    try:
        return toml.load(config_path)
    except Exception as e:
        print(
            f"Warning: Failed to load config from {config_path}: {e}", file=sys.stderr
        )
        return {}


def get_setting(
    tool_name: str,
    key: str,
    cli_val: Optional[Any] = None,
    env_var: Optional[str] = None,
    default: Optional[Any] = None,
) -> Any:
    """Resolve a setting based on standard precedence: CLI > Env > Config > Default."""
    if cli_val is not None:
        return cli_val
    if env_var and env_var in os.environ:
        return os.environ[env_var]
    config = load_config(tool_name)
    if key in config:
        return config[key]
    return default


def init_config(tool_name: str, defaults: dict[str, Any], force: bool = False) -> Path:
    """Initialize a default config file if it doesn't exist."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config_path = CONFIG_DIR / f"{tool_name}.toml"
    if config_path.exists() and not force:
        return config_path
    with open(config_path, "w") as f:
        f.write(f"# Configuration for {tool_name}\n\n")
        toml.dump(defaults, f)
    return config_path
