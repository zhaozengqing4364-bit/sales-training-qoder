"""Narrow infrastructure and cross-domain ports owned by audio_assessment."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field


class PresignedAudioPart(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    upload_url: str
    object_key: str
    expires_at: str
    required_headers: dict[str, str]


class AudioObjectMetadata(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    object_key: str
    size_bytes: int = Field(ge=0)
    sha256: str
    content_type: str | None = None


class StoredAudioObject(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    artifact_ref: str = Field(pattern=r"^artifact://")
    object_key: str
    size_bytes: int = Field(ge=0)
    sha256: str
    content_type: str


class AudioMediaInspection(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    content_type: str
    duration_seconds: float = Field(gt=0)
    sample_rate_hz: int = Field(gt=0)
    channels: int = Field(gt=0, le=32)
    speech_ratio: float = Field(ge=0, le=1)
    silence_ratio: float = Field(ge=0, le=1)
    clipping_ratio: float = Field(ge=0, le=1)
    mean_volume_db: float
    tool_version: str


class NormalizedAudio(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    path: Path
    inspection: AudioMediaInspection
    content_type: Literal["audio/wav"] = "audio/wav"


class AudioOutcomePayload(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    organization_id: str
    actor_id: str
    attempt_id: str
    result_type: str
    result_id: str
    score: float | None
    max_score: float | None
    passed: bool | None
    assessment_result: str
    source_refs: tuple[dict[str, str], ...] = ()
    lineage: dict[str, Any]
    confidence: float | None = Field(default=None, ge=0, le=1)
    critical_flags: tuple[str, ...] = ()
    degradations: tuple[str, ...] = ()
    next_action: dict[str, Any] | None = None
    idempotency_key: str
    trace_id: str | None = None
    supersedes_outcome_id: str | None = None


class AudioGovernanceActor(Protocol):
    @property
    def organization_id(self) -> str: ...

    @property
    def actor_id(self) -> str: ...

    @property
    def capabilities(self) -> frozenset[str]: ...

    @property
    def trace_id(self) -> str | None: ...


@runtime_checkable
class AudioAttemptInvalidationPort(Protocol):
    async def invalidate(
        self,
        *,
        actor: AudioGovernanceActor,
        attempt_id: str,
        reason: str,
        idempotency_key: str,
    ) -> None: ...


@runtime_checkable
class AudioObjectStoragePort(Protocol):
    @property
    def backend_name(self) -> str: ...

    def presign_part(
        self,
        *,
        upload_session_id: str,
        part_number: int,
        object_key: str,
        content_type: str,
        size_bytes: int,
        sha256: str,
        expires_seconds: int,
    ) -> PresignedAudioPart: ...

    async def head(self, object_key: str) -> AudioObjectMetadata: ...

    async def materialize(
        self, object_keys: tuple[str, ...], destination: Path
    ) -> None: ...

    async def store_file(
        self,
        *,
        object_key: str,
        source: Path,
        content_type: str,
        sha256: str,
    ) -> StoredAudioObject: ...

    def signed_get_url(self, object_key: str, *, expires_seconds: int) -> str: ...

    async def delete(self, object_keys: tuple[str, ...]) -> None: ...


@runtime_checkable
class AudioMediaToolPort(Protocol):
    async def inspect_and_normalize(
        self,
        *,
        source: Path,
        destination: Path,
        declared_content_type: str,
        max_duration_seconds: int,
    ) -> NormalizedAudio: ...


@runtime_checkable
class AudioOutcomeWriterPort(Protocol):
    async def record(self, payload: AudioOutcomePayload) -> str: ...


__all__ = [
    "AudioAttemptInvalidationPort",
    "AudioGovernanceActor",
    "AudioMediaInspection",
    "AudioMediaToolPort",
    "AudioObjectMetadata",
    "AudioObjectStoragePort",
    "AudioOutcomePayload",
    "AudioOutcomeWriterPort",
    "NormalizedAudio",
    "PresignedAudioPart",
    "StoredAudioObject",
]
