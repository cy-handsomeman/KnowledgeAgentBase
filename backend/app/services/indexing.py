from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.orm import Session

from models.document import Document, DocumentChunk
from services.chunking import chunk_pages, split_text
from services.parsing import ParsingError, extract_pdf_pages, extract_txt


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
    db.execute(
        delete(DocumentChunk).where(DocumentChunk.document_id == document.id)
    )

    try:
        chunks = _extract_chunks(document)
        if not chunks:
            raise ParsingError("文档没有可索引的文本内容")

        for chunk_index, (content, page_number) in enumerate(chunks):
            db.add(
                DocumentChunk(
                    document_id=document.id,
                    chunk_index=chunk_index,
                    content=content,
                    page_number=page_number,
                )
            )
        document.status = "READY"
        document.error_message = None
    except Exception as error:
        document.status = "FAILED"
        document.error_message = str(error)[:1000]

    db.commit()
