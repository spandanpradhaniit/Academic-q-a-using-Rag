from qdrant_client import QdrantClient

from app.rag import vector_store


def test_qdrant_vector_upsert_search_and_document_delete(monkeypatch):
    client = QdrantClient(":memory:")
    monkeypatch.setattr(vector_store, "_client", lambda: client)

    vector_store.upsert_vectors(
        "kb-owner-one",
        [
            {
                "chunk_id": "doc-a:0",
                "document_id": "doc-a",
                "vector": [1.0, 0.0],
            },
            {
                "chunk_id": "doc-b:0",
                "document_id": "doc-b",
                "vector": [0.0, 1.0],
            },
        ],
        vector_size=2,
    )

    results = vector_store.search_vectors("kb-owner-one", [0.9, 0.1], 2)
    assert results[0][0] == "doc-a:0"
    assert results[0][1] > results[1][1]

    vector_store.delete_document_vectors("kb-owner-one", "doc-a")

    remaining = vector_store.search_vectors("kb-owner-one", [1.0, 0.0], 2)
    assert [chunk_id for chunk_id, _ in remaining] == ["doc-b:0"]
    assert vector_store.search_vectors("different-kb", [1.0, 0.0], 2) == []
