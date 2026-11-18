"""Text → 384-d unit vectors. fastembed (local, free) in dev/prod; feature hashing in tests/CI."""

import hashlib
import logging
import math
import re
import threading
from collections.abc import Sequence

from app.core.config import BACKEND_DIR, settings
from app.models import EMBEDDING_DIM

log = logging.getLogger(__name__)
_lock = threading.Lock()
_model = None
_TOKEN = re.compile(r"[a-z0-9]+")


class EmbeddingUnavailable(RuntimeError):
    pass


def provider_name() -> str:
    return "hash" if settings.embeddings_provider.strip().lower() == "hash" else "fastembed"


# ---------------------------------------------------------------- hash (deterministic)
def _bucket(feature: str) -> tuple[int, float]:
    h = hashlib.blake2b(feature.encode(), digest_size=8).digest()
    n = int.from_bytes(h, "little")
    return n % EMBEDDING_DIM, (1.0 if (n >> 63) & 1 else -1.0)


def _stem(tok: str) -> str:
    for suffix in ("ing", "es", "s"):
        if len(tok) > len(suffix) + 2 and tok.endswith(suffix):
            return tok[: -len(suffix)]
    return tok


def hash_embed(text: str) -> list[float]:
    vec = [0.0] * EMBEDDING_DIM
    tokens = [_stem(t) for t in _TOKEN.findall(text.lower())]
    for tok in tokens:
        idx, sign = _bucket("w:" + tok)
        vec[idx] += 2.0 * sign
        padded = f"#{tok}#"
        for i in range(len(padded) - 2):
            idx, sign = _bucket("c:" + padded[i : i + 3])
            vec[idx] += 0.5 * sign
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


# ---------------------------------------------------------------- fastembed
def _fastembed():
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                try:
                    from fastembed import TextEmbedding

                    _model = TextEmbedding(
                        settings.embedding_model, cache_dir=str(BACKEND_DIR / ".fastembed_cache")
                    )
                except Exception as exc:  # noqa: BLE001 — network/model download problems
                    raise EmbeddingUnavailable(f"fastembed failed to load: {exc}") from exc
    return _model


def _clean(texts: Sequence[str]) -> list[str]:
    return [(t or "").strip()[:2000] or "item" for t in texts]


def embed_passages(texts: Sequence[str]) -> list[list[float]]:
    texts = _clean(texts)
    if not texts:
        return []
    if provider_name() == "hash":
        return [hash_embed(t) for t in texts]
    model = _fastembed()
    return [v.tolist() for v in model.passage_embed(texts)]


def embed_query(text: str) -> list[float]:
    (text,) = _clean([text])
    if provider_name() == "hash":
        return hash_embed(text)
    model = _fastembed()
    return next(iter(model.query_embed(text))).tolist()


def warm_up() -> None:
    """Load the model at startup so the first search isn't slow. Never raises."""
    if provider_name() == "hash":
        return
    try:
        embed_query("warm up")
    except EmbeddingUnavailable as exc:
        log.error("%s — semantic search is off until it loads", exc)
