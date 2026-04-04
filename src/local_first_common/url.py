"""URL cleaning utilities."""

from urllib.parse import parse_qsl, urlencode, urlparse

# Query parameters that are tracking-only and carry no page identity.
_TRACKING_PARAMS: frozenset[str] = frozenset({
    # UTM (Google Analytics / social scheduling tools)
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    # Platform click-tracking
    "fbclid",   # Facebook
    "gclid",    # Google Ads
    "mc_eid",   # Mailchimp
    # NOTE: "ref" and "source" intentionally excluded — too generic.
    # e.g. GitHub uses ?ref=main for branch refs; many sites use ?source= legitimately.
})


def clean_url(url: str) -> str:
    """Strip known tracking query parameters from a URL.

    The URL's path and non-tracking parameters are preserved.
    Returns the original string unchanged if parsing fails.
    """
    try:
        parsed = urlparse(url)
        # Sort query params for consistent output
        qsl = parse_qsl(parsed.query)
        kept = sorted((k, v) for k, v in qsl if k.lower() not in _TRACKING_PARAMS)
        clean_query = urlencode(kept)
        return parsed._replace(query=clean_query).geturl()
    except Exception:
        return url


def normalize_url(url: str) -> str:
    """Normalize a URL for deduplication.

    1. Strip tracking parameters (via clean_url).
    2. Lowercase scheme and netloc.
    3. Strip trailing slashes from path.
    4. Force https for known sites that use both interchangeably (e.g. news.ycombinator.com).
    """
    url = clean_url(url)
    try:
        parsed = urlparse(url)
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()
        path = parsed.path.rstrip("/")
        if not path:
            path = ""

        # Consolidate http/https for specific domains prone to mixed usage
        if netloc in ("news.ycombinator.com", "ycombinator.com"):
            scheme = "https"

        return parsed._replace(scheme=scheme, netloc=netloc, path=path).geturl()
    except Exception:
        return url
