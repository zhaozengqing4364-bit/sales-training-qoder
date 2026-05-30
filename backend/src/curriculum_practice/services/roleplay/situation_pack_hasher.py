from __future__ import annotations

from curriculum_practice.services.asset_references import stable_hash
from curriculum_practice.services.roleplay.situation_pack_dto import SituationPackDTO


def situation_pack_content_hash(dto: SituationPackDTO) -> str:
    """Hash canonical domain fields for Phase A vs B1 reconciliation."""
    return stable_hash(_domain_payload(dto))


def _domain_payload(dto: SituationPackDTO) -> dict[str, object]:
    payload: dict[str, object] = {
        "relationship_context": dto.relationship_context,
        "visible_information_scope": dto.visible_information_scope,
        "forbidden_claim_patterns": dto.forbidden_claim_patterns,
        "forbidden_topic_codes": dto.forbidden_topic_codes,
        "forbidden_stage_codes": dto.forbidden_stage_codes,
        "conflict_response_strategy": dto.conflict_response_strategy,
        "behavior_rules_for_prompt_only": dto.behavior_rules_for_prompt_only,
        "disclosure_policy": dto.disclosure_policy,
        "runtime_violation_policy": dto.runtime_violation_policy,
        "compatible_practice_modes": dto.compatible_practice_modes,
        "compatible_scenario_types": dto.compatible_scenario_types,
    }
    if dto.initial_stage_hint is not None:
        payload["initial_stage_hint"] = dto.initial_stage_hint
    if dto.stage_transition_notes:
        payload["stage_transition_notes"] = list(dto.stage_transition_notes)
    return payload
