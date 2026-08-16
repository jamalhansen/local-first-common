"""Readwise Reader integration.

Saves articles to, and lists articles from, the Readwise Reader inbox via
the official API. API docs: https://readwise.io/reader_api
"""

import logging

import requests

from local_first_common.article_fetcher import FeedItem

logger = logging.getLogger(__name__)

_SAVE_URL = "https://readwise.io/api/v3/save/"
_LIST_URL = "https://readwise.io/api/v3/list/"


def save_to_readwise(
    token: str,
    url: str,
    *,
    title: str = "",
    summary: str = "",
    tags: list[str] | None = None,
    published_date: str = "",
    search_term: str | None = None,
    platform: str | None = None,
) -> bool:
    """Save a URL to the Readwise Reader inbox.

    Args:
        token:          Readwise access token.
        url:            Article URL (required by the API).
        title:          Article title (optional, Reader will fetch if omitted).
        summary:        Short summary shown in Reader (optional).
        tags:           List of tag strings (optional).
        published_date: ISO 8601 date string e.g. "2026-03-11" (optional).
        search_term:    Discovery search term to add as a tag (optional).
        platform:       Discovery platform to add as a tag (optional).

    Returns:
        True on success (HTTP 200 or 201), False on any error.
    """
    if not token:
        logger.error("Readwise token is not set — cannot save to Reader")
        return False

    # Deep copy/init tags list
    all_tags = list(tags) if tags else []
    if platform:
        all_tags.append(f"platform:{platform}")
    if search_term:
        all_tags.append(f"term:{search_term}")

    payload: dict = {"url": url}
    if title:
        payload["title"] = title
    if summary:
        payload["summary"] = summary
    if all_tags:
        payload["tags"] = all_tags
    if published_date:
        payload["published_date"] = published_date

    try:
        resp = requests.post(
            _SAVE_URL,
            json=payload,
            headers={"Authorization": f"Token {token}"},
            timeout=10,
        )
        if resp.status_code in (200, 201):
            return True
        logger.warning(
            "Readwise API returned %s for %s: %s",
            resp.status_code, url, resp.text[:200],
        )
        return False
    except requests.RequestException as e:
        logger.warning("Failed to save %s to Readwise: %s", url, e)
        return False


def _document_to_feed_item(doc: dict) -> FeedItem:
    """Map a single Reader API document object onto the shared FeedItem shape.

    ``source_url`` is the original article URL (what we want to link to);
    ``url`` is Reader's own reader.readwise.io URL and is only used as a
    fallback for documents that don't carry an external source (e.g. notes).
    """
    return FeedItem(
        title=doc.get("title") or "",
        description=doc.get("summary") or "",
        url=doc.get("source_url") or doc.get("url") or "",
        source="readwise-reader",
        published=doc.get("published_date") or "",
        platform="reader",
    )


def list_reader_documents(
    token: str,
    *,
    location: str | None = "new",
    category: str | None = None,
    updated_after: str | None = None,
    tag: str | None = None,
    limit: int = 100,
) -> list[FeedItem]:
    """Fetch documents from the Readwise Reader library, paginating through all results.

    Args:
        token:         Readwise access token.
        location:      Filter by location — "new", "later", "shortlist", "archive",
                        "feed", or None to skip this filter and return all locations.
                        Defaults to "new" (unread inbox items), the ingest case this
                        function exists for.
        category:      Filter by document type — "article", "email", "rss", "pdf",
                        "epub", "tweet", "video", etc. None returns all types,
                        including "highlight"/"note" entries that aren't real content.
        updated_after: ISO 8601 timestamp; only return documents modified after this.
        tag:           Filter by a single tag.
        limit:         Page size sent to the API (1-100). Pagination is handled
                        internally regardless of this value; it only affects how
                        many requests are made.

    Returns:
        A flat list of FeedItem, across all pages. Stops and returns whatever was
        gathered so far if a page request fails (partial results beat a crashed
        scheduled run).

    Note: the API is rate-limited to 20 requests/minute per token. This function
    does not implement backoff — fine for routine "new" polling, but a large
    backfill (e.g. category=None across full history) could exceed it.
    """
    if not token:
        logger.error("Readwise token is not set — cannot list Reader documents")
        return []

    items: list[FeedItem] = []
    cursor: str | None = None

    while True:
        params: dict = {"limit": limit}
        if location is not None:
            params["location"] = location
        if category is not None:
            params["category"] = category
        if updated_after is not None:
            params["updatedAfter"] = updated_after
        if tag is not None:
            params["tag"] = tag
        if cursor is not None:
            params["pageCursor"] = cursor

        try:
            resp = requests.get(
                _LIST_URL,
                params=params,
                headers={"Authorization": f"Token {token}"},
                timeout=10,
            )
        except requests.RequestException as e:
            logger.warning("Failed to list Reader documents: %s", e)
            break

        if resp.status_code != 200:
            logger.warning(
                "Readwise API returned %s listing documents: %s",
                resp.status_code, resp.text[:200],
            )
            break

        data = resp.json()
        items.extend(_document_to_feed_item(doc) for doc in data.get("results", []))

        cursor = data.get("nextPageCursor")
        if not cursor:
            break

    return items
