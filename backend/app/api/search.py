from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.deps import get_current_user
from db.session import get_db
from models.user import User
from schemas.search import SearchRequest, SearchResponse
from services.permissions import can_access_knowledge_base
from services.retrieval import retrieve_matches

router = APIRouter(prefix="/api", tags=["search"])


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

    matches = retrieve_matches(db, current_user.id, knowledge_base_id, payload.question)

    return SearchResponse(
        knowledge_base_id=knowledge_base_id,
        question=payload.question,
        matches=matches,
    )
