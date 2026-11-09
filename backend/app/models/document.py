from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_knowledge_base_id_created_at", "knowledge_base_id", "created_at"),
        Index("ix_documents_knowledge_base_id_status", "knowledge_base_id", "status"),
        Index("ix_documents_uploaded_by", "uploaded_by"),
    )

    id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    knowledge_base_id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey("knowledge_bases.id"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str | None] = mapped_column(mysql.LONGTEXT, nullable=True)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False)
    file_size: Mapped[int | None] = mapped_column(
        mysql.BIGINT(unsigned=True), nullable=True
    )
    uploaded_by: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="UPLOADED"
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index"),
        Index("ix_document_chunks_document_id", "document_id"),
    )

    id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    document_id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(
        mysql.INTEGER(unsigned=True), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int | None] = mapped_column(
        mysql.INTEGER(unsigned=True), nullable=True
    )
    vector_id: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
