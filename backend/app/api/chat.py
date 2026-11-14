from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from api.deps import get_current_user
from db.session import get_db
from models.chat import ChatMessage, ChatSession
from models.knowledge_base import KnowledgeBase
from models.knowledge_group import GroupMember
from models.user import User
from schemas.chat import ChatMessageOut, ChatSessionOut
from services.permissions import can_access_knowledge_base

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _get_own_session(db: Session, user_id: int, session_id: int) -> ChatSession:
    chat_session = db.get(ChatSession, session_id)
    if chat_session is None or chat_session.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在或无权访问",
        )
    return chat_session


@router.get("/sessions", response_model=list[ChatSessionOut])
def list_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # 用一次联表查询完成权限过滤，避免逐个会话回查知识库与群组成员。
    sessions = db.scalars(
        select(ChatSession)
        .join(KnowledgeBase, KnowledgeBase.id == ChatSession.knowledge_base_id)
        .outerjoin(
            GroupMember,
            and_(
                GroupMember.group_id == KnowledgeBase.group_id,
                GroupMember.user_id == current_user.id,
            ),
        )
        .where(
            ChatSession.user_id == current_user.id,
            or_(
                and_(
                    KnowledgeBase.scope_type == "personal",
                    KnowledgeBase.owner_user_id == current_user.id,
                ),
                and_(
                    KnowledgeBase.scope_type == "enterprise_group",
                    GroupMember.user_id == current_user.id,
                ),
            ),
        )
        .order_by(ChatSession.updated_at.desc(), ChatSession.id.desc())
    ).all()
    return list(sessions)


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageOut])
def list_messages(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    chat_session = _get_own_session(db, current_user.id, session_id)
    if not can_access_knowledge_base(
        db, current_user.id, chat_session.knowledge_base_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在或无权访问",
        )
    return db.scalars(
        select(ChatMessage)
        .where(ChatMessage.session_id == chat_session.id)
        .order_by(ChatMessage.id)
    ).all()


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    chat_session = _get_own_session(db, current_user.id, session_id)
    db.delete(chat_session)
    db.commit()
