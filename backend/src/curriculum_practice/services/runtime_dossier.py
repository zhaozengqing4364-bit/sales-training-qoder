from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from curriculum_practice.models import CaseItem, RoleProfile
from curriculum_practice.services.asset_references import stable_hash
from roleplay.compiler import (
    roleplay_readiness_from_contract,
    visible_case_payload,
)
from roleplay.contracts import LEGACY_ROLEPLAY_STATUS

CURRICULUM_RUNTIME_SNAPSHOT_STALE = "CURRICULUM_RUNTIME_SNAPSHOT_STALE"


class CurriculumRuntimeDossierError(ValueError):
    def __init__(
        self,
        code: str = CURRICULUM_RUNTIME_SNAPSHOT_STALE,
        *,
        missing: list[str] | None = None,
        message: str | None = None,
    ) -> None:
        super().__init__(message or code)
        self.code = code
        self.missing = missing or []


@dataclass(slots=True)
class CurriculumRuntimeDossier:
    case_items: list[dict[str, Any]] = field(default_factory=list)
    role_profiles: list[dict[str, Any]] = field(default_factory=list)
    asset_refs: list[dict[str, Any]] = field(default_factory=list)
    roleplay_contract: dict[str, Any] | None = None
    roleplay_disclosure_state: dict[str, Any] | None = None
    dossier_hash: str = ""

    @property
    def has_prompt_context(self) -> bool:
        return bool(self.case_items or self.role_profiles)

    def instruction_section(self) -> str:
        if not self.has_prompt_context:
            return ""

        sections = ["【课程运行资料】", "以下资料来自会话创建时冻结的课程快照，只用于本次对练角色扮演。"]
        roleplay_section = _roleplay_contract_section(self.roleplay_contract)
        if roleplay_section:
            sections.extend(["", roleplay_section])
        for case_item in self.case_items:
            case_lines = _case_instruction_lines(case_item)
            if case_lines:
                sections.extend(["", "【业务剧本】", *case_lines])

        for role_profile in self.role_profiles:
            sections.extend(
                [
                    "",
                    "【客户画像】",
                    f"- 角色类型：{_text(role_profile.get('role_type'))}",
                    f"- 角色名称：{_text(role_profile.get('role_name'))}",
                    f"- 沟通风格：{_text(role_profile.get('communication_style'))}",
                    f"- 压力等级：{_text(role_profile.get('pressure_level'))}",
                    f"- 知识边界：{_join(role_profile.get('knowledge_boundary'))}",
                    f"- 行为规则：{_join(role_profile.get('behavior_rules'))}",
                    f"- 声音风格提示：{_text(role_profile.get('voice_style_hint'))}",
                ]
            )
            persona_ref = _text(role_profile.get("persona_ref"))
            if persona_ref:
                sections.append(f"- Persona 引用：{persona_ref}")

        return "\n".join(line for line in sections if line is not None).strip()

    def runtime_metrics(self) -> dict[str, Any]:
        return {
            "dossier_hash": self.dossier_hash,
            "asset_refs": list(self.asset_refs),
            "case_item_count": len(self.case_items),
            "role_profile_count": len(self.role_profiles),
            "roleplay_contract": roleplay_readiness_from_contract(
                self.roleplay_contract
            ),
            "roleplay_disclosure_state": {
                "status": (
                    self.roleplay_disclosure_state.get("status")
                    if isinstance(self.roleplay_disclosure_state, dict)
                    else "missing"
                ),
                "visible_keys_count": len(
                    self.roleplay_disclosure_state.get("visible_keys", [])
                    if isinstance(self.roleplay_disclosure_state, dict)
                    and isinstance(self.roleplay_disclosure_state.get("visible_keys"), list)
                    else []
                ),
                "disclosed_keys_count": len(
                    self.roleplay_disclosure_state.get("disclosed_keys", [])
                    if isinstance(self.roleplay_disclosure_state, dict)
                    and isinstance(self.roleplay_disclosure_state.get("disclosed_keys"), list)
                    else []
                ),
            },
        }


