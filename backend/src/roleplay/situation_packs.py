"""Neutral immutable Situation Pack contract and canonical hash."""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from json import dumps
from typing import Any, Protocol

from roleplay.defaults import DEFAULT_ROLEPLAY_SITUATION_PACKS

_VOLATILE_HASH_FIELDS = {
    "actor_id",
    "created_at",
    "compiled_at",
    "compiled_by",
    "published_at",
    "snapshot_hash",
    "trace_id",
    "updated_at",
}


def _as_dict(value: object | None) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {}


def _as_string_list(value: object) -> list[str]:
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


@dataclass(frozen=True, slots=True)
class SituationPackSnapshot:
    """Canonical Situation Pack shape shared by config and entity adapters."""

    code: str
    label: str
    version: str
    status: str
    relationship_context: dict[str, Any]
    visible_information_scope: dict[str, Any]
    forbidden_claim_patterns: list[str]
    forbidden_topic_codes: list[str]
    forbidden_stage_codes: list[str]
    conflict_response_strategy: str
    behavior_rules_for_prompt_only: list[str]
    disclosure_policy: dict[str, Any]
    runtime_violation_policy: dict[str, Any]
    compatible_practice_modes: list[str]
    compatible_scenario_types: list[str]
    initial_stage_hint: str | None = None
    stage_transition_notes: tuple[str, ...] = field(default_factory=tuple)
    audit: dict[str, Any] | None = None

    @classmethod
    def from_ruleset_entry(
        cls, entry: dict[str, Any]
    ) -> SituationPackSnapshot:
        return cls(
            code=str(entry.get("code") or "").strip(),
            label=str(entry.get("label") or ""),
            version=str(entry.get("version") or "v1"),
            status=str(entry.get("status") or "draft"),
            relationship_context=_as_dict(entry.get("default_relationship_context")),
            visible_information_scope=_as_dict(
                entry.get("default_visible_information_scope")
            ),
            forbidden_claim_patterns=_as_string_list(
                entry.get("default_forbidden_claim_patterns")
            ),
            forbidden_topic_codes=_as_string_list(
                entry.get("default_forbidden_topic_codes")
            ),
            forbidden_stage_codes=_as_string_list(
                entry.get("default_forbidden_stage_codes")
            ),
            conflict_response_strategy=str(
                entry.get("default_conflict_response_strategy")
                or "neutral_clarification"
            ),
            behavior_rules_for_prompt_only=_as_string_list(
                entry.get("default_behavior_rules_for_prompt_only")
            ),
            disclosure_policy=_as_dict(entry.get("default_disclosure_policy")),
            runtime_violation_policy=_as_dict(
                entry.get("default_runtime_violation_policy")
            ),
            compatible_practice_modes=_as_string_list(
                entry.get("compatible_practice_modes")
            ),
            compatible_scenario_types=_as_string_list(
                entry.get("compatible_scenario_types")
            ),
            initial_stage_hint=_optional_text(entry.get("initial_stage_hint")),
            stage_transition_notes=tuple(
                _as_string_list(entry.get("stage_transition_notes"))
            ),
            audit=_as_dict(entry.get("audit")) or None,
        )

    @classmethod
    def from_entity(cls, row: Any) -> SituationPackSnapshot:
        return cls(
            code=str(getattr(row, "code", "") or "").strip(),
            label=str(getattr(row, "label", "") or ""),
            version=str(getattr(row, "version", "v1") or "v1"),
            status=str(getattr(row, "status", "draft") or "draft"),
            relationship_context=_as_dict(getattr(row, "relationship_context", None)),
            visible_information_scope=_as_dict(
                getattr(row, "visible_information_scope", None)
            ),
            forbidden_claim_patterns=_as_string_list(
                getattr(row, "forbidden_claim_patterns", None)
            ),
            forbidden_topic_codes=_as_string_list(
                getattr(row, "forbidden_topic_codes", None)
            ),
            forbidden_stage_codes=_as_string_list(
                getattr(row, "forbidden_stage_codes", None)
            ),
            conflict_response_strategy=str(
                getattr(row, "conflict_response_strategy", None)
                or "neutral_clarification"
            ),
            behavior_rules_for_prompt_only=_as_string_list(
                getattr(row, "behavior_rules_for_prompt_only", None)
            ),
            disclosure_policy=_as_dict(getattr(row, "disclosure_policy", None)),
            runtime_violation_policy=_as_dict(
                getattr(row, "runtime_violation_policy", None)
            ),
            compatible_practice_modes=_as_string_list(
                getattr(row, "compatible_practice_modes", None)
            ),
            compatible_scenario_types=_as_string_list(
                getattr(row, "compatible_scenario_types", None)
            ),
        )

    def as_canonical_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "code": self.code,
            "label": self.label,
            "version": self.version,
            "status": self.status,
            "relationship_context": dict(self.relationship_context),
            "visible_information_scope": dict(self.visible_information_scope),
            "forbidden_claim_patterns": list(self.forbidden_claim_patterns),
            "forbidden_topic_codes": list(self.forbidden_topic_codes),
            "forbidden_stage_codes": list(self.forbidden_stage_codes),
            "conflict_response_strategy": self.conflict_response_strategy,
            "behavior_rules_for_prompt_only": list(
                self.behavior_rules_for_prompt_only
            ),
            "disclosure_policy": dict(self.disclosure_policy),
            "runtime_violation_policy": dict(self.runtime_violation_policy),
            "compatible_practice_modes": list(self.compatible_practice_modes),
            "compatible_scenario_types": list(self.compatible_scenario_types),
        }
        if self.initial_stage_hint:
            payload["initial_stage_hint"] = self.initial_stage_hint
        if self.stage_transition_notes:
            payload["stage_transition_notes"] = list(self.stage_transition_notes)
        if self.audit:
            payload["audit"] = dict(self.audit)
        return payload

    def as_legacy_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "code": self.code,
            "label": self.label,
            "version": self.version,
            "status": self.status,
            "default_relationship_context": dict(self.relationship_context),
            "default_visible_information_scope": dict(self.visible_information_scope),
            "default_forbidden_claim_patterns": list(self.forbidden_claim_patterns),
            "default_forbidden_topic_codes": list(self.forbidden_topic_codes),
            "default_forbidden_stage_codes": list(self.forbidden_stage_codes),
            "default_conflict_response_strategy": self.conflict_response_strategy,
            "default_behavior_rules_for_prompt_only": list(
                self.behavior_rules_for_prompt_only
            ),
            "default_disclosure_policy": dict(self.disclosure_policy),
            "default_runtime_violation_policy": dict(self.runtime_violation_policy),
            "compatible_practice_modes": list(self.compatible_practice_modes),
            "compatible_scenario_types": list(self.compatible_scenario_types),
        }
        if self.initial_stage_hint:
            payload["initial_stage_hint"] = self.initial_stage_hint
        if self.stage_transition_notes:
            payload["stage_transition_notes"] = list(self.stage_transition_notes)
        if self.audit:
            payload["audit"] = dict(self.audit)
        return payload


