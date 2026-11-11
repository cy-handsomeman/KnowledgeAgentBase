from datetime import datetime

from pydantic import BaseModel, ConfigDict


class KnowledgeBaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    scope_type: str
    group_id: int | None
    owner_user_id: int | None
    created_at: datetime
