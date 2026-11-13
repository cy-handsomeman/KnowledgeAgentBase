from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.deps import get_current_user
from api.ratelimit import user_rate_limit
from db.session import get_db
from models.user import User
from schemas.agent import AgentRequest, AgentResponse
from services.agent import run_agent
from services.llm import LLMError

router = APIRouter(prefix="/api", tags=["agent"])


@router.post(
    "/knowledge-bases/{knowledge_base_id}/agent",
    response_model=AgentResponse,
    dependencies=[Depends(user_rate_limit(10, 60, "agent"))],
)
def run_knowledge_agent(
    knowledge_base_id: int,
    payload: AgentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        session_id, answer, sources, has_evidence, steps, created_at = run_agent(
            db, current_user.id, knowledge_base_id, payload.question, payload.session_id
        )
    except PermissionError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except LLMError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)
        ) from error
    return AgentResponse(
        session_id=session_id,
        answer=answer,
        sources=sources,
        has_evidence=has_evidence,
        steps=steps,
        created_at=created_at,
    )
