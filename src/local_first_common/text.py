"""Text processing utilities for Obsidian-aware tools."""

import re


def strip_wikilinks(text: str) -> str:
    """Replace Obsidian wikilinks with their display text.

    [[Link|Alias]] → Alias
    [[Link]]       → Link
    """
    text = re.sub(r"\[\[([^|\]]+)\|([^\]]+)\]\]", r"\2", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    return text


def looks_like_article(text: str, min_words: int = 200) -> bool:
    """Heuristic: does this look like the body of an article?

    Returns True if the text contains at least min_words whitespace-delimited tokens.
    """
    return len(text.split()) >= min_words
