from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.deps import get_current_user
from db.session import get_db
from models.document import Document, DocumentChunk
from models.user import User
from schemas.search import SearchMatch, SearchRequest, SearchResponse
from services.embedding import EmbeddingService
from services.permissions import can_access_document, can_access_knowledge_base
from services.vector_store import search_chunks

router = APIRouter(prefix="/api", tags=["search"])

TOP_K = 5


@router.post(
    "/knowledge-bases/{knowledge_base_id}/search",
    response_model=SearchResponse,
)
def search_knowledge_base(
    knowledge_base_id: int,
    payload: SearchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not can_access_knowledge_base(db, current_user.id, knowledge_base_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="知识库不存在或无权访问",
        )

    query_vector = EmbeddingService().embed_query(payload.question)
    raw_matches = search_chunks(query_vector, knowledge_base_id, limit=TOP_K)

    matches = []
    for item in raw_matches:
        metadata = item["metadata"] or {}
        chunk_id = metadata.get("chunk_id")
        if chunk_id is None:
            continue

        chunk = db.get(DocumentChunk, int(chunk_id))
        if chunk is None:
            continue

        document = db.get(Document, chunk.document_id)
        if document is None or document.knowledge_base_id != knowledge_base_id:
            continue

        if not can_access_document(db, current_user.id, document.id):
            continue

        distance = float(item["distance"])
        score = max(-1.0, min(1.0, 1 - distance * distance / 2))

        matches.append(
            SearchMatch(
                document_id=document.id,
                document_title=document.title,
                chunk_id=chunk.id,
                chunk_index=chunk.chunk_index,
                page_number=chunk.page_number,
                content=item["content"],
                score=round(score, 4),
            )
        )

    return SearchResponse(
        knowledge_base_id=knowledge_base_id,
        question=payload.question,
        matches=matches,
    )
