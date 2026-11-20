import asyncio
import sys
from types import ModuleType, SimpleNamespace

from app.rag import rerank


async def _fake_rerank(question: str, candidates: list[dict]) -> list[dict]:
    sorted_candidates = sorted(candidates, key=lambda item: item.get("score", 0.0), reverse=True)
    for index, item in enumerate(sorted_candidates, start=1):
        item["rerank_score"] = 0.95 if item["chunk_id"] == "c1" else 0.30
        item["rerank_rank"] = index
    return sorted_candidates


def test_rerank_candidates_returns_ordered_results(monkeypatch):
    class DummyReranker:
        async def rerank(self, question: str, candidates: list[dict]) -> list[dict]:
            return await _fake_rerank(question, candidates)

    monkeypatch.setattr(rerank, "get_reranker", lambda name: DummyReranker())
    candidates = [
        {"chunk_id": "c2", "content": "second candidate", "score": 0.2},
        {"chunk_id": "c1", "content": "first candidate", "score": 0.8},
    ]

    ordered = asyncio.run(rerank.rerank_candidates("what is the answer?", candidates, "bge_local"))

    assert ordered[0]["chunk_id"] == "c1"
    assert ordered[0]["rerank_rank"] == 1
    assert ordered[0]["rerank_score"] >= ordered[1]["rerank_score"]


def test_no_reranker_returns_original_order():
    candidates = [
        {"chunk_id": "c2", "content": "second candidate", "score": 0.2},
        {"chunk_id": "c1", "content": "first candidate", "score": 0.8},
    ]
    ordered = asyncio.run(rerank.rerank_candidates("what is the answer?", candidates, "none"))
    assert [item["chunk_id"] for item in ordered] == ["c2", "c1"]


def test_cohere_reranker_uses_candidate_positions_for_result_indices(monkeypatch):
    class FakeClient:
        def __init__(self, _api_key):
            pass

        def rerank(self, **_kwargs):
            return SimpleNamespace(
                results=[
                    SimpleNamespace(index=1, relevance_score=0.9),
                    SimpleNamespace(index=0, relevance_score=0.2),
                ]
            )

    fake_module = ModuleType("cohere")
    fake_module.Client = FakeClient
    monkeypatch.setitem(sys.modules, "cohere", fake_module)
    monkeypatch.setattr(
        rerank,
        "get_settings",
        lambda: SimpleNamespace(cohere_api_key="test-key", rerank_timeout_seconds=5),
    )
    candidates = [
        {"chunk_id": "doc-a:0", "content": "first source"},
        {"chunk_id": "doc-b:4", "content": "second source"},
    ]

    ordered = asyncio.run(rerank.CohereReranker().rerank("question", candidates))

    assert [item["chunk_id"] for item in ordered] == ["doc-b:4", "doc-a:0"]
    assert [item["rerank_score"] for item in ordered] == [0.9, 0.2]
