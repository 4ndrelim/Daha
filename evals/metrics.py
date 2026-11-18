"""Small, dependency-free ranking and set metrics."""

import math
import statistics


def ndcg_at_k(ranked: list[str], relevance: dict[str, int], k: int = 10) -> float:
    dcg = sum((2 ** relevance.get(x, 0) - 1) / math.log2(i + 2) for i, x in enumerate(ranked[:k]))
    ideal = sorted(relevance.values(), reverse=True)[:k]
    idcg = sum((2**r - 1) / math.log2(i + 2) for i, r in enumerate(ideal))
    return dcg / idcg if idcg else 0.0


def precision_at_k(ranked: list[str], relevant: set[str], k: int = 5) -> float:
    top = ranked[:k]
    return sum(1 for x in top if x in relevant) / k if top else 0.0


def mrr(ranked: list[str], relevant: set[str]) -> float:
    for i, x in enumerate(ranked):
        if x in relevant:
            return 1.0 / (i + 1)
    return 0.0


def p95(values: list[float]) -> float:
    if not values:
        return 0.0
    if len(values) < 2:
        return values[0]
    return statistics.quantiles(values, n=20)[-1]


def mean(values) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0
