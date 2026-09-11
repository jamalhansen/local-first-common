"""Unified ingestion for local files and URLs."""
import logging
from pathlib import Path

import frontmatter

from .html import extract_main_content, extract_metadata
from .tracking import Tool, tracked_fetch
from .url import clean_url

logger = logging.getLogger(__name__)


def ingest_any(source: str, tool: Tool | None = None) -> tuple[str, str]:
    """Ingest content from a URL or a local file. Returns (title, content).
    
    Args:
        source: A URL (starting with http) or a local file path.
        tool: Optional tracking Tool object to log the fetch.
        
    Returns:
        A tuple of (title, content).
        
    Raises:
        FileNotFoundError: If a local source does not exist.
        RuntimeError: If a URL fetch fails.
    """
    if source.startswith(("http://", "https://")):
        return ingest_url(source, tool=tool)
    
    path = Path(source).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"Source not found: {source}")
        
    return ingest_file(path)


def ingest_url(url: str, tool: Tool | None = None) -> tuple[str, str]:
    """Fetch URL and extract main content. Returns (title, content)."""
    url = clean_url(url)
    # Use a dummy tool if none provided to satisfy tracked_fetch requirement
    _tool = tool or Tool(name="ingestion", id=None)
    
    with tracked_fetch(_tool, url) as fetch:
        if fetch.html is None:
            raise RuntimeError(f"Failed to fetch {url}: {fetch.error_message}")
        
        metadata = extract_metadata(fetch.html)
        content = extract_main_content(fetch.html)
        title = metadata.title or "Untitled URL"
        fetch.title = title
        return title, content


def ingest_file(path: Path) -> tuple[str, str]:
    """Load content from a local file (Markdown or plain text). Returns (title, content)."""
    if path.suffix.lower() == ".md":
        try:
            post = frontmatter.load(path)
            title = post.get("title") or path.stem
            return title, post.content
        except Exception as e:  # noqa: BLE001 - malformed frontmatter in a user's own file should fall back to plain text, not crash
            logger.warning("Failed to parse frontmatter for %s: %s", path, e)
            # Fallback to plain text
            content = path.read_text(encoding="utf-8")
            return path.stem, content
    else:
        content = path.read_text(encoding="utf-8")
        title = path.stem
        return title, content
