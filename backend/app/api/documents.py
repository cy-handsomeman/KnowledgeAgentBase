from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps import get_current_user
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

router = APIRouter(prefix="/api", tags=["documents"])


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
    db.delete(document)
    db.commit()
