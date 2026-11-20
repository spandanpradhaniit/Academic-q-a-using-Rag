from uuid import uuid4
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.dependencies import CurrentUser
from app.database.connection import get_db
from app.database.models import Message,Conversation,ChatFeedback
from app.schemas import FeedbackInput
router=APIRouter(prefix="/feedback",tags=["feedback"])
@router.post("",status_code=201,summary="Submit feedback for an answer")
def submit_feedback(payload:FeedbackInput,user:CurrentUser,db:Session=Depends(get_db)):
    row=db.scalar(select(Message).join(Conversation).where(Message.id==payload.message_id,Message.sender_type=="assistant",Conversation.user_id==user.id))
    if not row:raise HTTPException(404,"Answer message not found")
    fb=ChatFeedback(id=str(uuid4()),message_id=row.id,user_id=user.id,rating=payload.rating,comment=payload.comment);db.add(fb);db.commit()
    return {"feedback_id":fb.id,"message_id":fb.message_id,"rating":fb.rating,"comment":fb.comment}
