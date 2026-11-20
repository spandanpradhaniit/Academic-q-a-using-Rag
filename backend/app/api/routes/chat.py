import asyncio,json,time
import logging
from datetime import datetime,timezone
from uuid import uuid4
from fastapi import APIRouter,Depends,HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.dependencies import CurrentUser
from app.database.connection import get_db
from app.database.models import Subject,Conversation,Message,Document,DocumentChunk,KnowledgeBase,SourceCitation,SearchQuery
from app.rag.indexing import hybrid_search
from app.rag.query_rewrite import rewrite_question
from app.rag.relevance import compute_confidence, relevance_gate
from app.schemas import AskInput
from app.services.answers import (
    build_answer_system_prompt,
    create_answer_model,
    generate_follow_up_questions,
    generate_grounded_answer,
    is_low_confidence_answer,
    validate_citations,
)
router=APIRouter(prefix="/chat",tags=["chat"])
logger = logging.getLogger(__name__)
NO_CONTEXT="Information not found in the provided documents."


def _answer_history(messages: list[Message]) -> list[dict[str, str]]:
    return [
        {"sender_type": message.sender_type, "content": message.content}
        for message in messages
        if not (
            message.sender_type == "assistant"
            and is_low_confidence_answer(message.content)
        )
    ]


def _build_sources(candidates:list[dict]) -> list[dict]:
    sources=[]
    for rank,ch in enumerate(candidates,1):
        sources.append({
            "documentId":ch["document_id"],
            "document":ch["document_name"],
            "page":ch["page_number"],
            "excerpt":ch["content"][:500],
            "relevance":ch.get("score",0),
            "document_id":ch["document_id"],
            "document_name":ch["document_name"],
            "page_number":ch["page_number"],
            "snippet":ch["content"][:500],
            "score":ch.get("score",0),
            "rank":rank,
            "semantic_rank":ch.get("semantic_rank"),
            "semantic_score":ch.get("semantic_score"),
            "keyword_rank":ch.get("keyword_rank"),
            "keyword_score":ch.get("keyword_score"),
            "rrf_score":ch.get("rrf_score",ch.get("score",0)),
            "rerank_rank":ch.get("rerank_rank",rank),
            "rerank_score":ch.get("rerank_score"),
            "semanticRank":ch.get("semantic_rank"),
            "semanticScore":ch.get("semantic_score"),
            "keywordRank":ch.get("keyword_rank"),
            "keywordScore":ch.get("keyword_score"),
            "rerankedPosition":ch.get("rerank_rank",rank),
            "rerankScore":ch.get("rerank_score"),
            "rrfScore":ch.get("rrf_score",ch.get("score",0)),
        })
    return sources


async def _stream_answer(question:str, candidates:list[dict], prior:list[dict], user_id:str, conversation_id:str):
    answer,model = await generate_grounded_answer(question,candidates,[{"sender_type":m.sender_type,"content":m.content} for m in prior])
    llm = None
    settings = __import__("app.core.config", fromlist=["get_settings"]).get_settings()
    if settings.llm_provider == "groq":
        if not settings.groq_api_key:
            raise RuntimeError("GROQ_API_KEY is required when LLM_PROVIDER=groq")
        from langchain_groq import ChatGroq
        llm = ChatGroq(model=settings.llama_model, api_key=settings.groq_api_key, temperature=0.2)
    else:
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required to generate answers")
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(model=settings.openai_model, api_key=settings.openai_api_key, temperature=0.2)
    context = "\n\n".join(f"[Source {i + 1}: {chunk['document_name']}, page {chunk['page_number']}]\n{chunk['content']}" for i, chunk in enumerate(candidates))
    system = build_answer_system_prompt(context)
    messages = [__import__("langchain_core.messages", fromlist=["SystemMessage", "HumanMessage", "AIMessage"]).SystemMessage(content=system)]
    for item in prior[-8:]:
        if item.get("sender_type") == "user":
            messages.append(__import__("langchain_core.messages", fromlist=["HumanMessage"]).HumanMessage(content=item["content"]))
        elif item.get("sender_type") == "assistant":
            from langchain_core.messages import AIMessage
            messages.append(AIMessage(content=item["content"]))
    messages.append(__import__("langchain_core.messages", fromlist=["HumanMessage"]).HumanMessage(content=question))
    pieces=[]
    async for chunk in llm.astream(messages):
        text = chunk.content if hasattr(chunk, "content") else str(chunk)
        if isinstance(text, list):
            text = "".join(str(part.get("text", "")) if isinstance(part, dict) else str(part) for part in text)
        if not text:
            continue
        pieces.append(str(text))
        yield {"type":"token","token":str(text)}
    full = "".join(pieces)
    yield {"type":"final","answer":full or answer,"model":model,"conversation_id":conversation_id,"message_id":str(uuid4()),"response_time_ms":0,"sources":_build_sources(candidates),"confidence":round(max((item.get("score",0) for item in candidates), default=0),3)}


