class ProviderError(Exception):
    """Base class for all provider-related errors."""
    pass

class ModelNotFoundError(ProviderError):
    """Raised when the requested model is not found on the provider."""
    pass

class ConnectionError(ProviderError):
    """Raised when there is a connection issue with the provider."""
    pass
