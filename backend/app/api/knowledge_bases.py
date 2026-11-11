from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps import get_current_user
from db.session import get_db
from models.knowledge_base import KnowledgeBase
from models.knowledge_group import GroupMember
from models.user import User
from schemas.knowledge_base import KnowledgeBaseOut
from services.permissions import can_access_knowledge_base

router = APIRouter(prefix="/api/knowledge-bases", tags=["knowledge-bases"])


@router.get("", response_model=list[KnowledgeBaseOut])
def list_my_knowledge_bases(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    enterprise = db.scalars(
        select(KnowledgeBase)
        .join(GroupMember, GroupMember.group_id == KnowledgeBase.group_id)
        .where(GroupMember.user_id == current_user.id)
        .order_by(KnowledgeBase.id)
    ).all()

    personal = db.scalars(
        select(KnowledgeBase)
        .where(
            KnowledgeBase.scope_type == "personal",
            KnowledgeBase.owner_user_id == current_user.id,
        )
        .order_by(KnowledgeBase.id)
    ).all()

    return list(enterprise) + list(personal)


@router.get("/{knowledge_base_id}", response_model=KnowledgeBaseOut)
def get_knowledge_base(
    knowledge_base_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not can_access_knowledge_base(db, current_user.id, knowledge_base_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="知识库不存在或无权访问",
        )
    return db.get(KnowledgeBase, knowledge_base_id)
