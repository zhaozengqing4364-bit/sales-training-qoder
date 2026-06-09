from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class RegradePreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_revision_id: str | None = Field(None, min_length=1, max_length=36)


class RegradeRunRequest(RegradePreviewRequest):
    reason: str = Field(..., min_length=1, max_length=1000)


class RegradePreviewResponse(BaseModel):
    target_type: Literal["quiz_attempt", "audio_submission"]
    target_id: str
    target_revision_id: str
    impact_scope: dict[str, Any]
    before_snapshot: dict[str, Any]
    after_snapshot: dict[str, Any]


class RegradeRunResponse(RegradePreviewResponse):
    regrade_run_id: str
    status: Literal["completed", "failed"]
    reason: str
    trace_id: str
    created_at: object
