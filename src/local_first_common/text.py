import re
import logging

logger = logging.getLogger(__name__)

# High-signal verbs that suggest actionable thoughts or intentional learning
_SIGNAL_VERBS = {
    "buy", "fix", "call", "write", "draft", "send", "email", "setup", 
    "build", "create", "test", "learn", "read", "research", "explore",
    "check", "review", "update", "add", "remove", "delete", "refactor",
    "deploy", "ship", "verify", "validate", "open", "close", "start", "stop"
}

# Low-signal filler that often starts "rambling" thoughts
_NOISE_STARTERS = {
    "i think", "maybe", "perhaps", "it seems", "i feel", "i wonder",
    "sometimes", "usually", "generally", "i'm not sure", "it might"
}

def is_english(text: str) -> bool:
    """Check if text is primarily English. Fails open (returns True) on error."""
    if not text:
        return False
    if len(text) < 5: # Too short to reliably detect, so assume English
        return True
    try:
        from langdetect import detect
        return detect(text) == 'en'
    except Exception:
        # Fail open
        return True

def looks_like_article(text: str, min_words: int = 200) -> bool:
    """Heuristic to check if content looks like a full article vs noise."""
    if not text:
        return False
    
    words = text.split()
    word_count = len(words)
    
    if word_count < min_words:
        return False
        
    # Full articles usually have paragraph structure
    paragraphs = [p for p in text.split('\n\n') if p.strip()]
    if len(paragraphs) < 3 and word_count > 500:
        return False
        
    return True

def strip_wikilinks(text: str) -> str:
    """Remove Obsidian [[wikilink]] or [[wikilink|alias]] markers."""
    text = re.sub(r"\[\[[^\]|]+\|([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    return text

def is_high_signal(text: str) -> bool:
    """Determine if a thought/task string is high-signal enough to surface."""
    clean = text.lower().strip()
    if not clean:
        return False

    stripped = strip_wikilinks(clean)
    if stripped.endswith("?"):
        return True

    words = stripped.split()
    if not words:
        return False

    # 2. Actionable verbs at the start (very high signal)
    first_word = words[0].rstrip(":,;.")
    if first_word in _SIGNAL_VERBS:
        return True

    # 3. Noise check: Rambling starters
    for starter in _NOISE_STARTERS:
        if clean.startswith(starter):
            return len(words) > 12

    # 4. Length-based heuristic: Keep anything 4 words or longer by default
    if len(words) >= 4:
        return True

    # 5. Search for signal verbs anywhere in the string
    if any(w.rstrip(":,;.") in _SIGNAL_VERBS for w in words):
        return True

    return False
