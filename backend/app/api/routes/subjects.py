from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.dependencies import CurrentUser
from app.database.connection import get_db
from app.database.models import Subject, KnowledgeBase
from app.schemas import SubjectInput

router = APIRouter(prefix="/subjects", tags=["subjects"])
def dump(row): return {"subject_id":row.id,"name":row.name,"code":row.code,"description":row.description,"semester":row.semester,"user_id":row.created_by,"created_at":row.created_at,"updated_at":row.updated_at}
@router.get("", summary="List subjects")
def list_subjects(user: CurrentUser, db: Session=Depends(get_db)):
    return [dump(x) for x in db.scalars(select(Subject).where(Subject.created_by==user.id).order_by(Subject.created_at.desc()))]
@router.post("", status_code=status.HTTP_201_CREATED, summary="Create a subject")
def create_subject(payload: SubjectInput, user: CurrentUser, db: Session=Depends(get_db)):
    row=Subject(id=str(uuid4()),created_by=user.id,**payload.model_dump()); db.add(row); db.flush()
    db.add(KnowledgeBase(id=str(uuid4()),user_id=user.id,subject_id=row.id,name=row.name,faiss_index_path=f"data/faiss/{row.id}",bm25_index_path=f"data/bm25/{row.id}")); db.commit(); db.refresh(row); return dump(row)
@router.get("/{subject_id}", summary="Get a subject")
def get_subject(subject_id: str,user: CurrentUser,db: Session=Depends(get_db)):
    row=db.scalar(select(Subject).where(Subject.id==subject_id,Subject.created_by==user.id))
    if not row: raise HTTPException(404,"Subject not found")
    return dump(row)
@router.put("/{subject_id}", summary="Update a subject")
def update_subject(subject_id: str,payload: SubjectInput,user: CurrentUser,db: Session=Depends(get_db)):
    row=db.scalar(select(Subject).where(Subject.id==subject_id,Subject.created_by==user.id))
    if not row: raise HTTPException(404,"Subject not found")
    for k,v in payload.model_dump().items(): setattr(row,k,v)
    db.commit(); db.refresh(row); return dump(row)
@router.delete("/{subject_id}",status_code=204,summary="Delete a subject")
def delete_subject(subject_id: str,user: CurrentUser,db: Session=Depends(get_db)):
    row=db.scalar(select(Subject).where(Subject.id==subject_id,Subject.created_by==user.id))
    if not row: raise HTTPException(404,"Subject not found")
    db.delete(row); db.commit()
