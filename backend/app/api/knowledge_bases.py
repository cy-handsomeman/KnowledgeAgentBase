from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.deps import get_current_user
from db.session import get_db
from models.document import Document
from models.knowledge_base import KnowledgeBase
from models.knowledge_group import GroupMember, KnowledgeGroup
from models.user import User
from schemas.knowledge_base import (
    KnowledgeBaseCreate,
    KnowledgeBaseOut,
    KnowledgeBaseUpdate,
)
from services.permissions import (
    can_access_knowledge_base,
    can_edit_group,
    can_edit_knowledge_base,
    get_group_role,
)

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


@router.post("", response_model=KnowledgeBaseOut, status_code=status.HTTP_201_CREATED)
def create_knowledge_base(
    payload: KnowledgeBaseCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.scope_type == "personal":
        existing = db.scalar(
            select(KnowledgeBase).where(
                KnowledgeBase.owner_user_id == current_user.id
            )
        )
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="你已经有个人知识库了",
            )
        knowledge_base = KnowledgeBase(
            name=payload.name,
            scope_type="personal",
            owner_user_id=current_user.id,
        )
    else:
        if payload.group_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="企业知识库必须指定群组",
            )
        group = db.get(KnowledgeGroup, payload.group_id)
        if group is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="群组不存在或无权访问",
            )
        if get_group_role(db, current_user.id, payload.group_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="群组不存在或无权访问",
            )
        if not can_edit_group(db, current_user.id, payload.group_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权在该群组创建知识库",
            )
        existing = db.scalar(
            select(KnowledgeBase).where(KnowledgeBase.group_id == payload.group_id)
        )
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="该群组已经有知识库了",
            )
        knowledge_base = KnowledgeBase(
            name=payload.name,
            scope_type="enterprise_group",
            group_id=payload.group_id,
        )

    db.add(knowledge_base)
    db.commit()
    db.refresh(knowledge_base)
    return knowledge_base


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


@router.patch("/{knowledge_base_id}", response_model=KnowledgeBaseOut)
def rename_knowledge_base(
    knowledge_base_id: int,
    payload: KnowledgeBaseUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not can_access_knowledge_base(db, current_user.id, knowledge_base_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="知识库不存在或无权访问",
        )
    if not can_edit_knowledge_base(db, current_user.id, knowledge_base_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权修改该知识库",
        )

    knowledge_base = db.get(KnowledgeBase, knowledge_base_id)
    knowledge_base.name = payload.name
    db.commit()
    db.refresh(knowledge_base)
    return knowledge_base


@router.delete(
    "/{knowledge_base_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_knowledge_base(
    knowledge_base_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not can_access_knowledge_base(db, current_user.id, knowledge_base_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="知识库不存在或无权访问",
        )
    if not can_edit_knowledge_base(db, current_user.id, knowledge_base_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权删除该知识库",
        )

    document_count = (
        db.scalar(
            select(func.count())
            .select_from(Document)
            .where(Document.knowledge_base_id == knowledge_base_id)
        )
        or 0
    )
    if document_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="知识库中还有文档，请先清空文档再删除",
        )

    knowledge_base = db.get(KnowledgeBase, knowledge_base_id)
    db.delete(knowledge_base)
    db.commit()
