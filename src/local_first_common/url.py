"""URL cleaning utilities."""

import re
from urllib.parse import parse_qsl, urlencode, urlparse

# arXiv paper id, e.g. "2403.02691" or "2403.02691v3" -- the version suffix and
# the /abs//html//pdf/ path prefix are presentation details, not identity: the
# same paper shows up under all of them within days of each other in the wild.
_ARXIV_PATH_RE = re.compile(r"^/(?:abs|html|pdf)/([0-9]{4}\.[0-9]{4,5})(?:v[0-9]+)?$")

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
    except Exception:  # noqa: BLE001 - malformed URL from an untrusted source; return unchanged rather than crash, per this function's own contract
        return url


def normalize_url(url: str) -> str:
    """Normalize a URL for deduplication.

    1. Strip tracking parameters (via clean_url).
    2. Lowercase scheme and netloc.
    3. Strip trailing slashes from path.
    4. Strip the fragment. Fragments are never sent to the server, so two URLs
       differing only by fragment (e.g. a GitHub README anchor) are the same
       resource for dedup purposes even though clean_url (used elsewhere for
       display) deliberately preserves them.
    5. Force https for known sites that use both interchangeably (e.g. news.ycombinator.com).
    6. Collapse arXiv's DOI form (doi.org/10.48550/arXiv.X) to its abs-page form
       (arxiv.org/abs/X) -- same paper, two URLs, both seen in the wild for the same
       capture within a day of each other.
    7. Collapse arXiv's /abs/, /html/, and /pdf/ path forms, and any version
       suffix (v1, v2, ...), to a single versionless /abs/X form -- the same
       paper resurfaces under all of these within days of each other, and a
       revised version isn't a new source for capture purposes.
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

        if netloc == "doi.org" and path.lower().startswith("/10.48550/arxiv."):
            arxiv_id = path[len("/10.48550/arxiv."):]
            netloc = "arxiv.org"
            path = f"/abs/{arxiv_id}"

        if netloc == "arxiv.org":
            match = _ARXIV_PATH_RE.match(path)
            if match:
                path = f"/abs/{match.group(1)}"

        return parsed._replace(scheme=scheme, netloc=netloc, path=path, fragment="").geturl()
    except Exception:  # noqa: BLE001 - malformed URL from an untrusted source; return unchanged rather than crash, per this function's own contract
        return url
