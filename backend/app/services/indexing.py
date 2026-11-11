from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.orm import Session

from models.document import Document, DocumentChunk
from models.knowledge_base import KnowledgeBase
from services.chunking import chunk_pages, split_text
from services.embedding import EmbeddingService
from services.parsing import ParsingError, extract_pdf_pages, extract_txt
from services.vector_store import delete_document_vectors, upsert_chunks


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


def index_document(db: Session, document: Document) -> None:
    delete_document_vectors(document.id)
    db.execute(
        delete(DocumentChunk).where(DocumentChunk.document_id == document.id)
    )

    try:
        chunks = _extract_chunks(document)
        if not chunks:
            raise ParsingError("文档没有可索引的文本内容")

        knowledge_base = db.get(KnowledgeBase, document.knowledge_base_id)

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

        contents = [row.content for row in rows]
        vectors = EmbeddingService().embed_documents(contents)
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
    except Exception as error:
        document.status = "FAILED"
        document.error_message = str(error)[:1000]
        try:
            delete_document_vectors(document.id)
        except Exception:
            pass

    db.commit()
