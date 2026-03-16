"""Clipboard access utilities."""

import subprocess


def get_clipboard() -> str:
    """Return clipboard contents as a string.

    Uses macOS pbpaste first; falls back to pyperclip on other platforms.
    Returns an empty string if the clipboard is empty or inaccessible.
    """
    try:
        result = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=5)
        return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        import pyperclip
        return pyperclip.paste().strip()
