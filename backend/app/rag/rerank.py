import asyncio
import hashlib
import json
import os
from collections import OrderedDict
from typing import Any, Iterable

import numpy as np

from app.core.config import get_settings

_CACHE: OrderedDict[tuple[str, str], float] = OrderedDict()
_MAX_CACHE = 512


def _digest_key(question: str, chunk_id: str) -> str:
    return hashlib.sha256(f"{question}\n{chunk_id}".encode("utf-8")).hexdigest()


def _truncate_text(text: str, max_chars: int = 1500) -> str:
    value = (text or "").strip()
    if len(value) <= max_chars:
        return value
    return value[:max_chars].rstrip()


def _normalize_score(score: Any) -> float:
    try:
        return float(score)
    except (TypeError, ValueError):
        return 0.0


class Reranker:
    name = "none"

    async def rerank(self, question: str, candidates: list[dict]) -> list[dict]:
        return candidates


class NoReranker(Reranker):
    name = "none"


class BgeLocalReranker(Reranker):
    name = "bge_local"
    _model = None
    _lock = asyncio.Lock()

    @classmethod
    async def _get_model(cls):
        if cls._model is not None:
            return cls._model
        async with cls._lock:
            if cls._model is not None:
                return cls._model
            try:
                from sentence_transformers import CrossEncoder
            except Exception:
                cls._model = None
                return None
            cls._model = CrossEncoder("BAAI/bge-reranker-base")
            return cls._model

    async def rerank(self, question: str, candidates: list[dict]) -> list[dict]:
        if not candidates:
            return []
        model = await self._get_model()
        if model is None:
            return list(candidates)
        texts = [
            (question, _truncate_text(str(item.get("content", "")), 1500))
            for item in candidates
        ]
        pairs = [pair for pair in texts if pair[1]]
        if not pairs:
            return list(candidates)

        def _predict() -> np.ndarray:
            return np.asarray(model.predict(pairs, show_progress_bar=False), dtype=float)

        scores = await asyncio.to_thread(_predict)
        for item, score in zip(candidates, scores):
            item["rerank_score"] = float(score)
            item["rerank_rank"] = None
        ordered = sorted(candidates, key=lambda x: float(x.get("rerank_score", 0.0)), reverse=True)
        for rank, item in enumerate(ordered, start=1):
            item["rerank_rank"] = rank
        return ordered


class CohereReranker(Reranker):
    name = "cohere"

    async def rerank(self, question: str, candidates: list[dict]) -> list[dict]:
        if not candidates:
            return []
        api_key = os.getenv("COHERE_API_KEY") or getattr(get_settings(), "cohere_api_key", "")
        if not api_key:
            return list(candidates)
        try:
            import cohere
        except Exception:
            return list(candidates)
        documents = [_truncate_text(str(item.get("content", "")), 1500) for item in candidates]
        try:
            client = cohere.Client(api_key)
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    lambda: client.rerank(
                        model="rerank-v3.5",
                        query=question,
                        documents=documents,
                        top_n=len(documents),
                    )
                ),
                timeout=float(getattr(get_settings(), "rerank_timeout_seconds", 5)),
            )
        except Exception:
            return list(candidates)

        ranked = list(candidates)
        if hasattr(response, "results"):
            score_by_index = {result.index: _normalize_score(getattr(result, "relevance_score", 0.0)) for result in response.results}
            for index, item in enumerate(ranked):
                item["rerank_score"] = score_by_index.get(index, 0.0)
            ordered = sorted(ranked, key=lambda x: x.get("rerank_score", 0.0), reverse=True)
            for rank, item in enumerate(ordered, start=1):
                item["rerank_rank"] = rank
            return ordered
        return ranked


def get_reranker(name: str | None = None) -> Reranker:
    selected = (name or getattr(get_settings(), "reranker", "none")).lower()
    if selected == "bge_local":
        return BgeLocalReranker()
    if selected == "cohere":
        return CohereReranker()
    return NoReranker()


async def rerank_candidates(question: str, candidates: list[dict], reranker_name: str | None = None) -> list[dict]:
    if not candidates:
        return []
    selected = get_reranker(reranker_name)
    ordered = await selected.rerank(question, list(candidates))
    for index, item in enumerate(ordered, start=1):
        item["rerank_score"] = item.get("rerank_score", item.get("score", 0.0))
        item["rerank_rank"] = item.get("rerank_rank", index)
        _CACHE[(question, str(item.get("chunk_id", "")))] = float(item.get("rerank_score", 0.0))
        if len(_CACHE) > _MAX_CACHE:
            _CACHE.popitem(last=False)
    return ordered


def rerank_score_for(question: str, chunk_id: str) -> float | None:
    value = _CACHE.get((question, str(chunk_id)))
    return None if value is None else float(value)
