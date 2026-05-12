from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from common.db.schemas import SessionResponse


class TrainingTaskStatus(StrEnum):
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class TrainingTaskScenarioType(StrEnum):
    SALES = "sales"
    PRESENTATION = "presentation"


class TrainingTaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1, max_length=200)
    assignee_id: str = Field(..., min_length=1, max_length=36)
    scenario_type: TrainingTaskScenarioType
    goal: str = Field(..., min_length=1)
    focus_intent: str | None = Field(None, max_length=120)
    due_date: datetime | None = None
    completion_criteria: dict[str, Any] = Field(default_factory=dict)
    source: str = Field(default="manual", min_length=1, max_length=50)
    status: TrainingTaskStatus = TrainingTaskStatus.ASSIGNED
    resulting_session_id: str | None = Field(None, max_length=36)
    before_after_summary: dict[str, Any] | None = None


class TrainingTaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(None, min_length=1, max_length=200)
    scenario_type: TrainingTaskScenarioType | None = None
    goal: str | None = Field(None, min_length=1)
    focus_intent: str | None = Field(None, max_length=120)
    due_date: datetime | None = None
    completion_criteria: dict[str, Any] | None = None
    source: str | None = Field(None, min_length=1, max_length=50)
    status: TrainingTaskStatus | None = None
    resulting_session_id: str | None = Field(None, max_length=36)
    before_after_summary: dict[str, Any] | None = None


class TrainingTaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    task_id: str
    title: str
    assignee_id: str
    scenario_type: str
    goal: str
    focus_intent: str | None = None
    due_date: datetime | None = None
    completion_criteria: dict[str, Any]
    source: str
    status: str
    resulting_session_id: str | None = None
    before_after_summary: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class TrainingTaskListResponse(BaseModel):
    total: int
    items: list[TrainingTaskResponse]
    page: int
    page_size: int
    has_more: bool


class TrainingTaskStartSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: str | None = Field(None, max_length=36)
    persona_id: str | None = Field(None, max_length=36)
    presentation_id: str | None = Field(None, max_length=36)
    scenario_id: str | None = Field(None, max_length=36)
    voice_mode: str | None = Field(None, pattern="^(legacy|stepfun_realtime)$")
    runtime_profile_id: str | None = Field(None, max_length=36)


class TrainingTaskStartSessionResponse(TrainingTaskResponse):
    session: SessionResponse


class TrainingTaskCompleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(..., min_length=1, max_length=36)
