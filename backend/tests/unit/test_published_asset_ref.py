from __future__ import annotations

from dataclasses import asdict

import pytest
from pydantic import ValidationError

from curriculum_practice.schemas import PublishedAssetRef, PublishedAssetRefSchema


def _sample_ref(*, with_snapshot: bool = True) -> PublishedAssetRef:
    return PublishedAssetRef(
        asset_type="situation_pack",
        asset_id=None,
        asset_code="first_visit",
        version="v1",
        content_hash="sha256:pack-content",
        snapshot_label="published",
        source_bundle_key="roleplay.situation_packs.ruleset",
        source_config_version_id="cfg-version-1" if with_snapshot else None,
        source_config_id="cfg-source-1" if with_snapshot else None,
        snapshot_selector="packs[code=first_visit]" if with_snapshot else None,
        source_snapshot_hash="sha256:snapshot-json" if with_snapshot else None,
        resolved_at="2026-05-27T10:00:00+00:00",
    )


def test_should_round_trip_published_asset_ref_through_schema() -> None:
    original = _sample_ref()

    schema = original.to_schema()
    restored = schema.to_dataclass()

    assert restored == original
    assert schema.model_dump() == {
        "asset_type": "situation_pack",
        "asset_id": None,
        "asset_code": "first_visit",
        "version": "v1",
        "content_hash": "sha256:pack-content",
        "snapshot_label": "published",
        "source_bundle_key": "roleplay.situation_packs.ruleset",
        "source_config_version_id": "cfg-version-1",
        "source_config_id": "cfg-source-1",
        "snapshot_selector": "packs[code=first_visit]",
        "source_snapshot_hash": "sha256:snapshot-json",
        "resolved_at": "2026-05-27T10:00:00+00:00",
    }


def test_should_round_trip_nested_refs_map_json_payload() -> None:
    refs = {
        "situation_pack_ref": _sample_ref().to_schema().model_dump(),
        "persona_ref": PublishedAssetRef(
            asset_type="persona",
            asset_id="persona-1",
            asset_code=None,
            version="3",
            content_hash="sha256:persona",
            snapshot_label="published",
            source_bundle_key=None,
            source_config_version_id=None,
            source_config_id=None,
            snapshot_selector=None,
            source_snapshot_hash=None,
            resolved_at="2026-05-27T10:00:00+00:00",
        ).to_schema().model_dump(),
    }

    restored = {
        key: PublishedAssetRefSchema.model_validate(payload).to_dataclass()
        for key, payload in refs.items()
    }

    assert restored["situation_pack_ref"] == _sample_ref()
    assert restored["persona_ref"].asset_type == "persona"
    assert restored["persona_ref"].asset_id == "persona-1"


@pytest.mark.parametrize(
    ("source_config_version_id", "snapshot_selector", "expected"),
    [
        ("cfg-version-1", "packs[code=first_visit]", True),
        (None, "packs[code=first_visit]", False),
        ("cfg-version-1", None, False),
        (None, None, False),
        ("", "packs[code=first_visit]", False),
        ("cfg-version-1", "", False),
    ],
)
def test_should_report_snapshot_reconstruction_eligibility(
    source_config_version_id: str | None,
    snapshot_selector: str | None,
    expected: bool,
) -> None:
    ref = PublishedAssetRef(
        asset_type="situation_pack",
        asset_id=None,
        asset_code="first_visit",
        version="v1",
        content_hash="sha256:pack-content",
        snapshot_label="published",
        source_bundle_key="roleplay.situation_packs.ruleset",
        source_config_version_id=source_config_version_id,
        source_config_id="cfg-source-1",
        snapshot_selector=snapshot_selector,
        source_snapshot_hash="sha256:snapshot-json",
        resolved_at="2026-05-27T10:00:00+00:00",
    )

    assert ref.can_reconstruct_from_snapshot() is expected


def test_should_preserve_dataclass_json_serializable_shape() -> None:
    payload = asdict(_sample_ref())

    round_tripped = PublishedAssetRefSchema.model_validate(payload).to_dataclass()

    assert round_tripped == _sample_ref()


def test_should_reject_config_bundle_ref_missing_governance_fields() -> None:
    payload = asdict(_sample_ref())
    payload["source_config_version_id"] = None

    with pytest.raises(ValidationError) as exc_info:
        PublishedAssetRefSchema.model_validate(payload)

    assert "source_config_version_id" in str(exc_info.value)


def test_should_reject_native_ref_with_partial_config_bundle_governance() -> None:
    payload = asdict(_sample_ref())
    payload["asset_type"] = "persona"
    payload["asset_id"] = "persona-1"
    payload["asset_code"] = None
    payload["source_bundle_key"] = None

    with pytest.raises(ValidationError) as exc_info:
        PublishedAssetRefSchema.model_validate(payload)

    assert "Native PublishedAssetRef cannot include partial" in str(exc_info.value)
