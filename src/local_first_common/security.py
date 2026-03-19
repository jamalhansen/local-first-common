"""Security scanner — compatibility shim.

This module previously combined all security checks in one place. It has been
split into two purpose-built scripts:

  - scripts/pre_commit_check.py  — staged-file checks (personal paths,
                                   sensitive filenames, .gitignore coverage)
  - scripts/pre_push_check.py    — gitleaks against committed history

Use those directly for new code. This shim exists for backwards compatibility
with any callers using `python -m local_first_common.security`.
"""

import subprocess
import sys
from pathlib import Path

# local-first-common/src/local_first_common/security.py
#   parents[0] = local_first_common/
#   parents[1] = src/
#   parents[2] = local-first-common/
_SCRIPTS_DIR = Path(__file__).parents[2] / "scripts"
_PRE_COMMIT = _SCRIPTS_DIR / "pre_commit_check.py"
_PRE_PUSH = _SCRIPTS_DIR / "pre_push_check.py"


def run_scan(repo_path: Path, verbose: bool = False) -> bool:
    """Run both pre-commit and pre-push scans. Returns True if clean."""
    clean = True

    commit_cmd = [sys.executable, str(_PRE_COMMIT), str(repo_path), "--all-files"]
    if verbose:
        commit_cmd.append("--verbose")
    clean &= subprocess.run(commit_cmd).returncode == 0

    push_cmd = [sys.executable, str(_PRE_PUSH), str(repo_path)]
    if verbose:
        push_cmd.append("--verbose")
    clean &= subprocess.run(push_cmd).returncode == 0

    return clean


def main() -> None:
    import argparse

    print(
        "⚠️  local_first_common.security is deprecated.\n"
        "   Use scripts/pre_commit_check.py --all-files and scripts/pre_push_check.py instead.\n",
        file=sys.stderr,
    )

    parser = argparse.ArgumentParser(
        description="Security scanner (deprecated — delegates to pre_commit_check + pre_push_check)"
    )
    parser.add_argument("path", nargs="?", default=".", help="Repo path (default: current directory)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show passing checks too")
    args = parser.parse_args()

    ok = run_scan(Path(args.path).resolve(), verbose=args.verbose)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
