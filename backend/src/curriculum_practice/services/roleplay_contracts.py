from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from inspect import isawaitable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from agent.models import Persona
from common.business_rules.defaults import (
    DEFAULT_ROLEPLAY_SITUATION_PACKS,
    ROLEPLAY_SITUATION_PACKS_KEY,
)
from common.business_rules.service import BusinessRuleConfigService
from curriculum_practice.models import CaseItem, PracticeTemplate
from curriculum_practice.schemas import (
    GateResult,
    PracticeTemplatePublishCandidate,
    PublishedAssetRef,
    ReferenceReader,
)
from curriculum_practice.services.asset_references import stable_hash
from curriculum_practice.services.asset_resolution import (
    build_config_asset_runtime_metadata,
    resolve_session_asset_resolution,
)
from curriculum_practice.services.roleplay.situation_pack_dto import SituationPackDTO
from curriculum_practice.services.roleplay.situation_pack_hasher import (
    situation_pack_content_hash,
)
from curriculum_practice.services.roleplay.situation_pack_reference_query import (
    SituationPackReferenceQuery,
)
from curriculum_practice.services.roleplay.situation_pack_repository import (
    SituationPackRepository,
)

ROLEPLAY_CONTRACT_SCHEMA_VERSION = "roleplay_contract_v1"
ROLEPLAY_CONTRACT_COMPILER_VERSION = "roleplay_contract_compiler_v1"
ROLEPLAY_STAGE_AUTHORITY = "SalesStageCapability"
LEGACY_ROLEPLAY_STATUS = "legacy_unstructured_roleplay"
GENERAL_PRACTICE_SITUATION = "general_practice"

ROLEPLAY_ALLOWED_VISIBLE_KEYS = {
    "industry",
    "company_profile",
    "customer_role",
    "pain_points",
    "objections",
    "success_criteria",
    "hidden_information",
    "budget",
    "decision_chain",
    "competitor_quote",
    "internal_floor_price",
    "renewal_risk",
    "compensation_boundary",
}

BLOCKING_VIOLATION_ACTIONS = {
    "cancel_or_regenerate_once",
    "regenerate_once",
    "cancel_stream",
    "hard_fail",
}

ROLEPLAY_DISCLOSURE_STATE_KEY = "roleplay_disclosure_state"
ROLEPLAY_COMPLIANCE_METRICS_KEY = "roleplay_compliance"


@dataclass(frozen=True, slots=True)
class RoleplayCompileFailure:
    gate_name: str
    reason_code: str
    message: str

    def as_gate_result(self) -> GateResult:
        return GateResult(
            gate_name=self.gate_name,
            status="failed",
            reason_code=self.reason_code,
            message=self.message,
        )


class RoleplayContractCompileError(ValueError):
    def __init__(self, failures: list[RoleplayCompileFailure]) -> None:
        self.failures = failures
        first = failures[0] if failures else None
        self.reason_code = first.reason_code if first else "roleplay_contract_compile"
        super().__init__(
            first.message if first else "Roleplay Contract compile failed."
        )

    @property
    def gate_results(self) -> list[GateResult]:
        return [failure.as_gate_result() for failure in self.failures]


