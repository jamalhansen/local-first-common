"""Pre-commit security scanner for local-first projects.

Checks staged files (or all tracked files with --all-files) for:
  - Personal paths embedded in source code
  - Sensitive filenames accidentally staged
  - Missing .gitignore entries for sensitive files

Run as pre-commit hook (staged files only):
    Automatically called by git — installed by install_hooks.py

Run as full scan across all tracked files:
    python3 scripts/pre_commit_check.py [path] --all-files [--verbose]
"""

import re
import subprocess
import sys
from pathlib import Path

# ── Constants ─────────────────────────────────────────────────────────────────

PERSONAL_PATH_PATTERN = re.compile(r"/Users/[^/\s\"']+/")

REQUIRED_GITIGNORE_ENTRIES = [
    ".env",
    ".envrc",
    "CLAUDE.md",
    "uv.toml",
    ".venv",
]

SENSITIVE_FILENAME_PATTERNS = [
    re.compile(r"\.env$"),
    re.compile(r"\.pem$"),
    re.compile(r"\.key$"),
    re.compile(r"credentials\.json$"),
    re.compile(r"secrets\."),
]

SOURCE_EXTENSIONS = {".py", ".md", ".toml", ".json", ".yaml", ".yml", ".sh"}

PERSONAL_PATH_ALLOWLIST = {
    "README.md",
    "pyproject.toml",
    "pre_commit_check.py",  # scanner files contain the pattern string itself
    "pre_push_check.py",
    "security.py",
    "SKILL.md",             # skill files reference real vault/project paths by design
    "MEMORY.md",            # memory files contain personal paths by design
}


# ── Checks ────────────────────────────────────────────────────────────────────

def _get_files(repo_path: Path, all_files: bool) -> list[str]:
    """Return staged files or all tracked files depending on mode."""
    try:
        if all_files:
            cmd = ["git", "ls-files"]
        else:
            cmd = ["git", "diff", "--cached", "--name-only"]
        result = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True)
        return [f.strip() for f in result.stdout.splitlines() if f.strip()]
    except Exception:
        return []


def check_personal_paths(repo_path: Path, all_files: bool = False) -> list[str]:
    """Check source files for hardcoded personal paths."""
    findings = []
    for filename in _get_files(repo_path, all_files):
        if Path(filename).name in PERSONAL_PATH_ALLOWLIST:
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


def check_sensitive_filenames(repo_path: Path, all_files: bool = False) -> list[str]:
    """Check files for sensitive filenames."""
    findings = []
    for filename in _get_files(repo_path, all_files):
        name = Path(filename).name
        for pattern in SENSITIVE_FILENAME_PATTERNS:
            if pattern.search(name):
                findings.append(f"  {'tracked' if all_files else 'staged'} sensitive file: {filename}")
                break
    return findings


def check_gitignore(repo_path: Path) -> list[str]:
    """Check that .gitignore covers required sensitive entries."""
    gitignore = repo_path / ".gitignore"
    if not gitignore.exists():
        return ["  .gitignore missing entirely"]

    content = gitignore.read_text(encoding="utf-8")
    findings = []
    for entry in REQUIRED_GITIGNORE_ENTRIES:
        pattern = re.compile(r"^" + re.escape(entry) + r"\s*$", re.MULTILINE)
        if not pattern.search(content):
            findings.append(f"  .gitignore missing entry: {entry}")
    return findings


# ── Runner ────────────────────────────────────────────────────────────────────

def run_scan(repo_path: Path, all_files: bool = False, verbose: bool = False) -> bool:
    """Run all pre-commit checks. Returns True if clean, False if issues found."""
    all_findings: dict[str, list[str]] = {}

    checks = [
        ("Personal paths", lambda p: check_personal_paths(p, all_files)),
        ("Gitignore coverage", check_gitignore),
        ("Sensitive filenames", lambda p: check_sensitive_filenames(p, all_files)),
    ]

    for label, fn in checks:
        findings = fn(repo_path)
        if findings:
            all_findings[label] = findings
        elif verbose:
            print(f"  ✓ {label}")

    if not all_findings:
        print("✓ Pre-commit scan passed.")
        return True

    print("✗ Pre-commit scan found issues:\n")
    for label, findings in all_findings.items():
        print(f"[{label}]")
        for f in findings:
            print(f)
        print()
    return False


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Pre-commit security scanner for local-first projects")
    parser.add_argument("path", nargs="?", default=".", help="Repo path (default: current directory)")
    parser.add_argument("--all-files", action="store_true", help="Scan all tracked files, not just staged")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show passing checks too")
    args = parser.parse_args()

    repo_path = Path(args.path).resolve()
    ok = run_scan(repo_path, all_files=args.all_files, verbose=args.verbose)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
