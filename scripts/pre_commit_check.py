"""Pre-commit security scanner for local-first projects.

Checks staged files (or all tracked files with --all-files) for:
  - Personal paths embedded in source code
  - Sensitive filenames accidentally staged
  - Missing .gitignore entries for sensitive files
  - Typer anti-pattern (default value as first arg to typer.Option)
  - Duplicate register_tool() across multiple source files
  - Direct LLM library imports (must use local-first-common providers)
  - Tracked .pyc / __pycache__ files committed to git
  - Relative imports in src/main.py (broken entry-point pattern)

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

# Repos exempt from LLM-import and register_tool checks
EXEMPT_REPOS = {"local-first-common", "local-first-mcp", "pebble", "local-ai-tool-template"}

# Typer anti-pattern: default value supplied as first positional arg to typer.Option()
# Correct form: typer.Option("--flag", ...) or typer.Option("-f", ...)
TYPER_ANTIPATTERN_RE = re.compile(
    r"""typer\.Option\((?:os\.environ|['"]\s*[^-])""",
)

# Direct LLM library imports that should go through local-first-common providers
DIRECT_LLM_IMPORT_RE = re.compile(
    r"""^(?:import|from)\s+(?:anthropic|openai|google\.generativeai|groq|ollama)\b""",
    re.MULTILINE,
)


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


def check_typer_antipattern(repo_path: Path, all_files: bool = False) -> list[str]:
    """Check staged/tracked Python files for the Typer anti-pattern.

    The anti-pattern is passing a default value as the first positional arg
    to typer.Option() instead of a flag string.  Correct form:
        provider: Annotated[str, typer.Option("--provider", "-p", ...)] = "ollama"
    """
    findings = []
    for filename in _get_files(repo_path, all_files):
        path = repo_path / filename
        if path.suffix != ".py" or not path.exists():
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for match in TYPER_ANTIPATTERN_RE.finditer(content):
            line_num = content[: match.start()].count("\n") + 1
            findings.append(
                f"  {filename}:{line_num} — Typer anti-pattern: default value as first arg "
                f"to typer.Option() (causes 'Name defined twice' error). "
                f"Use Annotated[..., typer.Option('--flag', ...)] = default instead."
            )
    return findings


def check_duplicate_register_tool(repo_path: Path) -> list[str]:
    """Check that register_tool() appears in at most one source file per repo.

    Calling register_tool() from multiple files creates duplicate run entries
    in the tracking DB for every invocation.
    """
    src_dir = repo_path / "src"
    if not src_dir.exists():
        return []
    if repo_path.name in EXEMPT_REPOS:
        return []

    files_with_registration: list[str] = []
    for py_file in src_dir.rglob("*.py"):
        try:
            if "register_tool(" in py_file.read_text(encoding="utf-8", errors="ignore"):
                files_with_registration.append(str(py_file.relative_to(repo_path)))
        except Exception:
            continue

    if len(files_with_registration) > 1:
        names = ", ".join(files_with_registration)
        return [
            f"  register_tool() found in {len(files_with_registration)} files (must be exactly 1): {names}"
        ]
    return []


def check_direct_llm_imports(repo_path: Path, all_files: bool = False) -> list[str]:
    """Check for direct LLM library imports in src/ Python files.

    All LLM access must go through local_first_common.providers so that
    provider switching, model tracking, and timed_run work correctly.
    """
    if repo_path.name in EXEMPT_REPOS:
        return []

    src_dir = repo_path / "src"
    findings = []
    for filename in _get_files(repo_path, all_files):
        path = repo_path / filename
        if path.suffix != ".py" or not path.exists():
            continue
        # Only flag files inside src/
        try:
            path.relative_to(src_dir)
        except ValueError:
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for match in DIRECT_LLM_IMPORT_RE.finditer(content):
            line_num = content[: match.start()].count("\n") + 1
            findings.append(
                f"  {filename}:{line_num} — direct LLM import: {match.group().strip()!r} "
                f"(use local_first_common.providers instead)"
            )
    return findings


def check_tracked_bytecode(repo_path: Path) -> list[str]:
    """Check that no .pyc files or __pycache__ directories are tracked by git.

    Bytecode files are machine-specific and should never be committed.
    They are usually caught by .gitignore, but can sneak in if .gitignore
    was added after the first commit.
    """
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=repo_path,
            capture_output=True,
            text=True,
        )
        tracked = result.stdout.splitlines()
    except Exception:
        return []

    findings = []
    for f in tracked:
        if f.endswith(".pyc") or f.endswith(".pyo") or "__pycache__" in f:
            findings.append(f"  tracked bytecode file: {f}  (run: git rm --cached {f!r})")
    return findings


def check_main_entry_point(repo_path: Path) -> list[str]:
    """Check src/main.py for relative imports, which break the installed entry point.

    src/ is not a package — it's a source root.  Using 'from .module import x'
    in src/main.py causes ImportError when the installed script is invoked.
    Use absolute imports instead: 'from package_name.module import x'.
    """
    main_py = repo_path / "src" / "main.py"
    if not main_py.exists():
        return []
    try:
        content = main_py.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []

    findings = []
    relative_import_re = re.compile(r"^\s*from\s+\.", re.MULTILINE)
    for match in relative_import_re.finditer(content):
        line_num = content[: match.start()].count("\n") + 1
        line = content.splitlines()[line_num - 1].strip()
        findings.append(
            f"  src/main.py:{line_num} — relative import in entry-point file: {line!r}  "
            f"(use absolute import, e.g. 'from package_name.module import app')"
        )
    return findings


def check_test_coverage(repo_path: Path) -> list[str]:
    """Check that test coverage is at least 50% if tests exist."""
    tests_dir = repo_path / "tests"
    if not tests_dir.exists():
        return []

    try:
        # Run pytest with coverage and check if it fails the threshold
        # We use -q to keep it quiet and --cov-fail-under=50
        result = subprocess.run(
            ["uv", "run", "pytest", "-q", "--cov=src", "--cov-fail-under=50"],
            cwd=repo_path,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            # If it failed due to coverage, find the total coverage line
            if "Required test coverage of 50% not reached" in result.stdout:
                match = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", result.stdout)
                val = match.group(1) if match else "below 50"
                return [f"  Test coverage too low: {val}% (minimum 50%)"]
            elif "unrecognized arguments: --cov=src" in result.stderr:
                return ["  pytest-cov not installed or configured in pyproject.toml"]
            else:
                # Other test failure
                return [f"  Tests failed (exit code {result.returncode})"]
        return []
    except Exception as e:
        return [f"  Error running coverage check: {e}"]


# ── Runner ────────────────────────────────────────────────────────────────────

def run_scan(repo_path: Path, all_files: bool = False, verbose: bool = False) -> bool:
    """Run all pre-commit checks. Returns True if clean, False if issues found."""
    all_findings: dict[str, list[str]] = {}

    checks = [
        ("Personal paths", lambda p: check_personal_paths(p, all_files)),
        ("Gitignore coverage", check_gitignore),
        ("Sensitive filenames", lambda p: check_sensitive_filenames(p, all_files)),
        ("Typer anti-pattern", lambda p: check_typer_antipattern(p, all_files)),
        ("Duplicate register_tool", check_duplicate_register_tool),
        ("Direct LLM imports", lambda p: check_direct_llm_imports(p, all_files)),
        ("Tracked bytecode", check_tracked_bytecode),
        ("Entry-point imports", check_main_entry_point),
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
