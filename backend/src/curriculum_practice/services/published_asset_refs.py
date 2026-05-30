from __future__ import annotations

from datetime import UTC, datetime
from inspect import isawaitable
from typing import Any

from common.business_rules.defaults import ROLEPLAY_SITUATION_PACKS_KEY
from common.business_rules.service import BusinessRuleResolution
from curriculum_practice.schemas import (
    PracticeTemplatePublishCandidate,
    PublishedAssetRef,
    ReferenceReader,
)
from curriculum_practice.services.asset_references import (
    PUBLISHED_SNAPSHOT_LABEL,
    stable_hash,
)
from curriculum_practice.services.roleplay.situation_pack_dto import SituationPackDTO
from curriculum_practice.services.roleplay.situation_pack_hasher import (
    situation_pack_content_hash,
)
from curriculum_practice.services.roleplay.situation_pack_repository import (
    SituationPackRepository,
)
from curriculum_practice.services.roleplay_contracts import (
    GENERAL_PRACTICE_SITUATION,
    _as_dict,
    _case_roleplay_policy,
    _first_non_blank,
    _persona_roleplay_defaults,
    _template_roleplay_required,
)

_ASSET_ID_KEYS: dict[str, str] = {
    "persona": "id",
    "case_item": "case_item_id",
    "role_profile": "role_profile_id",
    "learning_content": "learning_content_id",
    "scoring_ruleset": "ruleset_id",
    "examiner_agent": "examiner_agent_id",
}

_REF_KEYS: dict[str, str] = {
    "persona": "persona_ref",
    "case_item": "case_item_ref",
    "role_profile": "role_profile_ref",
    "learning_content": "learning_content_ref",
    "scoring_ruleset": "scoring_ruleset_ref",
    "examiner_agent": "examiner_agent_ref",
    "situation_pack": "situation_pack_ref",
}


class PublishedAssetRefBuildError(ValueError):
    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


async def build_published_asset_refs(
    candidate: PracticeTemplatePublishCandidate,
    *,
    reference_reader: ReferenceReader,
    situation_packs: SituationPackRepository,
    situation_pack_config: BusinessRuleResolution | None = None,
    resolved_at: str | None = None,
) -> dict[str, dict[str, Any]]:
    """Freeze publish-time asset pointers after publish gates pass."""
    resolved_at_value = resolved_at or datetime.now(UTC).isoformat()
    refs: dict[str, PublishedAssetRef] = {}

    persona = await _require_reference(reference_reader, "persona", candidate.persona_id)
    refs["persona_ref"] = _entity_published_ref(
        "persona",
        persona,
        resolved_at=resolved_at_value,
    )

    ruleset = await _require_reference(
        reference_reader,
        "scoring_ruleset",
        candidate.scoring_ruleset_id,
    )
    refs["scoring_ruleset_ref"] = _entity_published_ref(
        "scoring_ruleset",
        ruleset,
        resolved_at=resolved_at_value,
    )

    optional_refs = (
        ("case_item", candidate.case_item_id),
        ("role_profile", candidate.role_profile_id),
        ("learning_content", candidate.learning_content_id),
        ("examiner_agent", candidate.examiner_agent_id),
    )
    for asset_type, asset_id in optional_refs:
        if not asset_id:
            continue
        reference = await _require_reference(reference_reader, asset_type, asset_id)
        ref_key = _REF_KEYS[asset_type]
        refs[ref_key] = _entity_published_ref(
            asset_type,
            reference,
            resolved_at=resolved_at_value,
        )

    situation_code = await resolve_template_situation_pack_code(
        candidate,
        reference_reader=reference_reader,
    )
    pack = situation_packs.get_published(situation_code)
    if pack is None:
        raise PublishedAssetRefBuildError(
            "situation_pack_missing",
            f"Roleplay Situation Pack {situation_code!r} is missing or not published.",
        )
    refs["situation_pack_ref"] = _situation_pack_published_ref(
        pack,
        config=situation_pack_config,
        resolved_at=resolved_at_value,
    )

    return {
        key: ref.to_schema().model_dump()
        for key, ref in refs.items()
    }


