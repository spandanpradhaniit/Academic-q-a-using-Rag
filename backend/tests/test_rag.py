import asyncio

import faiss
import numpy as np
from types import SimpleNamespace

from app.rag import indexing, ingestion
from app.rag.ingestion import chunk_pages


def test_chunks_retain_page_numbers(monkeypatch):
    monkeypatch.setattr(ingestion, "get_settings", lambda: SimpleNamespace(chunk_size=24, chunk_overlap=5))
    chunks = chunk_pages([{"page_number": 7, "content": "alpha beta gamma delta epsilon zeta eta theta iota"}])
    assert len(chunks) > 1
    assert {chunk["page_number"] for chunk in chunks} == {7}


def test_hybrid_search_returns_relevant_page_citations(tmp_path, monkeypatch):
    settings = SimpleNamespace(
        faiss_dir=tmp_path / "faiss",
        bm25_dir=tmp_path / "bm25",
        top_k_semantic=4,
        top_k_keyword=4,
        top_k_candidates=30,
        top_k_final=3,
        rrf_k=60,
        use_weighted_rrf=True,
        semantic_weight=0.7,
        keyword_weight=0.3
    )
    monkeypatch.setattr(indexing, "get_settings", lambda: settings)

    async def fake_embed(texts):
        return np.array([[1.0, 0.0] for _ in texts], dtype="float32")

    monkeypatch.setattr(indexing, "embed_texts", fake_embed)
    key = indexing._key("kb-1")
    path = settings.faiss_dir / key
    path.mkdir(parents=True)
    index = faiss.IndexFlatIP(2)
    index.add(np.array([[1.0, 0.0], [0.0, 1.0]], dtype="float32"))
    faiss.write_index(index, str(path / "index.faiss"))
    (path / "ids.json").write_text('["chunk-1", "chunk-2"]', encoding="utf-8")
    chunks = [
        {"chunk_id": "chunk-1", "content": "K-means clustering assigns points to centroids", "page_number": 4, "document_name": "ML.pdf"},
        {"chunk_id": "chunk-2", "content": "DBSCAN groups density connected points", "page_number": 9, "document_name": "ML.pdf"},
    ]
    results = asyncio.run(indexing.hybrid_search("kb-1", "K-means centroids", chunks))
    assert results
    assert results[0]["chunk_id"] == "chunk-1"
    assert results[0]["page_number"] == 4
    assert "rrf_score" in results[0]
    assert "semantic_rank" in results[0]
    assert "keyword_rank" in results[0]


def test_rrf_per_method_info_and_caching(tmp_path, monkeypatch):
    settings = SimpleNamespace(
        faiss_dir=tmp_path / "faiss",
        bm25_dir=tmp_path / "bm25",
        top_k_semantic=4,
        top_k_keyword=4,
        top_k_candidates=30,
        top_k_final=3,
        rrf_k=60,
        use_weighted_rrf=True,
        semantic_weight=0.7,
        keyword_weight=0.3
    )
    monkeypatch.setattr(indexing, "get_settings", lambda: settings)

    chunks = [
        {"chunk_id": "c1", "content": "apple banana fruit", "page_number": 1},
        {"chunk_id": "c2", "content": "orange citrus fruit", "page_number": 2},
    ]
    indexing.invalidate_bm25_cache()
    results = asyncio.run(indexing.hybrid_search("kb-test", "apple", chunks))
    assert len(results) > 0
    c1_res = [r for r in results if r["chunk_id"] == "c1"][0]
    assert c1_res["keyword_rank"] == 1
    assert c1_res["keyword_score"] is not None
    assert c1_res["rrf_score"] > 0

    # Ensure BM25 cache is populated
    assert "kb-test" in indexing._bm25_cache
    indexing.invalidate_bm25_cache("kb-test")
    assert "kb-test" not in indexing._bm25_cache


def test_hybrid_search_does_not_rank_zero_score_bm25_chunks(tmp_path, monkeypatch):
    settings = SimpleNamespace(
        faiss_dir=tmp_path / "faiss",
        bm25_dir=tmp_path / "bm25",
        top_k_candidates=30,
        top_k_final=3,
        rrf_k=60,
        use_weighted_rrf=True,
        semantic_weight=0.7,
        keyword_weight=0.3,
    )
    monkeypatch.setattr(indexing, "get_settings", lambda: settings)
    indexing.invalidate_bm25_cache("kb-no-keyword-match")
    chunks = [
        {"chunk_id": "c1", "content": "apple banana fruit", "page_number": 1},
        {"chunk_id": "c2", "content": "orange citrus fruit", "page_number": 2},
    ]

    results = asyncio.run(indexing.hybrid_search("kb-no-keyword-match", "quantum mechanics", chunks))

    assert results == []


def test_pdf_text_extraction_preserves_page_number(tmp_path):
    import pymupdf

    pdf = tmp_path / "course-notes.pdf"
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "Academic notes describe clustering and research methods.")
    document.save(pdf)
    document.close()
    from app.rag.ingestion import extract_pdf_pages

    progress = []
    pages = extract_pdf_pages(
        pdf,
        progress_callback=lambda processed, total: progress.append((processed, total)),
    )
    assert pages[0]["page_number"] == 1
    assert "clustering" in pages[0]["content"]
    assert progress == [(1, 1)]


def test_hybrid_search_returns_empty_when_no_chunks():
    results = asyncio.run(indexing.hybrid_search("kb-1", "anything", []))
    assert results == []
