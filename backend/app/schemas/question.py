from pydantic import BaseModel


class QuestionRequest(BaseModel):
    question: str
    knowledge_base_id: int
