from __future__ import annotations
from app.ai.client import AIClient

_client: AIClient | None = None


def get_ai_client() -> AIClient:
    """
    Dependency helper to retrieve the correct configured AIClient instance.
    """
    global _client
    if _client is None:
        from app.ai.remote_client import RemoteAIClient
        _client = RemoteAIClient()
    return _client
