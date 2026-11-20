from app.core.config import get_settings


def relevance_gate(candidates: list[dict]) -> list[dict]:
    if not candidates:
        return []
    settings = get_settings()
    threshold = float(getattr(settings, "min_relevance", 0.001))
    kept: list[dict] = []
    for candidate in candidates:
        if candidate.get("rerank_score") is not None:
            try:
                if float(candidate["rerank_score"]) >= threshold:
                    kept.append(candidate)
            except (TypeError, ValueError):
                continue
            continue

        semantic_score = candidate.get("semantic_score")
        keyword_score = candidate.get("keyword_score")
        try:
            semantic_match = (
                semantic_score is not None and float(semantic_score) >= threshold
            )
            keyword_match = keyword_score is not None and float(keyword_score) > 0
        except (TypeError, ValueError):
            semantic_match = keyword_match = False

        if semantic_match or keyword_match:
            kept.append(candidate)
            continue

        if semantic_score is None and keyword_score is None:
            score = candidate.get("rrf_score", candidate.get("score"))
            try:
                if score is not None and float(score) >= 0.0001:
                    kept.append(candidate)
            except (TypeError, ValueError):
                continue
    return kept


def compute_confidence(candidates: list[dict], answer: str | None = None) -> tuple[float, bool]:
    if not candidates:
        return 0.0, True
    top_score = 0.0
    for candidate in candidates:
        score = candidate.get("rerank_score")
        if score is None:
            score = candidate.get("semantic_score")
        if score is None:
            score = candidate.get("keyword_score")
        if score is None:
            score = candidate.get("score")
        if score is None:
            continue
        try:
            numeric = float(score)
        except (TypeError, ValueError):
            continue
        if numeric > top_score:
            top_score = numeric
    calibrated = 0.0 if top_score <= 0 else min(1.0, max(0.0, top_score))
    if answer and any(marker in (answer or "").lower() for marker in (
        "not enough information",
        "not found in the provided documents",
        "insufficient information",
        "cannot determine",
        "do not contain enough information",
        "do not have enough information",
    )):
        calibrated = min(calibrated, 0.35)
        return calibrated, True
    return calibrated, calibrated < 0.6
