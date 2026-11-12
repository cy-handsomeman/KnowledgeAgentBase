from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps import get_current_user
from api.ratelimit import user_rate_limit
from db.session import get_db
from models.chat import ChatMessage, ChatSession
from models.knowledge_base import KnowledgeBase
from models.user import User
from schemas.ask import AskRequest, AskResponse, SourceOut
from services.llm import LLMError, chat_completion
from services.permissions import can_access_knowledge_base
from services.rag import HISTORY_MESSAGE_LIMIT, build_messages, parse_answer
from services.retrieval import retrieve_matches

router = APIRouter(prefix="/api", tags=["ask"])


@router.post(
    "/knowledge-bases/{knowledge_base_id}/ask",
    response_model=AskResponse,
    dependencies=[Depends(user_rate_limit(20, 60, "ask"))],
)
def ask_knowledge_base(
    knowledge_base_id: int,
    payload: AskRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not can_access_knowledge_base(db, current_user.id, knowledge_base_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="知识库不存在或无权访问",
        )

    knowledge_base = db.get(KnowledgeBase, knowledge_base_id)

    history: list[ChatMessage] = []
    if payload.session_id is not None:
        chat_session = db.get(ChatSession, payload.session_id)
        if chat_session is None or chat_session.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="会话不存在或无权访问",
            )
        if chat_session.knowledge_base_id != knowledge_base_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="会话的检索范围与请求不一致",
            )
        history = db.scalars(
            select(ChatMessage)
            .where(ChatMessage.session_id == chat_session.id)
            .order_by(ChatMessage.id.desc())
            .limit(HISTORY_MESSAGE_LIMIT)
        ).all()[::-1]
    else:
        chat_session = ChatSession(
            user_id=current_user.id,
            title=payload.question[:100],
            scope_type=knowledge_base.scope_type,
            knowledge_base_id=knowledge_base_id,
        )
        db.add(chat_session)
        db.flush()

    retrieval_question = payload.question
    previous_question = next(
        (message.content for message in reversed(history) if message.role == "user"),
        None,
    )
    if previous_question:
        retrieval_question = f"{previous_question}\n{payload.question}"

    matches = retrieve_matches(
        db, current_user.id, knowledge_base_id, retrieval_question
    )

    if matches:
        try:
            raw_answer = chat_completion(
                build_messages(
                    payload.question,
                    matches,
                    [(message.role, message.content) for message in history],
                ),
                json_mode=True,
            )
        except LLMError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(error),
            )
        answer, has_evidence = parse_answer(raw_answer, len(matches))
        sources = (
            [
                SourceOut(
                    document_id=match.document_id,
                    document_title=match.document_title,
                    chunk_id=match.chunk_id,
                    page_number=match.page_number,
                    score=match.score,
                    snippet=match.content[:200],
                )
                for match in matches
            ]
            if has_evidence
            else []
        )
    else:
        answer = "根据现有资料无法回答。"
        sources = []
        has_evidence = False

    db.add(
        ChatMessage(
            session_id=chat_session.id,
            role="user",
            content=payload.question,
        )
    )
    assistant_message = ChatMessage(
        session_id=chat_session.id,
        role="assistant",
        content=answer,
        sources_json=[source.model_dump() for source in sources],
        has_evidence=has_evidence,
    )
    db.add(assistant_message)
    chat_session.updated_at = datetime.now()
    db.commit()
    db.refresh(assistant_message)

    return AskResponse(
        session_id=chat_session.id,
        answer=answer,
        sources=sources,
        has_evidence=has_evidence,
        created_at=assistant_message.created_at,
    )
