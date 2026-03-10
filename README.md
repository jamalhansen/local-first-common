# local-first-common

Shared utilities for local-first AI tools. Extracts the common plumbing — LLM providers, Obsidian vault I/O, Typer CLI helpers, and test utilities — so each tool stays focused on what it actually does.

## Installation

Add as a git dependency in any project's `pyproject.toml`:

```toml
[project.dependencies]
local-first-common = {git = "https://github.com/jamalhansen/local-first-common.git", branch = "main"}
```

Then run `uv sync`.

### Local development override

When actively changing this library alongside a project, add a `uv.toml` in the project directory (gitignored) to point at your local clone:

```toml
# uv.toml  (add to .gitignore)
[sources]
local-first-common = {path = "../local-first-common", editable = true}
```

## What's included

### `local_first_common.providers`

Multi-provider LLM abstraction. All providers share a common interface: `complete(system, user, response_model=None) -> str | dict`.

Pass a Pydantic model as `response_model` to get back a parsed `dict`. Omit it to get a plain `str`.

```python
from local_first_common.providers import PROVIDERS

provider = PROVIDERS["ollama"]()
result = provider.complete("You are a helpful assistant.", "Summarise this in 3 bullets.")

# Structured output via Pydantic
from pydantic import BaseModel

class Summary(BaseModel):
    bullets: list[str]
    confidence: int

result = provider.complete("...", "...", response_model=Summary)
# {"bullets": [...], "confidence": 8}
```

**Available providers:**

| Key | Class | Default model | Requires |
|---|---|---|---|
| `ollama` | `OllamaProvider` | `phi4-mini` | Ollama running locally |
| `anthropic` | `AnthropicProvider` | `claude-haiku-4-5-20251001` | `ANTHROPIC_API_KEY` + `uv add anthropic` |
| `gemini` | `GeminiProvider` | `gemini-2.0-flash` | `GEMINI_API_KEY` + `uv add google-genai` |
| `groq` | `GroqProvider` | `llama-3.3-70b-versatile` | `GROQ_API_KEY` |
| `deepseek` | `DeepSeekProvider` | `deepseek-chat` | `DEEPSEEK_API_KEY` |

`anthropic` and `google-genai` SDKs are lazy-imported — only need to be installed in projects that actually use those providers.

Override the model at instantiation time:

```python
provider = PROVIDERS["anthropic"](model="claude-sonnet-4-6")
provider = PROVIDERS["ollama"](model="llama3.2:3b")
```

---

### `local_first_common.obsidian`

Utilities for reading and writing Obsidian markdown vaults.

```python
from local_first_common.obsidian import (
    find_vault_root,
    get_daily_note_path,
    get_week_dates,
    append_to_daily_note,
    render_obsidian_template,
    load_daily_notes_for_week,
    iter_daily_notes,
    format_notes_for_llm,
)
from datetime import date
from pathlib import Path

# Locate vault (reads OBSIDIAN_VAULT_PATH env var, or walks up for .obsidian/)
vault = find_vault_root()

# Daily note path
path = get_daily_note_path(vault, date.today(), subdir="Timeline")

# Append a section to a daily note (creates file + parent dirs if needed)
append_to_daily_note(path, "## Voice Journal\n\n- Thought one\n")

# Load a week of notes for an LLM prompt
dates = get_week_dates(date.today())
notes = load_daily_notes_for_week(vault, dates, subdir="Timeline")
prompt_text = format_notes_for_llm(notes)

# Render Obsidian template variables
render_obsidian_template("{{date:YYYY-MM-DD}}", date.today())  # "2026-03-10"
render_obsidian_template("{{yesterday}}", date.today())        # "2026-03-09"
```

**`find_vault_root(env_var="OBSIDIAN_VAULT_PATH")`** — checks env var first, then walks up looking for `.obsidian/`, falls back to cwd.

**`append_to_daily_note(note_path, content, template_path=None)`** — appends to an existing note with `---` separator, or creates a new one rendered from a template.

---

### `local_first_common.cli`

Typer option factories for consistent `--provider`, `--model`, `--dry-run`, `--verbose`, `--debug` flags across all tools.

```python
import typer
from typing import Annotated, Optional
from local_first_common.providers import PROVIDERS
from local_first_common.cli import (
    provider_option, model_option, dry_run_option,
    verbose_option, debug_option, resolve_provider,
)

app = typer.Typer()

@app.command()
def run(
    provider: Annotated[str, provider_option(PROVIDERS)] = "ollama",
    model: Annotated[Optional[str], model_option()] = None,
    dry_run: Annotated[bool, dry_run_option()] = False,
    verbose: Annotated[bool, verbose_option()] = False,
    debug: Annotated[bool, debug_option()] = False,
):
    llm = resolve_provider(PROVIDERS, provider, model, debug=debug)
    ...
```

**`provider_option(providers, default="ollama")`** — respects the `MODEL_PROVIDER` env var as a fallback default.

**`resolve_provider(providers, name, model, debug=False)`** — instantiates the named provider; raises `typer.BadParameter` with valid options listed on unknown names.

---

### `local_first_common.testing`

`MockProvider` for use in project test suites. Records all calls, returns preset responses, optionally raises errors.

```python
from local_first_common.testing import MockProvider

def test_my_feature():
    provider = MockProvider(response='{"score": 9, "summary": "Great post"}')

    # Plain string response
    result = provider.complete("system prompt", "user message")
    assert result == '{"score": 9, "summary": "Great post"}'

    # Structured output
    from pydantic import BaseModel
    class Score(BaseModel):
        score: int
        summary: str

    result = provider.complete("sys", "usr", response_model=Score)
    assert result["score"] == 9

    # Call history
    assert len(provider.calls) == 2
    assert provider.calls[0] == ("system prompt", "user message")

    # Error path testing
    failing = MockProvider(response="x", raise_error="API unavailable")
    with pytest.raises(RuntimeError, match="API unavailable"):
        failing.complete("sys", "usr")
```

## Project structure

```
src/local_first_common/
├── __init__.py
├── providers/
│   ├── __init__.py      # PROVIDERS dict + all exports
│   ├── base.py          # BaseProvider ABC
│   ├── ollama.py        # httpx-based, no SDK required
│   ├── anthropic.py     # lazy import: uv add anthropic
│   ├── groq.py          # httpx-based
│   ├── deepseek.py      # httpx-based
│   └── gemini.py        # lazy import: uv add google-genai
├── obsidian.py          # Vault I/O utilities
├── cli.py               # Typer option helpers
└── testing.py           # MockProvider
tests/
├── test_providers.py    # 45 tests, all providers mocked
├── test_obsidian.py     # 21 tests, file I/O via tmp_path
└── test_testing.py      # 6 tests
```

## Running tests

```bash
uv run pytest
```

## Adding a new provider

1. Create `src/local_first_common/providers/myprovider.py` subclassing `BaseProvider`
2. Add it to `PROVIDERS` in `src/local_first_common/providers/__init__.py`
3. Add a `TestMyProvider` class in `tests/test_providers.py`
