from uuid import uuid4
from datetime import datetime,timezone
from fastapi import APIRouter,Depends,HTTPException,Query,status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.dependencies import CurrentUser
from app.database.connection import get_db
from app.database.models import Conversation,Subject,Message,SourceCitation
from app.schemas import ConversationInput,ConversationUpdate
router=APIRouter(prefix="/conversations",tags=["conversations"])
def dump(c):return {"conversation_id":c.id,"user_id":c.user_id,"subject_id":c.subject_id,"title":c.title,"message_count":c.message_count,"is_archived":c.is_archived,"created_at":c.created_at,"updated_at":c.updated_at}
@router.post("",status_code=201,summary="Create a conversation")
def create_conversation(payload:ConversationInput,user:CurrentUser,db:Session=Depends(get_db)):
    if payload.subject_id and not db.scalar(select(Subject).where(Subject.id==payload.subject_id,Subject.created_by==user.id)):raise HTTPException(404,"Subject not found")
    c=Conversation(id=str(uuid4()),user_id=user.id,**payload.model_dump());db.add(c);db.commit();db.refresh(c);return dump(c)
@router.get("",summary="List conversations")
def list_conversations(user:CurrentUser,db:Session=Depends(get_db),page:int=Query(1,ge=1),limit:int=Query(20,ge=1,le=100)):
    return [dump(c) for c in db.scalars(select(Conversation).where(Conversation.user_id==user.id,Conversation.is_archived.is_(False)).order_by(Conversation.updated_at.desc()).offset((page-1)*limit).limit(limit))]
@router.get("/{conversation_id}",summary="Get a conversation with messages and citations")
def get_conversation(conversation_id:str,user:CurrentUser,db:Session=Depends(get_db)):
    c=db.scalar(select(Conversation).where(Conversation.id==conversation_id,Conversation.user_id==user.id))
    if not c:raise HTTPException(404,"Conversation not found")
    out=dump(c);out["messages"]=[]
    for m in db.scalars(select(Message).where(Message.conversation_id==c.id).order_by(Message.created_at)):
        row={"message_id":m.id,"sender_type":m.sender_type,"content":m.content,"created_at":m.created_at,"citations":[]}
        for x in db.scalars(select(SourceCitation).where(SourceCitation.message_id==m.id)):
            row["citations"].append({"document_id":x.document_id,"page_number":x.page_number,"snippet":x.content_snippet,"score":x.similarity_score})
        out["messages"].append(row)
    return out
@router.patch("/{conversation_id}",summary="Rename or archive a conversation")
def update_conversation(conversation_id:str,payload:ConversationUpdate,user:CurrentUser,db:Session=Depends(get_db)):
    c=db.scalar(select(Conversation).where(Conversation.id==conversation_id,Conversation.user_id==user.id))
    if not c:raise HTTPException(404,"Conversation not found")
    for k,v in payload.model_dump(exclude_unset=True).items():setattr(c,k,v)
    c.updated_at=datetime.now(timezone.utc);db.commit();return dump(c)
@router.delete("/{conversation_id}",status_code=204,summary="Delete a conversation")
def delete_conversation(conversation_id:str,user:CurrentUser,db:Session=Depends(get_db)):
    c=db.scalar(select(Conversation).where(Conversation.id==conversation_id,Conversation.user_id==user.id))
    if not c:raise HTTPException(404,"Conversation not found")
    db.delete(c);db.commit()
