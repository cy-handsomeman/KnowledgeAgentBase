from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeBaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    scope_type: str
    group_id: int | None
    owner_user_id: int | None
    created_at: datetime


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    scope_type: str = Field(pattern="^(enterprise_group|personal)$")
    group_id: int | None = None


class KnowledgeBaseUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
