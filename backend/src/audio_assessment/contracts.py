"""Closed contracts and user-safe projections for durable audio assessment."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

AUDIO_MAX_DURATION_SECONDS = 30 * 60
AUDIO_MAX_SIZE_BYTES = 100 * 1024 * 1024
AUDIO_UPLOAD_PART_SIZE_BYTES = 5 * 1024 * 1024
AUDIO_UPLOAD_TTL_SECONDS = 24 * 60 * 60
AUDIO_LOCAL_DRAFT_TTL_SECONDS = 7 * 24 * 60 * 60

ALLOWED_AUDIO_CONTENT_TYPES: tuple[str, ...] = (
    "audio/mpeg",
    "audio/mp3",
    "audio/mp4",
    "audio/wav",
    "audio/x-wav",
    "audio/webm",
    "audio/x-m4a",
)

ASSIGNMENT_SEGMENTS: tuple[str, ...] = (
    "discovery",
    "objection",
    "commitment",
)


def _canonical_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()


class UploadPartDeclaration(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    part_number: int = Field(ge=1, le=10_000)
    size_bytes: int = Field(ge=1, le=20 * 1024 * 1024)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class CreateUploadSessionInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    segment_id: str = Field(min_length=1, max_length=40)
    recording_mode: str = Field(default="browser", pattern=r"^(browser|file)$")
    original_filename: str = Field(min_length=1, max_length=500)
    content_type: str = Field(min_length=1, max_length=100)
    size_bytes: int = Field(ge=1, le=AUDIO_MAX_SIZE_BYTES)
    duration_seconds: float = Field(gt=0, le=AUDIO_MAX_DURATION_SECONDS)
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    parts: tuple[UploadPartDeclaration, ...] = Field(min_length=1, max_length=400)

    @model_validator(mode="after")
    def validate_manifest(self) -> CreateUploadSessionInput:
        expected_numbers = tuple(range(1, len(self.parts) + 1))
        if tuple(item.part_number for item in self.parts) != expected_numbers:
            raise ValueError("upload parts must be contiguous and ordered")
        if sum(item.size_bytes for item in self.parts) != self.size_bytes:
            raise ValueError("upload part sizes must equal the declared file size")
        manifest = [item.model_dump(mode="json") for item in self.parts]
        if _canonical_hash(manifest) != self.manifest_sha256:
            raise ValueError("upload manifest hash mismatch")
        return self


class ConfirmUploadPartInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    upload_session_id: str = Field(min_length=1, max_length=160)
    part_number: int = Field(ge=1, le=10_000)
    size_bytes: int = Field(ge=1, le=20 * 1024 * 1024)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class FinalizeUploadInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    upload_session_id: str = Field(min_length=1, max_length=160)


class SubmissionCommandInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    submission_id: str = Field(min_length=1, max_length=160)


class AudioSubmissionState(StrEnum):
    DRAFT = "draft"
    UPLOADING = "uploading"
    UPLOADED = "uploaded"
    VALIDATING = "validating"
    NORMALIZING = "normalizing"
    TRANSCRIBING = "transcribing"
    TRANSCRIPT_READY = "transcript_ready"
    SCORING = "scoring"
    RECONCILING = "reconciling"
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    FAILED_RECOVERABLE = "failed_recoverable"
    FAILED_TERMINAL = "failed_terminal"
    NEEDS_REVIEW = "needs_review"
    CANCELLED = "cancelled"
    INVALIDATED = "invalidated"
    EXPIRED = "expired"


class UploadSessionState(StrEnum):
    UPLOADING = "uploading"
    FINALIZED = "finalized"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class TranscriptSource(StrEnum):
    AUTOMATIC = "automatic"
    MANUAL_CORRECTION = "manual_correction"
    RETRANSCRIPTION = "retranscription"


class GovernedAIContractSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    business_purpose: str = Field(min_length=1, max_length=160)
    prompt_template_id: str | None = Field(default=None, max_length=160)
    prompt_revision_id: str | None = Field(default=None, max_length=160)
    model_routing_profile_id: str = Field(min_length=1, max_length=160)
    model_routing_revision_id: str = Field(min_length=1, max_length=160)
    input_schema_version: str = Field(min_length=1, max_length=120)
    output_schema_version: str = Field(min_length=1, max_length=120)
    timeout_policy_ref: str = Field(min_length=1, max_length=160)
    retry_policy_ref: str = Field(min_length=1, max_length=160)


class AudioCapturePolicySnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    allowed_recording_modes: tuple[Literal["browser", "file"], ...] = (
        "browser",
        "file",
    )
    allowed_content_types: tuple[str, ...] = ALLOWED_AUDIO_CONTENT_TYPES
    max_duration_seconds: int = Field(
        default=AUDIO_MAX_DURATION_SECONDS,
        ge=1,
        le=AUDIO_MAX_DURATION_SECONDS,
    )
    max_size_bytes: int = Field(
        default=AUDIO_MAX_SIZE_BYTES,
        ge=1,
        le=AUDIO_MAX_SIZE_BYTES,
    )
    part_size_bytes: int = Field(
        default=AUDIO_UPLOAD_PART_SIZE_BYTES,
        ge=256 * 1024,
        le=20 * 1024 * 1024,
    )
    local_draft_ttl_seconds: int = Field(
        default=AUDIO_LOCAL_DRAFT_TTL_SECONDS,
        ge=60,
        le=30 * 24 * 60 * 60,
    )
    upload_ttl_seconds: int = Field(
        default=AUDIO_UPLOAD_TTL_SECONDS,
        ge=300,
        le=7 * 24 * 60 * 60,
    )


class AudioQualityPolicySnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    minimum_asr_confidence: float = Field(default=0.65, ge=0, le=1)
    minimum_speech_ratio: float = Field(default=0.35, ge=0, le=1)
    maximum_silence_ratio: float = Field(default=0.65, ge=0, le=1)
    maximum_clipping_ratio: float = Field(default=0.05, ge=0, le=1)
    minimum_mean_volume_db: float = Field(default=-45, ge=-100, le=0)


class AudioScoreDimensionSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str = Field(min_length=1, max_length=120)
    label: str = Field(min_length=1, max_length=240)
    rubric: str = Field(min_length=1, max_length=10_000)
    weight: float = Field(gt=0, le=1)
    competency_keys: tuple[str, ...] = Field(default_factory=tuple, max_length=50)
    minimum_score: float | None = Field(default=None, ge=0, le=100)


class AudioScoringSchemeSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    language: str = Field(default="zh-CN", min_length=2, max_length=32)
    capture: AudioCapturePolicySnapshot = Field(
        default_factory=AudioCapturePolicySnapshot
    )
    quality: AudioQualityPolicySnapshot = Field(
        default_factory=AudioQualityPolicySnapshot
    )
    asr: GovernedAIContractSnapshot
    scoring: GovernedAIContractSnapshot
    dimensions: tuple[AudioScoreDimensionSnapshot, ...] = Field(
        min_length=1, max_length=100
    )
    pass_score: float = Field(default=75, ge=0, le=100)
    allowed_knowledge: tuple[str, ...] = Field(default_factory=tuple, max_length=200)
    allow_transcript_correction_request: bool = True

    @model_validator(mode="after")
    def validate_scoring_contract(self) -> AudioScoringSchemeSnapshot:
        if abs(sum(item.weight for item in self.dimensions) - 1.0) > 0.0001:
            raise ValueError("audio score dimension weights must sum to 1")
        if len({item.key for item in self.dimensions}) != len(self.dimensions):
            raise ValueError("audio score dimension keys must be unique")
        if any(
            value is None
            for value in (
                self.scoring.prompt_template_id,
                self.scoring.prompt_revision_id,
            )
        ):
            raise ValueError("audio scoring requires exact prompt lineage")
        if any(
            value is not None
            for value in (
                self.asr.prompt_template_id,
                self.asr.prompt_revision_id,
            )
        ):
            raise ValueError("audio ASR cannot carry prompt lineage")
        return self


class AudioMaterialSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    title: str = Field(min_length=1, max_length=240)
    task_prompt: str = Field(min_length=1, max_length=10_000)
    preparation_hints: tuple[str, ...] = Field(default_factory=tuple, max_length=100)


class AudioScenarioSegmentSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    segment_id: Literal["discovery", "objection", "commitment"]
    title: str = Field(min_length=1, max_length=240)
    customer_context: str = Field(min_length=1, max_length=10_000)
    prompt: str = Field(min_length=1, max_length=10_000)
    preparation_hints: tuple[str, ...] = Field(default_factory=tuple, max_length=100)


class AudioScenarioSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    title: str = Field(min_length=1, max_length=240)
    segments: tuple[AudioScenarioSegmentSnapshot, ...] = Field(
        min_length=3, max_length=3
    )

    @model_validator(mode="after")
    def fixed_launch_segments(self) -> AudioScenarioSnapshot:
        if tuple(item.segment_id for item in self.segments) != ASSIGNMENT_SEGMENTS:
            raise ValueError(
                "assignment scenario must use the fixed launch segment order"
            )
        return self


class UploadPartProjection(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    part_number: int = Field(ge=1, le=10_000)
    upload_url: str
    required_headers: dict[str, str]
    uploaded: bool
    size_bytes: int | None = Field(default=None, ge=1)
    sha256: str | None = None


class UploadSessionProjection(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    upload_session_id: str
    submission_id: str
    state: UploadSessionState
    expires_at: datetime
    part_size_bytes: int = Field(ge=1)
    expected_part_count: int = Field(ge=1)
    uploaded_part_count: int = Field(ge=0)
    parts: tuple[UploadPartProjection, ...]


class TranscriptSegment(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    sequence: int = Field(ge=1)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)
    text: str = Field(min_length=1, max_length=20_000)
    confidence: float | None = Field(default=None, ge=0, le=1)
    speaker: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def end_after_start(self) -> TranscriptSegment:
        if self.end_ms < self.start_ms:
            raise ValueError("segment end_ms must be >= start_ms")
        return self


class AudioTranscriptAIInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    audio_artifact_ref: str = Field(pattern=r"^artifact://")
    language: str = Field(min_length=2, max_length=32)


class AudioTranscriptAIOutput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    transcript: str = Field(min_length=1, max_length=1_000_000)
    confidence: float = Field(ge=0, le=1)
    language: str = Field(min_length=2, max_length=32)
    segments: tuple[TranscriptSegment, ...] = Field(
        default_factory=tuple, max_length=20_000
    )


class AudioScoringEvidenceSpan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    dimension_key: str = Field(min_length=1, max_length=120)
    segment_sequence: int | None = Field(default=None, ge=1)
    quote: str = Field(min_length=1, max_length=2_000)
    rationale: str = Field(min_length=1, max_length=2_000)


class AudioDimensionScore(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    dimension_key: str = Field(min_length=1, max_length=120)
    score: float = Field(ge=0, le=100)
    uncertainty: float = Field(default=0, ge=0, le=1)


class AudioScoringAIInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    submission_id: str = Field(min_length=1, max_length=160)
    activity_type: Literal["audio_assessment", "assignment"]
    segment_id: str = Field(min_length=1, max_length=40)
    scenario: dict[str, Any]
    transcript_revision_id: str = Field(min_length=1, max_length=160)
    transcript: str = Field(min_length=1, max_length=1_000_000)
    transcript_segments: tuple[TranscriptSegment, ...] = Field(max_length=20_000)
    quality_summary: dict[str, Any]
    dimensions: tuple[dict[str, Any], ...] = Field(min_length=1, max_length=100)
    allowed_knowledge: tuple[str, ...] = Field(default_factory=tuple, max_length=200)


class AudioScoringAIOutput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    dimension_scores: tuple[AudioDimensionScore, ...] = Field(
        min_length=1, max_length=100
    )
    evidence_spans: tuple[AudioScoringEvidenceSpan, ...] = Field(
        default_factory=tuple, max_length=500
    )
    missing_points: tuple[str, ...] = Field(default_factory=tuple, max_length=200)
    uncertainty: float = Field(ge=0, le=1)
    feedback: tuple[str, ...] = Field(default_factory=tuple, max_length=100)
    recommended_remediation: tuple[str, ...] = Field(
        default_factory=tuple, max_length=100
    )
    critical_flags: tuple[str, ...] = Field(default_factory=tuple, max_length=100)


class AudioRunnerProjection(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["audio_assessment", "assignment"]
    run_id: str
    status: str
    version: int = Field(ge=1)
    rules: dict[str, Any]
    segments: tuple[dict[str, Any], ...]
    active_upload: UploadSessionProjection | None = None
    result: dict[str, Any] | None = None


class AudioPipelineTaskInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    submission_id: str = Field(min_length=1, max_length=160)
    mode: Literal["initial", "retry", "retranscribe", "regrade"] = "initial"
    requested_by: str = Field(min_length=1, max_length=120)
    target_transcript_revision_id: str | None = Field(default=None, max_length=160)
    target_scoring_scheme_revision_id: str | None = Field(default=None, max_length=160)


class AudioPipelineTaskResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    submission_id: str
    run_id: str
    state: str
    transcript_revision_id: str | None = None
    score_outcome_version_id: str | None = None
    generic_outcome_id: str | None = None


__all__ = [
    "ALLOWED_AUDIO_CONTENT_TYPES",
    "ASSIGNMENT_SEGMENTS",
    "AUDIO_LOCAL_DRAFT_TTL_SECONDS",
    "AUDIO_MAX_DURATION_SECONDS",
    "AUDIO_MAX_SIZE_BYTES",
    "AUDIO_UPLOAD_PART_SIZE_BYTES",
    "AUDIO_UPLOAD_TTL_SECONDS",
    "AudioDimensionScore",
    "AudioCapturePolicySnapshot",
    "AudioMaterialSnapshot",
    "AudioPipelineTaskInput",
    "AudioPipelineTaskResult",
    "AudioRunnerProjection",
    "AudioScoringAIInput",
    "AudioScoringAIOutput",
    "AudioScoringSchemeSnapshot",
    "AudioScenarioSnapshot",
    "AudioSubmissionState",
    "AudioTranscriptAIInput",
    "AudioTranscriptAIOutput",
    "TranscriptSegment",
    "TranscriptSource",
    "GovernedAIContractSnapshot",
    "ConfirmUploadPartInput",
    "CreateUploadSessionInput",
    "FinalizeUploadInput",
    "SubmissionCommandInput",
    "UploadPartDeclaration",
    "UploadPartProjection",
    "UploadSessionProjection",
    "UploadSessionState",
]
