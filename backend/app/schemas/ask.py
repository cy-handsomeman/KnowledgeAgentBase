from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    session_id: int | None = None


class SourceOut(BaseModel):
    document_id: int
    document_title: str
    chunk_id: int
    page_number: int | None
    score: float


class AskResponse(BaseModel):
    session_id: int
    answer: str
    sources: list[SourceOut]
    has_evidence: bool
