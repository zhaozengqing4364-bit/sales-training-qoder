"""Object-storage boundary and deterministic fake adapter."""

from __future__ import annotations

import hashlib
from collections import deque
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from ai_platform.contracts import DataClassification


class StorageFailureKind(StrEnum):
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    UNAVAILABLE = "unavailable"
    PARTIAL_WRITE = "partial_write"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    NOT_FOUND = "not_found"


class ObjectStorageError(Exception):
    def __init__(self, kind: StorageFailureKind, safe_message: str) -> None:
        super().__init__(safe_message)
        self.kind = kind
        self.safe_message = safe_message


class StoredObjectRef(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    artifact_ref: str
    content_hash: str
    size_bytes: int = Field(ge=0)
    data_classification: DataClassification


class ObjectStoragePort(Protocol):
    async def put(
        self,
        *,
        object_key: str,
        content: bytes,
        data_classification: DataClassification,
        idempotency_key: str,
    ) -> StoredObjectRef: ...

    async def get(self, artifact_ref: str) -> bytes: ...


@dataclass(frozen=True, slots=True)
class StorageScenario:
    kind: str

    @classmethod
    def success(cls) -> StorageScenario:
        return cls(kind="success")

    @classmethod
    def timeout(cls) -> StorageScenario:
        return cls(kind="timeout")

    @classmethod
    def rate_limited(cls) -> StorageScenario:
        return cls(kind="rate_limited")

    @classmethod
    def unavailable(cls) -> StorageScenario:
        return cls(kind="unavailable")

    @classmethod
    def partial_write(cls) -> StorageScenario:
        return cls(kind="partial_write")


@dataclass(slots=True)
class _StoredObject:
    content: bytes
    ref: StoredObjectRef
    fingerprint: str


class DeterministicObjectStorage(ObjectStoragePort):
    def __init__(self, *, scenarios: list[StorageScenario]) -> None:
        if not scenarios:
            raise ValueError("at least one storage scenario is required")
        self._scenarios = deque(scenarios)
        self._objects: dict[str, _StoredObject] = {}
        self._idempotency: dict[str, _StoredObject] = {}
        self.put_calls = 0

    async def put(
        self,
        *,
        object_key: str,
        content: bytes,
        data_classification: DataClassification,
        idempotency_key: str,
    ) -> StoredObjectRef:
        content_hash = hashlib.sha256(content).hexdigest()
        fingerprint = hashlib.sha256(
            (f"{object_key}\0{data_classification.value}\0{content_hash}").encode()
        ).hexdigest()
        prior = self._idempotency.get(idempotency_key)
        if prior is not None:
            if prior.fingerprint != fingerprint:
                raise ObjectStorageError(
                    StorageFailureKind.IDEMPOTENCY_CONFLICT,
                    "相同幂等键对应了不同的对象内容。",
                )
            return prior.ref
        self.put_calls += 1
        if not self._scenarios:
            raise AssertionError("deterministic storage exhausted its scenarios")
        scenario = self._scenarios.popleft()
        if scenario.kind == "timeout":
            raise ObjectStorageError(StorageFailureKind.TIMEOUT, "对象存储响应超时。")
        if scenario.kind == "rate_limited":
            raise ObjectStorageError(
                StorageFailureKind.RATE_LIMITED, "对象存储请求过多。"
            )
        if scenario.kind == "unavailable":
            raise ObjectStorageError(
                StorageFailureKind.UNAVAILABLE, "对象存储暂时不可用。"
            )
        if scenario.kind == "partial_write":
            raise ObjectStorageError(
                StorageFailureKind.PARTIAL_WRITE,
                "对象未完整写入，未发布 artifact 引用。",
            )
        if scenario.kind != "success":
            raise AssertionError(f"unsupported storage scenario: {scenario.kind}")
        artifact_ref = f"artifact://object-storage/{object_key}"
        ref = StoredObjectRef(
            artifact_ref=artifact_ref,
            content_hash=f"sha256:{content_hash}",
            size_bytes=len(content),
            data_classification=data_classification,
        )
        stored = _StoredObject(content=bytes(content), ref=ref, fingerprint=fingerprint)
        self._objects[artifact_ref] = stored
        self._idempotency[idempotency_key] = stored
        return ref

    async def get(self, artifact_ref: str) -> bytes:
        try:
            return bytes(self._objects[artifact_ref].content)
        except KeyError as exc:
            raise ObjectStorageError(
                StorageFailureKind.NOT_FOUND, "对象存储引用不存在。"
            ) from exc
