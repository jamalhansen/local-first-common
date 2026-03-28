# local-first-common

Shared utilities for local-first AI tools. Extracts the common plumbing — LLM providers, config management, logging, Obsidian vault I/O, social media fetching, Typer CLI helpers, and test utilities.

## Installation

Add as a git dependency in any project's `pyproject.toml`:

```toml
[project.dependencies]
local-first-common = {git = "https://github.com/jamalhansen/local-first-common.git", branch = "main"}
```

Then run `uv sync`.

### Local development override

When actively changing this library alongside a project, use `uv` to link it locally:

```bash
uv add --editable ../local-first-common
```

## What's included

### `local_first_common.providers`

Multi-provider LLM abstraction with native **async** and **vision** support. All providers share a common interface: `complete(...)` and `acomplete(...)`.

```python
from local_first_common.providers import PROVIDERS

provider = PROVIDERS["ollama"]()
# Sync
result = provider.complete("sys", "user")
# Async
result = await provider.acomplete("sys", "user")

# Vision (Base64 strings)
result = provider.complete("describe", "img", images=["..."])
```

**Available providers:** `ollama`, `anthropic`, `gemini`, `groq`, `deepseek`.

#### Intelligent Model Discovery (Ollama)

The toolkit can recommend the best-fit Ollama models based on your current machine's hardware (RAM). This is **on-demand only** and never intrusive.

**1. Using Intent-based Aliases**
You can ask for a recommendation by passing an alias to the `--model` flag:

- `@best`: The highest-quality model your machine can comfortably run (e.g., `phi4` on a Mac Mini, `phi4-mini` on a MacBook Air).
- `@fast`: The lowest-latency model installed (e.g., `phi4-mini` or `llama3.2:1b`).
- `@vision`: The best installed model with vision capabilities (e.g., `llama3.2-vision` or `llava`).
- `@encoding`: Optimized for embeddings and fast processing.

**2. The Management CLI**
Run the shared management tool to see what is recommended for your current machine:

```bash
uv run local-first recommend
```

If you omit the `--model` flag entirely, the tool uses the provider's standard default model (e.g., `phi4-mini`) without performing discovery.

---

### `local_first_common.config`

Centralized environment variable handling via Pydantic `BaseSettings`. Loads from ENV or `.env` files.

```python
from local_first_common.config import settings

print(settings.obsidian_vault_path)
print(settings.model_provider)

# Standardized data paths
db_path = settings.get_db_path("my-tool", "cache.db")
# ~/.local/share/local-ai-tools/my-tool/cache.db
```

---

### `local_first_common.logging`

Standardized Rich-based logging.

```python
from local_first_common.logging import setup_logging
import logging

setup_logging(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.info("Tool started [bold cyan]successfully[/]")
```

---

### `local_first_common.social`

Centralized social media fetching logic for Bluesky and Mastodon.

```python
from local_first_common.social import bluesky, mastodon

# Fetch from Bluesky
posts = bluesky.fetch_posts(["#python", "localai"], limit=10)
# Fetch from Mastodon
statuses = mastodon.fetch_posts(["#ai"], instances=["mastodon.social"])
```

---

### `local_first_common.obsidian`

Utilities for reading and writing Obsidian markdown vaults. Standardizes vault discovery and note loading.

---

### `local_first_common.cli`

Typer option factories for consistent CLI flags across all tools.

```python
@app.command()
def run(
    provider: Annotated[str, provider_option(PROVIDERS)] = "ollama",
    model: Annotated[Optional[str], model_option()] = None,
    dry_run: Annotated[bool, dry_run_option()] = False,
    verbose: Annotated[bool, verbose_option()] = False,
    debug: Annotated[bool, debug_option()] = False,
):
    # setup_logging is automatically called inside resolve_provider
    llm = resolve_provider(PROVIDERS, provider, model, debug=debug, verbose=verbose)
```

---

### `local_first_common.testing`

`MockProvider` for deterministic unit testing. Now supports `acomplete` and `images`.

---

### `local_first_common.llm`

LLM response parsing utilities.

