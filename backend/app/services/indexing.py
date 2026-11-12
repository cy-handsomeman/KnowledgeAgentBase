from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from models.document import Document, DocumentChunk
from models.knowledge_base import KnowledgeBase
from services.chunking import chunk_pages, split_text
from services.embedding import EmbeddingService
from services.parsing import ParsingError, extract_pdf_pages, extract_txt
from services.vector_store import delete_vector_ids, upsert_chunks


def _extract_chunks(document: Document) -> list[tuple[str, int | None]]:
    if document.file_type == "pdf":
        if not document.file_path:
            raise ParsingError("PDF 文档缺少文件路径")
        return chunk_pages(extract_pdf_pages(Path(document.file_path)))

    if document.file_type == "txt":
        if not document.file_path:
            raise ParsingError("TXT 文档缺少文件路径")
        return [(chunk, None) for chunk in split_text(extract_txt(Path(document.file_path)))]

    return [(chunk, None) for chunk in split_text(document.content or "")]


def _count_chunks(db: Session, document_id: int) -> int:
    return db.scalar(
        select(func.count())
        .select_from(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
    ) or 0


def index_document(db: Session, document: Document) -> None:
    """重建文档索引：先完成解析、分块和向量化，成功后才替换旧索引。

    新索引写入失败时回滚事务，旧片段与旧向量保持可用；
    旧向量在新索引提交成功后再删除，删除失败只会留下不参与检索的孤儿向量。
    """
    previous_status = document.status
    old_vector_ids: list[str] = []

    try:
        chunks = _extract_chunks(document)
        if not chunks:
            raise ParsingError("文档没有可索引的文本内容")

        contents = [content for content, _ in chunks]
        vectors = EmbeddingService().embed_documents(contents)

        knowledge_base = db.get(KnowledgeBase, document.knowledge_base_id)
        old_rows = db.scalars(
            select(DocumentChunk).where(DocumentChunk.document_id == document.id)
        ).all()
        old_vector_ids = [row.vector_id for row in old_rows if row.vector_id]

        db.execute(
            delete(DocumentChunk).where(DocumentChunk.document_id == document.id)
        )

        rows = []
        for chunk_index, (content, page_number) in enumerate(chunks):
            row = DocumentChunk(
                document_id=document.id,
                chunk_index=chunk_index,
                content=content,
                page_number=page_number,
            )
            db.add(row)
            rows.append(row)
        db.flush()

        vector_ids = [f"chunk-{row.id}" for row in rows]
        metadatas = [
            {
                "document_id": document.id,
                "chunk_id": row.id,
                "knowledge_base_id": document.knowledge_base_id,
                "scope_type": knowledge_base.scope_type if knowledge_base else "",
                "group_id": (knowledge_base.group_id or 0) if knowledge_base else 0,
                "page_number": row.page_number or 0,
            }
            for row in rows
        ]

        upsert_chunks(vector_ids, contents, vectors, metadatas)
        for row, vector_id in zip(rows, vector_ids):
            row.vector_id = vector_id

        document.status = "READY"
        document.error_message = None
        db.commit()
    except Exception as error:
        db.rollback()
        has_old_index = _count_chunks(db, document.id) > 0
        if previous_status == "READY" and has_old_index:
            document.status = "READY"
            document.error_message = f"重建索引失败，已保留旧索引：{error}"[:1000]
        else:
            document.status = "FAILED"
            document.error_message = str(error)[:1000]
        db.commit()
        return

    try:
        delete_vector_ids(old_vector_ids)
    except Exception:
        # 旧片段已删除，残留向量因取不到片段而不会进入检索结果。
        pass
