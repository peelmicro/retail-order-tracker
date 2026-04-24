"""Shared helpers for Claude-backed agents."""


class ApiKeyMissingError(RuntimeError):
    """Raised when an agent cannot find a real Anthropic API key."""


def is_placeholder_api_key(key: str | None) -> bool:
    return not key or key == "your-api-key-here"
