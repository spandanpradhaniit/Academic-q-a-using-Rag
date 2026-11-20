import asyncio
import json
import re
from collections import OrderedDict

import faiss
import numpy as np
from langchain_openai import OpenAIEmbeddings
from rank_bm25 import BM25Okapi

from app.core.config import get_settings
from app.rag.rerank import rerank_candidates
from app.rag.vector_store import (
    delete_document_vectors,
    delete_knowledge_base,
    search_vectors,
    upsert_vectors,
)

_model = None
_model_lock = asyncio.Lock()
_index_locks: dict[str, asyncio.Lock] = {}
_bm25_cache: OrderedDict[str, tuple[BM25Okapi, list[str]]] = OrderedDict()
MAX_BM25_CACHE_ITEMS = 128


async def embed_texts(texts: list[str]) -> np.ndarray:
    global _model
    if _model is None:
        async with _model_lock:
            if _model is None:
                s = get_settings()
                if s.openai_api_key:
                    _model = OpenAIEmbeddings(model=s.embedding_model, api_key=s.openai_api_key)
                else:
                    from fastembed import TextEmbedding

                    _model = TextEmbedding()
    if hasattr(_model, "aembed_documents"):
        vectors = await _model.aembed_documents(texts)
        result = np.asarray(vectors, dtype="float32")
    else:
        embeddings = await asyncio.to_thread(lambda: list(_model.embed(texts)))
        result = np.asarray(embeddings, dtype="float32")
    faiss.normalize_L2(result)
    return result


def _key(knowledge_base_id: str, *_):
    return knowledge_base_id


