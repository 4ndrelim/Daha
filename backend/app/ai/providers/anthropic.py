"""Optional direct-Claude vision (AI_PROVIDER=anthropic). Structured output → DetectionPayload."""

import base64
import time

from app.ai.normalize import normalize_items
from app.ai.prompts import VISION_SYSTEM, vision_task_inline
from app.ai.providers.base import ProviderError
from app.ai.schemas import DetectionPayload, ProviderResult
from app.core.config import settings

# $ per 1M tokens (input, output); keep in sync with the model you set in ANTHROPIC_MODEL.
PRICES = {
    "claude-opus-5-5": (4.0, 20.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-haiku-5-5": (0.10, 0.50),
}


class AnthropicVisionProvider:
    name = "anthropic"

    def __init__(self):
        self.model = settings.anthropic_model
        self._client = None

    def _get_client(self):
        if not settings.anthropic_api_key:
            raise ProviderError("ANTHROPIC_API_KEY not set", "AI scanning isn't set up yet")
        if self._client is None:
            import anthropic

            self._client = anthropic.AsyncAnthropic(
                api_key=settings.anthropic_api_key, timeout=120.0, max_retries=2
            )
        return self._client

    async def detect(self, image_jpeg: bytes, filename: str) -> ProviderResult:
        import anthropic

        client = self._get_client()
        start = time.monotonic()
        try:
            resp = await client.beta.messages.parse(
                model=self.model,
                max_tokens=16000,
                system=VISION_SYSTEM,
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
                output_config={"effort": settings.anthropic_effort},
                output_format=DetectionPayload,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": base64.b64encode(image_jpeg).decode(),
                                },
                            },
                            {"type": "text", "text": vision_task_inline()},
                        ],
                    }
                ],
            )
        except anthropic.RateLimitError as exc:
            raise ProviderError("anthropic 429", "The AI is busy — try again in a minute") from exc
        except anthropic.APIStatusError as exc:
            raise ProviderError(f"anthropic HTTP {exc.status_code}") from exc
        except anthropic.APIConnectionError as exc:
            raise ProviderError("anthropic connection error") from exc
        if resp.stop_reason == "refusal":
            raise ProviderError("anthropic refusal", "We can't scan this photo")
        parsed = resp.parsed_output
        if parsed is None:
            raise ProviderError(f"anthropic: no parsed output (stop={resp.stop_reason})")
        price_in, price_out = PRICES.get(self.model, (4.0, 20.0))
        usage = resp.usage
        cost = (usage.input_tokens * price_in + usage.output_tokens * price_out) / 1_000_000
        return ProviderResult(
            items=normalize_items([i.model_dump() for i in parsed.items]),
            latency_ms=int((time.monotonic() - start) * 1000),
            cost_usd=round(cost, 5),
            raw={"id": resp.id, "model": resp.model, "stop_reason": resp.stop_reason},
        )
