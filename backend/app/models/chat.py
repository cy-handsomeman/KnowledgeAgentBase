from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class ChatSession(Base):
    __tablename__ = "chat_sessions"
    __table_args__ = (
        Index("ix_chat_sessions_user_id_updated_at", "user_id", "updated_at"),
        Index("ix_chat_sessions_knowledge_base_id", "knowledge_base_id"),
    )

    id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    user_id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(20), nullable=False)
    knowledge_base_id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey("knowledge_bases.id"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        Index("ix_chat_messages_session_id_created_at", "session_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    session_id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(mysql.LONGTEXT, nullable=False)
    sources_json: Mapped[dict | None] = mapped_column(mysql.JSON, nullable=True)
    has_evidence: Mapped[bool | None] = mapped_column(mysql.BOOLEAN, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
