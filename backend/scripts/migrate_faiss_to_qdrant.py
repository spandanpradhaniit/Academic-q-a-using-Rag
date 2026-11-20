from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select

from app.core.config import get_settings
from app.database.connection import SessionLocal
from app.database.models import Document, DocumentChunk
from app.rag.indexing import rebuild_indexes


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Copy one FAISS-backed knowledge base into Qdrant."
    )
    parser.add_argument("knowledge_base_id")
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Required to confirm this external vector-store write.",
    )
    args = parser.parse_args()
    settings = get_settings()
    if not args.confirm:
        parser.error("Pass --confirm after verifying QDRANT_URL and the knowledge base.")
    if not settings.qdrant_url:
        parser.error("Set QDRANT_URL before migrating.")
    if settings.vector_store.lower() != "qdrant":
        parser.error("Set VECTOR_STORE=qdrant before migrating.")

    with SessionLocal() as db:
        rows = db.execute(
            select(DocumentChunk, Document)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(
                Document.knowledge_base_id == args.knowledge_base_id,
                Document.status == "indexed",
            )
        ).all()
    if not rows:
        parser.error("No indexed document chunks found for that knowledge base.")

    chunks = [
        {
            "chunk_id": chunk.id,
            "content": chunk.content,
            "document_id": document.id,
        }
        for chunk, document in rows
    ]
    asyncio.run(rebuild_indexes(args.knowledge_base_id, chunks))

    with SessionLocal() as db:
        from app.database.models import KnowledgeBase

        knowledge_base = db.get(KnowledgeBase, args.knowledge_base_id)
        if knowledge_base is None:
            parser.error("Knowledge base disappeared during migration.")
        knowledge_base.vector_store = "qdrant"
        db.commit()
    print(f"Upserted {len(chunks)} chunks to Qdrant.")


if __name__ == "__main__":
    main()
