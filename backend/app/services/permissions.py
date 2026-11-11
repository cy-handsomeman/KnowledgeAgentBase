from sqlalchemy import select
from sqlalchemy.orm import Session

from models.document import Document
from models.knowledge_base import KnowledgeBase
from models.knowledge_group import GroupMember

EDIT_ROLES = {"editor", "admin"}


def get_group_role(db: Session, user_id: int, group_id: int) -> str | None:
    member = db.scalar(
        select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id,
        )
    )
    return member.role if member is not None else None


def is_group_member(db: Session, user_id: int, group_id: int) -> bool:
    return get_group_role(db, user_id, group_id) is not None


def can_edit_group(db: Session, user_id: int, group_id: int) -> bool:
    return get_group_role(db, user_id, group_id) in EDIT_ROLES


def can_manage_group(db: Session, user_id: int, group_id: int) -> bool:
    return get_group_role(db, user_id, group_id) == "admin"


def can_access_knowledge_base(db: Session, user_id: int, knowledge_base_id: int) -> bool:
    knowledge_base = db.get(KnowledgeBase, knowledge_base_id)
    if knowledge_base is None:
        return False

    if knowledge_base.scope_type == "personal":
        return knowledge_base.owner_user_id == user_id

    if knowledge_base.scope_type == "enterprise_group":
        return knowledge_base.group_id is not None and is_group_member(
            db, user_id, knowledge_base.group_id
        )

    return False


def can_access_document(db: Session, user_id: int, document_id: int) -> bool:
    document = db.get(Document, document_id)
    if document is None:
        return False
    return can_access_knowledge_base(db, user_id, document.knowledge_base_id)


def can_edit_knowledge_base(db: Session, user_id: int, knowledge_base_id: int) -> bool:
    knowledge_base = db.get(KnowledgeBase, knowledge_base_id)
    if knowledge_base is None:
        return False

    if knowledge_base.scope_type == "personal":
        return knowledge_base.owner_user_id == user_id

    if knowledge_base.scope_type == "enterprise_group":
        return knowledge_base.group_id is not None and can_edit_group(
            db, user_id, knowledge_base.group_id
        )

    return False


def can_edit_document(db: Session, user_id: int, document_id: int) -> bool:
    document = db.get(Document, document_id)
    if document is None:
        return False
    return can_edit_knowledge_base(db, user_id, document.knowledge_base_id)
