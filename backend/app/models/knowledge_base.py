from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, text
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"
    __table_args__ = (
        CheckConstraint(
            "(scope_type = 'enterprise_group' AND group_id IS NOT NULL AND owner_user_id IS NULL)"
            " OR (scope_type = 'personal' AND owner_user_id IS NOT NULL AND group_id IS NULL)",
            name="scope_type_matches_fields",
        ),
    )

    id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(20), nullable=False)
    group_id: Mapped[int | None] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey("knowledge_groups.id"),
        nullable=True,
        unique=True,
    )
    owner_user_id: Mapped[int | None] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey("users.id"),
        nullable=True,
        unique=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )
