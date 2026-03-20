from abc import ABC, abstractmethod
from typing import Sequence

# Actually, let's keep it simple and not depend on internal relative imports if not sure
# Better to use absolute if it's a library

class SocialReader(ABC):
    """Abstract base class for social media post readers."""

    @abstractmethod
    def search(self, query: str, limit: int = 20) -> Sequence:
        """Search for posts matching a query."""
        pass
