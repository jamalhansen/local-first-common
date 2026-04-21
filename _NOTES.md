# local-first-common — Dev Notes

Running log of decisions, discoveries, and architectural changes.
This file is the primary source for pattern extraction and blog post origin stories.

**Rule:** When something breaks, when you change an approach, or when a model surprises you -- write it here before moving on. The why matters more than the what.

---

## How to run

```bash
# Run all tests
uv run pytest

# Lint check
uv run ruff check src/

# Install hooks across all repos
python3 install_hooks.py --all
```

---

## Architecture

### Config: TOML functions, not pydantic-settings

**What:** `config.py` exposes three plain functions: `load_config(tool_name)`, `get_setting(tool_name, key, cli_val, default)`, `init_config(tool_name, defaults)`. Config files live at `~/.config/local-first/<tool>.toml`.

**Why:** Gemini rewrote this from a `pydantic_settings`-based `LocalFirstSettings` class during a cli.py refactor (2026-04-18). The pydantic-settings approach required a subclass per tool; the TOML approach is tool-agnostic. `pydantic-settings` was removed from `pyproject.toml` as an orphaned dependency.

**Tradeoff:** No type validation on config values. Callers must handle `None` from `get_setting` themselves.

### CLI helpers: flag strings only, no defaults

**What:** All helpers in `cli.py` (`dry_run_option`, `no_llm_option`, `provider_option`, etc.) return a `typer.Option(...)` containing only flag strings and help text. No default values.

**Why:** Gemini changed this during a helpers cleanup (2026-04-18). The original helpers bundled the default (`typer.Option(False, "--dry-run", ...)`) which allowed the non-Annotated style `param: bool = helper()`. After the change, that style fails: Typer/Click sees `"--dry-run"` as the boolean default and raises `'--dry-run' is not a valid boolean` at parse time.

**Consequence:** All 16 tool repos had to be migrated to `Annotated` in the same session. See Changes Log 2026-04-18.

**Tradeoff:** The `Annotated` style is more verbose but explicit and consistent. It's now enforced by `make check-standards`.

---

## Changes Log

### 2026-04-20 — Split processing and operational DB defaults again

**Changed:** Restored `tracking.py` to default back to `~/sync/local-first/processing_log.duckdb` for processing telemetry, and moved `logging.py` plus operational reports to `~/sync/logging/error_log.duckdb` with `LOCAL_FIRST_ERROR_LOG_DB` as the override.

**Because:** Processing telemetry (`processing_log`) and operational warning/error persistence (`operational_log`) were conflated into one default path, which blurred the difference between the table purpose and the physical database file.

**Learned:** Shared storage defaults need to follow data ownership, not convenience. A report that queries `operational_log` should default to the operational log file, not the processing telemetry file.

### 2026-04-18 — Tracking swallow paths now emit structured warnings

**Changed:** Updated `tracking.py` to log structured `WARNING` records (with `run_context` and `source_location`) for previously silent failure paths: `log_run()` insert failures, `timed_run` persistence failures, `register_tool()` registration failures, `tracked_fetch` insert failures, and `usage()` metadata extraction errors.

**Because:** A failed council run was hard to verify after the fact due to logging blind spots. Some tracking failures only emitted `warnings.warn` or were swallowed with `pass`, so they could be missed in operational analysis.

**Learned:** Non-raising telemetry code still needs durable visibility. Emitting both Python warnings and structured logger warnings preserves safety (never crash caller) while making failures queryable in `operational_log` when persistent logging is enabled.

### 2026-04-18 — Provider wrappers now log API/model/parse retry signals

**Changed:** Added structured warning logs in `providers/base.py` and individual provider adapters (`ollama`, `anthropic`, `groq`, `deepseek`, `gemini`) for model-not-found branches, HTTP/request failures, schema-retry loops, and JSON parse fallback failures.

**Because:** Provider wrappers were re-raising clean RuntimeErrors but often lacked durable context about where failures happened. This made postmortems harder when a run failed under strict schema validation.

**Learned:** Logging before re-raise gives both user-facing clarity (exception message) and ops visibility (context-rich warning row) without changing control flow.

### 2026-04-18 — Added provider failure ops script

**Changed:** Added `scripts/provider_failure_report.py` to summarize provider-related operational failures by `run_context`, model (`source_location`), and recent examples over a configurable lookback window.

**Because:** Once provider-layer warning logging was added, a focused query entrypoint was needed to inspect those signals quickly without crafting ad-hoc SQL each time.

**Learned:** A small, dedicated ops script speeds incident triage and makes cross-tool provider reliability easier to monitor.

### 2026-04-18 — Workspace-wide Annotated migration (forced)

**Changed:** All 16 tool repos migrated from `param: type = helper()` to `param: Annotated[type, helper()] = default`.

**Because:** Gemini's cli.py refactor stripped default values from helpers. The non-Annotated style passed `"--dry-run"` as the boolean default, causing Click parse errors on every tool at startup. The fix could not be a revert (blog-post-draft-reviewer and promo-generator had already migrated to Annotated).

