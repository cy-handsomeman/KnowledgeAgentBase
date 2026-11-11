from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps import get_current_user
from db.session import get_db
from models.knowledge_group import GroupMember, KnowledgeGroup
from models.user import User
from schemas.group import GroupOut

router = APIRouter(prefix="/api/groups", tags=["groups"])


@router.get("", response_model=list[GroupOut])
def list_my_groups(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = db.execute(
        select(KnowledgeGroup, GroupMember.role)
        .join(GroupMember, GroupMember.group_id == KnowledgeGroup.id)
        .where(GroupMember.user_id == current_user.id)
        .order_by(KnowledgeGroup.id)
    ).all()

    return [
        GroupOut(
            id=group.id,
            name=group.name,
            group_type=group.group_type,
            description=group.description,
            role=role,
        )
        for group, role in rows
    ]
