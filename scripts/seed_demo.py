import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR / "backend" / "app"))

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.security import hash_password
from db.session import SessionLocal
from models.knowledge_base import KnowledgeBase
from models.knowledge_group import GroupMember, KnowledgeGroup
from models.user import User

DEMO_PASSWORD = "Passw0rd!"


def get_or_create_user(db: Session, username: str) -> User:
    user = db.scalar(select(User).where(User.username == username))
    if user is None:
        user = User(username=username, password_hash=hash_password(DEMO_PASSWORD))
        db.add(user)
        db.flush()
        print(f"创建用户：{username} / {DEMO_PASSWORD}")
    else:
        print(f"用户已存在：{username}")
    return user


def get_or_create_group(
    db: Session, name: str, group_type: str, created_by: User
) -> KnowledgeGroup:
    group = db.scalar(select(KnowledgeGroup).where(KnowledgeGroup.name == name))
    if group is None:
        group = KnowledgeGroup(
            name=name, group_type=group_type, created_by=created_by.id
        )
        db.add(group)
        db.flush()
        print(f"创建群组：{name}")
    else:
        print(f"群组已存在：{name}")
    return group


def ensure_member(db: Session, group: KnowledgeGroup, user: User, role: str) -> None:
    member = db.get(GroupMember, (group.id, user.id))
    if member is None:
        db.add(GroupMember(group_id=group.id, user_id=user.id, role=role))
        db.flush()
        print(f"添加成员：{user.username} → {group.name}（{role}）")
    elif member.role != role:
        member.role = role
        print(f"更新成员角色：{user.username} → {group.name}（{role}）")


def get_or_create_enterprise_kb(db: Session, group: KnowledgeGroup) -> KnowledgeBase:
    knowledge_base = db.scalar(
        select(KnowledgeBase).where(KnowledgeBase.group_id == group.id)
    )
    if knowledge_base is None:
        knowledge_base = KnowledgeBase(
            name=f"{group.name}知识库",
            scope_type="enterprise_group",
            group_id=group.id,
        )
        db.add(knowledge_base)
        db.flush()
        print(f"创建知识库：{knowledge_base.name}")
    return knowledge_base


def get_or_create_personal_kb(db: Session, user: User) -> KnowledgeBase:
    knowledge_base = db.scalar(
        select(KnowledgeBase).where(KnowledgeBase.owner_user_id == user.id)
    )
    if knowledge_base is None:
        knowledge_base = KnowledgeBase(
            name=f"{user.username} 的个人知识库",
            scope_type="personal",
            owner_user_id=user.id,
        )
        db.add(knowledge_base)
        db.flush()
        print(f"创建知识库：{knowledge_base.name}")
    return knowledge_base


def main() -> None:
    db = SessionLocal()
    try:
        alice = get_or_create_user(db, "alice")
        bob = get_or_create_user(db, "bob")

        dev_group = get_or_create_group(db, "研发部", "department", alice)
        hr_group = get_or_create_group(db, "人力资源部", "department", bob)

        ensure_member(db, dev_group, alice, "admin")
        ensure_member(db, dev_group, bob, "member")
        ensure_member(db, hr_group, bob, "admin")

        get_or_create_enterprise_kb(db, dev_group)
        get_or_create_enterprise_kb(db, hr_group)
        get_or_create_personal_kb(db, alice)

        db.commit()
        print("示例数据准备完成")
        print("登录账号：alice / bob，密码均为", DEMO_PASSWORD)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
