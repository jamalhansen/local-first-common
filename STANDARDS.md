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

## Implementation for Developers

When building a new tool, use the helpers in `local_first_common.cli`:

```python
from local_first_common.cli import (
    dry_run_option,
    no_llm_option,
    resolve_provider,
)

@app.command()
def run(
    dry_run: Annotated[bool, dry_run_option()] = False,
    no_llm: Annotated[bool, no_llm_option()] = False,
    # ... other options
):
    if no_llm:
        dry_run = True
        
    llm = resolve_provider(PROVIDERS, provider_name, model, no_llm=no_llm)
    
    # ... logic ...
    
    if dry_run:
        print(result)
    else:
        save(result)
```
