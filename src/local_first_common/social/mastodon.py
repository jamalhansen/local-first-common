import logging
import requests

logger = logging.getLogger(__name__)


def keyword_to_hashtag(keyword: str) -> str:
    """Convert a keyword to a valid Mastodon hashtag (strips spaces and hyphens)."""
    return keyword.replace(" ", "").replace("-", "")


def fetch_posts(
    keywords: list[str],
    instances: list[str] | None = None,
    limit: int = 40,
) -> list[dict]:
    """Search Mastodon hashtag timelines for the given keywords."""
    instances = instances or ["mastodon.social"]
    all_statuses = []
    seen_ids = set()

    for instance in instances:
        for keyword in keywords:
            hashtag = keyword_to_hashtag(keyword)
            url = f"https://{instance}/api/v1/timelines/tag/{hashtag}"

            try:
                resp = requests.get(url, params={"limit": limit}, timeout=10)
                resp.raise_for_status()
                statuses = resp.json()
                for status in statuses:
                    status_id = status.get("id")
                    if status_id and status_id not in seen_ids:
                        seen_ids.add(status_id)
                        # Tag with source instance
                        status["_instance"] = instance
                        all_statuses.append(status)
            except requests.RequestException as e:
                logger.warning(
                    "Mastodon fetch failed for %s #%s: %s", instance, hashtag, e
                )
                continue
    return all_statuses
