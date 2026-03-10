# local-first-common

Shared Python utilities for local-first tools, including LLM provider abstractions, Obsidian vault helpers, and test utilities.

## Installation

```bash
uv add "local-first-common @ git+https://github.com/jamalhansen/local-first-common.git@main"
```

## What's Included

- **`local_first_common.providers`** — Abstract `BaseProvider` plus implementations for Ollama, Anthropic, Groq, DeepSeek, and Gemini
- **`local_first_common.obsidian`** — Read/write helpers for Obsidian markdown vaults (daily notes, templates, frontmatter)
- **`local_first_common.testing`** — `MockProvider` for deterministic unit tests
- **`local_first_common.cli`** — Reusable CLI helpers built on Typer

## Usage

### Providers

```python
from local_first_common.providers import PROVIDERS

provider = PROVIDERS["ollama"]()
response = provider.complete(system="You are a helpful assistant.", user="Hello!")
```

### Obsidian helpers

```python
from local_first_common.obsidian import get_daily_note_path, append_to_daily_note
from datetime import date
from pathlib import Path

note_path = get_daily_note_path(Path("~/vaults/MyVault"), date.today(), subdir="Daily")
append_to_daily_note(note_path, "## My Section\n\n- Item one\n")
```

### MockProvider (for tests)

```python
from local_first_common.testing import MockProvider

provider = MockProvider(response="## Thoughts\n\n- Test thought")
result = provider.complete("sys prompt", "user message")
assert provider.calls[0] == ("sys prompt", "user message")
```

## Project Structure

```
src/local_first_common/
  __init__.py
  cli.py
  obsidian.py
  testing.py
  providers/
    __init__.py
    base.py
    ollama.py
    anthropic.py
    groq.py
    deepseek.py
    gemini.py
tests/
  test_obsidian.py
  test_providers.py
  test_testing.py
```
