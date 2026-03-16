"""Pre-push security scanner for local-first projects.

Runs gitleaks against committed history as a final backstop before push.
Staged-file checks (personal paths, filenames, gitignore) belong in the
pre-commit hook — see pre_commit_check.py.

Run standalone:
    python3 scripts/pre_push_check.py [path] [--verbose]

Run as pre-push hook (installed by install_hooks.py):
    .git/hooks/pre-push → calls this module
"""

import subprocess
import sys
from pathlib import Path


# ── Checks ────────────────────────────────────────────────────────────────────

def check_gitleaks(repo_path: Path) -> list[str]:
    """Run gitleaks against committed history. Returns list of findings."""
    try:
        result = subprocess.run(
            ["gitleaks", "git", "--no-banner"],
            cwd=repo_path,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            lines = (result.stdout + result.stderr).strip().splitlines()
            return [line for line in lines if line.strip()]
        return []
    except FileNotFoundError:
        return ["[warning] gitleaks not installed — skipping secret scan (brew install gitleaks)"]


# ── Runner ────────────────────────────────────────────────────────────────────

def run_scan(repo_path: Path, verbose: bool = False) -> bool:
    """Run gitleaks. Returns True if clean, False if issues found."""
    findings = check_gitleaks(repo_path)

    if not findings:
        if verbose:
            print("  ✓ Secrets (gitleaks)")
        print("✓ Pre-push security scan passed.")
        return True

    print("✗ Pre-push security scan found issues:\n")
    print("[Secrets (gitleaks)]")
    for f in findings:
        print(f)
    print()
    return False


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Pre-push security scanner for local-first projects")
    parser.add_argument("path", nargs="?", default=".", help="Repo path (default: current directory)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show passing checks too")
    args = parser.parse_args()

    repo_path = Path(args.path).resolve()
    ok = run_scan(repo_path, verbose=args.verbose)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