@router.post("/ask",summary="Ask a source-grounded academic question")
def ask(payload:AskInput,user:CurrentUser,db:Session=Depends(get_db)):
    subject_id=payload.subject_id
    if subject_id and not db.scalar(select(Subject).where(Subject.id==subject_id,Subject.created_by==user.id)):raise HTTPException(404,"Subject not found")
    c=db.scalar(select(Conversation).where(Conversation.id==payload.conversation_id,Conversation.user_id==user.id)) if payload.conversation_id else None
    if payload.conversation_id and not c:raise HTTPException(404,"Conversation not found")
    if c and subject_id and c.subject_id!=subject_id:raise HTTPException(400,"Conversation subject does not match")
    if c and not subject_id:subject_id=c.subject_id
    if not c:c=Conversation(id=str(uuid4()),user_id=user.id,subject_id=subject_id,title=payload.question[:80]);db.add(c);db.flush()
    prior=db.scalars(select(Message).where(Message.conversation_id==c.id).order_by(Message.created_at.desc()).limit(12)).all()[::-1]
    history=_answer_history(prior)
    rewritten_question=rewrite_question(payload.question.strip(), history)
    user_msg=Message(id=str(uuid4()),conversation_id=c.id,sender_type="user",content=payload.question.strip());db.add(user_msg);db.flush()
    kb=db.scalar(select(KnowledgeBase).where(KnowledgeBase.user_id==user.id,KnowledgeBase.subject_id==subject_id))
    candidates=[]; start=time.perf_counter()
    if kb:
        chunks=db.execute(select(DocumentChunk,Document).join(Document,Document.id==DocumentChunk.document_id).where(Document.user_id==user.id,Document.knowledge_base_id==kb.id,Document.status=="indexed")).all()
        rows=[{"chunk_id":ch.id,"content":ch.content,"page_number":ch.page_number,"document_id":doc.id,"document_name":doc.title,"subject_id":doc.subject_id,"metadata":ch.metadata_json} for ch,doc in chunks]
        candidates=asyncio.run(hybrid_search(kb.id,rewritten_question or payload.question,rows))
    filtered_candidates = relevance_gate(candidates)
    try:
        answer, model = asyncio.run(
            generate_grounded_answer(
                rewritten_question or payload.question,
                filtered_candidates,
                history,
            )
        )
    except Exception as exc:
        raise HTTPException(
            503,
            detail={
                "code": "LLM_UNAVAILABLE",
                "message": "The AI service is temporarily unavailable. Please try again.",
            },
        ) from exc
    answer, invalid_citations = validate_citations(answer, len(filtered_candidates))
    confidence, low_confidence = compute_confidence(filtered_candidates, answer)
    low_confidence = low_confidence or is_low_confidence_answer(answer) or bool(invalid_citations)
    follow_up_questions = (
        asyncio.run(generate_follow_up_questions(payload.question, answer))
        if filtered_candidates and not is_low_confidence_answer(answer)
        else []
    )
    elapsed=int((time.perf_counter()-start)*1000); assistant=Message(id=str(uuid4()),conversation_id=c.id,sender_type="assistant",content=answer,model_used=model,response_time_ms=elapsed);db.add(assistant)
    sources=[]
    for rank,ch in enumerate(filtered_candidates,1):
        citation=SourceCitation(id=str(uuid4()),message_id=assistant.id,document_id=ch["document_id"],chunk_id=ch["chunk_id"],page_number=ch["page_number"],content_snippet=ch["content"][:500],similarity_score=ch.get("score",0),retrieval_method="hybrid",rank=rank);db.add(citation)
        sources.append({"documentId":ch["document_id"],"document":ch["document_name"],"page":ch["page_number"],"excerpt":ch["content"][:500],"relevance":ch.get("score",0),"document_id":ch["document_id"],"document_name":ch["document_name"],"page_number":ch["page_number"],"snippet":ch["content"][:500],"score":ch.get("score",0)})
    c.message_count+=2;c.updated_at=datetime.now(timezone.utc);db.add(SearchQuery(id=str(uuid4()),user_id=user.id,conversation_id=c.id,query_text=payload.question,rewritten_query_text=rewritten_question or payload.question,retrieved_chunks=len(filtered_candidates),response_time_ms=elapsed,model_used=model));db.commit()
    return {"conversation_id":c.id,"message_id":assistant.id,"answer":answer,"sources":sources,"confidence":round(confidence,3),"low_confidence":low_confidence,"model":model,"response_time_ms":elapsed,"follow_up_questions":follow_up_questions}


