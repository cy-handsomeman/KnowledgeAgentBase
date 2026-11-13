from datetime import datetime

from pydantic import BaseModel, Field

from schemas.ask import SourceOut


class AgentRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    session_id: int | None = None


class AgentStepOut(BaseModel):
    tool: str
    query: str
    result_count: int


class AgentResponse(BaseModel):
    session_id: int
    answer: str
    sources: list[SourceOut]
    has_evidence: bool
    steps: list[AgentStepOut]
    model_call_count: int
    elapsed_seconds: float
    tool_limit_reached: bool
    created_at: datetime
