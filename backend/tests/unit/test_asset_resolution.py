from __future__ import annotations

from curriculum_practice.services.asset_resolution import (
    ASSET_RESOLUTION_DIRECT_PRACTICE_LIVE,
    ASSET_RESOLUTION_TEMPLATE_FROZEN_REFS,
    ASSET_RESOLUTION_TEMPLATE_LEGACY_LIVE,
    classify_template_asset_resolution,
    merge_curriculum_into_voice_policy_snapshot,
    resolve_session_asset_resolution,
    template_legacy_warnings,
)


def test_should_classify_frozen_template_when_published_asset_refs_present() -> None:
    refs = {
        "situation_pack_ref": {
            "asset_type": "situation_pack",
            "asset_code": "first_visit",
            "version": "v1",
            "content_hash": "sha256:pack",
            "snapshot_label": "published",
            "source_bundle_key": "roleplay.situation_packs.ruleset",
            "source_config_version_id": "cfg-1",
            "source_config_id": "cfg-source-1",
            "snapshot_selector": "packs[code=first_visit]",
            "source_snapshot_hash": "sha256:bundle-snapshot",
            "resolved_at": "2026-05-27T10:00:00+00:00",
        }
    }

    assert classify_template_asset_resolution(refs) == ASSET_RESOLUTION_TEMPLATE_FROZEN_REFS
    assert template_legacy_warnings(refs) == []


def test_should_classify_legacy_template_when_published_asset_refs_missing() -> None:
    assert classify_template_asset_resolution({}) == ASSET_RESOLUTION_TEMPLATE_LEGACY_LIVE
    assert classify_template_asset_resolution(None) == ASSET_RESOLUTION_TEMPLATE_LEGACY_LIVE
    assert len(template_legacy_warnings(None)) == 1


def test_should_resolve_direct_practice_live_without_template() -> None:
    resolution = resolve_session_asset_resolution(
        practice_template_id=None,
        published_asset_refs=None,
    )

    assert resolution["mode"] == ASSET_RESOLUTION_DIRECT_PRACTICE_LIVE
    assert resolution["entry"] == "platform_direct_practice"


def test_should_merge_curriculum_contract_into_voice_policy_snapshot() -> None:
    from types import SimpleNamespace

    session = SimpleNamespace(
        curriculum_snapshot={
            "roleplay_contract": {
                "schema_version": "roleplay_contract_v1",
                "contract_id": "sha256:contract-1",
            },
            "asset_resolution": {
                "mode": ASSET_RESOLUTION_TEMPLATE_FROZEN_REFS,
                "entry": "practice_template",
                "practice_template_id": "template-1",
            },
        },
        voice_policy_snapshot={
            "voice_mode": "stepfun_realtime",
            "roleplay_contract": {"contract_id": "sha256:stale"},
        },
        practice_template_id="template-1",
    )

    merge_curriculum_into_voice_policy_snapshot(session)

    assert session.voice_policy_snapshot["roleplay_contract"]["contract_id"] == (
        "sha256:contract-1"
    )
    assert session.voice_policy_snapshot["asset_resolution"]["mode"] == (
        ASSET_RESOLUTION_TEMPLATE_FROZEN_REFS
    )
    assert "config_asset_center" in session.voice_policy_snapshot["runtime_metrics"]
