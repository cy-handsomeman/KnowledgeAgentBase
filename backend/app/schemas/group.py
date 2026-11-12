from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class GroupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    group_type: str
    description: str | None
    role: str


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    group_type: str = Field(default="department", pattern="^(company|department|project)$")
    description: str | None = Field(default=None, max_length=500)


class MemberOut(BaseModel):
    user_id: int
    username: str
    role: str
    joined_at: datetime


class MemberCreate(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    role: str = Field(default="member", pattern="^(member|editor|admin)$")


class MemberUpdate(BaseModel):
    role: str = Field(pattern="^(member|editor|admin)$")
