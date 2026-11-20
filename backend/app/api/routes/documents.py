import hashlib, asyncio
from datetime import datetime, timezone
import logging
from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import select, or_
from sqlalchemy.orm import Session
from app.api.dependencies import CurrentUser
from app.core.config import get_settings
from app.database.connection import get_db
from app.database.models import Document, Subject, KnowledgeBase, ProcessingJob, DocumentChunk
from app.services.storage import delete_document_file, document_response, store_document
from app.core.sanitization import sanitize_filename
from app.rag.indexing import delete_document_index, rebuild_indexes

router=APIRouter(prefix="/documents",tags=["documents"])
logger = logging.getLogger(__name__)


def _enqueue_processing(document_id: str, processing_job_id: str, db: Session) -> None:
    try:
        from app.workers.tasks import process_document_task

        process_document_task.delay(document_id, processing_job_id)
    except Exception as exc:
        logger.exception("Failed to enqueue processing for document %s", document_id)
        db.rollback()
        document = db.get(Document, document_id)
        if document:
            document.status = "failed"
            document.processing_error = "The ingestion job could not be queued."
            job = db.get(ProcessingJob, processing_job_id)
            if job:
                job.status = "failed"
                job.error_message = "The ingestion job could not be queued."
                job.completed_at = datetime.now(timezone.utc)
            db.commit()
        raise HTTPException(
            status_code=503,
            detail="Document saved, but the processing service is unavailable. Retry processing later.",
        ) from exc


def serialize(row,subject="Uncategorized"):
    return {"document_id":row.id,"id":row.id,"name":row.title,"title":row.title,"file_name":row.file_name,"subject":subject,"subject_id":row.subject_id,"file_size":row.file_size,"size":f"{row.file_size/1048576:.1f} MB","date":row.created_at.strftime("%b %d, %Y"),"type":"PDF document","chunks":row.chunk_count,"pages":row.page_count,"status":row.status.capitalize(),"processing_error":row.processing_error}
@router.post("/upload",status_code=status.HTTP_202_ACCEPTED,summary="Upload and process a PDF")
def upload_document(user:CurrentUser,db:Session=Depends(get_db),file:UploadFile=File(...),subject_id:str|None=None):
    settings=get_settings()
    filename=sanitize_filename(Path(file.filename or "document.pdf").name)
    if Path(filename).suffix.lower()!=".pdf" or file.content_type not in {"application/pdf","application/octet-stream"}: raise HTTPException(415,"Only PDF files are supported")
    subject=db.scalar(select(Subject).where(Subject.id==subject_id,Subject.created_by==user.id)) if subject_id else None
    if subject_id and not subject: raise HTTPException(404,"Subject not found")
    data=file.file.read(settings.max_file_size_mb*1024*1024+1)
    if len(data)>settings.max_file_size_mb*1024*1024: raise HTTPException(413,"PDF exceeds the upload size limit")
    if not data.startswith(b"%PDF-"): raise HTTPException(400,"The uploaded file is not a valid PDF")
    digest=hashlib.sha256(data).hexdigest()
    existing=db.scalar(select(Document).where(Document.user_id==user.id,Document.file_hash==digest))
    if existing: raise HTTPException(409,"This document has already been uploaded")
    kb=db.scalar(select(KnowledgeBase).where(KnowledgeBase.user_id==user.id,KnowledgeBase.subject_id==subject_id))
    if not kb:
        kb=KnowledgeBase(id=str(uuid4()),user_id=user.id,subject_id=subject_id,name=subject.name if subject else "Uncategorized",faiss_index_path="",bm25_index_path=""); db.add(kb); db.flush()
    doc_id=str(uuid4())
    storage_path=store_document(user.id,doc_id,data)
    row=Document(id=doc_id,user_id=user.id,subject_id=subject_id,knowledge_base_id=kb.id,title=Path(filename).stem[:200],file_name=filename,file_path=storage_path,file_size=len(data),file_type="application/pdf",file_hash=digest,status="queued")
    job_id=str(uuid4())
    db.add(row); db.add(ProcessingJob(id=job_id,document_id=doc_id,status="queued")); db.commit(); db.refresh(row)
    _enqueue_processing(doc_id,job_id,db)
    return serialize(row,subject.name if subject else "Uncategorized")
