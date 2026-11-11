import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps import get_current_user
from core.settings import settings
from db.session import get_db
from models.document import Document
from models.knowledge_base import KnowledgeBase
from models.user import User
from schemas.document import DocumentCreate, DocumentOut, DocumentSummary, DocumentUpdate
from services.permissions import (
    can_access_document,
    can_access_knowledge_base,
    can_edit_document,
    can_edit_knowledge_base,
)
from services.indexing import index_document
from services.vector_store import delete_document_vectors

router = APIRouter(prefix="/api", tags=["documents"])

MAX_UPLOAD_SIZE = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf": "pdf", ".txt": "txt"}


def _remove_uploaded_file(file_path: str) -> None:
    path = Path(file_path).resolve()
    upload_dir = Path(settings.upload_dir).resolve()
    if upload_dir in path.parents and path.is_file():
        path.unlink()


def _require_edit_access(db: Session, user_id: int, knowledge_base_id: int) -> None:
    if not can_access_knowledge_base(db, user_id, knowledge_base_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="知识库不存在或无权访问",
        )
    if not can_edit_knowledge_base(db, user_id, knowledge_base_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权编辑该知识库",
        )


def _get_document_or_404(db: Session, document_id: int) -> Document:
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文档不存在",
        )
    return document


@router.post(
    "/knowledge-bases/{knowledge_base_id}/documents",
    response_model=DocumentOut,
    status_code=status.HTTP_201_CREATED,
)
def create_document(
    knowledge_base_id: int,
    payload: DocumentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    knowledge_base = db.get(KnowledgeBase, knowledge_base_id)
    if knowledge_base is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="知识库不存在或无权访问",
        )
    _require_edit_access(db, current_user.id, knowledge_base_id)

    document = Document(
        knowledge_base_id=knowledge_base_id,
        title=payload.title,
        content=payload.content,
        file_type="markdown",
        uploaded_by=current_user.id,
        status="READY",
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    index_document(db, document)
    db.refresh(document)
    return document


@router.post(
    "/knowledge-bases/{knowledge_base_id}/documents/upload",
    response_model=DocumentOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    knowledge_base_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    knowledge_base = db.get(KnowledgeBase, knowledge_base_id)
    if knowledge_base is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="知识库不存在或无权访问",
        )
    _require_edit_access(db, current_user.id, knowledge_base_id)

    original_filename = Path(file.filename or "").name
    suffix = Path(original_filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只允许上传 PDF 或 TXT 文件",
        )

    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}{suffix}"
    target = upload_dir / stored_name

    size = 0
    try:
        with target.open("wb") as output:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_SIZE:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail="文件超过 10MB 限制",
                    )
                output.write(chunk)
    except HTTPException:
        target.unlink(missing_ok=True)
        raise
    finally:
        await file.close()

    document = Document(
        knowledge_base_id=knowledge_base_id,
        title=Path(original_filename).stem or stored_name,
        original_filename=original_filename,
        file_path=str(target),
        file_type=ALLOWED_EXTENSIONS[suffix],
        file_size=size,
        uploaded_by=current_user.id,
        status="PROCESSING",
    )
    db.add(document)
    try:
        db.commit()
    except Exception:
        db.rollback()
        target.unlink(missing_ok=True)
        raise
    db.refresh(document)
    index_document(db, document)
    db.refresh(document)
    return document


@router.get(
    "/knowledge-bases/{knowledge_base_id}/documents",
    response_model=list[DocumentSummary],
)
def list_documents(
    knowledge_base_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not can_access_knowledge_base(db, current_user.id, knowledge_base_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="知识库不存在或无权访问",
        )

    return db.scalars(
        select(Document)
        .where(Document.knowledge_base_id == knowledge_base_id)
        .order_by(Document.updated_at.desc(), Document.id.desc())
    ).all()


@router.get("/documents/{document_id}", response_model=DocumentOut)
def get_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not can_access_document(db, current_user.id, document_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文档不存在或无权访问",
        )
    return _get_document_or_404(db, document_id)


@router.put("/documents/{document_id}", response_model=DocumentOut)
def update_document(
    document_id: int,
    payload: DocumentUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not can_access_document(db, current_user.id, document_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文档不存在或无权访问",
        )
    if not can_edit_document(db, current_user.id, document_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权编辑该文档",
        )

    document = _get_document_or_404(db, document_id)
    if payload.title is not None:
        document.title = payload.title
    if payload.content is not None:
        document.content = payload.content

    db.commit()
    db.refresh(document)
    if payload.content is not None:
        index_document(db, document)
        db.refresh(document)
    return document


@router.post("/documents/{document_id}/reindex", response_model=DocumentOut)
def reindex_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not can_access_document(db, current_user.id, document_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文档不存在或无权访问",
        )
    if not can_edit_document(db, current_user.id, document_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权重建该文档索引",
        )

    document = _get_document_or_404(db, document_id)
    index_document(db, document)
    db.refresh(document)
    return document


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not can_access_document(db, current_user.id, document_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文档不存在或无权访问",
        )
    if not can_edit_document(db, current_user.id, document_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权删除该文档",
        )

    document = _get_document_or_404(db, document_id)
    file_path = document.file_path
    delete_document_vectors(document.id)
    db.delete(document)
    db.commit()
    if file_path:
        _remove_uploaded_file(file_path)