class RoleplayContractCompiler:
    def __init__(
        self,
        reference_reader: ReferenceReader | None = None,
        *,
        situation_packs: SituationPackRepository | None = None,
    ) -> None:
        self._reference_reader = reference_reader
        self._situation_packs = (
            situation_packs or SituationPackRepository.from_defaults()
        )

    async def compile_from_template(
        self,
        template_id: str,
        actor_id: str,
        *,
        compiled_at: str | None = None,
    ) -> dict[str, Any]:
        template = await self._read_reference("practice_template", template_id)
        template_data = _as_dict(template)
        if not template_data:
            raise RoleplayContractCompileError(
                [
                    RoleplayCompileFailure(
                        gate_name="roleplay_contract_compile",
                        reason_code="template_missing",
                        message="PracticeTemplate is required to compile Roleplay Contract.",
                    )
                ]
            )
        return await self.compile_from_template_data(
            template_data,
            actor_id,
            compiled_at=compiled_at,
        )

    async def compile_from_template_candidate(
        self,
        candidate: PracticeTemplatePublishCandidate,
        actor_id: str,
        *,
        compiled_at: str | None = None,
    ) -> dict[str, Any]:
        template_data = candidate.model_dump()
        return await self.compile_from_template_data(
            template_data,
            actor_id,
            compiled_at=compiled_at,
        )

    async def compile_from_frozen_refs(
        self,
        template_data: dict[str, Any],
        published_asset_refs: dict[str, PublishedAssetRef],
        actor_id: str,
        *,
        compiled_at: str | None = None,
        frozen_situation_pack: SituationPackDTO | None = None,
    ) -> dict[str, Any]:
        return await self.compile_from_template_data(
            template_data,
            actor_id,
            compiled_at=compiled_at,
            published_asset_refs=published_asset_refs,
            frozen_situation_pack=frozen_situation_pack,
        )

    async def compile_from_template_data(
        self,
        template_data: dict[str, Any],
        actor_id: str,
        *,
        compiled_at: str | None = None,
        published_asset_refs: dict[str, PublishedAssetRef] | None = None,
        frozen_situation_pack: SituationPackDTO | None = None,
    ) -> dict[str, Any]:
        failures: list[RoleplayCompileFailure] = []
        mode = str(template_data.get("mode") or "")
        required = _template_roleplay_required(template_data)
        if mode != "customer_roleplay" and not required:
            return self._legacy_contract(
                source_track="curriculum_template",
                actor_id=actor_id,
                compiled_at=compiled_at,
                source_refs=_source_refs(template_data=template_data),
            )

        persona = await self._optional_ref("persona", template_data.get("persona_id"))
        case_item = await self._optional_ref(
            "case_item", template_data.get("case_item_id")
        )
        role_profile = await self._optional_ref(
            "role_profile",
            template_data.get("role_profile_id"),
        )
        ruleset = await self._optional_ref(
            "scoring_ruleset",
            template_data.get("scoring_ruleset_id"),
        )

        if required and not case_item:
            failures.append(
                RoleplayCompileFailure(
                    gate_name="roleplay_contract_compile",
                    reason_code="case_item_required",
                    message="customer_roleplay PracticeTemplate requires a published CaseItem for Roleplay Contract.",
                )
            )

        source_refs = _source_refs(
            template_data=template_data,
            persona=persona,
            case_item=case_item,
            role_profile=role_profile,
            ruleset=ruleset,
        )
        case_policy = _case_roleplay_policy(case_item)
        persona_defaults = _persona_roleplay_defaults(persona)
        situation_pack_ref = (
            published_asset_refs.get("situation_pack_ref")
            if published_asset_refs
            else None
        )
        situation_code = _first_non_blank(
            situation_pack_ref.asset_code if situation_pack_ref is not None else None,
            template_data.get("situation_pack_code"),
            _as_dict(_as_dict(template_data.get("timeout_config")).get("roleplay")).get(
                "situation_code"
            ),
            case_policy.get("situation_code"),
            persona_defaults.get("situation_code"),
            "first_visit" if required else GENERAL_PRACTICE_SITUATION,
        )
        pack_dto, pack_failures = _resolve_situation_pack_for_compile(
            situation_code=situation_code,
            situation_pack_ref=situation_pack_ref,
            frozen_situation_pack=frozen_situation_pack,
            situation_packs=self._situation_packs,
        )
        failures.extend(pack_failures)
        if pack_dto is not None:
            failures.extend(
                _validate_pack_compatibility(pack_dto.as_legacy_dict(), template_data)
            )

        if failures:
            raise RoleplayContractCompileError(failures)

        assert pack_dto is not None
        pack = pack_dto.as_legacy_dict()
        relationship_context = _relationship_context(
            pack=pack,
            persona_defaults=persona_defaults,
            case_policy=case_policy,
        )
        visible_scope = _visible_information_scope(pack=pack, case_policy=case_policy)
        failures.extend(
            _validate_contract_semantics(
                situation_code=situation_code,
                relationship_context=relationship_context,
                visible_scope=visible_scope,
            )
        )
        failures.extend(
            _validate_contract_version_alignment(
                persona=persona,
                case_policy=case_policy,
                ruleset=ruleset,
            )
        )
        failures.extend(
            _validate_persona_prompt_conflicts(
                situation_code=situation_code,
                persona=persona,
                forbidden_claim_patterns=_merged_patterns(pack, case_policy),
            )
        )
        if failures:
            raise RoleplayContractCompileError(failures)

        return _build_contract(
            source_track="curriculum_template",
            source_refs=source_refs,
            situation_pack=pack,
            relationship_context=relationship_context,
            visible_scope=visible_scope,
            forbidden_claim_patterns=_merged_patterns(pack, case_policy),
            forbidden_topic_codes=_merged_topic_codes(pack, case_policy),
            conflict_response_strategy=_first_non_blank(
                case_policy.get("conflict_response_strategy_override"),
                pack.get("default_conflict_response_strategy"),
                "neutral_clarification",
            ),
            behavior_rules_for_prompt_only=_prompt_only_behavior_rules(
                role_profile,
                pack,
            ),
            disclosure_policy=_disclosure_policy(pack=pack, case_item=case_item),
            runtime_violation_policy=_runtime_violation_policy(pack, case_policy),
            actor_id=actor_id,
            compiled_at=compiled_at,
        )

    async def compile_from_persona(
        self,
        persona: object | dict[str, Any] | str | None,
        optional_context: dict[str, Any] | None = None,
        actor_id: str | None = None,
        *,
        compiled_at: str | None = None,
    ) -> dict[str, Any]:
        if isinstance(persona, str):
            persona_data = _as_dict(await self._optional_ref("persona", persona))
        else:
            return self.compile_from_persona_sync(
                persona,
                optional_context=optional_context,
                actor_id=actor_id,
                compiled_at=compiled_at,
            )
        return self.compile_from_persona_sync(
            persona_data,
            optional_context=optional_context,
            actor_id=actor_id,
            compiled_at=compiled_at,
        )

    def compile_from_persona_sync(
        self,
        persona: object | dict[str, Any] | None,
        optional_context: dict[str, Any] | None = None,
        actor_id: str | None = None,
        *,
        compiled_at: str | None = None,
    ) -> dict[str, Any]:
        persona_data = _as_dict(persona)
        context = optional_context if isinstance(optional_context, dict) else {}
        persona_defaults = _persona_roleplay_defaults(persona_data)
        if not persona_defaults:
            return self.legacy_contract(
                source_track="direct_practice",
                actor_id=actor_id or "",
                compiled_at=compiled_at,
                source_refs=_source_refs(persona=persona_data),
            )
        situation_code = _first_non_blank(
            context.get("situation_code"),
            persona_defaults.get("situation_code"),
            GENERAL_PRACTICE_SITUATION,
        )
        pack_dto = self._situation_packs.get_published(situation_code)
        if pack_dto is None:
            raise RoleplayContractCompileError(
                [
                    RoleplayCompileFailure(
                        gate_name="situation_pack_compatibility",
                        reason_code="situation_pack_missing",
                        message=f"Roleplay Situation Pack {situation_code!r} is missing or not published.",
                    )
                ]
            )

        pack = pack_dto.as_legacy_dict()
        relationship_context = {
            **_relationship_context(pack=pack, persona_defaults=persona_defaults),
            **_as_dict(context.get("relationship_context")),
        }
        visible_scope = _visible_information_scope(
            pack=pack,
            case_policy={
                "visible_information_keys": persona_defaults.get(
                    "visible_information_keys"
                ),
                "hidden_information_keys": persona_defaults.get(
                    "hidden_information_keys"
                ),
            },
        )
        failures = _validate_contract_semantics(
            situation_code=situation_code,
            relationship_context=relationship_context,
            visible_scope=visible_scope,
        )
        failures.extend(
            _validate_persona_prompt_conflicts(
                situation_code=situation_code,
                persona=persona_data,
                forbidden_claim_patterns=_merged_patterns(
                    pack,
                    {
                        "forbidden_claim_patterns_override": persona_defaults.get(
                            "forbidden_claim_patterns"
                        )
                    },
                ),
            )
        )
        if failures:
            raise RoleplayContractCompileError(failures)

        return _build_contract(
            source_track="direct_practice",
            source_refs=_source_refs(persona=persona_data),
            situation_pack=pack,
            relationship_context=relationship_context,
            visible_scope=visible_scope,
            forbidden_claim_patterns=_merged_patterns(
                pack,
                {
                    "forbidden_claim_patterns_override": persona_defaults.get(
                        "forbidden_claim_patterns"
                    )
                },
            ),
            forbidden_topic_codes=_merged_topic_codes(pack, persona_defaults),
            conflict_response_strategy=_first_non_blank(
                persona_defaults.get("conflict_response_strategy"),
                pack.get("default_conflict_response_strategy"),
                "neutral_clarification",
            ),
            behavior_rules_for_prompt_only=_as_string_list(
                persona_defaults.get("prompt_only_behavior_rules")
            ),
            disclosure_policy=_as_dict(persona_defaults.get("disclosure_policy"))
            or _as_dict(pack.get("default_disclosure_policy")),
            runtime_violation_policy=_runtime_violation_policy(pack, persona_defaults),
            actor_id=actor_id or "",
            compiled_at=compiled_at,
        )

    def legacy_contract(
        self,
        *,
        source_track: str,
        actor_id: str,
        source_refs: list[dict[str, Any]] | None = None,
        compiled_at: str | None = None,
    ) -> dict[str, Any]:
        return self._legacy_contract(
            source_track=source_track,
            actor_id=actor_id,
            source_refs=source_refs,
            compiled_at=compiled_at,
        )

    async def validate_template_candidate(
        self,
        candidate: PracticeTemplatePublishCandidate,
        actor_id: str,
    ) -> list[GateResult]:
        if candidate.mode != "customer_roleplay" and not _template_roleplay_required(
            candidate.model_dump()
        ):
            return []
        try:
            await self.compile_from_template_candidate(candidate, actor_id)
            return []
        except RoleplayContractCompileError as exc:
            return exc.gate_results

    def render_runtime_instructions(
        self,
        contract: dict[str, Any],
        runtime_state: dict[str, Any] | None = None,
        visible_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        runtime_state = runtime_state if isinstance(runtime_state, dict) else {}
        visible_payload = visible_payload if isinstance(visible_payload, dict) else {}
        return {
            "roleplay_contract_hash": _audit_hash(contract),
            "situation_code": _situation_code(contract),
            "relationship_context": _as_dict(contract.get("relationship_context")),
            "visible_payload": visible_payload,
            "current_sales_stage": runtime_state.get("current_sales_stage"),
            "disclosed_keys": _as_string_list(runtime_state.get("disclosed_keys")),
        }

    def check_output(
        self,
        contract: dict[str, Any],
        runtime_state: dict[str, Any] | None,
        transcript_delta_or_final_text: str,
    ) -> dict[str, Any]:
        return check_roleplay_output(
            contract=contract,
            text=transcript_delta_or_final_text,
            runtime_state=runtime_state,
        )

    async def _optional_ref(self, asset_type: str, asset_id: object) -> dict[str, Any]:
        asset_id_text = str(asset_id or "").strip()
        if not asset_id_text or self._reference_reader is None:
            return {}
        return _as_dict(await self._read_reference(asset_type, asset_id_text))

    async def _read_reference(self, asset_type: str, asset_id: str) -> object | None:
        if self._reference_reader is None:
            return None
        reference = self._reference_reader(asset_type, asset_id)
        if isawaitable(reference):
            return await reference
        return reference

    def _legacy_contract(
        self,
        *,
        source_track: str,
        actor_id: str,
        source_refs: list[dict[str, Any]] | None = None,
        compiled_at: str | None = None,
    ) -> dict[str, Any]:
        pack_dto = self._situation_packs.get_published(GENERAL_PRACTICE_SITUATION)
        pack = pack_dto.as_legacy_dict() if pack_dto is not None else {}
        return _build_contract(
            source_track=source_track,
            source_refs=source_refs or [],
            situation_pack=pack
            or {
                "code": GENERAL_PRACTICE_SITUATION,
                "version": "legacy_default",
                "label": "通用对练",
                "default_relationship_context": {"prior_interactions": "unspecified"},
            },
            relationship_context={"prior_interactions": "unspecified"},
            visible_scope={
                "initial_visible_keys": [],
                "conditionally_visible_keys": [],
                "hidden_by_default_keys": [],
            },
            forbidden_claim_patterns=[],
            forbidden_topic_codes=[],
            conflict_response_strategy="neutral_clarification",
            behavior_rules_for_prompt_only=[],
            disclosure_policy={
                "default_hidden": True,
                "phases": [],
                "never_disclose_keys": [],
            },
            runtime_violation_policy={
                "relationship_history_contradiction": "mark_for_report",
                "hidden_information_leak": "mark_for_report",
                "forbidden_topic": "mark_for_report",
                "persona_style_drift": "mark_for_report",
            },
            actor_id=actor_id,
            compiled_at=compiled_at,
            legacy_status=LEGACY_ROLEPLAY_STATUS,
        )


def check_roleplay_output(
    *,
    contract: dict[str, Any],
    text: str,
    runtime_state: dict[str, Any] | None = None,
    current_visible_keys: list[str] | None = None,
    current_sales_stage: str | None = None,
) -> dict[str, Any]:
    normalized = str(text or "").strip()
    if not normalized:
        return _compliance_decision(allowed=True)
    if (
        not isinstance(contract, dict)
        or contract.get("schema_version") != ROLEPLAY_CONTRACT_SCHEMA_VERSION
    ):
        return _compliance_decision(
            allowed=True,
            severity="warning",
            violation_code="ROLEPLAY_CONTRACT_MISSING",
            action="mark_for_report",
            audit_payload={"reason": "missing_or_invalid_contract"},
        )
    if contract.get("legacy_status") == LEGACY_ROLEPLAY_STATUS:
        return _compliance_decision(
            allowed=True,
            severity="warning",
            violation_code="ROLEPLAY_CONTRACT_LEGACY",
            action="mark_for_report",
            audit_payload={"contract_hash": _audit_hash(contract)},
        )

    runtime_state = runtime_state if isinstance(runtime_state, dict) else {}
    relationship_context = _as_dict(contract.get("relationship_context"))
    visible_keys = set(
        current_visible_keys or _as_string_list(runtime_state.get("visible_keys"))
    )
    if not visible_keys:
        scope = _as_dict(contract.get("visible_information_scope"))
        visible_keys = set(_as_string_list(scope.get("initial_visible_keys")))
    hidden_keys = set(
        _as_string_list(
            _as_dict(contract.get("visible_information_scope")).get(
                "hidden_by_default_keys"
            )
        )
    )

    for pattern in _as_string_list(contract.get("forbidden_claim_patterns")):
        if pattern and pattern in normalized:
            violation_code = (
                "ROLEPLAY_HISTORY_CONTRADICTION"
                if relationship_context.get("has_prior_meeting") is False
                else "ROLEPLAY_FORBIDDEN_CLAIM"
            )
            return _blocking_decision(
                contract,
                violation_code=violation_code,
                matched_pattern=pattern,
                policy_key="relationship_history_contradiction",
            )

    hidden_patterns = _as_string_list(
        _as_dict(contract.get("disclosure_policy")).get("never_disclose_keys")
    )
    for hidden_key in hidden_keys:
        if hidden_key not in visible_keys and hidden_key and hidden_key in normalized:
            return _blocking_decision(
                contract,
                violation_code="ROLEPLAY_HIDDEN_INFORMATION_LEAK",
                matched_pattern=hidden_key,
                policy_key="hidden_information_leak",
            )
    for hidden_pattern in hidden_patterns:
        if hidden_pattern and hidden_pattern in normalized:
            return _blocking_decision(
                contract,
                violation_code="ROLEPLAY_HIDDEN_INFORMATION_LEAK",
                matched_pattern=hidden_pattern,
                policy_key="hidden_information_leak",
            )

    sales_stage = current_sales_stage or str(
        runtime_state.get("current_sales_stage") or ""
    )
    forbidden_stages = set(
        _as_string_list(
            _as_dict(contract.get("sales_stage_policy")).get("forbidden_stage_codes")
        )
    )
    if sales_stage and sales_stage in forbidden_stages:
        return _blocking_decision(
            contract,
            violation_code="ROLEPLAY_FORBIDDEN_STAGE",
            matched_pattern=sales_stage,
            policy_key="forbidden_topic",
        )

    return _compliance_decision(
        allowed=True,
        audit_payload={"contract_hash": _audit_hash(contract)},
    )


def initial_roleplay_disclosure_state(
    contract: object,
    *,
    now_iso: str | None = None,
) -> dict[str, Any]:
    """Build the persisted disclosure state for a frozen Roleplay Contract."""
    if (
        not isinstance(contract, dict)
        or contract.get("schema_version") != ROLEPLAY_CONTRACT_SCHEMA_VERSION
    ):
        return {
            "status": "missing",
            "visible_keys": [],
            "disclosed_keys": [],
            "pending_trigger_evidence": [],
            "events": [],
            "contract_hash": None,
            "situation_code": None,
            "last_updated_at": now_iso or datetime.now(UTC).isoformat(),
        }
    scope = _as_dict(contract.get("visible_information_scope"))
    visible_keys = _as_string_list(scope.get("initial_visible_keys"))
    status = (
        "legacy" if contract.get("legacy_status") == LEGACY_ROLEPLAY_STATUS else "ready"
    )
    return {
        "status": status,
        "visible_keys": visible_keys,
        "disclosed_keys": [],
        "disclosed_payload": {},
        "pending_trigger_evidence": [],
        "events": [],
        "contract_hash": _audit_hash(contract),
        "situation_code": _situation_code(contract),
        "last_updated_at": now_iso or datetime.now(UTC).isoformat(),
    }


def normalize_roleplay_disclosure_state(
    contract: object,
    state: object,
    *,
    now_iso: str | None = None,
) -> dict[str, Any]:
    """Restore a persisted disclosure state and keep it aligned with the contract."""
    if not isinstance(state, dict):
        return initial_roleplay_disclosure_state(contract, now_iso=now_iso)
    expected_hash = _audit_hash(contract) if isinstance(contract, dict) else None
    if expected_hash and state.get("contract_hash") not in {None, expected_hash}:
        return initial_roleplay_disclosure_state(contract, now_iso=now_iso)
    initial = initial_roleplay_disclosure_state(contract, now_iso=now_iso)
    visible_keys = list(
        dict.fromkeys(
            [
                *initial.get("visible_keys", []),
                *_as_string_list(state.get("visible_keys")),
            ]
        )
    )
    disclosed_keys = [
        key
        for key in _as_string_list(state.get("disclosed_keys"))
        if key in visible_keys
    ]
    disclosed_payload = _as_dict(state.get("disclosed_payload"))
    return {
        **initial,
        "status": str(state.get("status") or initial.get("status") or "ready"),
        "visible_keys": visible_keys,
        "disclosed_keys": disclosed_keys,
        "disclosed_payload": {
            key: str(value)
            for key, value in disclosed_payload.items()
            if key in disclosed_keys and str(value).strip()
        },
        "pending_trigger_evidence": _as_list_of_dicts(
            state.get("pending_trigger_evidence")
        )[-20:],
        "events": _as_list_of_dicts(state.get("events"))[-100:],
        "last_updated_at": str(
            state.get("last_updated_at")
            or initial.get("last_updated_at")
            or now_iso
            or datetime.now(UTC).isoformat()
        ),
    }


def resolve_roleplay_disclosure_state(
    *,
    contract: object,
    previous_state: object,
    learner_message: str,
    current_sales_stage: str | None = None,
    evidence: dict[str, Any] | None = None,
    turn_number: int | None = None,
    now_iso: str | None = None,
) -> dict[str, Any]:
    """Apply deterministic disclosure triggers from the frozen contract."""
    state = normalize_roleplay_disclosure_state(
        contract, previous_state, now_iso=now_iso
    )
    if not isinstance(contract, dict) or state.get("status") != "ready":
        return state

    text = str(learner_message or "").strip()
    stage = str(current_sales_stage or "").strip()
    if not text and not stage:
        return state

    visible_keys = set(_as_string_list(state.get("visible_keys")))
    disclosed_keys = set(_as_string_list(state.get("disclosed_keys")))
    disclosed_payload = _as_dict(state.get("disclosed_payload"))
    conditional_keys = set(
        _as_string_list(
            _as_dict(contract.get("visible_information_scope")).get(
                "conditionally_visible_keys"
            )
        )
    )
    hidden_keys = set(
        _as_string_list(
            _as_dict(contract.get("visible_information_scope")).get(
                "hidden_by_default_keys"
            )
        )
    )
    eligible_keys = conditional_keys | hidden_keys
    if not eligible_keys:
        return state

    fired_events: list[dict[str, Any]] = []
    for index, phase in enumerate(
        _as_list_of_dicts(_as_dict(contract.get("disclosure_policy")).get("phases"))
    ):
        if not _phase_matches(phase, learner_message=text, sales_stage=stage):
            continue
        keys = [
            key
            for key in _phase_disclosure_keys(phase)
            if key in eligible_keys and key not in disclosed_keys
        ]
        if not keys:
            inferred_key = _infer_disclosure_key(phase, text, eligible_keys)
            keys = (
                [inferred_key]
                if inferred_key and inferred_key not in disclosed_keys
                else []
            )
        if not keys:
            continue
        snippet = _phase_disclosure_text(phase)
        event = {
            "event_type": "disclosure_phase_matched",
            "phase_index": index,
            "trigger": str(phase.get("trigger") or ""),
            "matched_keys": keys,
            "sales_stage": stage or None,
            "turn_number": turn_number,
            "evidence": evidence if isinstance(evidence, dict) else {},
            "trace_id": (evidence or {}).get("trace_id")
            if isinstance(evidence, dict)
            else None,
            "created_at": now_iso or datetime.now(UTC).isoformat(),
        }
        for key in keys:
            visible_keys.add(key)
            disclosed_keys.add(key)
            if snippet:
                disclosed_payload[key] = snippet
        fired_events.append(event)

    if not fired_events:
        state["pending_trigger_evidence"] = [
            *_as_list_of_dicts(state.get("pending_trigger_evidence"))[-19:],
            {
                "turn_number": turn_number,
                "sales_stage": stage or None,
                "message_excerpt": text[:120],
                "created_at": now_iso or datetime.now(UTC).isoformat(),
            },
        ]
        state["last_updated_at"] = now_iso or datetime.now(UTC).isoformat()
        return state

    state["visible_keys"] = list(
        dict.fromkeys([*state.get("visible_keys", []), *sorted(visible_keys)])
    )
    state["disclosed_keys"] = list(
        dict.fromkeys([*state.get("disclosed_keys", []), *sorted(disclosed_keys)])
    )
    state["disclosed_payload"] = {
        key: str(disclosed_payload[key])
        for key in state["disclosed_keys"]
        if key in disclosed_payload and str(disclosed_payload[key]).strip()
    }
    state["events"] = [*_as_list_of_dicts(state.get("events")), *fired_events][-100:]
    state["pending_trigger_evidence"] = _as_list_of_dicts(
        state.get("pending_trigger_evidence")
    )[-20:]
    state["last_updated_at"] = now_iso or datetime.now(UTC).isoformat()
    return state


def build_roleplay_turn_context(
    *,
    contract: object,
    disclosure_state: object,
    visible_payload: dict[str, Any] | None = None,
    current_sales_stage: str | None = None,
) -> dict[str, Any]:
    state = normalize_roleplay_disclosure_state(contract, disclosure_state)
    return {
        "contract_hash": _audit_hash(contract) if isinstance(contract, dict) else None,
        "situation_code": _situation_code(contract)
        if isinstance(contract, dict)
        else None,
        "current_sales_stage": current_sales_stage,
        "visible_keys": _as_string_list(state.get("visible_keys")),
        "disclosed_keys": _as_string_list(state.get("disclosed_keys")),
        "visible_payload": visible_payload if isinstance(visible_payload, dict) else {},
        "disclosure_state_status": str(state.get("status") or "missing"),
    }


def roleplay_compliance_summary_from_session(
    *,
    curriculum_snapshot: object,
    voice_policy_snapshot: object,
    runtime_state: object,
) -> dict[str, Any]:
    contract = None
    if isinstance(curriculum_snapshot, dict):
        contract = curriculum_snapshot.get("roleplay_contract")
    if not isinstance(contract, dict) and isinstance(voice_policy_snapshot, dict):
        contract = voice_policy_snapshot.get("roleplay_contract")
    readiness = roleplay_readiness_from_contract(contract)
    runtime_metrics = (
        voice_policy_snapshot.get("runtime_metrics")
        if isinstance(voice_policy_snapshot, dict)
        else None
    )
    roleplay_metrics = (
        runtime_metrics.get("roleplay_compliance")
        if isinstance(runtime_metrics, dict)
        else None
    )
    if not isinstance(roleplay_metrics, dict):
        roleplay_metrics = {}
    disclosure_state = (
        runtime_state.get(ROLEPLAY_DISCLOSURE_STATE_KEY)
        if isinstance(runtime_state, dict)
        else None
    )
    if not isinstance(disclosure_state, dict):
        disclosure_state = initial_roleplay_disclosure_state(contract)
    template_id = None
    published_asset_refs = None
    if isinstance(curriculum_snapshot, dict):
        asset_resolution = curriculum_snapshot.get("asset_resolution")
        if isinstance(asset_resolution, dict):
            template_id = asset_resolution.get("practice_template_id")
            published_asset_refs = asset_resolution.get("published_asset_refs")
        practice_template = curriculum_snapshot.get("practice_template")
        if isinstance(practice_template, dict):
            template_id = template_id or practice_template.get("asset_id")
    config_asset_runtime = build_config_asset_runtime_metadata(
        practice_template_id=str(template_id) if template_id else None,
        published_asset_refs=published_asset_refs,
        curriculum_snapshot=curriculum_snapshot,
        voice_policy_snapshot=voice_policy_snapshot,
    )
    if not config_asset_runtime.get("published_asset_refs") and isinstance(
        voice_policy_snapshot, dict
    ):
        runtime_metrics = voice_policy_snapshot.get("runtime_metrics")
        if isinstance(runtime_metrics, dict):
            center = runtime_metrics.get("config_asset_center")
            if isinstance(center, dict) and center.get("published_asset_refs"):
                config_asset_runtime = center
    asset_resolution = resolve_session_asset_resolution(
        practice_template_id=str(template_id) if template_id else None,
        published_asset_refs=config_asset_runtime.get("published_asset_refs"),
        curriculum_snapshot=curriculum_snapshot,
    )
    return {
        **readiness,
        "asset_resolution": asset_resolution,
        "config_asset_runtime": config_asset_runtime,
        "violation_count": int(roleplay_metrics.get("violation_count") or 0),
        "blocking_violation_count": int(
            roleplay_metrics.get("blocking_violation_count") or 0
        ),
        "regenerate_count": int(roleplay_metrics.get("regenerate_count") or 0),
        "cancel_stream_count": int(roleplay_metrics.get("cancel_stream_count") or 0),
        "hidden_leak_prevented_count": int(
            roleplay_metrics.get("hidden_leak_prevented_count") or 0
        ),
        "last_decision": roleplay_metrics.get("last_decision"),
        "last_action_at": roleplay_metrics.get("last_action_at"),
        "timeline": _as_list_of_dicts(roleplay_metrics.get("timeline")),
        "disclosed_keys_count": len(
            _as_string_list(disclosure_state.get("disclosed_keys"))
        ),
        "visible_keys_count": len(
            _as_string_list(disclosure_state.get("visible_keys"))
        ),
        "disclosure_state_status": str(disclosure_state.get("status") or "missing"),
    }


def roleplay_compliance_timeline_from_session(
    *,
    voice_policy_snapshot: object,
    runtime_state: object,
    include_internal_details: bool = False,
) -> list[dict[str, Any]]:
    runtime_metrics = (
        voice_policy_snapshot.get("runtime_metrics")
        if isinstance(voice_policy_snapshot, dict)
        else None
    )
    roleplay_metrics = (
        runtime_metrics.get(ROLEPLAY_COMPLIANCE_METRICS_KEY)
        if isinstance(runtime_metrics, dict)
        else None
    )
    if not isinstance(roleplay_metrics, dict):
        roleplay_metrics = {}
    disclosure_state = (
        runtime_state.get(ROLEPLAY_DISCLOSURE_STATE_KEY)
        if isinstance(runtime_state, dict)
        else None
    )
    disclosure_events = (
        _as_list_of_dicts(disclosure_state.get("events"))
        if isinstance(disclosure_state, dict)
        else []
    )
    timeline: list[dict[str, Any]] = []
    for item in _as_list_of_dicts(roleplay_metrics.get("timeline")):
        decision = _as_dict(item.get("decision"))
        timeline_item = {
            "event_type": "compliance_decision",
            "turn_number": item.get("turn_number"),
            "response_id": item.get("response_id"),
            "action": item.get("action"),
            "violation_code": decision.get("violation_code"),
            "severity": decision.get("severity"),
            "sales_stage": item.get("sales_stage"),
            "visible_keys_count": len(_as_string_list(item.get("visible_keys"))),
            "disclosed_keys_count": len(_as_string_list(item.get("disclosed_keys"))),
            "created_at": item.get("created_at"),
            "trace_id": item.get("trace_id"),
        }
        if include_internal_details:
            timeline_item.update(
                {
                    "matched_pattern": decision.get("matched_pattern"),
                    "decision": decision,
                    "visible_keys": _as_string_list(item.get("visible_keys")),
                    "disclosed_keys": _as_string_list(item.get("disclosed_keys")),
                }
            )
        timeline.append(timeline_item)
    for event in disclosure_events:
        timeline_item = {
            "event_type": "disclosure",
            "turn_number": event.get("turn_number"),
            "response_id": None,
            "action": "disclose_keys",
            "violation_code": None,
            "severity": "info",
            "sales_stage": event.get("sales_stage"),
            "visible_keys_count": None,
            "disclosed_keys_count": len(_as_string_list(event.get("matched_keys"))),
            "created_at": event.get("created_at"),
            "trace_id": event.get("trace_id"),
        }
        if include_internal_details:
            timeline_item.update(
                {
                    "matched_pattern": event.get("trigger"),
                    "decision": None,
                    "visible_keys": [],
                    "disclosed_keys": _as_string_list(event.get("matched_keys")),
                    "evidence": _as_dict(event.get("evidence")),
                }
            )
        timeline.append(timeline_item)
    timeline.sort(
        key=lambda item: (
            str(item.get("created_at") or ""),
            int(item.get("turn_number") or 0),
        )
    )
    return timeline


def roleplay_readiness_from_contract(contract: object) -> dict[str, Any]:
    if not isinstance(contract, dict):
        return {
            "status": "missing",
            "schema_version": None,
            "contract_hash": None,
            "situation_code": None,
            "blocking_issues": ["roleplay_contract_missing"],
        }
    status = "ready"
    issues: list[str] = []
    if contract.get("legacy_status") == LEGACY_ROLEPLAY_STATUS:
        status = "legacy"
        issues.append("legacy_unstructured_roleplay")
    if contract.get("schema_version") != ROLEPLAY_CONTRACT_SCHEMA_VERSION:
        status = "invalid"
        issues.append("schema_version_invalid")
    return {
        "status": status,
        "schema_version": contract.get("schema_version"),
        "contract_hash": _audit_hash(contract),
        "situation_code": _situation_code(contract),
        "blocking_issues": issues,
    }


def visible_case_payload(
    case_item: object,
    contract: dict[str, Any] | None,
    *,
    disclosure_state: dict[str, Any] | None = None,
    visible_keys: list[str] | None = None,
) -> dict[str, Any]:
    payload = {
        "industry": getattr(case_item, "industry", None),
        "company_profile": getattr(case_item, "company_profile", None),
        "customer_role": getattr(case_item, "customer_role", None),
        "pain_points": list(getattr(case_item, "pain_points", None) or []),
        "objections": list(getattr(case_item, "objections", None) or []),
        "success_criteria": list(getattr(case_item, "success_criteria", None) or []),
    }
    if (
        not isinstance(contract, dict)
        or contract.get("legacy_status") == LEGACY_ROLEPLAY_STATUS
    ):
        return payload
    resolved_visible_keys = _as_string_list(visible_keys)
    if not resolved_visible_keys and isinstance(disclosure_state, dict):
        resolved_visible_keys = _as_string_list(disclosure_state.get("visible_keys"))
    if not resolved_visible_keys:
        resolved_visible_keys = _as_string_list(
            _as_dict(contract.get("visible_information_scope")).get(
                "initial_visible_keys"
            )
        )
    visible_set = set(resolved_visible_keys)
    visible_payload = {
        key: value for key, value in payload.items() if key in visible_set
    }

    disclosed_payload = (
        _as_dict(disclosure_state.get("disclosed_payload"))
        if isinstance(disclosure_state, dict)
        else {}
    )
    for key, value in disclosed_payload.items():
        if key in visible_set and str(value).strip():
            visible_payload[key] = str(value).strip()
    return visible_payload


class RoleplaySituationPackAdminService:
    """Admin read model for Roleplay Situation Pack governance."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def repository(self) -> SituationPackRepository:
        return await SituationPackRepository.from_database(self._db)

    async def list_packs(self) -> dict[str, Any]:
        repo = await self.repository()
        packs = repo.list_all()
        return {
            "items": [_pack_admin_payload(pack.as_legacy_dict()) for pack in packs],
            "total": len(packs),
            "config_key": ROLEPLAY_SITUATION_PACKS_KEY,
            "management": {
                "bundle_key": ROLEPLAY_SITUATION_PACKS_KEY,
                "read_path": "curriculum_practice.services.roleplay.situation_pack_repository.SituationPackRepository.from_database",
                "admin_entry": "/admin/curriculum-practice/roleplay-situation-packs",
                "publish_entry": f"/api/v1/admin/config-bundles/{ROLEPLAY_SITUATION_PACKS_KEY}/publish",
                "rollback_entry": f"/api/v1/admin/config-bundles/{ROLEPLAY_SITUATION_PACKS_KEY}/rollback",
            },
        }

    async def get_pack(self, code: str) -> dict[str, Any] | None:
        repo = await self.repository()
        pack = repo.get_any(code)
        if pack is None:
            return None
        payload = _pack_admin_payload(pack.as_legacy_dict())
        payload["references"] = await self.references_for(code)
        return payload

    async def resolve_published(self, code: str) -> dict[str, Any] | None:
        repo = await self.repository()
        pack = repo.get_published(code)
        if pack is None:
            return None
        resolution = await BusinessRuleConfigService(self._db).resolve_active_config(
            ROLEPLAY_SITUATION_PACKS_KEY,
            fallback_value=DEFAULT_ROLEPLAY_SITUATION_PACKS,
            fallback_source="bundled_roleplay_situation_packs",
        )
        ruleset = resolution.value if isinstance(resolution.value, dict) else {}
        return {
            "pack": pack.as_canonical_dict(),
            "metadata": {
                "config_key": ROLEPLAY_SITUATION_PACKS_KEY,
                "read_path": "curriculum_practice.services.roleplay.situation_pack_repository.SituationPackRepository.from_database",
                "ruleset_version": str(ruleset.get("version") or ""),
                "source": resolution.source,
                "config_id": resolution.config_id,
                "config_version": resolution.version,
                "resolved_at": datetime.now(UTC).isoformat(),
            },
        }

    async def pack_publish_state(self, code: str) -> str | None:
        repo = await self.repository()
        pack = repo.get_any(code)
        if pack is None:
            return None
        if repo.get_published(code) is not None:
            return "published"
        return str(pack.status or "draft")

    async def references_for(self, code: str) -> dict[str, Any]:
        return await SituationPackReferenceQuery(self._db).list_references(code)


def _resolve_situation_pack_for_compile(
    *,
    situation_code: str,
    situation_pack_ref: PublishedAssetRef | None,
    frozen_situation_pack: SituationPackDTO | None,
    situation_packs: SituationPackRepository,
) -> tuple[SituationPackDTO | None, list[RoleplayCompileFailure]]:
    failures: list[RoleplayCompileFailure] = []
    if frozen_situation_pack is not None:
        return frozen_situation_pack, failures

    if situation_pack_ref is not None:
        if situation_pack_ref.can_reconstruct_from_snapshot():
            failures.append(
                RoleplayCompileFailure(
                    gate_name="situation_pack_compatibility",
                    reason_code="snapshot_reconstruction_failed",
                    message=(
                        "Published SituationPack ref requires immutable snapshot "
                        "reconstruction before compile."
                    ),
                )
            )
            return None, failures
        resolved_code = _first_non_blank(
            situation_pack_ref.asset_code,
            situation_code,
        )
        pack_dto = situation_packs.get_published(resolved_code)
        if pack_dto is None:
            failures.append(
                RoleplayCompileFailure(
                    gate_name="situation_pack_compatibility",
                    reason_code="situation_pack_missing",
                    message=(
                        f"Roleplay Situation Pack {resolved_code!r} is missing or "
                        "not published."
                    ),
                )
            )
            return None, failures
        if situation_pack_content_hash(pack_dto) != situation_pack_ref.content_hash:
            failures.append(
                RoleplayCompileFailure(
                    gate_name="situation_pack_compatibility",
                    reason_code="asset_hash_mismatch",
                    message=(
                        "Published SituationPack ref hash does not match the current "
                        "published pack."
                    ),
                )
            )
            return None, failures
        return pack_dto, failures

    # Legacy templates without published_asset_refs still resolve from live repository.
    pack_dto = situation_packs.get_published(situation_code)
    if pack_dto is None:
        failures.append(
            RoleplayCompileFailure(
                gate_name="situation_pack_compatibility",
                reason_code="situation_pack_missing",
                message=(
                    f"Roleplay Situation Pack {situation_code!r} is missing or "
                    "not published."
                ),
            )
        )
    return pack_dto, failures


def _build_contract(
    *,
    source_track: str,
    source_refs: list[dict[str, Any]],
    situation_pack: dict[str, Any],
    relationship_context: dict[str, Any],
    visible_scope: dict[str, Any],
    forbidden_claim_patterns: list[str],
    forbidden_topic_codes: list[str],
    conflict_response_strategy: str,
    behavior_rules_for_prompt_only: list[str],
    disclosure_policy: dict[str, Any],
    runtime_violation_policy: dict[str, Any],
    actor_id: str,
    compiled_at: str | None,
    legacy_status: str | None = None,
) -> dict[str, Any]:
    audit_compiled_at = compiled_at or datetime.now(UTC).isoformat()
    contract: dict[str, Any] = {
        "schema_version": ROLEPLAY_CONTRACT_SCHEMA_VERSION,
        "contract_id": "sha256:pending",
        "source_track": source_track,
        "source_refs": source_refs,
        "situation": {
            "code": str(situation_pack.get("code") or GENERAL_PRACTICE_SITUATION),
            "version": str(situation_pack.get("version") or "v1"),
            "label": str(situation_pack.get("label") or "通用对练"),
        },
        "relationship_context": _normalized_relationship_context(relationship_context),
        "sales_stage_policy": {
            "stage_authority": ROLEPLAY_STAGE_AUTHORITY,
            "initial_stage_hint": str(
                situation_pack.get("initial_stage_hint") or "opening"
            ),
            "forbidden_stage_codes": _as_string_list(
                situation_pack.get("default_forbidden_stage_codes")
            ),
            "stage_transition_notes": _as_string_list(
                situation_pack.get("stage_transition_notes")
            ),
        },
        "visible_information_scope": visible_scope,
        "forbidden_claim_patterns": forbidden_claim_patterns,
        "forbidden_topic_codes": forbidden_topic_codes,
        "conflict_response_strategy": conflict_response_strategy,
        "behavior_rules_for_prompt_only": behavior_rules_for_prompt_only,
        "disclosure_policy": _normalized_disclosure_policy(disclosure_policy),
        "runtime_violation_policy": runtime_violation_policy,
        "audit": {
            "compiled_at": audit_compiled_at,
            "compiled_by": actor_id,
            "compiler_version": ROLEPLAY_CONTRACT_COMPILER_VERSION,
            "contract_hash": "sha256:pending",
        },
    }
    if legacy_status:
        contract["legacy_status"] = legacy_status
    contract_hash = stable_hash(contract)
    contract["contract_id"] = contract_hash
    contract["audit"]["contract_hash"] = contract_hash
    return contract


def _pack_admin_payload(pack: dict[str, Any]) -> dict[str, Any]:
    return {
        "code": pack.get("code"),
        "label": pack.get("label"),
        "version": pack.get("version"),
        "status": pack.get("status"),
        "initial_stage_hint": pack.get("initial_stage_hint"),
        "relationship_context_defaults": _as_dict(
            pack.get("default_relationship_context")
        ),
        "default_visible_information_scope": _as_dict(
            pack.get("default_visible_information_scope")
        ),
        "default_forbidden_claim_patterns": _as_string_list(
            pack.get("default_forbidden_claim_patterns")
        ),
        "default_forbidden_topic_codes": _as_string_list(
            pack.get("default_forbidden_topic_codes")
        ),
        "default_forbidden_stage_codes": _as_string_list(
            pack.get("default_forbidden_stage_codes")
        ),
        "stage_transition_notes": _as_string_list(pack.get("stage_transition_notes")),
        "default_conflict_response_strategy": pack.get(
            "default_conflict_response_strategy"
        ),
        "default_behavior_rules_for_prompt_only": _as_string_list(
            pack.get("default_behavior_rules_for_prompt_only")
        ),
        "default_runtime_violation_policy": _as_dict(
            pack.get("default_runtime_violation_policy")
        ),
        "default_disclosure_policy": _as_dict(pack.get("default_disclosure_policy")),
        "compatible_practice_modes": _as_string_list(
            pack.get("compatible_practice_modes")
        ),
        "compatible_scenario_types": _as_string_list(
            pack.get("compatible_scenario_types")
        ),
        "audit": _as_dict(pack.get("audit")),
    }


def _template_situation_code(timeout_config: dict[str, Any]) -> str | None:
    roleplay = _as_dict(timeout_config.get("roleplay"))
    return _none_if_blank(roleplay.get("situation_code"))


def _case_situation_code(allowed_disclosure_policy: dict[str, Any]) -> str | None:
    return _none_if_blank(
        _as_dict(allowed_disclosure_policy.get("roleplay")).get("situation_code")
    )


def _persona_situation_code(persona_policy: dict[str, Any]) -> str | None:
    return _none_if_blank(
        _as_dict(persona_policy.get("roleplay_defaults")).get("situation_code")
    )


def _template_reference_payload(template: PracticeTemplate) -> dict[str, Any]:
    return {
        "asset_type": "practice_template",
        "asset_id": str(template.template_id),
        "name": template.name,
        "status": template.status,
        "version": template.version,
        "content_hash": template.content_hash,
    }


def _case_item_reference_payload(case_item: CaseItem) -> dict[str, Any]:
    return {
        "asset_type": "case_item",
        "asset_id": str(case_item.case_item_id),
        "label": f"{case_item.industry} / {case_item.customer_role}",
        "status": case_item.status,
        "version": case_item.version,
        "content_hash": case_item.content_hash,
    }


def _persona_reference_payload(persona: Persona) -> dict[str, Any]:
    return {
        "asset_type": "persona",
        "asset_id": str(persona.id),
        "name": persona.name,
        "status": persona.status,
        "category": persona.category,
    }


def _validate_pack_compatibility(
    pack: dict[str, Any],
    template_data: dict[str, Any],
) -> list[RoleplayCompileFailure]:
    failures: list[RoleplayCompileFailure] = []
    scenario_type = str(template_data.get("scenario_type") or "")
    mode = str(template_data.get("mode") or "")
    compatible_scenarios = set(_as_string_list(pack.get("compatible_scenario_types")))
    compatible_modes = set(_as_string_list(pack.get("compatible_practice_modes")))
    if compatible_scenarios and scenario_type not in compatible_scenarios:
        failures.append(
            RoleplayCompileFailure(
                gate_name="situation_pack_compatibility",
                reason_code="scenario_type_incompatible",
                message=f"Situation Pack {pack.get('code')} does not support scenario_type={scenario_type}.",
            )
        )
    if compatible_modes and mode not in compatible_modes:
        failures.append(
            RoleplayCompileFailure(
                gate_name="situation_pack_compatibility",
                reason_code="practice_mode_incompatible",
                message=f"Situation Pack {pack.get('code')} does not support mode={mode}.",
            )
        )
    return failures


def _validate_contract_semantics(
    *,
    situation_code: str,
    relationship_context: dict[str, Any],
    visible_scope: dict[str, Any],
) -> list[RoleplayCompileFailure]:
    failures: list[RoleplayCompileFailure] = []
    initial_keys = set(_as_string_list(visible_scope.get("initial_visible_keys")))
    hidden_keys = set(_as_string_list(visible_scope.get("hidden_by_default_keys")))
    unknown_keys = sorted((initial_keys | hidden_keys) - ROLEPLAY_ALLOWED_VISIBLE_KEYS)
    if unknown_keys:
        failures.append(
            RoleplayCompileFailure(
                gate_name="hidden_information_visibility",
                reason_code="visible_information_key_unknown",
                message=f"Roleplay visible/hidden scope contains unknown keys: {', '.join(unknown_keys)}.",
            )
        )
    overlap = sorted(initial_keys & hidden_keys)
    if overlap:
        failures.append(
            RoleplayCompileFailure(
                gate_name="hidden_information_visibility",
                reason_code="hidden_key_initially_visible",
                message=f"Roleplay hidden keys cannot be initially visible: {', '.join(overlap)}.",
            )
        )
    meeting_summary = relationship_context.get("meeting_history_summary")
    if situation_code == "first_visit":
        if relationship_context.get("has_prior_meeting") is True:
            failures.append(
                RoleplayCompileFailure(
                    gate_name="relationship_context_consistency",
                    reason_code="first_visit_has_prior_meeting",
                    message="first_visit cannot set has_prior_meeting=true.",
                )
            )
        if isinstance(meeting_summary, str) and meeting_summary.strip():
            failures.append(
                RoleplayCompileFailure(
                    gate_name="relationship_context_consistency",
                    reason_code="first_visit_has_meeting_history_summary",
                    message="first_visit cannot include meeting_history_summary.",
                )
            )
    if situation_code == "follow_up" and not (
        isinstance(meeting_summary, str) and meeting_summary.strip()
    ):
        failures.append(
            RoleplayCompileFailure(
                gate_name="relationship_context_consistency",
                reason_code="follow_up_missing_meeting_history_summary",
                message="follow_up requires meeting_history_summary or a traceable prior interaction summary.",
            )
        )
    prior_interactions = str(relationship_context.get("prior_interactions") or "")
    if (
        prior_interactions == "none"
        and isinstance(meeting_summary, str)
        and meeting_summary.strip()
    ):
        failures.append(
            RoleplayCompileFailure(
                gate_name="relationship_context_consistency",
                reason_code="meeting_history_summary_requires_prior_interaction",
                message="meeting_history_summary is only allowed when prior_interactions is not none.",
            )
        )
    return failures


def _validate_contract_version_alignment(
    *,
    persona: dict[str, Any],
    case_policy: dict[str, Any],
    ruleset: dict[str, Any],
) -> list[RoleplayCompileFailure]:
    versions = {
        "persona": _none_if_blank(
            _as_dict(persona.get("persona_policy")).get("roleplay_contract_version")
        ),
        "case_item": _none_if_blank(case_policy.get("roleplay_contract_version")),
        "scoring_ruleset": _none_if_blank(
            _as_dict(ruleset.get("definition_json")).get("roleplay_contract_version")
        ),
    }
    present = {key: value for key, value in versions.items() if value}
    if len(set(present.values())) <= 1:
        return []
    return [
        RoleplayCompileFailure(
            gate_name="roleplay_contract_version_alignment",
            reason_code="roleplay_contract_version_mismatch",
            message=f"Roleplay contract versions must align across assets: {present}.",
        )
    ]


def _validate_persona_prompt_conflicts(
    *,
    situation_code: str,
    persona: dict[str, Any],
    forbidden_claim_patterns: list[str],
) -> list[RoleplayCompileFailure]:
    prompt = _persona_prompt(persona)
    if situation_code != "first_visit" or not prompt:
        return []
    for pattern in forbidden_claim_patterns:
        if pattern and pattern in prompt:
            return [
                RoleplayCompileFailure(
                    gate_name="persona_roleprofile_conflict",
                    reason_code="persona_prompt_relationship_conflict",
                    message=f"Persona prompt contains first_visit forbidden relationship pattern: {pattern}.",
                )
            ]
    return []


def _case_roleplay_policy(case_item: dict[str, Any]) -> dict[str, Any]:
    policy = _as_dict(case_item.get("allowed_disclosure_policy"))
    roleplay = _as_dict(policy.get("roleplay"))
    if (
        "roleplay_contract_version" in policy
        and "roleplay_contract_version" not in roleplay
    ):
        roleplay["roleplay_contract_version"] = policy.get("roleplay_contract_version")
    return roleplay


def _persona_roleplay_defaults(persona: dict[str, Any]) -> dict[str, Any]:
    persona_policy = _as_dict(persona.get("persona_policy"))
    defaults = _as_dict(persona_policy.get("roleplay_defaults"))
    if (
        "roleplay_contract_version" in persona_policy
        and "roleplay_contract_version" not in defaults
    ):
        defaults["roleplay_contract_version"] = persona_policy.get(
            "roleplay_contract_version"
        )
    return defaults


def _relationship_context(
    *,
    pack: dict[str, Any],
    persona_defaults: dict[str, Any] | None = None,
    case_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    relationship = dict(_as_dict(pack.get("default_relationship_context")))
    persona_context = _as_dict((persona_defaults or {}).get("relationship_context"))
    case_context = _as_dict((case_policy or {}).get("relationship_context_override"))
    relationship.update(persona_context)
    relationship.update(case_context)
    return relationship


def _normalized_relationship_context(raw: dict[str, Any]) -> dict[str, Any]:
    prior = str(raw.get("prior_interactions") or "unspecified")
    if prior not in {
        "none",
        "one_meeting",
        "multiple_meetings",
        "existing_customer",
        "unspecified",
    }:
        prior = "unspecified"
    meeting_summary = raw.get("meeting_history_summary")
    if not isinstance(meeting_summary, str) or not meeting_summary.strip():
        meeting_summary = None
    return {
        "prior_interactions": prior,
        "has_prior_meeting": _optional_bool(raw.get("has_prior_meeting")),
        "has_seen_proposal": _optional_bool(raw.get("has_seen_proposal")),
        "has_discussed_budget": _optional_bool(raw.get("has_discussed_budget")),
        "has_existing_partnership": _optional_bool(raw.get("has_existing_partnership")),
        "meeting_history_summary": meeting_summary,
    }


def _visible_information_scope(
    *,
    pack: dict[str, Any],
    case_policy: dict[str, Any],
) -> dict[str, Any]:
    defaults = _as_dict(pack.get("default_visible_information_scope"))
    initial = _as_string_list(defaults.get("initial_visible_keys"))
    conditional = _as_string_list(defaults.get("conditionally_visible_keys"))
    hidden = _as_string_list(defaults.get("hidden_by_default_keys"))
    override_initial = _as_string_list(case_policy.get("visible_information_keys"))
    override_hidden = _as_string_list(case_policy.get("hidden_information_keys"))
    if override_initial:
        initial = override_initial
    if override_hidden:
        hidden = override_hidden
    conditional = sorted(set(conditional) | (set(hidden) - set(initial)))
    return {
        "initial_visible_keys": list(dict.fromkeys(initial)),
        "conditionally_visible_keys": list(dict.fromkeys(conditional)),
        "hidden_by_default_keys": list(dict.fromkeys(hidden)),
    }


def _merged_patterns(pack: dict[str, Any], policy: dict[str, Any]) -> list[str]:
    values = _as_string_list(pack.get("default_forbidden_claim_patterns"))
    values.extend(_as_string_list(policy.get("forbidden_claim_patterns_override")))
    values.extend(_as_string_list(policy.get("forbidden_claim_patterns")))
    return list(dict.fromkeys(item for item in values if item))


def _merged_topic_codes(pack: dict[str, Any], policy: dict[str, Any]) -> list[str]:
    values = _as_string_list(pack.get("default_forbidden_topic_codes"))
    values.extend(_as_string_list(policy.get("forbidden_topic_codes_override")))
    values.extend(_as_string_list(policy.get("forbidden_topic_codes")))
    return list(dict.fromkeys(item for item in values if item))


def _prompt_only_behavior_rules(
    role_profile: dict[str, Any],
    pack: dict[str, Any],
) -> list[str]:
    values = _as_string_list(pack.get("default_behavior_rules_for_prompt_only"))
    values.extend(_as_string_list(role_profile.get("behavior_rules")))
    return list(dict.fromkeys(item for item in values if item))


def _disclosure_policy(
    *,
    pack: dict[str, Any],
    case_item: dict[str, Any],
) -> dict[str, Any]:
    policy = _as_dict(case_item.get("allowed_disclosure_policy"))
    disclosure = {
        **_as_dict(pack.get("default_disclosure_policy")),
        **{
            "phases": policy.get("phases", []),
            "never_disclose_keys": _as_string_list(policy.get("never_disclose"))
            or _as_string_list(policy.get("never_disclose_keys")),
        },
    }
    return _normalized_disclosure_policy(disclosure)


def _normalized_disclosure_policy(policy: dict[str, Any]) -> dict[str, Any]:
    return {
        "default_hidden": True,
        "phases": policy.get("phases")
        if isinstance(policy.get("phases"), list)
        else [],
        "never_disclose_keys": _as_string_list(policy.get("never_disclose_keys")),
    }


def _runtime_violation_policy(
    pack: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    base = dict(_as_dict(pack.get("default_runtime_violation_policy")))
    override = _as_dict(policy.get("runtime_violation_policy"))
    base.update(override)
    base.setdefault("relationship_history_contradiction", "cancel_or_regenerate_once")
    base.setdefault("hidden_information_leak", "cancel_or_regenerate_once")
    base.setdefault("forbidden_topic", "mark_and_continue")
    base.setdefault("persona_style_drift", "mark_for_report")
    return base


def _template_roleplay_required(template_data: dict[str, Any]) -> bool:
    roleplay = _as_dict(_as_dict(template_data.get("timeout_config")).get("roleplay"))
    default_required = str(template_data.get("mode") or "") == "customer_roleplay"
    raw = roleplay.get(
        "required",
        roleplay.get("roleplay_contract_required", default_required),
    )
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        return raw.strip().lower() not in {"false", "0", "no", "off"}
    return True


def _source_refs(
    *,
    template_data: dict[str, Any] | None = None,
    persona: dict[str, Any] | None = None,
    case_item: dict[str, Any] | None = None,
    role_profile: dict[str, Any] | None = None,
    ruleset: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    if template_data:
        refs.append(_source_ref("practice_template", template_data))
    if persona:
        refs.append(_source_ref("persona", persona))
    if case_item:
        refs.append(_source_ref("case_item", case_item))
    if role_profile:
        refs.append(_source_ref("role_profile", role_profile))
    if ruleset:
        refs.append(_source_ref("scoring_ruleset", ruleset))
    return [ref for ref in refs if ref.get("asset_id")]


def _source_ref(asset_type: str, data: dict[str, Any]) -> dict[str, Any]:
    id_keys = {
        "practice_template": "template_id",
        "persona": "id",
        "case_item": "case_item_id",
        "role_profile": "role_profile_id",
        "scoring_ruleset": "ruleset_id",
    }
    asset_id = data.get(id_keys.get(asset_type, "id"))
    return {
        "asset_type": asset_type,
        "asset_id": str(asset_id or ""),
        "version": data.get("version"),
        "hash": data.get("content_hash") or stable_hash(data),
        "status": data.get("status"),
    }


def _compliance_decision(
    *,
    allowed: bool,
    severity: str = "none",
    violation_code: str | None = None,
    matched_pattern: str | None = None,
    action: str = "allow",
    audit_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "allowed": allowed,
        "severity": severity,
        "violation_code": violation_code,
        "matched_pattern": matched_pattern,
        "action": action,
        "audit_payload": audit_payload or {},
    }


def _blocking_decision(
    contract: dict[str, Any],
    *,
    violation_code: str,
    matched_pattern: str,
    policy_key: str,
) -> dict[str, Any]:
    policy = _as_dict(contract.get("runtime_violation_policy"))
    configured_action = str(policy.get(policy_key) or "mark_for_report")
    action = "mark_for_report"
    severity = "warning"
    allowed = True
    if configured_action in BLOCKING_VIOLATION_ACTIONS:
        action = (
            "regenerate_once" if "regenerate" in configured_action else "cancel_stream"
        )
        severity = "blocking"
        allowed = False
    elif configured_action == "mark_and_continue":
        action = "mark_for_report"
        severity = "warning"
    return _compliance_decision(
        allowed=allowed,
        severity=severity,
        violation_code=violation_code,
        matched_pattern=matched_pattern,
        action=action,
        audit_payload={
            "contract_hash": _audit_hash(contract),
            "policy_key": policy_key,
            "configured_action": configured_action,
        },
    )


def _situation_code(contract: dict[str, Any]) -> str | None:
    situation = contract.get("situation")
    if not isinstance(situation, dict):
        return None
    code = situation.get("code")
    return str(code) if code else None


def _audit_hash(contract: dict[str, Any]) -> str | None:
    audit = contract.get("audit")
    if isinstance(audit, dict) and audit.get("contract_hash"):
        return str(audit["contract_hash"])
    contract_id = contract.get("contract_id")
    return str(contract_id) if contract_id else None


def _persona_prompt(persona: dict[str, Any]) -> str:
    persona_policy = _as_dict(persona.get("persona_policy"))
    return str(
        persona_policy.get("system_prompt") or persona.get("system_prompt") or ""
    )


def _optional_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "on"}:
            return True
        if lowered in {"false", "0", "no", "off"}:
            return False
    return None


def _as_list_of_dicts(value: object | None) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _phase_disclosure_keys(phase: dict[str, Any]) -> list[str]:
    raw = (
        phase.get("disclose_keys")
        or phase.get("visible_keys")
        or phase.get("keys")
        or phase.get("disclose_key")
    )
    values = _as_string_list(raw)
    if values:
        return values
    disclose = phase.get("disclose")
    if isinstance(disclose, dict):
        return _as_string_list(disclose.get("keys") or disclose.get("key"))
    return []


def _phase_disclosure_text(phase: dict[str, Any]) -> str:
    disclose = phase.get("disclose")
    if isinstance(disclose, str) and disclose.strip():
        return disclose.strip()
    if isinstance(disclose, dict):
        text = (
            disclose.get("text") or disclose.get("content") or disclose.get("summary")
        )
        if isinstance(text, str) and text.strip():
            return text.strip()
    return ""


def _phase_matches(
    phase: dict[str, Any],
    *,
    learner_message: str,
    sales_stage: str,
) -> bool:
    message = learner_message.strip()
    keywords = _as_string_list(phase.get("keywords") or phase.get("keyword_match"))
    if keywords and any(keyword in message for keyword in keywords):
        return True
    trigger = str(phase.get("trigger") or "").strip()
    if trigger and trigger in message:
        return True
    stage_reached = str(
        phase.get("stage_reached") or phase.get("sales_stage") or ""
    ).strip()
    if stage_reached and sales_stage and stage_reached == sales_stage:
        return True
    question_category = str(phase.get("question_category") or "").strip()
    if question_category and _message_matches_question_category(
        message,
        question_category,
    ):
        return True
    return False


def _message_matches_question_category(message: str, category: str) -> bool:
    if not message:
        return False
    category_keywords = {
        "budget": ["预算", "ROI", "投入", "费用", "采购", "价格"],
        "decision_chain": ["谁负责", "决策", "审批", "拍板", "参与人"],
        "competitor": ["竞品", "替代", "对比", "供应商"],
        "integration": ["集成", "接口", "ERP", "MES", "CRM", "OA"],
        "success_criteria": ["成功", "指标", "验收", "衡量", "效果"],
    }
    keywords = category_keywords.get(category, [category])
    return any(keyword in message for keyword in keywords)


def _infer_disclosure_key(
    phase: dict[str, Any],
    learner_message: str,
    eligible_keys: set[str],
) -> str | None:
    text = " ".join(
        [
            learner_message,
            str(phase.get("trigger") or ""),
            " ".join(_as_string_list(phase.get("keywords"))),
            _phase_disclosure_text(phase),
        ]
    )
    key_keywords = {
        "budget": ["预算", "ROI", "投入", "采购", "费用", "价格"],
        "decision_chain": ["决策", "审批", "谁负责", "拍板", "参与人"],
        "competitor_quote": ["竞品", "报价", "替代"],
        "internal_floor_price": ["底价", "最低价", "价格"],
        "renewal_risk": ["续约", "风险", "满意"],
        "compensation_boundary": ["赔偿", "退款", "补偿"],
        "success_criteria": ["成功", "指标", "验收", "效果"],
        "hidden_information": ["隐藏", "内部", "更多", "细节"],
    }
    for key, keywords in key_keywords.items():
        if key in eligible_keys and any(keyword in text for keyword in keywords):
            return key
    return "hidden_information" if "hidden_information" in eligible_keys else None


def _as_dict(value: object | None) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump()
        return dumped if isinstance(dumped, dict) else {}
    instance_dict = getattr(value, "__dict__", None)
    if isinstance(instance_dict, dict):
        return {
            key: item for key, item in instance_dict.items() if not key.startswith("_")
        }
    return {
        key: getattr(value, key)
        for key in dir(value)
        if not key.startswith("_") and not callable(getattr(value, key))
    }


def _as_string_list(value: object) -> list[str]:
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _first_non_blank(*values: object) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _none_if_blank(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None
