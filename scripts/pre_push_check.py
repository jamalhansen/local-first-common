"""Pre-push security scanner for local-first projects.

Checks staged/committed files for:
  - Hardcoded secrets (via gitleaks)
  - Personal paths embedded in source code
  - Missing .gitignore entries for sensitive files
  - Sensitive filenames accidentally staged

Run standalone:
    python -m local_first_common.security [--staged] [path]

Run as pre-push hook (installed by install_hooks.py):
    .git/hooks/pre-push → calls this module
"""

import re
import subprocess
import sys
from pathlib import Path

# ── Constants ─────────────────────────────────────────────────────────────────

# Patterns that shouldn't appear in source files
PERSONAL_PATH_PATTERN = re.compile(r"/Users/[^/\s\"']+/")

# Files .gitignore must cover in every local-first project
REQUIRED_GITIGNORE_ENTRIES = [
    ".env",
    ".envrc",
    "CLAUDE.md",
    "uv.toml",
    ".venv",
]

# Filename patterns that should never be committed
SENSITIVE_FILENAME_PATTERNS = [
    re.compile(r"\.env$"),
    re.compile(r"\.pem$"),
    re.compile(r"\.key$"),
    re.compile(r"credentials\.json$"),
    re.compile(r"secrets\."),
]

# Source extensions to check for personal paths
SOURCE_EXTENSIONS = {".py", ".md", ".toml", ".json", ".yaml", ".yml", ".sh"}

# Files where personal paths are expected/acceptable
PERSONAL_PATH_ALLOWLIST = {"README.md", "pyproject.toml"}


# ── Checks ────────────────────────────────────────────────────────────────────

def check_gitleaks(repo_path: Path) -> list[str]:
    """Run gitleaks on staged changes. Returns list of findings."""
    try:
        result = subprocess.run(
            ["gitleaks", "git", "--staged", "--no-banner"],
            cwd=repo_path,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            # gitleaks exits non-zero when it finds leaks
            lines = (result.stdout + result.stderr).strip().splitlines()
            return [l for l in lines if l.strip()]
        return []
    except FileNotFoundError:
        return ["[warning] gitleaks not installed — skipping secret scan (brew install gitleaks)"]


def check_personal_paths(repo_path: Path) -> list[str]:
    """Check tracked source files for hardcoded personal paths."""
    findings = []
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=repo_path,
            capture_output=True,
            text=True,
        )
        staged_files = [f.strip() for f in result.stdout.splitlines() if f.strip()]
    except Exception:
        return []

    for filename in staged_files:
        if filename in PERSONAL_PATH_ALLOWLIST:
            continue
        path = repo_path / filename
        if path.suffix not in SOURCE_EXTENSIONS or not path.exists():
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for match in PERSONAL_PATH_PATTERN.finditer(content):
            line_num = content[: match.start()].count("\n") + 1
            findings.append(
                f"  {filename}:{line_num} — hardcoded personal path: {match.group()!r}"
            )
    return findings


def check_gitignore(repo_path: Path) -> list[str]:
    """Check that .gitignore covers required sensitive entries."""
    gitignore = repo_path / ".gitignore"
    if not gitignore.exists():
        return ["  .gitignore missing entirely"]

    content = gitignore.read_text(encoding="utf-8")
    findings = []
    for entry in REQUIRED_GITIGNORE_ENTRIES:
        # Match the entry as a standalone line (ignoring comments)
        pattern = re.compile(r"^" + re.escape(entry) + r"\s*$", re.MULTILINE)
        if not pattern.search(content):
            findings.append(f"  .gitignore missing entry: {entry}")
    return findings


def check_sensitive_filenames(repo_path: Path) -> list[str]:
    """Check staged files for sensitive filenames."""
    findings = []
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=repo_path,
            capture_output=True,
            text=True,
        )
        staged_files = [f.strip() for f in result.stdout.splitlines() if f.strip()]
    except Exception:
        return []

    for filename in staged_files:
        name = Path(filename).name
        for pattern in SENSITIVE_FILENAME_PATTERNS:
            if pattern.search(name):
                findings.append(f"  staged sensitive file: {filename}")
                break
    return findings


# ── Runner ────────────────────────────────────────────────────────────────────

def run_scan(repo_path: Path, verbose: bool = False) -> bool:
    """Run all checks. Returns True if clean, False if issues found."""
    all_findings: dict[str, list[str]] = {}

    checks = [
        ("Secrets (gitleaks)", check_gitleaks),
        ("Personal paths", check_personal_paths),
        ("Gitignore coverage", check_gitignore),
        ("Sensitive filenames", check_sensitive_filenames),
    ]

    for label, fn in checks:
        findings = fn(repo_path)
        if findings:
            all_findings[label] = findings
        elif verbose:
            print(f"  ✓ {label}")

    if not all_findings:
        print("✓ Security scan passed.")
        return True

    print("✗ Security scan found issues:\n")
    for label, findings in all_findings.items():
        print(f"[{label}]")
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