**Learned:** When a shared helper changes its contract, every caller breaks simultaneously. The Makefile anti-pattern check (`grep` for `typer.Option(os.environ` and `typer.Option("` without leading `--`) now exists to catch this before it ships. Test suites caught the breakage; the Makefile check now catches the pattern at commit time.

**Also fixed in the same session:**

- `weekly-thread-triage scan`: was passing ISO week string `"2026-W11"` to `get_week_dates()`, which always expected a `date` object. Fixed with `date.fromisocalendar()` parse.
- `marketing-persona-counsel` and `pedantic-troll`: Gemini left `...` placeholders at column 0 inside `if` blocks, causing `IndentationError` at import. Fixed by restructuring the blocks.
- `transcription-summarizer`: parameter named `provider_name` but body referenced `provider`. Fixed by renaming to `provider`.

### 2026-04-18 — Typer anti-pattern check restored in Makefile.workspace

**Changed:** `make check-standards` now greps for non-Annotated Typer patterns and fails if found. The check was silently dropped by Gemini during a Makefile refactor (the `done;` closing the loop was also dropped, swallowing the exit code).

**Because:** The check was the only enforcement mechanism preventing the Annotated regression. Without it, the next Gemini session could re-introduce the anti-pattern undetected.

**Learned:** A verification tool that doesn't fail is not a verification tool. The Makefile was printing `[PASS]` and exiting 0 on broken repos. See the BartBot post.

### 2026-04-18 — `pydantic-settings` removed from pyproject.toml

**Changed:** Removed `pydantic-settings>=2.13.1` from dependencies.

**Because:** `config.py` was rewritten to use TOML; `pydantic-settings` was no longer imported anywhere. The dependency was orphaned.

### 2026-04-18 — Persistent warning/error logging added to shared setup

**Changed:** `local_first_common.logging.setup_logging()` now supports a DuckDB-backed `OperationalLogHandler` that persists `WARNING` and above in an `operational_log` table. Added retention purge support (`LOCAL_FIRST_LOG_RETENTION_DAYS`, default 90), plus `purge_old_logs()` and `resolve_log_db_path()` helpers.

**Because:** The remediation plan found drift and hidden failures across tools. Console-only logging made recurring errors hard to inspect across repos. Persisting warnings/errors in the same tracking DB enables lightweight operational reporting and catches regressions earlier.

**Learned:** Shared logging must be part of tool startup, not optional per tool, or adoption drifts quickly. Pilot repos (`content-discovery-agent`, `promo-generator`, `weekly-review-generator`) were updated to call shared setup with `tool_name` so cross-repo queries become practical.

### 2026-04-18 — Phase 3 smoke coverage expanded across repos and CI

**Changed:** Added targeted smoke tests in shared-library suites for config-load failure handling, provider model discovery, operational warning/error persistence, and retention cleanup. Added a workspace CI workflow (`.github/workflows/phase3-smoke.yml`) that runs targeted smoke suites in `local-first-common`, `promo-generator`, `content-discovery-agent`, and `weekly-review-generator`.

**Because:** Shared-library regressions were still leaking into tool repos because only local tests were running by default. The CI matrix now checks the exact cross-repo paths that drifted before.

**Learned:** Small, deterministic smoke suites catch API drift earlier than broad end-to-end tests and are practical to enforce on every PR.

### 2026-04-18 — Phase 3 matrix expanded beyond pilot repos

**Changed:** Expanded `.github/workflows/phase3-smoke.yml` to include smoke jobs for `brand-voice-validator`, `frontmatter-validator`, `newsletter-prep-assistant`, and `resource-summarizer` in addition to the original pilot set.

**Because:** Shared-contract regressions can appear in non-pilot tools first; broader matrix coverage improves early detection before full workspace tests are run.

**Learned:** A small per-repo smoke command (not full suite) gives good regression signal while keeping CI runtime predictable.

### 2026-04-18 — Added fast script-entrypoint import gate in Phase 3 CI

**Changed:** Added an `entrypoint-imports` job in `.github/workflows/phase3-smoke.yml` that syncs each matrix repo and imports the first `[project.scripts]` module target from `pyproject.toml`.

**Because:** Some regressions show up as module wiring/import errors before tests run; this provides a fast, deterministic pre-test signal.

**Learned:** Separating import-wiring checks from behavior tests improves diagnosis speed in CI.

---

## Patterns Observed

- **Silent exit codes hide real failures:** Any Makefile loop that uses `echo [FAIL]` without incrementing a failure counter or setting `exit 1` produces a green dashboard for a broken system. The FAILED counter pattern (increment + final `exit $FAILED`) is the correct approach.
- **Shared helper contract changes cascade instantly:** When a helper used by 16 repos changes what it returns, all 16 break at the same time. Changes to `cli.py` helpers require an immediate workspace-wide audit.
- **Annotated makes defaults explicit:** Non-Annotated Typer style hides the default inside the helper call. Annotated puts the default at the call site, making it visible and checkable. This is why it's now required.
