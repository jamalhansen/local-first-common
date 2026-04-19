#!/usr/bin/env python3
"""Toggle local-first-common source between local path and GitHub URL.

Usage:
    python3 scripts/toggle_source.py local [repo ...]
    python3 scripts/toggle_source.py github [repo ...]
    python3 scripts/toggle_source.py status [repo ...]
    python3 scripts/toggle_source.py preflight

Examples:
    python3 scripts/toggle_source.py local
    python3 scripts/toggle_source.py local promo-generator weekly-review-generator
    python3 scripts/toggle_source.py github promo-generator
    python3 scripts/toggle_source.py status
    python3 scripts/toggle_source.py preflight
"""

import re
import subprocess
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

# When restoring the git source we preserve the original rev/branch key so
# round-tripping doesn't produce a noisy diff.  We stash the original value
# per-repo while switching to local and restore it on the way back.
_GITHUB_VALUE_DEFAULT = 'local-first-common = { git = "https://github.com/jamalhansen/local-first-common.git", branch = "main" }'


def _original_git_line(text: str) -> str:
    """Return the exact git-source line from text, or a sensible default."""
    m = GIT_URL_RE.search(text)
    return m.group(0) if m else _GITHUB_VALUE_DEFAULT

SKIP_REPOS = {"local-first-common", "local-ai-tool-template", "claude-skills"}


def find_repos(workspace: Path) -> list[Path]:
    return sorted(
        p.parent
        for p in workspace.glob("*/pyproject.toml")
        if p.parent.name not in SKIP_REPOS
    )


def _select_repos(workspace: Path, repo_names: list[str]) -> list[Path]:
    repos = find_repos(workspace)
    if not repo_names:
        return repos

    by_name = {r.name: r for r in repos}
    selected: list[Path] = []
    missing: list[str] = []
    for name in repo_names:
        repo = by_name.get(name)
        if repo is None:
            missing.append(name)
        else:
            selected.append(repo)

    if missing:
        print("Unknown repo(s): " + ", ".join(sorted(missing)))
        print("Use one of: " + ", ".join(sorted(by_name)))
        sys.exit(2)

    return selected


def get_source(text: str) -> str:
    """Return 'github', 'local', or 'none'."""
    if GIT_URL_RE.search(text):
        return "github"
    if LOCAL_PATH_RE.search(text):
        return "local"
    return "none"


def _git_head_line(repo: Path) -> str:
    """Return the local-first-common source line from git HEAD's pyproject.toml.

    This is the canonical version to restore when switching back to github —
    it preserves the exact original formatting (rev= vs branch=, spacing, etc.)
    regardless of what the working copy currently contains.
    """
    try:
        result = subprocess.run(
            ["git", "show", "HEAD:pyproject.toml"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        )
        return _original_git_line(result.stdout)
    except subprocess.CalledProcessError:
        return _GITHUB_VALUE_DEFAULT


def _tracked_file_status(repo: Path, rel_path: str) -> str:
    try:
        result = subprocess.run(
            ["git", "status", "--short", "--", rel_path],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return ""


def _report_churn(repos: list[Path]) -> None:
    pyproject_changed = []
    uv_lock_changed = []

    for repo in repos:
        py_status = _tracked_file_status(repo, "pyproject.toml")
        lock_status = _tracked_file_status(repo, "uv.lock")
        if py_status:
            pyproject_changed.append(repo.name)
        if lock_status:
            uv_lock_changed.append(repo.name)

    if pyproject_changed:
        print("\nChanged pyproject.toml:")
        for name in pyproject_changed:
            print(f"  - {name}")

    if uv_lock_changed:
        print("\nChanged uv.lock:")
        for name in uv_lock_changed:
            print(f"  - {name}")
    else:
        print("\nNo uv.lock changes detected yet (expected until sync/lock runs).")


def switch_to_local(workspace: Path, repo_names: list[str]) -> None:
    repos = _select_repos(workspace, repo_names)
    scope = "selected repos" if repo_names else "all repos"
    print(
        f"Switching {scope} to use local-first-common from ../local-first-common ..."
    )
    switched = 0
    for repo in repos:
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
    _report_churn(repos)


def switch_to_github(workspace: Path, repo_names: list[str]) -> None:
    repos = _select_repos(workspace, repo_names)
    scope = "selected repos" if repo_names else "all repos"
    print(f"Switching {scope} back to GitHub source for local-first-common ...")
    switched = 0
    for repo in repos:
        toml = repo / "pyproject.toml"
        text = toml.read_text()
        if "local-first-common" not in text:
            continue
        source = get_source(text)
        if source == "github":
            print(f"  - already github  {repo.name}")
        elif source == "local":
            # Restore from git HEAD to preserve the exact original formatting
            restore_line = _git_head_line(repo)
            updated = LOCAL_PATH_RE.sub(restore_line, text)
            toml.write_text(updated)
            print(f"  ✓ switched        {repo.name}")
            switched += 1
        else:
            print(f"  ? unrecognised source  {repo.name}")

    print(f"\nDone. {switched} repo(s) switched to GitHub.")
    _report_churn(repos)


def show_status(workspace: Path, repo_names: list[str]) -> None:
    repos = _select_repos(workspace, repo_names)
    print("local-first-common source status:")
    for repo in repos:
        toml = repo / "pyproject.toml"
        text = toml.read_text()
        if "local-first-common" not in text:
            continue
        source = get_source(text)
        symbol = {"github": "↑", "local": "↓", "none": "?"}[source]
        print(f"  {symbol} {source:<8}  {repo.name}")


def preflight(workspace: Path) -> int:
    """Report repos still in local mode before push/publish workflows.

    Returns 0 when everything is on GitHub source, else 1.
    """
    local_repos: list[str] = []
    for repo in find_repos(workspace):
        toml = repo / "pyproject.toml"
        text = toml.read_text()
        if "local-first-common" not in text:
            continue
        if get_source(text) == "local":
            local_repos.append(repo.name)

    if not local_repos:
        print("Preflight OK: all repos use GitHub source for local-first-common.")
        return 0

    print("Preflight FAIL: repo(s) still using local source:")
    for name in local_repos:
        print(f"  - {name}")
    print("Run: make use-github-selected REPOS='repo-a repo-b' (or make use-github)")
    return 1


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in (
        "local",
        "github",
        "status",
        "preflight",
    ):
        print(__doc__)
        sys.exit(1)

    # scripts/ -> local-first-common/ -> local-first/ (the workspace)
    workspace = Path(__file__).parent.parent.parent
    command = sys.argv[1]
    repo_names = sys.argv[2:]

    if command == "local":
        switch_to_local(workspace, repo_names)
    elif command == "github":
        switch_to_github(workspace, repo_names)
    elif command == "status":
        show_status(workspace, repo_names)
    elif command == "preflight":
        sys.exit(preflight(workspace))


if __name__ == "__main__":
    main()
