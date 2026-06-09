from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from curriculum_practice.schema_types import LearningContentStatus


class LearningContentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1, max_length=200)
    summary: str | None = Field(None, max_length=4000)
    owner: str | None = Field(None, min_length=1, max_length=120)
    source: str | None = Field(None, min_length=1, max_length=300)
    safety_flagged: bool = False


class LearningContentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(None, min_length=1, max_length=200)
    summary: str | None = Field(None, max_length=4000)
    owner: str | None = Field(None, min_length=1, max_length=120)
    source: str | None = Field(None, min_length=1, max_length=300)
    safety_flagged: bool | None = None


class LearningChapterCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    order_index: int | None = Field(None, ge=1)


class LearningChapterUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(None, min_length=1, max_length=200)
    content: str | None = Field(None, min_length=1)
    order_index: int | None = Field(None, ge=1)


class LearningChapterReorderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chapter_ids: list[str] = Field(..., min_length=1)


class LearningChapterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    chapter_id: str
    learning_content_id: str
    title: str
    content: str
    order_index: int
    created_at: object
    updated_at: object


class LearningContentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    learning_content_id: str
    title: str
    summary: str | None = None
    owner: str | None = None
    source: str | None = None
    status: LearningContentStatus
    safety_flagged: bool
    version: int
    content_hash: str | None = None
    published_at: object | None = None
    created_at: object
    updated_at: object
    chapters: list[LearningChapterResponse] = Field(default_factory=list)


class LearningContentListResponse(BaseModel):
    items: list[LearningContentResponse]
    total: int
