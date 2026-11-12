from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.deps import get_current_user
from db.session import get_db
from models.knowledge_base import KnowledgeBase
from models.knowledge_group import GroupMember, KnowledgeGroup
from models.user import User
from schemas.group import GroupCreate, GroupOut, MemberCreate, MemberOut, MemberUpdate
from services.permissions import get_group_role

router = APIRouter(prefix="/api/groups", tags=["groups"])


def _admin_count(db: Session, group_id: int) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(GroupMember)
            .where(
                GroupMember.group_id == group_id,
                GroupMember.role == "admin",
            )
        )
        or 0
    )


def _require_member(db: Session, user_id: int, group_id: int) -> str:
    role = get_group_role(db, user_id, group_id)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="群组不存在或无权访问",
        )
    return role


def _require_admin(db: Session, user_id: int, group_id: int) -> None:
    role = _require_member(db, user_id, group_id)
    if role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有管理员可以管理成员",
        )


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


@router.post("", response_model=GroupOut, status_code=status.HTTP_201_CREATED)
def create_group(
    payload: GroupCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    group = KnowledgeGroup(
        name=payload.name,
        group_type=payload.group_type,
        description=payload.description,
        created_by=current_user.id,
    )
    db.add(group)
    db.flush()

    db.add(
        GroupMember(group_id=group.id, user_id=current_user.id, role="admin")
    )
    db.add(
        KnowledgeBase(
            name=f"{payload.name}知识库",
            scope_type="enterprise_group",
            group_id=group.id,
        )
    )
    db.commit()
    db.refresh(group)

    return GroupOut(
        id=group.id,
        name=group.name,
        group_type=group.group_type,
        description=group.description,
        role="admin",
    )


@router.get("/{group_id}/members", response_model=list[MemberOut])
def list_members(
    group_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_member(db, current_user.id, group_id)

    rows = db.execute(
        select(GroupMember, User)
        .join(User, User.id == GroupMember.user_id)
        .where(GroupMember.group_id == group_id)
        .order_by(GroupMember.joined_at, GroupMember.user_id)
    ).all()

    return [
        MemberOut(
            user_id=user.id,
            username=user.username,
            role=member.role,
            joined_at=member.joined_at,
        )
        for member, user in rows
    ]


@router.post(
    "/{group_id}/members",
    response_model=MemberOut,
    status_code=status.HTTP_201_CREATED,
)
def add_member(
    group_id: int,
    payload: MemberCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(db, current_user.id, group_id)

    user = db.scalar(select(User).where(User.username == payload.username))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    existing = db.get(GroupMember, (group_id, user.id))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="该用户已在群组中",
        )

    member = GroupMember(group_id=group_id, user_id=user.id, role=payload.role)
    db.add(member)
    db.commit()
    db.refresh(member)

    return MemberOut(
        user_id=user.id,
        username=user.username,
        role=member.role,
        joined_at=member.joined_at,
    )


@router.patch("/{group_id}/members/{user_id}", response_model=MemberOut)
def update_member_role(
    group_id: int,
    user_id: int,
    payload: MemberUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(db, current_user.id, group_id)

    member = db.get(GroupMember, (group_id, user_id))
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="成员不存在",
        )

    if (
        member.role == "admin"
        and payload.role != "admin"
        and _admin_count(db, group_id) <= 1
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="群组至少需要保留一名管理员",
        )

    member.role = payload.role
    db.commit()
    db.refresh(member)

    user = db.get(User, user_id)
    return MemberOut(
        user_id=user.id,
        username=user.username,
        role=member.role,
        joined_at=member.joined_at,
    )


@router.delete(
    "/{group_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_member(
    group_id: int,
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(db, current_user.id, group_id)

    member = db.get(GroupMember, (group_id, user_id))
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="成员不存在",
        )

    if member.role == "admin" and _admin_count(db, group_id) <= 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="群组至少需要保留一名管理员",
        )

    db.delete(member)
    db.commit()
