"""Config Asset Center runtime resolution modes (Wave 3)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from curriculum_practice.models import PracticeTemplate
from curriculum_practice.schemas import PublishedAssetRefSchema
from curriculum_practice.services.frozen_asset_refs import parse_published_asset_refs

ASSET_RESOLUTION_DIRECT_PRACTICE_LIVE = "direct_practice_live"
ASSET_RESOLUTION_TEMPLATE_LEGACY_LIVE = "template_legacy_live"
ASSET_RESOLUTION_TEMPLATE_FROZEN_REFS = "template_frozen_refs"

_LEGACY_TEMPLATE_WARNING = (
    "PracticeTemplate has no publish-time published_asset_refs; "
    "runtime uses live asset lookup with legacy_unversioned labels."
)


def classify_template_asset_resolution(
    published_asset_refs: object | None,
) -> str:
    """Classify template-bound session resolution: frozen refs vs legacy live."""
    refs = parse_published_asset_refs(published_asset_refs)
    if refs:
        return ASSET_RESOLUTION_TEMPLATE_FROZEN_REFS
    return ASSET_RESOLUTION_TEMPLATE_LEGACY_LIVE


def template_legacy_warnings(
    published_asset_refs: object | None,
) -> list[str]:
    if classify_template_asset_resolution(published_asset_refs) == (
        ASSET_RESOLUTION_TEMPLATE_LEGACY_LIVE
    ):
        return [_LEGACY_TEMPLATE_WARNING]
    return []


def published_asset_refs_summary(
    published_asset_refs: object | None,
) -> dict[str, dict[str, Any]]:
    """Compact frozen-ref metadata for replay / report / support surfaces."""
    refs = parse_published_asset_refs(published_asset_refs)
    summary: dict[str, dict[str, Any]] = {}
    for key, ref in refs.items():
        summary[key] = _published_asset_ref_summary(ref)
    question_refs = _published_examiner_question_refs_summary(published_asset_refs)
    if question_refs:
        summary["examiner_question_refs"] = question_refs
    return summary


def _published_asset_ref_summary(ref: object) -> dict[str, Any]:
    return {
        "asset_type": ref.asset_type,
        "asset_id": ref.asset_id,
        "asset_code": ref.asset_code,
        "version": ref.version,
        "content_hash": ref.content_hash,
        "snapshot_label": ref.snapshot_label,
        "reconstructible_from_snapshot": ref.can_reconstruct_from_snapshot(),
        "source_bundle_key": ref.source_bundle_key,
        "source_config_version_id": ref.source_config_version_id,
        "snapshot_selector": ref.snapshot_selector,
        "logical_id": ref.logical_id,
        "revision_id": ref.revision_id,
        "revision_no": ref.revision_no,
    }


def _published_examiner_question_refs_summary(
    published_asset_refs: object | None,
) -> dict[str, dict[str, Any]]:
    if not isinstance(published_asset_refs, dict):
        return {}
    raw_question_refs = published_asset_refs.get("examiner_question_refs")
    if not isinstance(raw_question_refs, dict):
        return {}
    summary: dict[str, dict[str, Any]] = {}
    for question_id, payload in raw_question_refs.items():
        if not isinstance(payload, dict):
            continue
        ref = PublishedAssetRefSchema.model_validate(payload).to_dataclass()
        summary[str(question_id)] = _published_asset_ref_summary(ref)
    return summary


def build_asset_resolution_payload(
    *,
    mode: str,
    entry: str,
    practice_template_id: str | None = None,
    published_asset_refs: object | None = None,
    legacy_warnings: list[str] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "mode": mode,
        "entry": entry,
    }
    if practice_template_id:
        payload["practice_template_id"] = practice_template_id
    refs_summary = published_asset_refs_summary(published_asset_refs)
    if refs_summary:
        payload["published_asset_refs"] = refs_summary
    warnings = list(legacy_warnings or [])
    if warnings:
        payload["legacy_warnings"] = warnings
    return payload


def resolve_session_asset_resolution(
    *,
    practice_template_id: str | None,
    published_asset_refs: object | None,
    curriculum_snapshot: object | None = None,
) -> dict[str, Any]:
    """Resolve asset resolution for a persisted session."""
    if isinstance(curriculum_snapshot, dict):
        snapshot_resolution = curriculum_snapshot.get("asset_resolution")
        if isinstance(snapshot_resolution, dict) and snapshot_resolution.get("mode"):
            return deepcopy(snapshot_resolution)

    if practice_template_id:
        mode = classify_template_asset_resolution(published_asset_refs)
        return build_asset_resolution_payload(
            mode=mode,
            entry="practice_template",
            practice_template_id=practice_template_id,
            published_asset_refs=published_asset_refs,
            legacy_warnings=template_legacy_warnings(published_asset_refs),
        )

    return build_asset_resolution_payload(
        mode=ASSET_RESOLUTION_DIRECT_PRACTICE_LIVE,
        entry="platform_direct_practice",
    )


def build_config_asset_runtime_metadata(
    *,
    practice_template_id: str | None = None,
    published_asset_refs: object | None = None,
    curriculum_snapshot: object | None = None,
    voice_policy_snapshot: object | None = None,
) -> dict[str, Any]:
    """Metadata block for runtime_metrics.config_asset_center consumers."""
    asset_resolution = resolve_session_asset_resolution(
        practice_template_id=practice_template_id,
        published_asset_refs=published_asset_refs,
        curriculum_snapshot=curriculum_snapshot,
    )
    if isinstance(voice_policy_snapshot, dict):
        source = voice_policy_snapshot.get("source")
        if isinstance(source, dict) and source.get("legacy_direct_practice_fallback"):
            asset_resolution = {
                **asset_resolution,
                "legacy_direct_practice_fallback": True,
            }
    return {
        "asset_resolution": asset_resolution,
        "published_asset_refs": published_asset_refs_summary(published_asset_refs),
    }


def merge_curriculum_into_voice_policy_snapshot(
    session: object,
    *,
    template: PracticeTemplate | None = None,
) -> None:
    """After curriculum snapshot apply, align voice_policy with frozen contract."""
    curriculum_snapshot = getattr(session, "curriculum_snapshot", None)
    if not isinstance(curriculum_snapshot, dict):
        return

    voice_policy = getattr(session, "voice_policy_snapshot", None)
    merged = deepcopy(voice_policy) if isinstance(voice_policy, dict) else {}

    contract = curriculum_snapshot.get("roleplay_contract")
    if isinstance(contract, dict):
        merged["roleplay_contract"] = deepcopy(contract)

    template_id = (
        str(template.template_id)
        if template is not None
        else getattr(session, "practice_template_id", None)
    )
    published_refs = (
        dict(template.published_asset_refs or {})
        if template is not None
        else None
    )
    asset_resolution = resolve_session_asset_resolution(
        practice_template_id=str(template_id) if template_id else None,
        published_asset_refs=published_refs,
        curriculum_snapshot=curriculum_snapshot,
    )
    merged["asset_resolution"] = asset_resolution

    runtime_metrics = merged.get("runtime_metrics")
    if not isinstance(runtime_metrics, dict):
        runtime_metrics = {}
    else:
        runtime_metrics = dict(runtime_metrics)
    runtime_metrics["config_asset_center"] = build_config_asset_runtime_metadata(
        practice_template_id=str(template_id) if template_id else None,
        published_asset_refs=published_refs,
        curriculum_snapshot=curriculum_snapshot,
        voice_policy_snapshot=merged,
    )
    merged["runtime_metrics"] = runtime_metrics
    setattr(session, "voice_policy_snapshot", merged)
