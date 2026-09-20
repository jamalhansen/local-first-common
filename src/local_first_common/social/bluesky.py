import logging
from collections.abc import Sequence
from pathlib import Path

import requests

from local_first_common.tracking import Tool, tracked_call

from .base import SocialReader

logger = logging.getLogger(__name__)

_SEARCH_URL = "https://api.bsky.app/xrpc/app.bsky.feed.searchPosts"
_AUTH_URL = "https://bsky.social/xrpc/com.atproto.server.createSession"


def get_auth_token(
    handle: str, app_password: str, tool: Tool | None = None, db_path: str | Path | None = None
) -> str | None:
    """Fetch a bearer token from Bluesky using handle + app password.

    ``tool``: registered ``Tool`` (via ``register_tool()``) to log this call under
    in ``api_call_log``. Optional — omit for no logging.
    """
    with tracked_call(tool, "bluesky", "auth", db_path=db_path) as call:
        try:
            resp = requests.post(
                _AUTH_URL,
                json={"identifier": handle, "password": app_password},
                timeout=10,
            )
            resp.raise_for_status()
            call.http_status = resp.status_code
            call.success = True
            return resp.json().get("accessJwt")
        except requests.RequestException as e:
            logger.warning("Bluesky authentication failed: %s", e)
            call.error_message = str(e)
            call.http_status = getattr(e.response, "status_code", None)
            return None


def extract_urls_from_post(post: dict) -> list[str]:
    """Extract article URLs from a Bluesky PostView dict."""
    embed = post.get("embed") or {}
    external = embed.get("external") or {}
    uri = external.get("uri", "").strip()
    if uri:
        return [uri]

    urls: list[str] = []
    facets = (post.get("record") or {}).get("facets") or []
    for facet in facets:
        for feature in facet.get("features", []):
            if feature.get("$type") == "app.bsky.richtext.facet#link":
                link_uri = feature.get("uri", "").strip()
                if link_uri:
                    urls.append(link_uri)
    return urls


def get_post_url(post: dict) -> str:
    """Build a web URL for a Bluesky post from its record."""
    author = (post.get("author") or {}).get("handle", "")
    uri = post.get("uri", "")  # at://did:plc:.../app.bsky.feed.post/<rkey>
    rkey = uri.split("/")[-1] if "/" in uri else ""
    if author and rkey:
        return f"https://bsky.app/profile/{author}/post/{rkey}"
    return ""


def has_external_link(post: dict) -> bool:
    """Return True if the post has an embedded external link card."""
    embed = post.get("embed") or {}
    return bool(embed.get("external", {}).get("uri"))


def fetch_posts(
    keywords: Sequence[str],
    token: str | None = None,
    limit: int = 25,
    tool: Tool | None = None,
    db_path: str | Path | None = None,
) -> list[dict]:
    """Search Bluesky for posts matching keywords.

    ``tool``: registered ``Tool`` (via ``register_tool()``) to log this call under
    in ``api_call_log``. Optional — omit for no logging.
    """
    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    all_posts = []
    seen_uris = set()

    with tracked_call(tool, "bluesky", "fetch_posts", db_path=db_path) as call:
        call.success = True
        for keyword in keywords:
            try:
                resp = requests.get(
                    _SEARCH_URL,
                    params={"q": keyword, "limit": limit},
                    headers=headers,
                    timeout=10,
                )
                resp.raise_for_status()
                call.http_status = resp.status_code
                data = resp.json()
                for post in data.get("posts", []):
                    uri = post.get("uri")
                    if uri and uri not in seen_uris:
                        seen_uris.add(uri)
                        all_posts.append(post)
            except requests.RequestException as e:
                logger.warning("Bluesky fetch failed for %r: %s", keyword, e)
                call.success = False
                call.error_message = str(e)
                continue
        call.item_count = len(all_posts)

    return all_posts


class BlueskyReader(SocialReader):
    """Refined Bluesky reader class."""

    def __init__(self, handle: str = "", app_password: str = ""):
        self.handle = handle
        self.app_password = app_password
        self._token: str | None = None
        if handle and app_password:
            self._token = get_auth_token(handle, app_password)

    def fetch_posts(self, keywords: Sequence[str], limit: int = 25) -> list[dict]:
        return fetch_posts(keywords, token=self._token, limit=limit)

    def extract_urls(self, post: dict) -> list[str]:
        return extract_urls_from_post(post)
