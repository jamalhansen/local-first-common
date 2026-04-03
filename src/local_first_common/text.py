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


def strip_html(html: str) -> str:
    """Remove HTML tags and decode common entities from a string."""
    text = re.sub(r"<[^>]+>", " ", html)
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&quot;", '"').replace("&#39;", "'").replace("&apos;", "'")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def strip_code_blocks(text: str) -> str:
    """Remove fenced and inline code blocks from markdown text."""
    # Remove fenced code blocks (``` ... ```)
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    # Remove inline code blocks (` ... `)
    text = re.sub(r"`[^`]+`", "", text)
    return text


def strip_markdown_links(text: str) -> str:
    """Remove markdown and wiki links from text."""
    # Remove markdown links: [anchor](url)
    text = re.sub(r"\[[^\]]+\]\([^)]+\)", "", text)
    # Remove wiki links: [[slug]] or [[slug|anchor]]
    text = re.sub(r"\[\[[^\]]+\]\]", "", text)
    return text


def split_markdown_protected(text: str) -> list[str]:
    """Split markdown body into chunks, alternating [text, protected, text, protected, ...].
    Protected elements include fenced code, inline code, markdown links, and wiki links.
    """
    pattern = r"(```.*?```|`[^`]+`|\[[^\]]+\]\([^)]+\)|\[\[[^\]]+\]\])"
    return re.split(pattern, text, flags=re.DOTALL)


def looks_like_article(text: str, min_words: int = 200) -> bool:
    """Heuristic: does this look like the body of an article?

    Returns True if the text contains at least min_words whitespace-delimited tokens.
    """
    return len(text.split()) >= min_words
