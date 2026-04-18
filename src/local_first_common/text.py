import re
import logging

logger = logging.getLogger(__name__)

# High-signal verbs
_SIGNAL_VERBS = {
    "buy", "fix", "call", "write", "draft", "send", "email", "setup", 
    "build", "create", "test", "learn", "read", "research", "explore",
    "check", "review", "update", "add", "remove", "delete", "refactor",
    "deploy", "ship", "verify", "validate", "open", "close", "start", "stop"
}

_NOISE_STARTERS = {
    "i think", "maybe", "perhaps", "it seems", "i feel", "i wonder",
    "sometimes", "usually", "generally", "i'm not sure", "it might"
}

def is_english(text: str) -> bool:
    if not text:
        return False
    if len(text) < 5:
        return True
    try:
        from langdetect import detect
        return detect(text) == 'en'
    except Exception:
        return True

def looks_like_article(text: str, min_words: int = 200) -> bool:
    if not text:
        return False
    words = text.split()
    if len(words) < min_words:
        return False
    paragraphs = [p for p in text.split('\n\n') if p.strip()]
    if len(paragraphs) < 3 and len(words) > 500:
        return False
    return True

def strip_wikilinks(text: str) -> str:
    text = re.sub(r"\[\[[^\]|]+\|([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    return text

def strip_code_blocks(text: str) -> str:
    # 1. Remove fenced code blocks
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    # 2. Remove inline code
    text = re.sub(r"`.*?`", "", text)
    return text

def strip_markdown_links(text: str) -> str:
    return re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)

def strip_html(text: str) -> str:
    return re.sub(r"<[^>]*>", "", text)

def split_markdown_protected(text: str) -> list[str]:
    """
    Split markdown text into chunks, isolating protected elements.
    Returns: [text, protected, text, protected, ...]
    Protected elements include: fenced code blocks, inline code, markdown links, wiki links.
    """
    pattern = r"(```.*?```|`.*?`|\[[^\]]+\]\([^\)]+\)|\[\[[^\]]+\]\])"
    
    # split with capture group returns both text and matches
    chunks = re.split(pattern, text, flags=re.DOTALL)
    
    # We must return [text, protected, text, protected, ...]
    # re.split with a capture group returns:
    # [non-match, match, non-match, match, ...]
    # This is exactly what we want.
    return chunks

def is_high_signal(text: str) -> bool:
    clean = text.lower().strip()
    if not clean:
        return False
    stripped = strip_wikilinks(clean)
    if stripped.endswith("?"):
        return True
    words = stripped.split()
    if not words:
        return False
    if words[0].rstrip(":,;.") in _SIGNAL_VERBS:
        return True
    for starter in _NOISE_STARTERS:
        if clean.startswith(starter):
            return len(words) > 12
    if len(words) >= 4:
        return True
    if any(w.rstrip(":,;.") in _SIGNAL_VERBS for w in words):
        return True
    return False