@router.get("",summary="List and filter the user's documents")
def list_documents(user:CurrentUser,db:Session=Depends(get_db),search:str="",subject_id:str|None=None,status_filter:str|None=Query(None,alias="status"),page:int=Query(1,ge=1),limit:int=Query(20,ge=1,le=100),page_size:int|None=None):
    q=select(Document,Subject.name).outerjoin(Subject,Subject.id==Document.subject_id).where(Document.user_id==user.id)
    if subject_id:q=q.where(Document.subject_id==subject_id)
    if status_filter:q=q.where(Document.status==status_filter.lower())
    if search:q=q.where(or_(Document.title.ilike(f"%{search}%"),Document.file_name.ilike(f"%{search}%")))
    return [serialize(d,n or "Uncategorized") for d,n in db.execute(q.order_by(Document.created_at.desc()).offset((page-1)*(page_size or limit)).limit(page_size or limit))]
@router.get("/{document_id}/status",summary="Get document processing status")
def document_status(document_id:str,user:CurrentUser,db:Session=Depends(get_db)):
    d=db.scalar(select(Document).where(Document.id==document_id,Document.user_id==user.id))
    if not d:raise HTTPException(404,"Document not found")
    job=db.scalar(select(ProcessingJob).where(ProcessingJob.document_id==d.id).order_by(ProcessingJob.created_at.desc()))
    progress=100 if d.status=="indexed" else 0
    if d.status=="processing" and job and d.page_count:
        progress=min(99,round(job.pages_processed/d.page_count*100))
    return {"document_id":d.id,"status":d.status,"processing_error":d.processing_error,"pages":d.page_count,"chunks":d.chunk_count,"pages_processed":job.pages_processed if job else 0,"progress":progress}
@router.get("/{document_id}",summary="Get a document")
def get_document(document_id:str,user:CurrentUser,db:Session=Depends(get_db)):
    d=db.scalar(select(Document).where(Document.id==document_id,Document.user_id==user.id))
    if not d:raise HTTPException(404,"Document not found")
    name=db.scalar(select(Subject.name).where(Subject.id==d.subject_id)) or "Uncategorized"
    return serialize(d,name)
@router.get("/{document_id}/file",summary="Download a document PDF file")
def get_document_file(document_id:str,user:CurrentUser,db:Session=Depends(get_db)):
    d=db.scalar(select(Document).where(Document.id==document_id,Document.user_id==user.id))
    if not d:raise HTTPException(404,"Document not found")
    try:
        return document_response(d.file_path,d.file_name)
    except FileNotFoundError as exc:
        raise HTTPException(404,"Stored document file not found") from exc
@router.post("/{document_id}/reprocess",status_code=202,summary="Reprocess a PDF")
def reprocess(document_id:str,user:CurrentUser,db:Session=Depends(get_db)):
    d=db.scalar(select(Document).where(Document.id==document_id,Document.user_id==user.id))
    if not d:raise HTTPException(404,"Document not found")
    job_id=str(uuid4())
    d.status="queued"; d.processing_error=None; d.updated_at=datetime.now(timezone.utc); db.add(ProcessingJob(id=job_id,document_id=d.id,status="queued")); db.commit()
    _enqueue_processing(d.id,job_id,db)
    return {"success":True,"status":"processing"}
@router.delete("/{document_id}",status_code=204,summary="Delete a document")
def delete_document(document_id:str,user:CurrentUser,db:Session=Depends(get_db)):
    d=db.scalar(select(Document).where(Document.id==document_id,Document.user_id==user.id))
    if not d:raise HTTPException(404,"Document not found")
    storage_path=d.file_path; kb_id=d.knowledge_base_id; document_id=d.id; db.delete(d); db.commit()
    if kb_id:
        kb=db.get(KnowledgeBase,kb_id)
        if kb:
            settings=get_settings()
            if getattr(settings,"vector_store","faiss").lower()=="qdrant":
                asyncio.run(delete_document_index(kb_id,document_id))
            else:
                chunks=db.scalars(select(DocumentChunk).join(Document).where(Document.knowledge_base_id==kb_id)).all()
                asyncio.run(rebuild_indexes(kb_id,[{"chunk_id":c.id,"content":c.content,"document_id":c.document_id} for c in chunks]))
    try:
        delete_document_file(storage_path)
    except Exception as exc:
        logger.exception("Failed to delete stored file for document %s", document_id)
        raise HTTPException(
            status_code=503,
            detail="Document records were deleted, but stored file cleanup failed. Contact support.",
        ) from exc
    return None
