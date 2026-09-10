# Local-First AI Tools: Ecosystem Architecture & Roadmap

This document outlines the current capabilities, architectural standards, and future development roadmap for the 28 repositories in this local-first AI ecosystem.

---

## 1. What The Ecosystem Unlocks Today

The toolkit has evolved from disconnected standalone scripts into a composable, observable, and scriptable local-first AI workstation.

### A. Unix Pipeline Composability (`-` / `--pipe`)
Tools support reading directly from `stdin` via `-` and streaming output to `stdout`, keeping diagnostics and progress on `stderr`.
```bash
# Validate brand voice, check Hugo frontmatter, and output clean markdown:
cat post-draft.md | brand-voice-validator - | fm-validate - > clean-post.md
```

### B. Machine-Readable Automation (`--json` / `-j`)
Query and extraction tools support a clean JSON output format for programmatic consumption, scripting with `jq`, or direct inspection by autonomous agents:
```bash
# Extract candidates found today and summarize them:
discover list-candidates --json | jq -r '.[].url' | xargs -n 1 summarize-resource --json

# Semantic search across your Obsidian vault:
vsearch search "local-first sync" --limit 3 --json | jq -r '.results[].path'

# Query unclosed threads:
thread-triage scan --json | jq '.pending_count'
```

### C. Reusable Workflow Recipes (`make pipeline-...`)
High-level workflows are encapsulated in the root workspace Makefile with dry-run support:
- **`make pipeline-publish POST=path/to/draft.md [DRY_RUN=1]`**: Brand voice validation $\to$ frontmatter validation $\to$ series cross-link suggestions $\to$ promotional copy generation.
- **`make pipeline-photos DIR=path/to/photos [MAX_DIM=1600] [DRY_RUN=1]`**: Vision LLM renaming $\to$ GPS/EXIF scrubbing $\to$ web dimension scaling.
- **`make pipeline-weekly [DRY_RUN=1]`**: Open thread triage $\to$ weekly review note draft $\to$ newsletter curation kit.

### D. Centralized Observability & Telemetry
- **Processing Log (`~/sync/logging/processing_log.duckdb`)**: Every LLM execution—including multi-agent Pydantic-AI councils (`persona-counsel`, `marketing-persona-counsel`)—logs model identifiers, latency, input tokens, and output tokens. Run `make usage` to inspect token spend and execution stats.
- **Error Log (`~/sync/logging/error_log.duckdb`)**: Production warnings and errors automatically persist with tool lineage and timestamps. Run `make ops-report` for operational reports.
- **Test Isolation**: Test suites isolate `LOCAL_FIRST_TRACKING_DB` and `LOCAL_FIRST_ERROR_LOG_DB`, ensuring zero production log pollution.

---

## 2. Core Architectural Standard: Retiring `logic.py`

### The Problem with `logic.py`
Many tool repositories historically contained a file named `logic.py` inherited from the original template. This created three major issues:
1. **Developer & Agent Confusion**: Having 20+ files named `logic.py` across different repositories makes editor tabs, stack traces, and multi-repo searches confusing and ambiguous.
2. **Conflation of Concerns**: `logic.py` frequently mixed CLI routing (Typer apps, Click argument parsing, Rich terminal styling, exit codes) with domain business logic (file I/O, LLM calls, parsing, data transformation).
3. **Impeded Library Reusability**: When domain logic is mixed into a Typer CLI file, importing a function in another tool or test forces imports of CLI dependencies, Rich consoles, and argument annotations.

### The New Standard: Strict Separation of Concerns
Every tool should follow this file structure:

```text
my-tool/
├── pyproject.toml              # [project.scripts] my-tool = "my_tool.cli:app"
├── src/
│   ├── main.py                 # Minimal 3-line stub: from my_tool.cli import app; app()
│   └── my_tool/
│       ├── __init__.py
│       ├── cli.py              # CLI ONLY: Typer app, options, Rich console, exit codes
│       ├── core.py             # Pure domain logic / orchestrator (or domain modules)
│       ├── schema.py           # Pydantic schemas / models (if applicable)
│       └── prompts.py          # LLM prompt templates (if applicable)
└── tests/
    ├── conftest.py             # Includes isolate_tracking_db
    ├── test_cli.py             # CliRunner invocation tests
    └── test_core.py            # Direct unit tests for domain functions
```

#### Naming Conventions:
- **`cli.py`**: The CLI entrypoint. Defines `app = typer.Typer(...)` and all `@app.command()` handlers. Handles CLI argument parsing, flags, Rich tables/panels, and `typer.Exit()`.
- **`core.py`** (or domain-specific names like `scanner.py`, `extractor.py`, `renderer.py`, `storage.py`): Pure Python functions that accept primitive or model arguments, perform operations, and return data. Does not raise `typer.Exit` or import `typer.Option`.
- **`logic.py` is deprecated**: New tools must not create `logic.py`. Existing tools will be refactored to `cli.py` and domain modules.

---

## 3. Phased Roadmap

