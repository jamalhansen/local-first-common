import logging
import requests
from typing import Sequence
from .base import SocialReader

logger = logging.getLogger(__name__)

DEFAULT_INSTANCES = ["fosstodon.org", "mastodon.social"]

def fetch_posts(
    keywords: Sequence[str],
    instances: Sequence[str] = DEFAULT_INSTANCES,
    limit: int = 25,
) -> list[dict]:
    """Search Mastodon for posts matching keywords (as hashtags)."""
    all_posts = []
    seen_ids = set()

    for instance in instances:
        for keyword in keywords:
            tag = keyword.lstrip("#")
            url = f"https://{instance}/api/v1/timelines/tag/{tag}"
            try:
                resp = requests.get(url, params={"limit": limit}, timeout=10)
                resp.raise_for_status()
                for post in resp.json():
                    if post["id"] not in seen_ids:
                        seen_ids.add(post["id"])
                        all_posts.append(post)
            except requests.RequestException as e:
                logger.warning("Mastodon fetch failed for %s on %s: %s", tag, instance, e)
                continue
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
