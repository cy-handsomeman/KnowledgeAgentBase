from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class ChatSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    scope_type: str
    knowledge_base_id: int
    created_at: datetime
    updated_at: datetime


class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    content: str
    sources_json: Any | None
    has_evidence: bool | None
    created_at: datetime
