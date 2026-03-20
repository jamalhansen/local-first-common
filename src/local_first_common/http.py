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

def fetch_url(url: str, timeout: int = 15, headers: dict | None = None) -> str:
    """Fetch a URL and return the HTML content string.
    
    Args:
        url: The URL to fetch.
        timeout: Request timeout in seconds.
        headers: Optional headers to override defaults.
        
    Returns:
        The response text.
        
    Raises:
        RuntimeError: if the request fails or returns a non-200 status.
    """
    request_headers = headers or DEFAULT_HEADERS
    try:
        response = requests.get(url, headers=request_headers, timeout=timeout, allow_redirects=True)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        logger.warning("Failed to fetch URL %s: %s", url, e)
        raise RuntimeError(f"Failed to fetch URL: {e}") from e
