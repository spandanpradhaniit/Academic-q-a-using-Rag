from __future__ import annotations

import hashlib
import uuid

from app.core.config import get_settings


def _collection_name(knowledge_base_id: str) -> str:
    digest = hashlib.sha256(knowledge_base_id.encode("utf-8")).hexdigest()[:32]
    return f"academic_kb_{digest}"


def _point_id(chunk_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"academic-rag:{chunk_id}"))


def _client():
    settings = get_settings()
    if not settings.qdrant_url:
        raise RuntimeError("QDRANT_URL is required when VECTOR_STORE=qdrant.")
    try:
        from qdrant_client import QdrantClient
    except ImportError as exc:
        raise RuntimeError(
            "Install qdrant-client to use VECTOR_STORE=qdrant."
        ) from exc
    return QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None)


def upsert_vectors(
    knowledge_base_id: str,
    points: list[dict],
    vector_size: int,
) -> None:
    if not points:
        return
    from qdrant_client import models

    client = _client()
    collection = _collection_name(knowledge_base_id)
    if not client.collection_exists(collection):
        client.create_collection(
            collection_name=collection,
            vectors_config=models.VectorParams(
                size=vector_size,
                distance=models.Distance.COSINE,
            ),
        )
    client.upsert(
        collection_name=collection,
        wait=True,
        points=[
            models.PointStruct(
                id=_point_id(item["chunk_id"]),
                vector=item["vector"],
                payload={
                    "chunk_id": item["chunk_id"],
                    "document_id": item["document_id"],
                },
            )
            for item in points
        ],
    )


def delete_document_vectors(knowledge_base_id: str, document_id: str) -> None:
    from qdrant_client import models

    client = _client()
    collection = _collection_name(knowledge_base_id)
    if not client.collection_exists(collection):
        return
    client.delete(
        collection_name=collection,
        wait=True,
        points_selector=models.FilterSelector(
            filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="document_id",
                        match=models.MatchValue(value=document_id),
                    )
                ]
            )
        ),
    )


def search_vectors(
    knowledge_base_id: str,
    query_vector: list[float],
    limit: int,
) -> list[tuple[str, float]]:
    client = _client()
    collection = _collection_name(knowledge_base_id)
    if not client.collection_exists(collection):
        return []
    response = client.query_points(
        collection_name=collection,
        query=query_vector,
        limit=limit,
        with_payload=True,
    )
    results: list[tuple[str, float]] = []
    for point in response.points:
        payload = point.payload or {}
        chunk_id = payload.get("chunk_id")
        if isinstance(chunk_id, str):
            results.append((chunk_id, float(point.score)))
    return results


def delete_knowledge_base(knowledge_base_id: str) -> None:
    client = _client()
    collection = _collection_name(knowledge_base_id)
    if client.collection_exists(collection):
        client.delete_collection(collection)
