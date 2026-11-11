from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


class SearchMatch(BaseModel):
    document_id: int
    document_title: str
    chunk_id: int
    chunk_index: int
    page_number: int | None
    content: str
    score: float


class SearchResponse(BaseModel):
    knowledge_base_id: int
    question: str
    matches: list[SearchMatch]
