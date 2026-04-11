"""Pre-commit security scanner for local-first projects.

Extends py-tooling's general scanner with local-first-specific checks:
  - Duplicate register_tool() across multiple source files
  - Direct LLM library imports (must use local-first-common providers)

All general checks (personal paths, gitignore, sensitive filenames, bytecode,
entry-point imports, Typer anti-pattern) come from py-tooling.

Run as pre-commit hook (staged files only):
    Automatically called by git — installed by install_hooks.py

Run as full scan across all tracked files:
    python3 scripts/pre_commit_check.py [path] --all-files [--verbose]
"""

import re
import sys
from pathlib import Path

# ── py-tooling base scanner ───────────────────────────────────────────────────

_PY_TOOLING = Path.home() / "projects" / "py-tooling"
sys.path.insert(0, str(_PY_TOOLING / "scripts"))
from pre_commit_check import run_scan as _base_scan  # noqa: E402

# ── Local-first-specific constants ───────────────────────────────────────────

# Repos exempt from LLM-import and register_tool checks
EXEMPT_REPOS = {"local-first-common", "local-first-mcp", "pebble", "local-ai-tool-template"}

DIRECT_LLM_IMPORT_RE = re.compile(
    r"""^(?:import|from)\s+(?:anthropic|openai|google\.generativeai|groq|ollama)\b""",
    re.MULTILINE,
)


# ── Local-first-specific checks ───────────────────────────────────────────────

def _get_staged_or_all(repo_path: Path, all_files: bool) -> list[str]:
    import subprocess
    cmd = ["git", "ls-files"] if all_files else ["git", "diff", "--cached", "--name-only"]
    result = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True)
    return [f.strip() for f in result.stdout.splitlines() if f.strip()]


def check_duplicate_register_tool(repo_path: Path) -> list[str]:
    """Check that register_tool() appears in at most one source file per repo."""
    src_dir = repo_path / "src"
    if not src_dir.exists() or repo_path.name in EXEMPT_REPOS:
        return []
    files_with_registration = [
        str(py_file.relative_to(repo_path))
        for py_file in src_dir.rglob("*.py")
        if "register_tool(" in py_file.read_text(encoding="utf-8", errors="ignore")
    ]
    if len(files_with_registration) > 1:
        names = ", ".join(files_with_registration)
        return [f"  register_tool() in {len(files_with_registration)} files (must be 1): {names}"]
    return []


def check_direct_llm_imports(repo_path: Path, all_files: bool = False) -> list[str]:
    """Check for direct LLM library imports — must go through local_first_common.providers."""
    if repo_path.name in EXEMPT_REPOS:
        return []
    src_dir = repo_path / "src"
    findings = []
    for filename in _get_staged_or_all(repo_path, all_files):
        path = repo_path / filename
        if path.suffix != ".py" or not path.exists():
            continue
        try:
            path.relative_to(src_dir)
        except ValueError:
            continue
        content = path.read_text(encoding="utf-8", errors="ignore")
        for match in DIRECT_LLM_IMPORT_RE.finditer(content):
            line_num = content[: match.start()].count("\n") + 1
            findings.append(
                f"  {filename}:{line_num} — direct LLM import: {match.group().strip()!r} "
                f"(use local_first_common.providers instead)"
            )
    return findings


# ── Runner ────────────────────────────────────────────────────────────────────

def run_scan(repo_path: Path, all_files: bool = False, verbose: bool = False) -> bool:
    """Run general + local-first-specific checks."""
    extra = [
        ("Duplicate register_tool", check_duplicate_register_tool),
        ("Direct LLM imports",      lambda p: check_direct_llm_imports(p, all_files)),
    ]
    return _base_scan(repo_path, all_files=all_files, verbose=verbose, extra_checks=extra)


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Pre-commit scanner for local-first projects")
    parser.add_argument("path", nargs="?", default=".", help="Repo path (default: current directory)")
    parser.add_argument("--all-files", action="store_true")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    repo_path = Path(args.path).resolve()
    ok = run_scan(repo_path, all_files=args.all_files, verbose=args.verbose)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
