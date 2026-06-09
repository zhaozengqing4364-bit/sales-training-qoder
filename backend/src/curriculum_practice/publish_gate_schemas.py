from __future__ import annotations

from pydantic import BaseModel

from curriculum_practice.schema_types import GateStatus


class GateResult(BaseModel):
    gate_name: str
    status: GateStatus
    reason_code: str
    message: str


class PublishGateDecision(BaseModel):
    can_publish: bool
    results: list[GateResult]