async def resolve_template_situation_pack_code(
    candidate: PracticeTemplatePublishCandidate,
    *,
    reference_reader: ReferenceReader,
) -> str:
    template_data = candidate.model_dump()
    required = _template_roleplay_required(template_data)
    persona = await _optional_reference(reference_reader, "persona", candidate.persona_id)
    case_item = await _optional_reference(
        reference_reader,
        "case_item",
        candidate.case_item_id,
    )
    case_policy = _case_roleplay_policy(case_item)
    persona_defaults = _persona_roleplay_defaults(persona)
    roleplay = _as_dict(_as_dict(template_data.get("timeout_config")).get("roleplay"))
    explicit_code = _first_non_blank(
        template_data.get("situation_pack_code"),
        roleplay.get("situation_code"),
    )
    if explicit_code:
        return explicit_code
    return _first_non_blank(
        case_policy.get("situation_code"),
        persona_defaults.get("situation_code"),
        "first_visit" if required else GENERAL_PRACTICE_SITUATION,
    )


def _entity_published_ref(
    asset_type: str,
    reference: dict[str, Any],
    *,
    resolved_at: str,
) -> PublishedAssetRef:
    asset_id_key = _ASSET_ID_KEYS[asset_type]
    asset_id = str(reference[asset_id_key])
    version = str(reference.get("version", "1"))
    if asset_type in {"persona", "scoring_ruleset"}:
        content_hash = stable_hash(reference)
    else:
        content_hash = str(reference.get("content_hash") or stable_hash(reference))
    return PublishedAssetRef(
        asset_type=asset_type,
        asset_id=asset_id,
        asset_code=None,
        version=version,
        content_hash=content_hash,
        snapshot_label=PUBLISHED_SNAPSHOT_LABEL,
        source_bundle_key=None,
        source_config_version_id=None,
        source_config_id=None,
        snapshot_selector=None,
        source_snapshot_hash=None,
        resolved_at=resolved_at,
    )


def _situation_pack_published_ref(
    pack: SituationPackDTO,
    *,
    config: BusinessRuleResolution | None,
    resolved_at: str,
) -> PublishedAssetRef:
    code = pack.code
    config_id = config.config_id if config is not None else None
    config_version_id = config.config_version_id if config is not None else None
    source_snapshot_hash = (
        stable_hash(config.value) if config is not None and config.value else None
    )
    if not config_id or not config_version_id or not source_snapshot_hash:
        raise PublishedAssetRefBuildError(
            "situation_pack_config_version_missing",
            "Published SituationPack refs require source_config_id, "
            "source_config_version_id, and source_snapshot_hash.",
        )
    return PublishedAssetRef(
        asset_type="situation_pack",
        asset_id=None,
        asset_code=code,
        version=str(pack.version),
        content_hash=situation_pack_content_hash(pack),
        snapshot_label=PUBLISHED_SNAPSHOT_LABEL,
        source_bundle_key=ROLEPLAY_SITUATION_PACKS_KEY,
        source_config_version_id=config_version_id,
        source_config_id=config_id,
        snapshot_selector=f"packs[code={code}]",
        source_snapshot_hash=source_snapshot_hash,
        resolved_at=resolved_at,
    )


async def _require_reference(
    reference_reader: ReferenceReader,
    asset_type: str,
    asset_id: str,
) -> dict[str, Any]:
    reference = await _read_reference(reference_reader, asset_type, asset_id)
    if not reference:
        raise PublishedAssetRefBuildError(
            "reference_missing",
            f"{asset_type} reference {asset_id} does not exist or is not published.",
        )
    return reference


async def _optional_reference(
    reference_reader: ReferenceReader,
    asset_type: str,
    asset_id: str | None,
) -> dict[str, Any]:
    asset_id_text = str(asset_id or "").strip()
    if not asset_id_text:
        return {}
    return _as_dict(await _read_reference(reference_reader, asset_type, asset_id_text))


async def _read_reference(
    reference_reader: ReferenceReader,
    asset_type: str,
    asset_id: str,
) -> dict[str, Any] | None:
    reference = reference_reader(asset_type, asset_id)
    if isawaitable(reference):
        reference = await reference
    if reference is None:
        return None
    return _as_dict(reference)
