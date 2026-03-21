#!/usr/bin/env python3
"""Toggle local-first-common source between local path and GitHub URL.

Usage:
    python3 scripts/toggle_source.py local   # Switch all repos to ../local-first-common
    python3 scripts/toggle_source.py github  # Switch all repos back to GitHub URL
    python3 scripts/toggle_source.py status  # Show current source for each repo
"""

import re
import sys
from pathlib import Path

# Matches:  local-first-common = { git = "https://...", branch = "main" }
GIT_URL_RE = re.compile(
    r'local-first-common\s*=\s*\{[^}]*git[^}]*\}'
)

# Matches:  local-first-common = {path = "../local-first-common", editable = true}
LOCAL_PATH_RE = re.compile(
    r'local-first-common\s*=\s*\{[^}]*path[^}]*\}'
)

LOCAL_VALUE = 'local-first-common = {path = "../local-first-common", editable = true}'
GITHUB_VALUE = 'local-first-common = { git = "https://github.com/jamalhansen/local-first-common.git", branch = "main" }'

SKIP_REPOS = {"local-first-common", "local-ai-tool-template", "claude-skills"}


def find_repos(workspace: Path) -> list[Path]:
    return sorted(
        p.parent
        for p in workspace.glob("*/pyproject.toml")
        if p.parent.name not in SKIP_REPOS
    )


def get_source(text: str) -> str:
    """Return 'github', 'local', or 'none'."""
    if GIT_URL_RE.search(text):
        return "github"
    if LOCAL_PATH_RE.search(text):
        return "local"
    return "none"


def switch_to_local(workspace: Path) -> None:
    print("Switching all repos to use local-first-common from ../local-first-common ...")
    switched = 0
    for repo in find_repos(workspace):
        toml = repo / "pyproject.toml"
        text = toml.read_text()
        if "local-first-common" not in text:
            continue
        source = get_source(text)
        if source == "local":
            print(f"  - already local  {repo.name}")
        elif source == "github":
            updated = GIT_URL_RE.sub(LOCAL_VALUE, text)
            toml.write_text(updated)
            print(f"  ✓ switched       {repo.name}")
            switched += 1
        else:
            print(f"  ? unrecognised source  {repo.name}")

    print(f"\nDone. {switched} repo(s) switched to local.")
    if switched:
        print("Run 'make use-github' before committing or pushing.")


def switch_to_github(workspace: Path) -> None:
    print("Switching all repos back to GitHub source for local-first-common ...")
    switched = 0
    for repo in find_repos(workspace):
        toml = repo / "pyproject.toml"
        text = toml.read_text()
        if "local-first-common" not in text:
            continue
        source = get_source(text)
        if source == "github":
            print(f"  - already github  {repo.name}")
        elif source == "local":
            updated = LOCAL_PATH_RE.sub(GITHUB_VALUE, text)
            toml.write_text(updated)
            print(f"  ✓ switched        {repo.name}")
            switched += 1
        else:
            print(f"  ? unrecognised source  {repo.name}")

    print(f"\nDone. {switched} repo(s) switched to GitHub.")


def show_status(workspace: Path) -> None:
    print("local-first-common source status:")
    for repo in find_repos(workspace):
        toml = repo / "pyproject.toml"
        text = toml.read_text()
        if "local-first-common" not in text:
            continue
        source = get_source(text)
        symbol = {"github": "↑", "local": "↓", "none": "?"}[source]
        print(f"  {symbol} {source:<8}  {repo.name}")


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in ("local", "github", "status"):
        print(__doc__)
        sys.exit(1)

    # scripts/ -> local-first-common/ -> local-first/ (the workspace)
    workspace = Path(__file__).parent.parent.parent
    command = sys.argv[1]

    if command == "local":
        switch_to_local(workspace)
    elif command == "github":
        switch_to_github(workspace)
    elif command == "status":
        show_status(workspace)


if __name__ == "__main__":
    main()
