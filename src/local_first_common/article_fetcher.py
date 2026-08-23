"""Fetch article metadata from URLs found in social posts.

Provides ``FeedItem`` (the common article item representation) and
``fetch_article_metadata``, which wraps ``tracked_fetch`` so every URL attempt
is logged to the central ``fetch_log`` table.

Typical usage::

    from local_first_common.article_fetcher import fetch_article_metadata
    from local_first_common.tracking import register_tool

    _TOOL = register_tool("my-tool")

    item = fetch_article_metadata(
        url,
        tool=_TOOL,
        source_url=post_url,
        source_platform="bluesky",
    )
    if item:
        # use item.title, item.description, item.url, item.source, item.published
        ...
"""

import logging
import re
from dataclasses import dataclass
from urllib.parse import urlparse

from local_first_common import html
from local_first_common.tracking import Tool, tracked_fetch
from local_first_common.url import normalize_url

logger = logging.getLogger(__name__)

# Domains that reliably block scrapers or sit behind paywalls — skipped before
# any HTTP request is made. Covers Medium and its publication network.
_DEFAULT_BLOCKED_DOMAINS: frozenset[str] = frozenset({
    "medium.com",
    "towardsdatascience.com",
    "betterprogramming.pub",
    "plainenglish.io",
    "levelup.gitconnected.com",
})


@dataclass
class FeedItem:
    """A fetched article with extracted metadata."""

    title: str
    description: str
    url: str
    source: str
    published: str = ""  # ISO date e.g. "2026-03-07", empty if unavailable
    found_at: str | None = None  # URL of the page/post where this link was first found
    search_term: str | None = None  # The term used to discover this link
    platform: str | None = None  # The platform where this link was discovered


def _is_blocked(netloc: str, blocked_domains: frozenset[str]) -> bool:
    """Return True if netloc matches any domain in the blocklist (exact or subdomain)."""
    host = netloc.lower().split(":")[0]  # strip port if present
    return any(
        host == domain or host.endswith("." + domain)
        for domain in blocked_domains
    )


_ENGAGEMENT_COUNT_RE = re.compile(r"^[\d.,]+[KMB]?$")
_HANDLE_RE = re.compile(r"^@\w+$")


def _derive_metadata_from_rendered_text(text: str) -> tuple[str, str]:
    """Best-effort (title, description) split from a rendered page's raw text.

    Used when a page's server-rendered HTML has no usable <meta> title at
    all (x.com serves none for individual tweets) but a real-browser render
    recovered the content. Social platforms share a rough shape: some fixed
    chrome, an "@handle" line, a run of engagement-count lines, then the real
    text. Keying off the handle line rather than matching specific chrome
    strings survives a UI copy change; it does not survive the platform
    dropping the handle-then-counts layout entirely. Worst case on a layout
    this doesn't recognize is a mediocre title built from the whole page,
    which still beats discarding a render that succeeded.
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    handle_idx = next((i for i, line in enumerate(lines) if _HANDLE_RE.fullmatch(line)), None)
    if handle_idx is not None:
        rest = [
            line for line in lines[handle_idx + 1:]
            if not _ENGAGEMENT_COUNT_RE.fullmatch(line)
        ]
    else:
        rest = lines
    content = " ".join(rest) or text.strip()
    return content[:80].strip(), content[:500].strip()


def _try_render(url: str, renderer) -> str:
    """Best-effort rendered fetch. Returns "" on any failure, including a
    missing playwright install — rendering is a fallback, never a hard
    requirement, and the caller already has whatever the plain fetch found.
    """
    if renderer is None:
        from local_first_common.js_render import fetch_rendered_text

        renderer = fetch_rendered_text
    try:
        return (renderer(url) or "").strip()
    except Exception as e:
        logger.info("Rendered fetch failed for %s: %s: %s", url, type(e).__name__, e)
        return ""


def fetch_article_metadata(
    url: str,
    blocked_domains: frozenset[str] = frozenset(),
    tool: Tool | None = None,
    source_url: str | None = None,
    source_platform: str | None = None,
    search_term: str | None = None,
    session: any = None,
    render_domains: frozenset[str] = frozenset(),
    renderer=None,
) -> FeedItem | None:
    """Fetch a URL and extract title and description from its HTML meta tags.

    Skips URLs whose domain is in the default block list or in
    ``blocked_domains`` without making an HTTP request.

    When ``tool`` is provided the attempt is logged to the central fetch_log
    table via ``tracked_fetch``. ``source_url`` is the social post where this
    link was found; ``source_platform`` is e.g. ``'bluesky'`` or ``'mastodon'``.

    If ``session`` is provided and has a ``mark_failed(url, status_code)`` method,
    it is called on fetch failure.

    ``render_domains`` names hosts known to serve no usable metadata to a
    plain fetch (x.com serves no <title> at all for a tweet page). When the
    plain fetch's title comes back empty and the URL's host is in this set, a
    real-browser render is attempted as a fallback and a title/description
    are derived from its text. Empty by default: rendering only happens when
    a caller opts in.
    """
    url = normalize_url(url)
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        logger.debug("Skipping invalid URL: %s", url)
        return None

    netloc = parsed.netloc
    all_blocked = _DEFAULT_BLOCKED_DOMAINS | blocked_domains
    if _is_blocked(netloc, all_blocked):
        logger.debug("Skipping blocked domain: %s", netloc)
        return None

    _tool = tool or Tool(name="", id=None)
    with tracked_fetch(_tool, url, source_url=source_url, source_platform=source_platform) as fetch:
        if fetch.html is None:
            logger.warning("Failed to fetch %s: %s", url, fetch.error_message)
            if session and hasattr(session, "mark_failed"):
                session.mark_failed(url, fetch.http_status)
            return None

        try:
            metadata = html.extract_metadata(fetch.html)
        except Exception as e:
            logger.warning("Failed to parse metadata for %s: %s", url, e)
            if session and hasattr(session, "mark_failed"):
                session.mark_failed(url)
            return None

        title, description, published = metadata.title, metadata.description, metadata.published_date

        if not title and render_domains:
            host = netloc.lower().split(":")[0]
            if host.startswith("www."):
                host = host[4:]
            if host in render_domains:
                rendered = _try_render(url, renderer)
                if rendered:
                    title, description = _derive_metadata_from_rendered_text(rendered)

        if not title:
            logger.warning("No title found for %s — skipping", url)
            if session and hasattr(session, "mark_failed"):
                session.mark_failed(url)
            return None

        fetch.title = title
        source = urlparse(url).netloc

        return FeedItem(
            title=title,
            description=description,
            url=url,
            source=source,
            published=published,
            found_at=source_url,
            search_term=search_term,
            platform=source_platform,
        )