class CurriculumRuntimeDossierHydrator:
    """Hydrate prompt-safe curriculum dossier from frozen snapshot references."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def hydrate(
        self,
        curriculum_snapshot: object,
        *,
        roleplay_disclosure_state: dict[str, Any] | None = None,
    ) -> CurriculumRuntimeDossier:
        if not isinstance(curriculum_snapshot, dict):
            return CurriculumRuntimeDossier(dossier_hash=stable_hash({}))
        refs = curriculum_snapshot.get("content_assets")
        if not isinstance(refs, list):
            return CurriculumRuntimeDossier(dossier_hash=stable_hash({}))

        case_items: list[dict[str, Any]] = []
        role_profiles: list[dict[str, Any]] = []
        asset_refs: list[dict[str, Any]] = []
        roleplay_contract = curriculum_snapshot.get("roleplay_contract")
        if not isinstance(roleplay_contract, dict):
            roleplay_contract = None

        for ref in _asset_refs(refs, "case_item"):
            case_item = await self._load_case_item(ref)
            case_items.append(
                _case_prompt_payload(
                    case_item,
                    roleplay_contract,
                    roleplay_disclosure_state=roleplay_disclosure_state,
                )
            )
            asset_refs.append(_runtime_ref(ref))

        for ref in _asset_refs(refs, "role_profile"):
            role_profile = await self._load_role_profile(ref)
            role_profiles.append(_role_prompt_payload(role_profile))
            asset_refs.append(_runtime_ref(ref))

        dossier_payload = {
            "case_items": case_items,
            "role_profiles": role_profiles,
            "asset_refs": asset_refs,
            "roleplay_contract": roleplay_contract,
            "roleplay_disclosure_state": roleplay_disclosure_state,
        }
        return CurriculumRuntimeDossier(
            case_items=case_items,
            role_profiles=role_profiles,
            asset_refs=asset_refs,
            roleplay_contract=roleplay_contract,
            roleplay_disclosure_state=roleplay_disclosure_state,
            dossier_hash=stable_hash(dossier_payload),
        )

    async def _load_case_item(self, ref: dict[str, Any]) -> CaseItem:
        asset_id = _asset_id(ref)
        case_item = await self._db.get(CaseItem, asset_id)
        if (
            case_item is None
            or getattr(case_item, "status", None) != "published"
            or not _asset_matches_ref(case_item, ref)
        ):
            raise CurriculumRuntimeDossierError(
                missing=[f"case_item:{asset_id}"],
                message="Frozen CaseItem reference is missing, unpublished, or stale.",
            )
        return case_item

    async def _load_role_profile(self, ref: dict[str, Any]) -> RoleProfile:
        asset_id = _asset_id(ref)
        role_profile = await self._db.get(RoleProfile, asset_id)
        if (
            role_profile is None
            or getattr(role_profile, "status", None) != "published"
            or not _asset_matches_ref(role_profile, ref)
        ):
            raise CurriculumRuntimeDossierError(
                missing=[f"role_profile:{asset_id}"],
                message="Frozen RoleProfile reference is missing, unpublished, or stale.",
            )
        return role_profile


def compose_curriculum_runtime_instructions(
    base_instructions: str,
    dossier: CurriculumRuntimeDossier,
) -> str:
    base = str(base_instructions or "").strip()
    section = dossier.instruction_section()
    if not section:
        return base
    if not base:
        return section
    return f"{base}\n\n{section}"


def _asset_refs(refs: list[object], asset_type: str) -> list[dict[str, Any]]:
    return [
        ref
        for ref in refs
        if isinstance(ref, dict)
        and ref.get("asset_type") == asset_type
        and isinstance(ref.get("asset_id"), str)
    ]


def _asset_id(ref: dict[str, Any]) -> str:
    return str(ref.get("asset_id") or "").strip()


def _asset_matches_ref(asset: object, ref: dict[str, Any]) -> bool:
    return str(getattr(asset, "content_hash", "")) == str(
        ref.get("hash")
    ) and _int(getattr(asset, "version", 0)) == _int(ref.get("version"))


def _int(value: object) -> int:
    if not isinstance(value, int | str):
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _runtime_ref(ref: dict[str, Any]) -> dict[str, Any]:
    return {
        "asset_type": str(ref.get("asset_type") or ""),
        "asset_id": _asset_id(ref),
        "version": ref.get("version"),
        "hash": str(ref.get("hash") or ""),
        "snapshot_label": str(ref.get("snapshot_label") or ""),
    }


def _case_prompt_payload(
    case_item: CaseItem,
    roleplay_contract: dict[str, Any] | None,
    *,
    roleplay_disclosure_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return visible_case_payload(
        case_item,
        roleplay_contract,
        disclosure_state=roleplay_disclosure_state,
    )


def _role_prompt_payload(role_profile: RoleProfile) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "role_type": role_profile.role_type,
        "role_name": role_profile.role_name,
        "communication_style": role_profile.communication_style,
        "pressure_level": role_profile.pressure_level,
        "knowledge_boundary": list(role_profile.knowledge_boundary or []),
        "behavior_rules": list(role_profile.behavior_rules or []),
        "voice_style_hint": role_profile.voice_style_hint,
    }
    if role_profile.persona_ref:
        payload["persona_ref"] = role_profile.persona_ref
    return payload


def _text(value: object) -> str:
    return str(value or "").strip()


def _join(value: object) -> str:
    if isinstance(value, list):
        return "；".join(str(item).strip() for item in value if str(item).strip())
    return _text(value)


def _as_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _case_instruction_lines(case_item: dict[str, Any]) -> list[str]:
    labels = {
        "industry": "行业",
        "company_profile": "公司背景",
        "customer_role": "客户角色",
        "pain_points": "客户痛点",
        "objections": "常见异议",
        "success_criteria": "成功标准",
    }
    lines: list[str] = []
    for key, label in labels.items():
        if key not in case_item:
            continue
        value = case_item.get(key)
        text = _join(value) if isinstance(value, list) else _text(value)
        if text:
            lines.append(f"- {label}：{text}")
    return lines


def _roleplay_contract_section(contract: dict[str, Any] | None) -> str:
    if not isinstance(contract, dict):
        return ""
    if contract.get("legacy_status") == LEGACY_ROLEPLAY_STATUS:
        return ""
    situation = _as_dict(contract.get("situation"))
    relationship = _as_dict(contract.get("relationship_context"))
    scope = _as_dict(contract.get("visible_information_scope"))
    patterns = contract.get("forbidden_claim_patterns")
    conflict_strategy = _text(contract.get("conflict_response_strategy"))
    lines = [
        "【角色合同】",
        f"- 情景：{_text(situation.get('label')) or _text(situation.get('code'))}",
        f"- 关系史：{_relationship_summary(relationship)}",
        f"- 首轮可见字段：{_join(scope.get('initial_visible_keys'))}",
        f"- 默认隐藏字段：{_join(scope.get('hidden_by_default_keys'))}",
    ]
    pattern_text = _join(patterns)
    if pattern_text:
        lines.append(f"- 不得声称：{pattern_text}")
    if conflict_strategy:
        lines.append(f"- 冲突响应策略：{conflict_strategy}")
    prompt_rules = _join(contract.get("behavior_rules_for_prompt_only"))
    if prompt_rules:
        lines.append(f"- 行为规则：{prompt_rules}")
    lines.append("- 不要主动披露未出现在当前可见字段中的隐藏信息。")
    return "\n".join(lines)


def _relationship_summary(relationship: dict[str, Any]) -> str:
    prior = _text(relationship.get("prior_interactions")) or "unspecified"
    facts: list[str] = [f"prior_interactions={prior}"]
    for key in (
        "has_prior_meeting",
        "has_seen_proposal",
        "has_discussed_budget",
        "has_existing_partnership",
    ):
        if relationship.get(key) is not None:
            facts.append(f"{key}={relationship.get(key)}")
    summary = _text(relationship.get("meeting_history_summary"))
    if summary:
        facts.append(f"meeting_history_summary={summary}")
    return "，".join(facts)
