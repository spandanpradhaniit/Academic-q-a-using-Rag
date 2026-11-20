from datetime import datetime,timedelta,timezone
from fastapi import APIRouter,Depends,Query
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from app.api.dependencies import CurrentUser
from app.database.connection import get_db
from app.database.models import Document,SearchQuery,Conversation,ChatFeedback,Subject
router=APIRouter(prefix="/analytics",tags=["analytics"])
@router.get("/overview",summary="Get usage and document overview")
def overview(user:CurrentUser,db:Session=Depends(get_db)):
    n=lambda model:db.scalar(select(func.count()).select_from(model).where(model.user_id==user.id)) or 0
    avg=db.scalar(select(func.avg(SearchQuery.response_time_ms)).where(SearchQuery.user_id==user.id)) or 0
    return {"total_documents":n(Document),"indexed_documents":db.scalar(select(func.count()).select_from(Document).where(Document.user_id==user.id,Document.status=="indexed")) or 0,"total_questions":n(SearchQuery),"total_conversations":n(Conversation),"positive_feedback":db.scalar(select(func.count()).select_from(ChatFeedback).where(ChatFeedback.user_id==user.id,ChatFeedback.rating=="positive")) or 0,"negative_feedback":db.scalar(select(func.count()).select_from(ChatFeedback).where(ChatFeedback.user_id==user.id,ChatFeedback.rating=="negative")) or 0,"average_response_time":round(float(avg),2)}
@router.get("/questions",summary="Get recent question activity")
def questions(user:CurrentUser,db:Session=Depends(get_db),days:int=Query(30,ge=1,le=365)):
    rows=db.scalars(select(SearchQuery).where(SearchQuery.user_id==user.id,SearchQuery.created_at>=datetime.now(timezone.utc)-timedelta(days=days)).order_by(SearchQuery.created_at.desc()).limit(500))
    return [{"query":x.query_text,"response_time_ms":x.response_time_ms,"created_at":x.created_at,"conversation_id":x.conversation_id} for x in rows]
@router.get("/subjects",summary="Get question counts by subject")
def subject_analytics(user:CurrentUser,db:Session=Depends(get_db)):
    return [{"subject_id":sid,"questions":count} for sid,count in db.execute(select(Conversation.subject_id,func.count(SearchQuery.id)).join(SearchQuery,SearchQuery.conversation_id==Conversation.id).where(Conversation.user_id==user.id).group_by(Conversation.subject_id))]
