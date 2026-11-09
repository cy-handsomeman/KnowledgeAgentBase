from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, text
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class KnowledgeGroup(Base):
    __tablename__ = "knowledge_groups"

    id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    group_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )


class GroupMember(Base):
    __tablename__ = "group_members"

    group_id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey("knowledge_groups.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="member"
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
