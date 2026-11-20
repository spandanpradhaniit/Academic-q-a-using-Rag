from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4
import asyncio

from sqlalchemy import delete, select

from app.core.config import get_settings
from app.database.connection import SessionLocal
from app.database.models import (
    Document,
    DocumentChunk,
    KnowledgeBase,
    ProcessingJob,
)
from app.rag.indexing import rebuild_indexes, upsert_document_index, _key
from app.rag.ingestion import chunk_pages, extract_pdf_pages
from app.services.storage import materialize_document


def process_document(document_id: str, processing_job_id: str | None = None) -> None:
    with SessionLocal() as db:
        doc = db.get(Document, document_id)
        if not doc:
            return

        doc.status = "processing"
        doc.processing_error = None
        job = (
            db.get(ProcessingJob, processing_job_id)
            if processing_job_id
            else db.scalar(
                select(ProcessingJob)
                .where(ProcessingJob.document_id == doc.id)
                .order_by(ProcessingJob.created_at.desc())
            )
        )
        if not job:
            job = ProcessingJob(
                id=str(uuid4()),
                document_id=doc.id,
                status="processing",
            )
            db.add(job)
        job.status = "processing"
        job.started_at = datetime.now(timezone.utc)
        db.commit()

        try:
            last_progress_commit = 0

            def update_progress(processed: int, total: int) -> None:
                nonlocal last_progress_commit
                doc.page_count = total
                job.pages_processed = processed
                if processed - last_progress_commit >= 5 or processed == total:
                    db.commit()
                    last_progress_commit = processed

            with TemporaryDirectory(prefix=f"academic-qa-{doc.id}-") as working_dir:
                pdf_path = materialize_document(
                    doc.file_path,
                    Path(working_dir) / "source.pdf",
                )
                pages = extract_pdf_pages(
                    pdf_path,
                    progress_callback=update_progress,
                )

            chunks = chunk_pages(pages)
            records = [
                DocumentChunk(
                    id=f"{doc.id}:{index}",
                    document_id=doc.id,
                    chunk_index=index,
                    content=chunk["content"],
                    page_number=chunk["page_number"],
                    token_count=chunk["token_count"],
                    metadata_json={
                        "document_id": doc.id,
                        "page_number": chunk["page_number"],
                        "chunk_index": index,
                        "document_name": doc.title,
                        "subject_id": doc.subject_id,
                    },
                )
                for index, chunk in enumerate(chunks)
            ]
            db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == doc.id))
            db.add_all(records)
            db.flush()

            all_chunks = db.scalars(
                select(DocumentChunk)
                .join(Document)
                .where(Document.knowledge_base_id == doc.knowledge_base_id)
            ).all()
            knowledge_base = db.get(KnowledgeBase, doc.knowledge_base_id)
            if not knowledge_base:
                raise RuntimeError(f"Knowledge base {doc.knowledge_base_id} not found.")
            knowledge_base.total_chunks = len(all_chunks)
            knowledge_base.total_documents = db.query(Document).filter(
                Document.knowledge_base_id == knowledge_base.id
            ).count()
            doc.chunk_count = len(records)
            doc.page_count = len(pages)
            db.commit()

            settings = get_settings()
            if settings.vector_store.lower() == "qdrant":
                asyncio.run(
                    upsert_document_index(
                        knowledge_base.id,
                        doc.id,
                        [
                            {"chunk_id": chunk.id, "content": chunk.content}
                            for chunk in records
                        ],
                    )
                )
                knowledge_base.vector_store = "qdrant"
            else:
                payload = [
                    {
                        "chunk_id": chunk.id,
                        "content": chunk.content,
                        "document_id": chunk.document_id,
                    }
                    for chunk in all_chunks
                ]
                asyncio.run(rebuild_indexes(knowledge_base.id, payload))
                knowledge_base.vector_store = "faiss"
                knowledge_base.faiss_index_path = str(
                    settings.faiss_dir / _key(knowledge_base.id)
                )
                knowledge_base.bm25_index_path = str(
                    settings.bm25_dir / _key(knowledge_base.id)
                )

            job.pages_processed = doc.page_count
            job.chunks_created = len(records)
            job.status = "completed"
            job.completed_at = datetime.now(timezone.utc)
            doc.status = "indexed"
            doc.updated_at = datetime.now(timezone.utc)
            db.commit()
        except Exception as exc:
            db.rollback()
            doc = db.get(Document, document_id)
            job = db.scalar(
                select(ProcessingJob)
                .where(ProcessingJob.document_id == document_id)
                .order_by(ProcessingJob.created_at.desc())
            )
            if doc:
                doc.status = "failed"
                doc.processing_error = str(exc)[:1000]
            if job:
                job.status = "failed"
                job.error_message = str(exc)[:1000]
                job.completed_at = datetime.now(timezone.utc)
            db.commit()
            raise