### Phase 1: Retiring `logic.py` & Structural Refactoring
- [x] **Step 1.1: Modernize `local-ai-tool-template`**:
  - Replace `src/local_ai_tool_template/logic.py` with `cli.py` and `core.py`.
  - Update `[project.scripts]` to `process = "local_ai_tool_template.cli:app"`.
  - Update template tests and README.
- [x] **Step 1.2: Update Workspace Standards & Verification**:
  - Update `Makefile.workspace` (`fix-scriptable` and standards checks) to support and prefer `cli:app`.
  - Update `STANDARDS.md` to document the `cli.py` + `core.py` separation.
- [x] **Step 1.3: Refactor Clean Separation in Key Tools**:
  - All 25 tools across the workspace refactored from `logic.py` into dedicated `cli.py` (CLI parsing, Rich formatting, exit codes) and `core.py` (pure domain logic) with backward compatibility shims.
  - Script entry points updated across all `pyproject.toml` files to `<pkg>.cli:app`.
- [x] **Step 1.4: Refactor Monolithic Modules**:
  - `series-cross-link-suggester`: Split 680-line `logic.py` into `cli.py`, `scanner.py`, and `injector.py`.
  - `pebble`: Modularized into `cli.py`, `storage.py`, `inbox.py`, and `agents.py`.

### Phase 2: Autonomous Background Workflows (`launchd` / `cron`)
- [ ] **Step 2.1: Automated Discovery Intake**:
  - Create a lightweight `launchd` plist / cron recipe to run `discover run` periodically (e.g. every 2 hours).
  - Add optional automatic notification (via `osascript` or terminal-notifier) when new candidates score $\ge 0.85$.
- [ ] **Step 2.2: Sunday Night Weekly Review Batch**:
  - Automate `make pipeline-weekly` to execute every Sunday at 8:00 PM.
  - Automatically stage the draft weekly review note in Obsidian for Monday morning review.
- [ ] **Step 2.3: Inbound Photo Intake Watcher**:
  - Provide a script/daemon watching `~/Inbound-Photos` using `fswatch` to trigger `make pipeline-photos` upon new file drop.

### Phase 3: Cross-Tool Local Memory & Context Layer
- [x] **Step 3.1: Context Injection for Drafting & Review**:
  - `blog-post-draft-reviewer` and `promo-generator` query `vsearch` (via direct SQLite BM25 or hybrid search) for relevant background context from your Obsidian vault.
  - Injects recent related ideas, prior series installments, and cross-references directly into prompt contexts with `--vault-context/--no-vault-context`.
- [x] **Step 3.2: Persona Memory**:
  - Enable `persona-counsel` to pull prior council recommendations and dissonance reports automatically from past monthly notes via vsearch (SQLite BM25) and disk scan fallback with `--memory/--no-memory`.
- [x] **Step 3.3: Content Discovery Synergy**:
  - `content-discovery-agent`: Added `search_kept_items` in `store.py` and `discover search-kept` CLI command to search kept items by tag/topic/query.
  - `newsletter-prep-assistant`: Enabled `--topic` / `--tag` filtering of kept finds from the content-discovery SQLite archive with automatic topic inference from draft blog posts and fallback to recent finds.
  - `blog-post-draft-reviewer`: Enabled querying the content-discovery SQLite archive for saved research articles matching the draft being reviewed with `--discovery-context/--no-discovery-context`.

### Phase 4: Local SLM + Cloud Hybrid Tiering
- [x] **Step 4.1: Fast Local Tier (3B–8B SLMs)**:
  - Configure deterministic classification, frontmatter parsing, tag suggestions, and voice extraction to default to fast local models (e.g., `llama3.2:3b`, `qwen2.5-coder:7b`) via Ollama.
  - Target latency under 1 second with $0 token cost.
- [x] **Step 4.2: High-Reasoning Cloud Tier**:
  - Route creative synthesis, adversarial critique (`pedantic-troll`), and deep multi-perspective persona councils to frontier cloud models (`claude-3-7-sonnet`, `gemini-2.5-pro`) via `tier="reasoning"`.
- [x] **Step 4.3: Automatic Local-to-Cloud Fallback**:
  - Enhanced `local_first_common.providers` with `FallbackProvider` and integrated into `resolve_provider` to detect Ollama connection failures or timeouts and seamlessly fall back to an active cloud provider.

### Phase 5: Multi-Repo Portability Architecture Formally Retained
- [x] **Step 5.1: Workspace vs Multi-Repo Portability Evaluation**:
  - Evaluated native `uv [tool.uv.workspace]` monorepo structure against the workspace's 27 independent Git repositories.
  - Native `uv` workspace requires `workspace = true` in member `tool.uv.sources`, which inherently breaks standalone cloning, portability, and independent remote distribution on other machines.
  - Decision: Retain the multi-repo architecture to preserve standalone GitHub/Bitbucket repository portability.
- [x] **Step 5.2: Preserved `toggle_source.py` Workflow**:
  - Maintained `make use-local` (for fast local development across packages) and `make use-github` (for clean, portable Git commits and remote publishing).
  - Validated with pre-push portability hooks (`pre_push_check.py`) and automated `make verify` preflight across all 27 repositories.

