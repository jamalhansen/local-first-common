import logging
from collections.abc import Sequence
from pathlib import Path

import requests

from local_first_common.tracking import Tool, tracked_call

from .base import SocialReader

logger = logging.getLogger(__name__)

DEFAULT_INSTANCES = ["fosstodon.org", "mastodon.social"]

def fetch_posts(
    keywords: Sequence[str],
    instances: Sequence[str] = DEFAULT_INSTANCES,
    limit: int = 25,
    tool: Tool | None = None,
    db_path: str | Path | None = None,
) -> list[dict]:
    """Search Mastodon for posts matching keywords (as hashtags).

    ``tool``: registered ``Tool`` (via ``register_tool()``) to log this call under
    in ``api_call_log``. Optional — omit for no logging.
    """
    all_posts = []
    seen_ids = set()

    with tracked_call(tool, "mastodon", "fetch_posts", db_path=db_path) as call:
        call.success = True
        for instance in instances:
            for keyword in keywords:
                tag = keyword.lstrip("#")
                url = f"https://{instance}/api/v1/timelines/tag/{tag}"
                try:
                    resp = requests.get(url, params={"limit": limit}, timeout=10)
                    resp.raise_for_status()
                    call.http_status = resp.status_code
                    for post in resp.json():
                        if post["id"] not in seen_ids:
                            seen_ids.add(post["id"])
                            all_posts.append(post)
                except requests.RequestException as e:
                    logger.warning("Mastodon fetch failed for %s on %s: %s", tag, instance, e)
                    call.success = False
                    call.error_message = str(e)
                    continue
        call.item_count = len(all_posts)

    return all_posts

def extract_urls_from_post(post: dict) -> list[str]:
    """Extract URLs from a Mastodon post dict."""
    return [link.get("url") for link in post.get("card", {}).get("links", []) if link.get("url")]

class MastodonReader(SocialReader):
    """Refined Mastodon reader class."""

    def __init__(self, instances: Sequence[str] = DEFAULT_INSTANCES):
        self.instances = instances

    def fetch_posts(self, keywords: Sequence[str], limit: int = 25) -> list[dict]:
        return fetch_posts(keywords, instances=self.instances, limit=limit)

    def extract_urls(self, post: dict) -> list[str]:
        # Mastodon stores the main link in the 'card'
        card = post.get("card")
        if card and card.get("url"):
            return [card["url"]]
        return []
