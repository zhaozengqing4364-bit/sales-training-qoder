from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

AnswerabilityType = Literal["sufficient", "partial", "insufficient", "blocked", "unanswered"]
SourceStatusType = Literal["ready", "blocked", "not_run"]


class KnowledgeCitation(BaseModel):
    """Normalized citation payload returned by the knowledge answer engine."""

    document_id: str | None = Field(None, description="Source document identifier")
    document_title: str | None = Field(None, description="Human-readable source title")
    chunk_id: str | None = Field(None, description="Source chunk identifier")
    snippet: str | None = Field(None, description="Quoted evidence snippet")
    score: float | None = Field(None, description="Normalized retrieval/ranking score")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Non-breaking extension metadata for downstream compatibility",
    )


class KnowledgeAnswerRequest(BaseModel):
    """Project-owned request contract for grounded answering."""

    query: str = Field(..., min_length=1, description="User question to answer")
    session_id: str | None = Field(None, description="Owning session identifier")
    scenario_type: str | None = Field(None, description="Runtime scenario type")
    knowledge_base_ids: list[str] = Field(
        default_factory=list,
        description="Knowledge base IDs bound to the request",
    )
    entrypoint: str | None = Field(
        None,
        description="Call site identifier such as realtime/report/replay",
    )
    runtime_options: dict[str, Any] = Field(
        default_factory=dict,
        description="Per-request execution options resolved by the caller",
    )


class KnowledgeAnswerResult(BaseModel):
    """Project-owned result contract with stable observability fields."""

    final_text: str | None = Field(None, description="Grounded answer text when available")
    blocked_text: str | None = Field(
        None,
        description="Learner-safe blocked response when grounded answering cannot proceed",
    )
    answerability: AnswerabilityType = Field(
        default="unanswered",
        description="Coverage verdict for the current answer run",
    )
    source_status: SourceStatusType = Field(
        default="not_run",
        description="Availability of the retrieval source behind this result",
    )
    citations: list[KnowledgeCitation] = Field(
        default_factory=list,
        description="Evidence citations that support the answer",
    )
    rewritten_queries: list[str] = Field(
        default_factory=list,
        description="Normalized or expanded retrieval queries used during execution",
    )
    unsupported_claims: list[str] = Field(
        default_factory=list,
        description="Claims filtered out because support was insufficient",
    )
    audit_run_id: str | None = Field(
        None,
        description="Persistent audit row ID once audit storage is wired in",
    )
    retrieval_summary: dict[str, Any] = Field(
        default_factory=dict,
        description="Compact retrieval diagnostics for runtime/report/replay compatibility",
    )


class KnowledgeAuditStep(BaseModel):
    """Step-level audit payload for future engine persistence."""

    step_name: str = Field(..., description="Logical engine step name")
    input_payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Bounded input payload for the step",
    )
    output_payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Bounded output payload for the step",
    )
    duration_ms: int = Field(default=0, ge=0, description="Step duration in milliseconds")
    status: str = Field(default="not_run", description="Step outcome status")
