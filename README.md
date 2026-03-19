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

## Pre-push security hooks

Install secret scanning and path sanitization hooks across all repos:

```bash
python3 install_hooks.py --all
```

## Adding a new provider

1. Create `src/local_first_common/providers/myprovider.py` subclassing `BaseProvider`.
2. Implement both `complete` and `acomplete`.
3. Add it to `PROVIDERS` in `src/local_first_common/providers/__init__.py`.