@router.post("/ask/stream")
def ask_stream(payload:AskInput,user:CurrentUser,db:Session=Depends(get_db)):
    stream_started = time.perf_counter()
    subject_id=payload.subject_id
    if subject_id and not db.scalar(select(Subject).where(Subject.id==subject_id,Subject.created_by==user.id)):raise HTTPException(404,"Subject not found")
    c=db.scalar(select(Conversation).where(Conversation.id==payload.conversation_id,Conversation.user_id==user.id)) if payload.conversation_id else None
    if payload.conversation_id and not c:raise HTTPException(404,"Conversation not found")
    if c and subject_id and c.subject_id!=subject_id:raise HTTPException(400,"Conversation subject does not match")
    if c and not subject_id:subject_id=c.subject_id
    if not c:c=Conversation(id=str(uuid4()),user_id=user.id,subject_id=subject_id,title=payload.question[:80]);db.add(c);db.flush()
    prior=db.scalars(select(Message).where(Message.conversation_id==c.id).order_by(Message.created_at.desc()).limit(12)).all()[::-1]
    history=_answer_history(prior)
    rewritten_question=rewrite_question(payload.question.strip(), history)
    user_msg=Message(id=str(uuid4()),conversation_id=c.id,sender_type="user",content=payload.question.strip());db.add(user_msg);db.flush()
    kb=db.scalar(select(KnowledgeBase).where(KnowledgeBase.user_id==user.id,KnowledgeBase.subject_id==subject_id))
    candidates=[]
    if kb:
        chunks=db.execute(select(DocumentChunk,Document).join(Document,Document.id==DocumentChunk.document_id).where(Document.user_id==user.id,Document.knowledge_base_id==kb.id,Document.status=="indexed")).all()
        rows=[{"chunk_id":ch.id,"content":ch.content,"page_number":ch.page_number,"document_id":doc.id,"document_name":doc.title,"subject_id":doc.subject_id,"metadata":ch.metadata_json} for ch,doc in chunks]
        candidates=asyncio.run(hybrid_search(kb.id,rewritten_question or payload.question,rows))
    filtered_candidates = relevance_gate(candidates)

    async def _generate():
        assistant_id=str(uuid4())
        try:
            llm, model = create_answer_model()
        except Exception:
            logger.exception("Could not initialize the configured answer model")
            yield f"data: {json.dumps({'type':'error','code':'LLM_UNAVAILABLE','message':'The answer model is not configured correctly. Check the backend provider settings.'})}\n\n"
            return

        meta = {
            "type":"meta",
            "conversation_id":c.id,
            "message_id":assistant_id,
            "sources":_build_sources(filtered_candidates),
            "rewritten_question":rewritten_question or payload.question,
            "retrieval_metadata":{
                "retrieved":len(filtered_candidates),
                "question":payload.question,
                "rewritten_question":rewritten_question or payload.question,
                "reranker":__import__("app.core.config", fromlist=["get_settings"]).get_settings().reranker,
            },
            "model":model,
        }
        yield f"data: {json.dumps(meta)}\n\n"
        context = "\n\n".join(f"[Source {i + 1}: {chunk['document_name']}, page {chunk['page_number']}]\n{chunk['content']}" for i, chunk in enumerate(filtered_candidates))
        system = build_answer_system_prompt(context)
        from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
        messages = [SystemMessage(content=system)]
        for item in history[-8:]:
            if item.get("sender_type") == "user":
                messages.append(HumanMessage(content=item["content"]))
            elif item.get("sender_type") == "assistant":
                messages.append(AIMessage(content=item["content"]))
        messages.append(HumanMessage(content=rewritten_question or payload.question))
        text = ""
        try:
            async for chunk in llm.astream(messages):
                token = chunk.content if hasattr(chunk, "content") else str(chunk)
                if isinstance(token, list):
                    token = "".join(str(part.get("text", "")) if isinstance(part, dict) else str(part) for part in token)
                if not token:
                    continue
                text += str(token)
                yield f"data: {json.dumps({'type':'token','token':str(token)})}\n\n"
        except Exception:
            logger.exception("Streaming answer generation failed")
            yield f"data: {json.dumps({'type':'error','code':'LLM_UNAVAILABLE','message':'The AI provider could not complete the answer. Check provider availability and backend logs, then retry.'})}\n\n"
            return

        if not text.strip():
            logger.error("Streaming answer model returned no text")
            yield f"data: {json.dumps({'type':'error','code':'EMPTY_LLM_RESPONSE','message':'The AI provider returned an empty answer. Please retry.'})}\n\n"
            return

        answer_text, invalid_citations = validate_citations(
            text,
            len(filtered_candidates),
        )
        confidence, low_confidence = compute_confidence(
            filtered_candidates,
            answer_text,
        )
        low_confidence = (
            low_confidence
            or is_low_confidence_answer(answer_text)
            or bool(invalid_citations)
        )
        follow_up_questions = (
            await generate_follow_up_questions(payload.question, answer_text)
            if filtered_candidates and answer_text and not is_low_confidence_answer(answer_text)
            else []
        )
        response_time_ms = int((time.perf_counter()-stream_started)*1000)
        assistant = Message(id=assistant_id, conversation_id=c.id, sender_type="assistant", content=answer_text, model_used=model, response_time_ms=response_time_ms)
        db.add(assistant)
        for rank, ch in enumerate(filtered_candidates, 1):
            db.add(SourceCitation(id=str(uuid4()), message_id=assistant.id, document_id=ch["document_id"], chunk_id=ch["chunk_id"], page_number=ch["page_number"], content_snippet=ch["content"][:500], similarity_score=ch.get("score",0), retrieval_method="hybrid", rank=rank))
        c.message_count += 2
        c.updated_at = datetime.now(timezone.utc)
        db.add(SearchQuery(id=str(uuid4()), user_id=user.id, conversation_id=c.id, query_text=payload.question, rewritten_query_text=rewritten_question or payload.question, retrieved_chunks=len(filtered_candidates), response_time_ms=response_time_ms, model_used=model))
        db.commit()
        yield f"data: {json.dumps({'type':'final','message_id':assistant.id,'conversation_id':c.id,'answer':answer_text,'sources':_build_sources(filtered_candidates),'rewritten_question':rewritten_question or payload.question,'retrieval_metadata':{'retrieved':len(filtered_candidates),'question':payload.question,'rewritten_question':rewritten_question or payload.question},'confidence':round(confidence,3),'low_confidence':low_confidence,'model':model,'response_time_ms':response_time_ms,'invalid_citations':validate_citations(answer_text, len(filtered_candidates))[1],'follow_up_questions':follow_up_questions})}\n\n"
    return StreamingResponse(_generate(), media_type="text/event-stream")
@router.post("/history",include_in_schema=False)
def create_chat_history_alias():raise HTTPException(405,"Use /api/conversations")
