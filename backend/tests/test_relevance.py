from types import SimpleNamespace

from app.rag.relevance import compute_confidence, relevance_gate


def test_relevance_gate_filters_low_relevance_candidates(monkeypatch):
    monkeypatch.setattr(
        "app.rag.relevance.get_settings",
        lambda: SimpleNamespace(min_relevance=0.25),
    )
    candidates = [
        {"chunk_id": "a", "rerank_score": 0.8},
        {"chunk_id": "b", "rerank_score": 0.1},
    ]
    kept = relevance_gate(candidates)
    assert [item["chunk_id"] for item in kept] == ["a"]


def test_compute_confidence_flags_no_context_answer():
    candidates = [{"chunk_id": "a", "rerank_score": 0.8}]
    confidence, low_confidence = compute_confidence(candidates, "The uploaded documents do not contain enough information.")
    assert confidence <= 0.35
    assert low_confidence is True


def test_compute_confidence_returns_high_score_for_good_match():
    candidates = [{"chunk_id": "a", "rerank_score": 0.8}]
    confidence, low_confidence = compute_confidence(candidates, "Normalization reduces redundancy.")
    assert confidence == 0.8
    assert low_confidence is False
