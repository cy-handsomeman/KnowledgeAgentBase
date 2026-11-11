from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DocumentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    content: str = ""


class DocumentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    content: str | None = None


class DocumentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    file_type: str
    status: str
    created_at: datetime
    updated_at: datetime


class DocumentOut(DocumentSummary):
    knowledge_base_id: int
    content: str | None
    original_filename: str | None
    file_path: str | None
    file_size: int | None
    uploaded_by: int
    error_message: str | None
