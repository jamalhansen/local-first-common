from abc import ABC, abstractmethod
from collections.abc import Sequence


class SocialReader(ABC):
    """Abstract base class for social media post readers."""

    @abstractmethod
    def fetch_posts(self, keywords: Sequence[str], limit: int = 25) -> Sequence[dict]:
        """Search for posts matching keywords. Returns raw post dicts."""

    @abstractmethod
    def extract_urls(self, post: dict) -> list[str]:
        """Extract external URLs from a post dict."""