def _tokenize(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


def invalidate_bm25_cache(knowledge_base_id: str | None = None) -> None:
    if knowledge_base_id:
        _bm25_cache.pop(knowledge_base_id, None)
    else:
        _bm25_cache.clear()


def _cache_bm25(key: str, bm25: BM25Okapi, ids: list[str]) -> None:
    _bm25_cache[key] = (bm25, ids)
    _bm25_cache.move_to_end(key)
    while len(_bm25_cache) > MAX_BM25_CACHE_ITEMS:
        _bm25_cache.popitem(last=False)


def _load_bm25_from_disk(knowledge_base_id: str) -> tuple[BM25Okapi, list[str]] | None:
    s = get_settings()
    corpus_path = s.bm25_dir / _key(knowledge_base_id) / "corpus.json"
    if not corpus_path.exists():
        return None
    try:
        payload = json.loads(corpus_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(payload, list):
        return None
    tokenized = [_tokenize(item["content"]) if isinstance(item, dict) and "content" in item else [] for item in payload]
    ids = [item["chunk_id"] for item in payload if isinstance(item, dict) and "chunk_id" in item]
    if not ids or len(tokenized) != len(ids):
        return None
    return BM25Okapi(tokenized), ids


def _get_or_create_bm25(knowledge_base_id: str, chunks: list[dict]) -> tuple[BM25Okapi, list[str]]:
    key = _key(knowledge_base_id)
    chunk_ids = [item["chunk_id"] for item in chunks]
    if key in _bm25_cache:
        bm25, ids = _bm25_cache[key]
        if ids == chunk_ids:
            _bm25_cache.move_to_end(key)
            return bm25, ids
        invalidate_bm25_cache(key)

    disk_bm25 = _load_bm25_from_disk(knowledge_base_id)
    if disk_bm25 and disk_bm25[1] == chunk_ids:
        _cache_bm25(key, disk_bm25[0], disk_bm25[1])
        return disk_bm25

    tokenized = [_tokenize(x["content"]) for x in chunks]
    bm25 = BM25Okapi(tokenized)
    ids = chunk_ids
    _cache_bm25(key, bm25, ids)
    return bm25, ids


def _persist_bm25_corpus(knowledge_base_id: str, chunks: list[dict]) -> None:
    path = get_settings().bm25_dir / _key(knowledge_base_id) / "corpus.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    corpus = [
        {"chunk_id": item["chunk_id"], "content": item["content"]}
        for item in chunks
    ]
    temporary.write_text(json.dumps(corpus), encoding="utf-8")
    temporary.replace(path)


async def rebuild_indexes(knowledge_base_id: str, chunks: list[dict]) -> None:
    s = get_settings()
    key = _key(knowledge_base_id)
    lock = _index_locks.setdefault(key, asyncio.Lock())
    async with lock:
        fd = s.faiss_dir / key
        bd = s.bm25_dir / key
        invalidate_bm25_cache(key)
        if not chunks:
            if getattr(s, "vector_store", "faiss").lower() == "qdrant":
                await asyncio.to_thread(delete_knowledge_base, knowledge_base_id)
            for p in (fd, bd):
                if p.exists():
                    import shutil

                    await asyncio.to_thread(shutil.rmtree, p)
            return

        vectors = await embed_texts([x["content"] for x in chunks])
        await asyncio.to_thread(bd.mkdir, parents=True, exist_ok=True)
        if getattr(s, "vector_store", "faiss").lower() == "qdrant":
            points = [
                {
                    "chunk_id": item["chunk_id"],
                    "document_id": item["document_id"],
                    "vector": vector.tolist(),
                }
                for item, vector in zip(chunks, vectors)
            ]
            await asyncio.to_thread(
                upsert_vectors,
                knowledge_base_id,
                points,
                int(vectors.shape[1]),
            )
        else:
            ix = faiss.IndexFlatIP(vectors.shape[1])
            ix.add(vectors)
            ids = [x["chunk_id"] for x in chunks]
            await asyncio.to_thread(fd.mkdir, parents=True, exist_ok=True)
            await asyncio.to_thread(faiss.write_index, ix, str(fd / "index.faiss"))
            await asyncio.to_thread((fd / "ids.json").write_text, json.dumps(ids), "utf-8")
        await asyncio.to_thread(_persist_bm25_corpus, knowledge_base_id, chunks)
        _get_or_create_bm25(knowledge_base_id, chunks)


async def upsert_document_index(
    knowledge_base_id: str,
    document_id: str,
    chunks: list[dict],
) -> None:
    settings = get_settings()
    if getattr(settings, "vector_store", "faiss").lower() != "qdrant":
        raise RuntimeError("Per-document vector upsert requires VECTOR_STORE=qdrant.")
    key = _key(knowledge_base_id)
    lock = _index_locks.setdefault(key, asyncio.Lock())
    async with lock:
        corpus_path = settings.bm25_dir / key / "corpus.json"
        corpus_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            old_corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            old_corpus = []
        if not isinstance(old_corpus, list):
            raise ValueError(f"BM25 corpus for knowledge base {knowledge_base_id} is invalid.")
        retained = [
            item
            for item in old_corpus
            if isinstance(item, dict)
            and not str(item.get("chunk_id", "")).startswith(f"{document_id}:")
        ]
        normalized_chunks = [
            {
                **item,
                "document_id": document_id,
            }
            for item in chunks
        ]
        combined = retained + [
            {"chunk_id": item["chunk_id"], "content": item["content"]}
            for item in normalized_chunks
        ]
        await asyncio.to_thread(_persist_bm25_corpus, knowledge_base_id, combined)
        invalidate_bm25_cache(key)
        if normalized_chunks:
            vectors = await embed_texts([item["content"] for item in normalized_chunks])
            points = [
                {
                    "chunk_id": item["chunk_id"],
                    "document_id": document_id,
                    "vector": vector.tolist(),
                }
                for item, vector in zip(normalized_chunks, vectors)
            ]
            await asyncio.to_thread(
                upsert_vectors,
                knowledge_base_id,
                points,
                int(vectors.shape[1]),
            )


async def delete_document_index(knowledge_base_id: str, document_id: str) -> None:
    settings = get_settings()
    if getattr(settings, "vector_store", "faiss").lower() != "qdrant":
        raise RuntimeError("Per-document vector deletion requires VECTOR_STORE=qdrant.")
    key = _key(knowledge_base_id)
    lock = _index_locks.setdefault(key, asyncio.Lock())
    async with lock:
        await asyncio.to_thread(
            delete_document_vectors,
            knowledge_base_id,
            document_id,
        )
        corpus_path = settings.bm25_dir / key / "corpus.json"
        if corpus_path.exists():
            payload = json.loads(corpus_path.read_text(encoding="utf-8"))
            if not isinstance(payload, list):
                raise ValueError(f"BM25 corpus for knowledge base {knowledge_base_id} is invalid.")
            retained = [
                item
                for item in payload
                if not str(item.get("chunk_id", "")).startswith(f"{document_id}:")
            ]
            await asyncio.to_thread(
                _persist_bm25_corpus,
                knowledge_base_id,
                retained,
            )
        invalidate_bm25_cache(key)


async def delete_knowledge_base_indexes(
    knowledge_base_id: str,
    vector_store: str | None = None,
) -> None:
    settings = get_settings()
    key = _key(knowledge_base_id)
    lock = _index_locks.setdefault(key, asyncio.Lock())
    async with lock:
        invalidate_bm25_cache(key)
        store = (vector_store or getattr(settings, "vector_store", "faiss")).lower()
        if store == "qdrant":
            await asyncio.to_thread(delete_knowledge_base, knowledge_base_id)
        for directory in (
            settings.faiss_dir / key,
            settings.bm25_dir / key,
        ):
            if directory.exists():
                import shutil

                await asyncio.to_thread(shutil.rmtree, directory)


def _keyword_fallback_scores(question: str, chunks: list[dict], limit: int) -> dict[str, float]:
    tokens = _tokenize(question)
    if not tokens:
        return {}
    token_set = set(tokens)
    scores: dict[str, float] = {}
    for chunk in chunks:
        content_tokens = _tokenize(chunk.get("content", ""))
        overlap = sum(1 for token in token_set if token in content_tokens)
        if overlap > 0:
            scores[chunk["chunk_id"]] = float(overlap)
    return dict(sorted(scores.items(), key=lambda pair: pair[1], reverse=True)[:limit])


async def hybrid_search(knowledge_base_id: str, question: str, chunks: list[dict]) -> list[dict]:
    if not chunks:
        return []

    s = get_settings()
    key = _key(knowledge_base_id)
    fp = s.faiss_dir / key / "index.faiss"
    ip = s.faiss_dir / key / "ids.json"
    candidate_limit = min(int(getattr(s, "top_k_candidates", 30)), len(chunks))
    rrf_k = int(getattr(s, "rrf_k", 60))
    use_weighted = bool(getattr(s, "use_weighted_rrf", True))
    semantic_weight = float(getattr(s, "semantic_weight", 0.7))
    keyword_weight = float(getattr(s, "keyword_weight", 0.3))
    if use_weighted:
        total_weight = max(semantic_weight + keyword_weight, 1.0)
        w_sem = semantic_weight / total_weight
        w_kw = keyword_weight / total_weight
    else:
        w_sem = 0.5
        w_kw = 0.5

    sem_scores: dict[str, float] = {}
    sem_ranks: dict[str, int] = {}
    if getattr(s, "vector_store", "faiss").lower() == "qdrant":
        query_vector = (await embed_texts([question]))[0].tolist()
        ranked = await asyncio.to_thread(
            search_vectors,
            knowledge_base_id,
            query_vector,
            candidate_limit,
        )
        for rank, (chunk_id, score) in enumerate(ranked, start=1):
            sem_ranks[chunk_id] = rank
            sem_scores[chunk_id] = score
    elif fp.exists() and ip.exists():
        q = await embed_texts([question])
        ix = await asyncio.to_thread(faiss.read_index, str(fp))
        scores, positions = await asyncio.to_thread(ix.search, q, min(candidate_limit, ix.ntotal or candidate_limit))
        with open(ip, "r", encoding="utf-8") as fh:
            ids = json.load(fh)
        for rank, (score, position) in enumerate(zip(scores[0], positions[0]), start=1):
            if position < 0 or position >= len(ids):
                continue
            chunk_id = ids[int(position)]
            if chunk_id not in sem_ranks:
                sem_ranks[chunk_id] = rank
                sem_scores[chunk_id] = float(score)

    tokens = _tokenize(question)
    bm25, bm25_ids = _get_or_create_bm25(knowledge_base_id, chunks)
    kw_scores: dict[str, float] = {}
    kw_ranks: dict[str, int] = {}
    bm_scores = bm25.get_scores(tokens) if tokens else np.zeros(len(chunks), dtype=float)
    order = sorted(range(len(bm_scores)), key=lambda i: float(bm_scores[i]), reverse=True)[:candidate_limit]

    for rank, idx in enumerate(order, start=1):
        score = float(bm_scores[int(idx)])
        if score <= 0:
            continue
        chunk_id = bm25_ids[int(idx)]
        kw_ranks[chunk_id] = rank
        kw_scores[chunk_id] = score

    if not kw_scores:
        kw_scores = _keyword_fallback_scores(question, chunks, candidate_limit)
        kw_ranks = {chunk_id: rank for rank, chunk_id in enumerate(kw_scores.keys(), start=1)}

    by_id = {chunk["chunk_id"]: chunk for chunk in chunks}
    results: list[dict] = []
    for cid in set(sem_ranks) | set(kw_ranks):
        chunk = by_id.get(cid)
        if chunk is None:
            continue
        semantic_rank = sem_ranks.get(cid)
        keyword_rank = kw_ranks.get(cid)
        rrf_score = 0.0
        if semantic_rank is not None:
            rrf_score += (w_sem / (rrf_k + semantic_rank))
        if keyword_rank is not None:
            rrf_score += (w_kw / (rrf_k + keyword_rank))

        row = dict(chunk)
        row["score"] = round(rrf_score, 6)
        row["rrf_score"] = round(rrf_score, 6)
        row["semantic_rank"] = semantic_rank
        row["semantic_score"] = round(sem_scores.get(cid, 0.0), 6) if cid in sem_scores else None
        row["keyword_rank"] = keyword_rank
        row["keyword_score"] = round(kw_scores.get(cid, 0.0), 6) if cid in kw_scores else None
        results.append(row)

    results.sort(key=lambda x: x["rrf_score"], reverse=True)
    reranked = results[: int(getattr(s, "rerank_top_k", 30))]
    reranker_name = getattr(s, "reranker", "none")
    if reranker_name and str(reranker_name).lower() != "none":
        reranked = await rerank_candidates(question, reranked, reranker_name)
        reranked = reranked[: int(getattr(s, "top_k_final", 5))]
    else:
        reranked = results[: int(getattr(s, "top_k_final", 5))]
    return reranked
