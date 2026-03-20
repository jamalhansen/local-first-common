#!/usr/bin/env python3
"""Install git pre-commit and pre-push security hooks into local-first repos.

pre-commit: ruff, pytest, personal-path scan, gitignore check, sensitive filenames
pre-push:   gitleaks (secret scan against committed history)

Usage:
    # Install in current repo:
    python install_hooks.py

    # Install in all local-first repos (including local-first-common):
    python install_hooks.py --all

    # Install in a specific repo:
    python install_hooks.py --repo ../resource-summarizer
"""

import argparse
import stat
from pathlib import Path

# Current hook version
HOOK_VERSION = "1.0.0"

PRE_COMMIT_HOOK = f"""\
#!/bin/sh
# Pre-commit checks — installed by local-first-common/install_hooks.py
# Version: {HOOK_VERSION}
# Runs ruff, pytest, and staged-file security scan before every commit.
# To bypass (emergencies only): git commit --no-verify

REPO_ROOT=$(git rev-parse --show-toplevel)
SCANNER="$HOME/projects/local-first/local-first-common/scripts/pre_commit_check.py"

cd "$REPO_ROOT" || exit 1

echo "Running ruff check..."
uv run ruff check .
STATUS=$?
if [ $STATUS -ne 0 ]; then
    echo ""
    echo "Commit blocked: ruff found lint errors. Fix them or use --no-verify to bypass."
    exit 1
fi

echo "Running pytest..."
uv run pytest -q
STATUS=$?
if [ $STATUS -ne 0 ]; then
    echo ""
    echo "Commit blocked: tests failed. Fix them or use --no-verify to bypass."
    exit 1
fi

echo "Running pre-commit security scan..."
python3 "$SCANNER" "$REPO_ROOT" --verbose
STATUS=$?
if [ $STATUS -ne 0 ]; then
    echo ""
    echo "Commit blocked: security scan failed. Fix the issues above or use --no-verify to bypass."
    exit 1
fi

exit 0
"""

PRE_PUSH_HOOK = f"""\
#!/bin/sh
# Pre-push checks — installed by local-first-common/install_hooks.py
# Version: {HOOK_VERSION}
# Runs gitleaks against committed history as a final backstop.
# To bypass (emergencies only): git push --no-verify

REPO_ROOT=$(git rev-parse --show-toplevel)
SCANNER="$HOME/projects/local-first/local-first-common/scripts/pre_push_check.py"

cd "$REPO_ROOT" || exit 1

echo "Running pre-push security scan (gitleaks)..."
python3 "$SCANNER" "$REPO_ROOT" --verbose
STATUS=$?

if [ $STATUS -ne 0 ]; then
    echo ""
    echo "Push blocked: gitleaks found secrets in committed history. Fix the issues above or use --no-verify to bypass."
    exit 1
fi

exit 0
"""

LOCAL_FIRST_DIR = Path(__file__).parent.parent


def find_repos() -> list[Path]:
    """Find all local-first git repos, including local-first-common."""
    repos = []
    for d in LOCAL_FIRST_DIR.iterdir():
        if d.is_dir() and (d / ".git").is_dir():
            repos.append(d)
    return sorted(repos)


def install_hook(repo: Path, hook_name: str, script: str, marker: str) -> bool:
    """Install a named git hook into a repo. Returns True on success."""
    hooks_dir = repo / ".git" / "hooks"
    if not hooks_dir.is_dir():
        print(f"  ✗ {repo.name}/{hook_name}: no .git/hooks directory")
        return False

    hook_path = hooks_dir / hook_name

    if hook_path.exists():
        content = hook_path.read_text()
        if marker in content and f"Version: {HOOK_VERSION}" in content:
            print(f"  ✓ {repo.name}/{hook_name}: already installed (v{HOOK_VERSION})")
            return True
        else:
            backup = hook_path.with_suffix(".pre-security-backup")
            hook_path.rename(backup)
            print(f"  ~ {repo.name}/{hook_name}: backed up existing hook to {backup.name}")

    hook_path.write_text(script)
    hook_path.chmod(hook_path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    print(f"  ✓ {repo.name}/{hook_name}: installed (v{HOOK_VERSION})")
    return True


def install_hooks(repo: Path) -> int:
    """Install both hooks into a repo. Returns count installed/already-present."""
    count = 0
    count += install_hook(repo, "pre-commit", PRE_COMMIT_HOOK, "pre_commit_check.py")
    count += install_hook(repo, "pre-push", PRE_PUSH_HOOK, "pre_push_check.py")
    return count


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--all", action="store_true", help="Install in all local-first repos")
    parser.add_argument("--repo", help="Install in a specific repo path")
    args = parser.parse_args()

    if args.repo:
        repos = [Path(args.repo).resolve()]
    elif args.all:
        repos = find_repos()
        print(f"Found {len(repos)} repos:\n")
    else:
        repos = [Path.cwd()]

    total = 0
    for repo in repos:
        total += install_hooks(repo)

    print(f"\nDone. {total} hooks installed/verified across {len(repos)} repos.")


if __name__ == "__main__":
    main()