```python
from local_first_common.llm import parse_json_response, try_xml_parse

# Strip ```json fences and parse
data = parse_json_response(raw)

# XML fallback for local models that garble JSON
xml = try_xml_parse(raw, ["score", "summary", "language", "tags"])
# Returns dict if all fields found, None if any missing
```

---

### `local_first_common.scoring`

Base class for LLM-based content scorers. Handles JSON parsing with XML fallback, provider error catching, and parse failure counting.

```python
from local_first_common.scoring import BaseScorer, ScoredItem

class MyScorer(BaseScorer):
    system_prompt = "Return JSON with score, tags, summary, language."

scorer = MyScorer()
result = scorer.score(provider, user_message)
# result: ScoredItem(score=0.85, tags=["ai"], summary="...", language="en") | None

# Counters for tracking (wire to timed_run):
scorer.xml_fallback_count   # times XML fallback was used
scorer.parse_error_count    # times both JSON and XML failed
```

---

### `local_first_common.readwise`

Readwise Reader API integration.

```python
from local_first_common.readwise import save_to_readwise

ok = save_to_readwise(
    token,
    "https://example.com/article",
    title="Article Title",
    summary="One sentence summary.",
    tags=["ai", "python"],
    published_date="2026-03-01",
)
```

---

### `local_first_common.models`

Pydantic model for Obsidian frontmatter. Use for any tool that reads or writes structured vault notes.

```python
from local_first_common.models import ContentMetadata
import frontmatter

post = frontmatter.load(path)
meta = ContentMetadata.from_metadata(post.metadata)

meta.tags           # List[str] — bare "ai" string → ["ai"] automatically
meta.category       # str — "[[Newsletter]]" or "uncategorized" (default)
meta.category_name  # str — strips brackets: "Newsletter"
meta.published_date # Optional[datetime] — "" coerced to None
meta.status         # str — defaults to "draft"
meta.title          # Optional[str] — accepts both "title" and "Title" frontmatter keys

# Write back — omits None fields and the "uncategorized" default
post.metadata = meta.to_metadata()
frontmatter.dump(post, path)
```

**Category convention:** `Category` is a wikilink to an Obsidian template, e.g. `[[Newsletter]]`. Notes without a `Category` field parse fine and get `category = "uncategorized"` — query this to find notes that still need categorising.

---

### `local_first_common.tracking`

DuckDB-backed run logging. Tracks every LLM call: tool, model, duration, item count, token usage, and parse quality counters.

```python
from local_first_common.tracking import register_tool, timed_run

_TOOL = register_tool("my-tool")  # once at startup

with timed_run("my-tool", provider.model, source_location=url) as run:
    results = process_items(items)
    run.item_count = len(results)
    run.xml_fallbacks = scorer.xml_fallback_count or None
    run.parse_errors = scorer.parse_error_count or None
```

DB: `~/sync/local-first/processing_log.duckdb` (override: `LOCAL_FIRST_TRACKING_DB`).

## Workspace Orchestration

This repository contains a `Makefile.workspace` designed to manage the entire local-first AI toolkit from the workspace root. 

### Setup

To use the global commands, create a symlink in your workspace root:

```bash
ln -s local-first-common/Makefile.workspace Makefile
```

### Available Commands

Run these from the workspace root:

- `make list`: Show all tools in the workspace.
- `make sync`: Run `uv sync` across all projects.
- `make test`: Run all test suites.
- `make check`: Run `ruff` linting across the workspace.
- `make pre-commit`: Run all verification steps (ruff, tests, security) for all projects.
- `make status`: Show which sub-repositories have uncommitted changes.
- `make verify`: Ensure all tools strictly adhere to the `main.py` entry point standard.

## Pre-push security hooks

Install secret scanning and path sanitization hooks across all repos:

```bash
python3 install_hooks.py --all
```

## Adding a new provider

1. Create `src/local_first_common/providers/myprovider.py` subclassing `BaseProvider`.
2. Implement both `complete` and `acomplete`.
3. Add it to `PROVIDERS` in `src/local_first_common/providers/__init__.py`.
