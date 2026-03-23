# Local-First AI Tools: CLI Standards

To ensure a predictable and safe user experience across the entire toolkit, all tools follow these standard CLI parameter patterns.

## Standard Parameters

### `--dry-run` (short: `-n`)
*   **Definition**: "No Side-Effects" mode.
*   **Behavior**: Perform all application logic, including calling the LLM backend to generate content, but **do not persist** the results to permanent storage.
*   **Persistence targets**: Obsidian vault, SQLite databases, files on disk, or external APIs (e.g., Readwise).
*   **Output**: Always print the final result or a detailed summary of what *would* have happened to `stdout`.
*   **Use Case**: "Show me the actual AI response before I save it to my vault."

### `--no-llm`
*   **Definition**: "Skip AI" mode.
*   **Behavior**: Do not call any LLM provider (Ollama, Anthropic, etc.). Instead, use mock responses (e.g., `[LLM MOCK RESPONSE]`) for any AI-generated fields.
*   **Interaction**: **Implies `--dry-run`**. It is generally unsafe or useless to persist mock data.
*   **Use Case**: "Test my CLI arguments, file parsing, and template rendering instantly without spending tokens or waiting for inference."

### `--provider` (short: `-p`)
*   **Behavior**: Choose the LLM backend.
*   **Choices**: `ollama`, `anthropic`, `gemini`, `groq`, `deepseek`, or `mock`.
*   **Default**: Defaults to `ollama` (local) unless the `MODEL_PROVIDER` environment variable is set.

### `--model` (short: `-m`)
*   **Behavior**: Override the default model for the chosen provider.
*   **Special Aliases**: For `ollama`, supports aliases like `@fast`, `@best`, and `@vision` which resolve to appropriate models based on your machine's hardware profile.

### `--verbose` (short: `-v`)
*   **Behavior**: Show extra progress information, such as which files are being processed or intermediate logic steps.

### `--debug` (short: `-d`)
*   **Behavior**: Show raw prompts sent to the LLM and the raw responses received.

---

## Run Tracking

Every tool must register itself and log each LLM run to the central DuckDB
at `~/sync/local-first/processing_log.duckdb`.

### `register_tool(name)` — required for all tools

Call once at module load (after all imports, before any function definitions).
This inserts a row into the `tools` table the first time the tool runs and is
a no-op on subsequent runs.

```python
from local_first_common.tracking import register_tool, timed_run

_TOOL = register_tool("my-tool-name")
```

### `timed_run(...)` — required for every LLM call

Wrap each LLM call in a `timed_run` context manager. Set `item_count`,
`input_tokens`, and `output_tokens` inside the block so they're captured in
`processing_log`.

```python
with timed_run("my-tool-name", llm.model, source_location=source) as _run:
    result = llm.complete(system, user)
    _run.item_count = 1
    _run.input_tokens = getattr(llm, "input_tokens", None) or None
    _run.output_tokens = getattr(llm, "output_tokens", None) or None
```

- `input_tokens` / `output_tokens`: populated automatically for Anthropic and
  Groq providers. Ollama and mock providers leave these `None`.
- `source_location`: a URL, file path, or date string identifying what was
  processed.

### `tracked_fetch(tool, url, ...)` — required for tools that fetch external URLs

If your tool fetches article URLs found in social posts or elsewhere, use
`tracked_fetch` (via `fetch_article_metadata`) instead of calling
`http.fetch_url` directly. This logs every attempt to `fetch_log` with HTTP
status, duration, and source lineage.

```python
from local_first_common.article_fetcher import fetch_article_metadata

item = fetch_article_metadata(
    url,
    tool=_TOOL,
    source_url=post_url,       # the social post where the link was found
    source_platform="bluesky", # 'bluesky', 'mastodon', etc.
)
```

If your tool fetches URLs that aren't from social posts (e.g. user-supplied),
use `tracked_fetch` directly:

```python
from local_first_common.tracking import tracked_fetch

with tracked_fetch(_TOOL, url) as fetch:
    if fetch.html is None:
        raise RuntimeError(f"Failed to fetch: {fetch.error_message}")
    fetch.title = parse_title(fetch.html)
    # use fetch.html ...
```

---

## Implementation for Developers

When building a new tool, use the helpers in `local_first_common.cli`:

```python
from local_first_common.cli import (
    dry_run_option,
    no_llm_option,
    resolve_dry_run,
    resolve_provider,
)

@app.command()
def run(
    dry_run: Annotated[bool, dry_run_option()] = False,
    no_llm: Annotated[bool, no_llm_option()] = False,
    # ... other options
):
    # Standard rule: --no-llm always implies --dry-run
    dry_run = resolve_dry_run(dry_run, no_llm)
        
    llm = resolve_provider(PROVIDERS, provider_name, model, no_llm=no_llm)
    
    # ... logic ...
    
    # llm.complete() automatically handles JSON parsing, retries on 
    # validation failure (if response_model is provided), and provides
    # mock data in --no-llm mode.
    result = llm.complete(system, user, response_model=MySchema)
    
    if dry_run:
        print(result)
    else:
        save(result)
```
