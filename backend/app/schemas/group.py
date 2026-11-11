from pydantic import BaseModel, ConfigDict


class GroupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    group_type: str
    description: str | None
    role: str
