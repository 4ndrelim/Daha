from functools import lru_cache
from typing import Protocol

from app.ai.schemas import ProviderResult
from app.core.config import settings


class ProviderError(RuntimeError):
    """A provider call failed. `user_message` is safe to show; str(exc) is for logs."""

    def __init__(self, detail: str, user_message: str = "We couldn't read this photo. Try again."):
        super().__init__(detail)
        self.user_message = user_message


class VisionProvider(Protocol):
    name: str
    model: str

    async def detect(self, image_jpeg: bytes, filename: str) -> ProviderResult: ...


@lru_cache
def _provider(name: str) -> VisionProvider:
    if name == "mock":
        from app.ai.providers.mock import MockVisionProvider

        return MockVisionProvider()
    if name == "harnessrouter":
        from app.ai.providers.harnessrouter import HarnessRouterVisionProvider

        return HarnessRouterVisionProvider()
    if name == "anthropic":
        from app.ai.providers.anthropic import AnthropicVisionProvider

        return AnthropicVisionProvider()
    raise ValueError(f"Unknown AI_PROVIDER {name!r} (use mock | harnessrouter | anthropic)")


def get_vision_provider() -> VisionProvider:
    return _provider(settings.ai_provider.strip().lower())
