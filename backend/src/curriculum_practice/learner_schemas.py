from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from curriculum_practice.learning_content_schemas import LearningChapterResponse
from curriculum_practice.schema_types import LearnerLevel


class LearningProgressResponse(BaseModel):
    completed_chapter_ids: list[str]
    completed_count: int
    total_chapters: int
    is_completed: bool
    state: Literal["not_started", "in_progress", "completed"]
    primary_cta: Literal["continue learning", "start exam"]


class LearnerStudyContentResponse(BaseModel):
    learning_content_id: str
    title: str
    summary: str | None = None
    owner: str | None = None
    source: str | None = None
    chapters: list[LearningChapterResponse]
    progress: LearningProgressResponse


class ChapterCompleteResponse(BaseModel):
    chapter_id: str
    already_completed: bool
    progress: LearningProgressResponse


class LearnerProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    self_assessed_level: LearnerLevel | None = None
    admin_overridden_level: LearnerLevel | None = None
    effective_level: LearnerLevel
    self_assessed_at: object | None = None
    overridden_by: str | None = None
    overridden_at: object | None = None


class LearnerSelfAssessmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: LearnerLevel


class LearnerAdminOverrideRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: LearnerLevel
