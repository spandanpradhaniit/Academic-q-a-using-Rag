from __future__ import annotations

import math


def retrieval_metrics(
    ranked_sources: list[dict],
    relevant_sources: set[tuple[str, int]],
    k: int = 5,
) -> dict[str, float]:
    if not relevant_sources:
        return {
            "recall_at_5": 0.0,
            "mrr": 0.0,
            "ndcg_at_5": 0.0,
            "page_hit_rate": 0.0,
        }

    top = ranked_sources[:k]
    hits = [
        (str(row["document_id"]), int(row["page_number"])) in relevant_sources
        for row in top
    ]
    hit_count = sum(hits)
    reciprocal_rank = next(
        (1.0 / rank for rank, hit in enumerate(hits, start=1) if hit),
        0.0,
    )
    dcg = sum(
        1.0 / math.log2(rank + 1)
        for rank, hit in enumerate(hits, start=1)
        if hit
    )
    ideal_hits = min(len(relevant_sources), k)
    idcg = sum(
        1.0 / math.log2(rank + 1)
        for rank in range(1, ideal_hits + 1)
    )
    return {
        "recall_at_5": hit_count / len(relevant_sources),
        "mrr": reciprocal_rank,
        "ndcg_at_5": dcg / idcg if idcg else 0.0,
        "page_hit_rate": float(any(hits)),
    }


def is_correct_refusal(answer: str) -> bool:
    normalized = (answer or "").lower()
    refusal_markers = (
        "not enough information",
        "not found in the provided documents",
        "do not contain enough information",
        "do not have enough information",
        "insufficient information",
        "cannot determine",
        "unable to determine",
    )
    return any(marker in normalized for marker in refusal_markers)
