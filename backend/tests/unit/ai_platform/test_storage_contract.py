"""Deterministic object-storage boundary contract tests."""

from __future__ import annotations

import pytest

from ai_platform import (
    DataClassification,
    DeterministicObjectStorage,
    ObjectStorageError,
    StorageFailureKind,
    StorageScenario,
)


async def test_storage_success_and_duplicate_delivery_are_effect_once() -> None:
    storage = DeterministicObjectStorage(scenarios=[StorageScenario.success()])

    first = await storage.put(
        object_key="org-1/audio/recording-1",
        content=b"audio-bytes",
        data_classification=DataClassification.CONFIDENTIAL,
        idempotency_key="upload-1",
    )
    replay = await storage.put(
        object_key="org-1/audio/recording-1",
        content=b"audio-bytes",
        data_classification=DataClassification.CONFIDENTIAL,
        idempotency_key="upload-1",
    )

    assert replay == first
    assert storage.put_calls == 1
    assert await storage.get(first.artifact_ref) == b"audio-bytes"


@pytest.mark.parametrize(
    ("scenario", "kind"),
    [
        (StorageScenario.timeout(), StorageFailureKind.TIMEOUT),
        (StorageScenario.rate_limited(), StorageFailureKind.RATE_LIMITED),
        (StorageScenario.unavailable(), StorageFailureKind.UNAVAILABLE),
        (StorageScenario.partial_write(), StorageFailureKind.PARTIAL_WRITE),
    ],
)
async def test_storage_failures_are_deterministic_and_never_publish_partial_refs(
    scenario: StorageScenario,
    kind: StorageFailureKind,
) -> None:
    storage = DeterministicObjectStorage(scenarios=[scenario])

    with pytest.raises(ObjectStorageError) as exc_info:
        await storage.put(
            object_key="org-1/audio/recording-1",
            content=b"sensitive-audio",
            data_classification=DataClassification.RESTRICTED,
            idempotency_key="upload-1",
        )

    assert exc_info.value.kind is kind
    with pytest.raises(ObjectStorageError) as missing:
        await storage.get("artifact://object-storage/org-1/audio/recording-1")
    assert missing.value.kind is StorageFailureKind.NOT_FOUND


async def test_storage_rejects_idempotency_key_reuse_with_different_content() -> None:
    storage = DeterministicObjectStorage(scenarios=[StorageScenario.success()])
    await storage.put(
        object_key="org-1/audio/recording-1",
        content=b"first",
        data_classification=DataClassification.CONFIDENTIAL,
        idempotency_key="upload-1",
    )

    with pytest.raises(ObjectStorageError) as exc_info:
        await storage.put(
            object_key="org-1/audio/recording-1",
            content=b"different",
            data_classification=DataClassification.CONFIDENTIAL,
            idempotency_key="upload-1",
        )

    assert exc_info.value.kind is StorageFailureKind.IDEMPOTENCY_CONFLICT


@pytest.mark.parametrize(
    "changed",
    [
        {"object_key": "org-2/audio/recording-1"},
        {"data_classification": DataClassification.RESTRICTED},
    ],
)
async def test_storage_idempotency_binds_key_and_classification(
    changed: dict[str, object],
) -> None:
    storage = DeterministicObjectStorage(scenarios=[StorageScenario.success()])
    arguments: dict[str, object] = {
        "object_key": "org-1/audio/recording-1",
        "content": b"same-bytes",
        "data_classification": DataClassification.CONFIDENTIAL,
        "idempotency_key": "upload-1",
    }
    await storage.put(**arguments)

    with pytest.raises(ObjectStorageError) as exc_info:
        await storage.put(**{**arguments, **changed})

    assert exc_info.value.kind is StorageFailureKind.IDEMPOTENCY_CONFLICT
