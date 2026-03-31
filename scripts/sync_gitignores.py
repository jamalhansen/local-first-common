from pathlib import Path

# Master list of ignore patterns to ensure are present in all workspace repos
MASTER_IGNORES = {
    ".DS_Store",
    ".pytest_cache/",
    ".ruff_cache/",
    ".coverage",
    ".venv/",
    "__pycache__/",
    ".env",
    ".envrc",
    "CLAUDE.md",
    "uv.toml",
    "*.pyc",
    "*.pyo",
    "*.pyd",
}

def sync_gitignore(repo_path: Path):
    gitignore_path = repo_path / ".gitignore"
    if not gitignore_path.exists():
        print(f"  [CREATE] {repo_path.name}/.gitignore")
        existing_lines = set()
    else:
        with open(gitignore_path, "r") as f:
            existing_lines = {line.strip() for line in f if line.strip() and not line.startswith("#")}

    missing = MASTER_IGNORES - existing_lines
    if missing:
        print(f"  [UPDATE] {repo_path.name}/.gitignore - adding {len(missing)} entries")
        with open(gitignore_path, "a") as f:
            if existing_lines:
                f.write("\n")
            f.write("# Workspace standard ignores\n")
            for pattern in sorted(missing):
                f.write(f"{pattern}\n")
    else:
        print(f"  [OK]     {repo_path.name}/.gitignore")

def main():
    workspace_root = Path(__file__).parent.parent.parent
    repos = [
        d for d in workspace_root.iterdir() 
        if d.is_dir() and (d / "pyproject.toml").exists()
    ]
    
    print(f"Syncing standard .gitignore to {len(repos)} repos...")
    for repo in sorted(repos):
        sync_gitignore(repo)

if __name__ == "__main__":
    main()
