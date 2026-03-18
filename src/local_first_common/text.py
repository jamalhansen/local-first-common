"""Text processing utilities for Obsidian-aware tools."""

import re


def is_english(text: str) -> bool:
    """Return True if text appears to be written in English.

    Uses langdetect for probabilistic language detection.  Deterministic mode
    is enabled via ``DetectorFactory.seed = 0`` so results are stable across
    runs (important for tests and deduplication logic).

    Fails open: returns ``True`` if langdetect is not installed, the text is
    too short to classify reliably, or detection raises any exception.  This
    means ambiguous posts are kept rather than silently dropped.

    Requires the ``langdetect`` package:
        uv add langdetect
    """
    try:
        from langdetect import DetectorFactory, detect  # type: ignore[import]

        DetectorFactory.seed = 0  # deterministic output
        return detect(text) == "en"
    except Exception:
        return True  # fail open — keep posts we can't classify


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