class SituationPackPort(Protocol):
    def get_published(self, code: str) -> SituationPackSnapshot | None: ...


class BundledSituationPackSource:
    """In-memory source for versioned defaults when no governed adapter is supplied."""

    def __init__(self, ruleset: dict[str, Any] | None = None) -> None:
        payload = ruleset or DEFAULT_ROLEPLAY_SITUATION_PACKS
        self._published = {
            snapshot.code: snapshot
            for item in payload.get("packs", [])
            if isinstance(item, dict)
            and (snapshot := SituationPackSnapshot.from_ruleset_entry(item)).status
            == "published"
        }

    def get_published(self, code: str) -> SituationPackSnapshot | None:
        return self._published.get(str(code or "").strip())

    def list_published(self) -> list[SituationPackSnapshot]:
        return [self._published[code] for code in sorted(self._published)]


def situation_pack_content_hash(snapshot: SituationPackSnapshot) -> str:
    return _stable_hash(_domain_payload(snapshot))


def _domain_payload(snapshot: SituationPackSnapshot) -> dict[str, object]:
    payload: dict[str, object] = {
        "relationship_context": snapshot.relationship_context,
        "visible_information_scope": snapshot.visible_information_scope,
        "forbidden_claim_patterns": snapshot.forbidden_claim_patterns,
        "forbidden_topic_codes": snapshot.forbidden_topic_codes,
        "forbidden_stage_codes": snapshot.forbidden_stage_codes,
        "conflict_response_strategy": snapshot.conflict_response_strategy,
        "behavior_rules_for_prompt_only": snapshot.behavior_rules_for_prompt_only,
        "disclosure_policy": snapshot.disclosure_policy,
        "runtime_violation_policy": snapshot.runtime_violation_policy,
        "compatible_practice_modes": snapshot.compatible_practice_modes,
        "compatible_scenario_types": snapshot.compatible_scenario_types,
    }
    if snapshot.initial_stage_hint is not None:
        payload["initial_stage_hint"] = snapshot.initial_stage_hint
    if snapshot.stage_transition_notes:
        payload["stage_transition_notes"] = list(snapshot.stage_transition_notes)
    return payload


def _stable_hash(payload: object) -> str:
    return (
        "sha256:"
        + sha256(
            dumps(
                _without_volatile_fields(payload),
                sort_keys=True,
                ensure_ascii=False,
                separators=(",", ":"),
                default=str,
            ).encode("utf-8")
        ).hexdigest()
    )


def _without_volatile_fields(payload: object) -> object:
    if isinstance(payload, dict):
        return {
            key: _without_volatile_fields(value)
            for key, value in payload.items()
            if key not in _VOLATILE_HASH_FIELDS
        }
    if isinstance(payload, list):
        return [_without_volatile_fields(item) for item in payload]
    return payload


def _optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None
