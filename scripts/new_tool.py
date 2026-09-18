#!/usr/bin/env python3
"""Scaffold a new local-first tool repo matching STANDARDS.md's file layout.

Every one of the ~28 tool repos in this workspace has been hand-assembled to
the same shape: pyproject.toml with a git dependency on local-first-common,
src/<pkg>/{cli,core}.py with cli.py wired to register_tool() and the standard
--dry-run/--no-llm/--provider/--model options, a tests/ dir, a synced
.gitignore, and git hooks installed via install_hooks.py. This script does
that setup once instead of by hand each time.

Usage:
    python3 new_tool.py my-new-tool "One-sentence description of what it does"
    python3 new_tool.py my-new-tool "..." --dest ~/projects/local-first

Creates <dest>/<tool-name>/, runs `uv sync`, `git init` + first commit, and
installs the standard pre-commit/pre-push hooks via install_hooks.py.
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from sync_gitignores import MASTER_IGNORES

WORKSPACE_ROOT = Path(__file__).parent.parent.parent
INSTALL_HOOKS = Path(__file__).parent.parent / "install_hooks.py"


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def package_name(slug: str) -> str:
    return slug.replace("-", "_")


def render_pyproject(slug: str, pkg: str, description: str) -> str:
    return f'''[project]
name = "{slug}"
version = "0.1.0"
description = "{description}"
requires-python = ">=3.12"
dependencies = [
    "typer>=0.15.0",
    "click<8.3.2",  # 8.3.2 breaks typer 0.24.1's option parsing: AttributeError 'bool' object has no attribute 'isidentifier'. Unpin once a compatible typer release lands.
    "rich>=14.3.3",
    "local-first-common",
]

[project.scripts]
{slug} = "{pkg}.cli:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/{pkg}"]

[dependency-groups]
dev = [
    "pytest>=9.0.2",
    "pytest-cov>=6.0.0",
]

[tool.uv.sources]
local-first-common = {{ git = "https://github.com/jamalhansen/local-first-common.git", branch = "main" }}

[tool.pytest.ini_options]
pythonpath = ["src"]
'''


def render_main(pkg: str) -> str:
    return f"from {pkg}.cli import app\n\nif __name__ == \"__main__\":\n    app()\n"


def render_init() -> str:
    return ""


def render_core(pkg: str) -> str:
    return f'''"""Pure domain logic for {pkg.replace("_", "-")} -- no CLI/Typer imports here.

Keep this module importable and testable without going through the CLI:
cli.py should be a thin layer over functions defined here.
"""


def run(dry_run: bool = False) -> str:
    """Placeholder entry point. Replace with the tool's real logic."""
    return "not yet implemented"
'''


def render_cli(slug: str, pkg: str, description: str) -> str:
    return f'''from typing import Annotated

import typer
from local_first_common.cli import (
    dry_run_option,
    model_option,
    no_llm_option,
    provider_option,
    resolve_dry_run,
)
from local_first_common.tracking import register_tool
from rich.console import Console

from .core import run

TOOL_NAME = "{slug}"
_TOOL = register_tool(TOOL_NAME)

console = Console(stderr=True)
app = typer.Typer(help="{description}")


@app.command()
def main(
    provider: Annotated[str, provider_option()] = "ollama",
    model: Annotated[str | None, model_option()] = None,
    dry_run: Annotated[bool, dry_run_option()] = False,
    no_llm: Annotated[bool, no_llm_option()] = False,
) -> None:
    """{description}"""
    dry_run = resolve_dry_run(dry_run, no_llm)
    result = run(dry_run=dry_run)
    console.print(result)


if __name__ == "__main__":
    app()
'''


def render_conftest() -> str:
    return "from local_first_common.testing import isolate_tracking_db  # noqa: F401\n"


def render_test_core(pkg: str) -> str:
    return f'''from {pkg}.core import run


def test_run_returns_a_string():
    assert isinstance(run(), str)
'''


def render_test_cli(pkg: str) -> str:
    return f'''from typer.testing import CliRunner

from {pkg}.cli import app


def test_default_invocation_exits_clean():
    result = CliRunner().invoke(app, [])
    assert result.exit_code == 0
    assert "not yet implemented" in result.output
'''


def render_readme(slug: str, description: str) -> str:
    return f"""# {slug}

{description}

## Quickstart

```bash
uv run {slug}
```

## Status

Scaffolded via `local-first-common/scripts/new_tool.py` -- replace `core.run()`
and the CLI options in `cli.py` with the tool's real logic.
"""


def render_gitignore() -> str:
    return "\n".join(sorted(MASTER_IGNORES)) + "\n"


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def scaffold(slug: str, description: str, dest: Path) -> Path:
    pkg = package_name(slug)
    repo = dest / slug
    if repo.exists():
        raise SystemExit(f"{repo} already exists -- refusing to overwrite.")

    write_file(repo / "pyproject.toml", render_pyproject(slug, pkg, description))
    write_file(repo / "README.md", render_readme(slug, description))
    write_file(repo / ".gitignore", render_gitignore())
    write_file(repo / "src" / "main.py", render_main(pkg))
    write_file(repo / "src" / pkg / "__init__.py", render_init())
    write_file(repo / "src" / pkg / "core.py", render_core(pkg))
    write_file(repo / "src" / pkg / "cli.py", render_cli(slug, pkg, description))
    write_file(repo / "tests" / "conftest.py", render_conftest())
    write_file(repo / "tests" / "test_core.py", render_test_core(pkg))
    write_file(repo / "tests" / "test_cli.py", render_test_cli(pkg))
    return repo


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", help="Tool name, e.g. 'my-new-tool'")
    parser.add_argument("description", help="One-sentence description")
    parser.add_argument(
        "--dest",
        default=str(WORKSPACE_ROOT),
        help="Parent directory to create the new repo in (default: this workspace root)",
    )
    parser.add_argument(
        "--skip-setup",
        action="store_true",
        help="Only write files; skip git init / uv sync / hook install",
    )
    args = parser.parse_args()

    slug = slugify(args.name)
    dest = Path(args.dest).expanduser().resolve()
    repo = scaffold(slug, args.description, dest)
    print(f"Scaffolded {repo}")

    if args.skip_setup:
        return

    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["uv", "sync"], cwd=repo, check=True)
    subprocess.run(
        [sys.executable, str(INSTALL_HOOKS), "--repo", str(repo)], check=True
    )
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", f"Scaffold {slug} via new_tool.py"],
        cwd=repo,
        check=True,
    )
    print(f"\nDone. {repo} is git-initialized, dependencies synced, hooks installed.")
    print(f"Next: implement {slug.replace('-', '_')}/core.py, then `uv run {slug}`.")


if __name__ == "__main__":
    main()
