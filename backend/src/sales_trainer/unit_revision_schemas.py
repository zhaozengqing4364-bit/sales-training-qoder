from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class UnitRevisionResponse(BaseModel):
    revision_id: str
    revision_no: int
    status: Literal["working", "published", "archived"]
    change_class: Literal[
        "non_semantic",
        "semantic",
        "binding",
        "scoring_high_risk",
    ]
    title: str | None = None
    question_count: int
    is_active: bool
    is_working: bool
    source_revision_id: str | None = None
    payload_hash: str
    reason: str | None = None
    trace_id: str | None = None
    created_by: str | None = None
    published_by: str | None = None
    created_at: object
    published_at: object | None = None


class UnitRevisionListResponse(BaseModel):
    items: list[UnitRevisionResponse]
    total: int


class UnitRollbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_revision_id: str = Field(..., min_length=1, max_length=36)
    reason: str = Field(..., min_length=1, max_length=1000)
