#!/usr/bin/env python3
"""Install git pre-push security hooks into local-first repos.

Usage:
    # Install in current repo:
    python install_hooks.py

    # Install in all local-first repos:
    python install_hooks.py --all

    # Install in a specific repo:
    python install_hooks.py --repo ../resource-summarizer
"""

import argparse
import stat
import sys
from pathlib import Path

HOOK_SCRIPT = """\
#!/bin/sh
# Pre-push checks — installed by local-first-common/install_hooks.py
# Runs ruff, pytest, and security scan before every push.
# To bypass (emergencies only): git push --no-verify

REPO_ROOT=$(git rev-parse --show-toplevel)
SCANNER="$HOME/projects/local-first/local-first-common/scripts/pre_push_check.py"

cd "$REPO_ROOT" || exit 1

echo "Running ruff check..."
uv run ruff check .
STATUS=$?
if [ $STATUS -ne 0 ]; then
    echo ""
    echo "Push blocked: ruff found lint errors. Fix them or use --no-verify to bypass."
    exit 1
fi

echo "Running pytest..."
uv run pytest -q
STATUS=$?
if [ $STATUS -ne 0 ]; then
    echo ""
    echo "Push blocked: tests failed. Fix them or use --no-verify to bypass."
    exit 1
fi

echo "Running pre-push security scan..."
python3 "$SCANNER" "$REPO_ROOT" --verbose
STATUS=$?

if [ $STATUS -ne 0 ]; then
    echo ""
    echo "Push blocked: security scan failed. Fix the issues above or use --no-verify to bypass."
    exit 1
fi

exit 0
"""

LOCAL_FIRST_DIR = Path(__file__).parent.parent


def find_repos() -> list[Path]:
    """Find all local-first git repos (excluding local-first-common itself)."""
    repos = []
    for d in LOCAL_FIRST_DIR.iterdir():
        if d.is_dir() and (d / ".git").is_dir() and d.name != "local-first-common":
            repos.append(d)
    return sorted(repos)


def install_hook(repo: Path) -> bool:
    """Install the pre-push hook into a repo. Returns True on success."""
    hooks_dir = repo / ".git" / "hooks"
    if not hooks_dir.is_dir():
        print(f"  ✗ {repo.name}: no .git/hooks directory")
        return False

    hook_path = hooks_dir / "pre-push"

    if hook_path.exists():
        content = hook_path.read_text()
        if "pre_push_check.py" in content and "ruff check" in content:
            print(f"  ✓ {repo.name}: already installed")
            return True
        else:
            # Back up existing hook
            backup = hook_path.with_suffix(".pre-security-backup")
            hook_path.rename(backup)
            print(f"  ~ {repo.name}: backed up existing hook to {backup.name}")

    hook_path.write_text(HOOK_SCRIPT)
    hook_path.chmod(hook_path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    print(f"  ✓ {repo.name}: installed")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--all", action="store_true", help="Install in all local-first repos")
    parser.add_argument("--repo", help="Install in a specific repo path")
    args = parser.parse_args()

    if args.repo:
        repos = [Path(args.repo).resolve()]
    elif args.all:
        repos = find_repos()
        print(f"Found {len(repos)} repos:\n")
    else:
        # Default: current directory
        repos = [Path.cwd()]

    installed = 0
    for repo in repos:
        if install_hook(repo):
            installed += 1

    print(f"\nDone. Installed: {installed}, Skipped: {len(repos) - installed}")


if __name__ == "__main__":
    main()
