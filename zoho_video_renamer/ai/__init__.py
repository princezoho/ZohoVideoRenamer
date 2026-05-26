"""AI provider clients for image-based naming."""

from .base import VisionClient, NameResult


def get_client(provider: str, **kwargs) -> VisionClient:
    """Factory. provider must be one of: 'anthropic', 'openai'."""
    provider = provider.lower()
    if provider == "anthropic":
        from .anthropic import AnthropicVisionClient
        return AnthropicVisionClient(**kwargs)
    if provider == "openai":
        from .openai import OpenAIVisionClient
        return OpenAIVisionClient(**kwargs)
    raise ValueError(f"Unknown AI provider: {provider!r}. Use 'anthropic' or 'openai'.")
