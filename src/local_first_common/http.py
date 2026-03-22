import requests
import logging

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


class FetchError(RuntimeError):
    """Raised when fetch_url fails. Carries the HTTP status code if available."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def fetch_url(url: str, timeout: int = 15, headers: dict | None = None) -> str:
    """Fetch a URL and return the HTML content string.

    Args:
        url: The URL to fetch.
        timeout: Request timeout in seconds.
        headers: Optional headers to override defaults.

    Returns:
        The response text.

    Raises:
        FetchError: if the request fails or returns a non-200 status.
            FetchError.status_code is set for HTTP errors, None for network errors.
    """
    request_headers = headers or DEFAULT_HEADERS
    try:
        response = requests.get(url, headers=request_headers, timeout=timeout, allow_redirects=True)
        response.raise_for_status()
        return response.text
    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code if e.response is not None else None
        raise FetchError(f"Failed to fetch URL: {e}", status_code=status_code) from e
    except requests.exceptions.RequestException as e:
        raise FetchError(f"Failed to fetch URL: {e}", status_code=None) from e
