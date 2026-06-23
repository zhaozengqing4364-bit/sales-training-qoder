from __future__ import annotations

from collections import Counter
from copy import deepcopy
from typing import Any

from common.roleplay_contracts import roleplay_contract_hash

V1_ASSET_REVISION = "it_leader_roleplay_v1_2026_06_23"
V1_SCENARIO_CODE = "it_leader_first_visit_shixi_v1"

ROLEPLAY_PHASE_IDS = (
    "opening_intent",
    "current_state_discovery",
    "solution_credibility",
    "next_step_advancement",
)

REQUIRED_SAMPLE_COVERAGE_TAGS = frozenset(
    {
        "opening",
        "current_state_discovery",
        "risk_identification",
        "value_explanation",
        "credibility_response",
        "next_step_advancement",
        "hidden_info_non_disclosure",
        "knowledge_gap_degradation",
        "scoring_evidence_binding",
    }
)


class ItLeaderRoleplayV1ValidationError(ValueError):
    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


KNOWLEDGE_VISIBILITY_RULES: dict[str, Any] = {
    "schema_version": "knowledge_visibility_rules_v1",
    "asset_revision": V1_ASSET_REVISION,
    "layers": [
        {
            "id": "customer_background",
            "label": "客户背景 KB",
            "allowed_consumers": ["realtime_customer", "offline_scorer", "admin"],
            "realtime_customer_visible": True,
            "visibility": "customer_visible",
        },
        {
            "id": "product_facts_limited",
            "label": "产品事实 KB",
            "allowed_consumers": ["realtime_customer", "offline_scorer", "admin"],
            "realtime_customer_visible": True,
            "visibility": "customer_visible_limited",
            "limits": [
                "只能使用已预取或检索命中的石犀平台事实",
                "缺少部署、性能或集成事实时必须追问可验证材料或 PoC 指标",
            ],
        },
        {
            "id": "scoring_coach",
            "label": "评分教练 KB",
            "allowed_consumers": ["offline_scorer", "admin"],
            "realtime_customer_visible": False,
            "visibility": "scorer_admin_only",
        },
    ],
    "degradation_policy": {
        "on_product_fact_missing": "ask_for_verifiable_material_or_poc_metric",
        "quality_flag": "knowledge_gap_degradation",
        "counter": "knowledge_timeout_count",
        "forbid_unsupported_product_claims": True,
    },
}

SESSION_STATE_CARD_SCHEMA: dict[str, Any] = {
    "schema_version": "session_state_card_schema_v1",
    "asset_revision": V1_ASSET_REVISION,
    "required": [
        "version",
        "sequence",
        "current_phase_id",
        "customer_attitude",
        "confirmed_facts",
        "learner_actions_done",
        "learner_actions_missing",
        "objections_raised",
        "hidden_info_revealed",
        "next_pressure",
        "quality_flags",
    ],
    "phase_id_source": "roleplay_phase",
    "sales_stage_authority": "SalesStageCapability",
}

SESSION_STATE_CARD_DEFAULT: dict[str, Any] = {
    "schema_version": "session_state_card_v1",
    "asset_revision": V1_ASSET_REVISION,
    "version": 1,
    "sequence": 0,
    "current_phase_id": "opening_intent",
    "current_phase_type": "roleplay_phase",
    "customer_attitude": "谨慎但愿意继续听",
    "confirmed_facts": [],
    "learner_actions_done": [],
    "learner_actions_missing": [
        "说明拜访目的",
        "澄清现有系统和数据流动现状",
        "回应部署、性能、集成和 PoC 可验证性",
        "提出下一步调研或 PoC 路径",
    ],
    "objections_raised": [],
    "hidden_info_revealed": [],
    "next_pressure": "追问本次拜访目的和希望了解的现状范围",
    "quality_flags": [],
}

SCORING_RUBRIC: dict[str, Any] = {
    "schema_version": "scoring_rubric_v1",
    "ruleset_id": "it_leader_roleplay_v1_business_rubric",
    "asset_revision": V1_ASSET_REVISION,
    "total_score": 100,
    "dimensions": [
        {"id": "opening_intent", "label": "开场与来意", "max_score": 15},
        {"id": "current_state_discovery", "label": "现状澄清", "max_score": 20},
        {"id": "risk_identification", "label": "风险识别", "max_score": 20},
        {"id": "value_explanation", "label": "价值说明", "max_score": 20},
        {"id": "credibility_response", "label": "可信度回应", "max_score": 15},
        {"id": "next_step_advancement", "label": "下一步推进", "max_score": 10},
    ],
    "evidence_policy": {
        "required_source": "learner_utterance",
        "forbid_ai_customer_evidence": True,
        "forbid_hidden_answer_key_in_learner_view": True,
    },
    "compatibility_note": (
        "This six-item rubric is the v1 report projection. It does not replace "
        "the existing five coaching dimensions in the evaluation layer."
    ),
}

REGRESSION_SAMPLE_METADATA: list[dict[str, Any]] = [
    {
        "id": "excellent_opening_discovery_001",
        "quality_tier": "excellent",
        "expected_score_band": [88, 100],
        "coverage_tags": [
            "opening",
            "current_state_discovery",
            "scoring_evidence_binding",
        ],
        "fixture_type": "metadata_only",
    },
    {
        "id": "excellent_risk_value_002",
        "quality_tier": "excellent",
        "expected_score_band": [88, 100],
        "coverage_tags": [
            "risk_identification",
            "value_explanation",
            "credibility_response",
        ],
        "fixture_type": "metadata_only",
    },
    {
        "id": "excellent_poc_next_step_003",
        "quality_tier": "excellent",
        "expected_score_band": [88, 100],
        "coverage_tags": [
            "next_step_advancement",
            "hidden_info_non_disclosure",
            "knowledge_gap_degradation",
        ],
        "fixture_type": "metadata_only",
    },
    {
        "id": "average_partial_discovery_001",
        "quality_tier": "average",
        "expected_score_band": [60, 79],
        "coverage_tags": ["opening", "current_state_discovery"],
        "fixture_type": "metadata_only",
    },
    {
        "id": "average_value_without_proof_002",
        "quality_tier": "average",
        "expected_score_band": [60, 79],
        "coverage_tags": ["value_explanation", "credibility_response"],
        "fixture_type": "metadata_only",
    },
    {
        "id": "average_unclear_next_step_003",
        "quality_tier": "average",
        "expected_score_band": [60, 79],
        "coverage_tags": ["next_step_advancement", "scoring_evidence_binding"],
        "fixture_type": "metadata_only",
    },
    {
        "id": "poor_skip_discovery_001",
        "quality_tier": "poor",
        "expected_score_band": [0, 49],
        "coverage_tags": ["opening", "current_state_discovery"],
        "fixture_type": "metadata_only",
    },
    {
        "id": "poor_overpromise_capability_002",
        "quality_tier": "poor",
        "expected_score_band": [0, 49],
        "coverage_tags": [
            "risk_identification",
            "credibility_response",
            "knowledge_gap_degradation",
        ],
        "fixture_type": "metadata_only",
    },
    {
        "id": "poor_hidden_leak_no_advance_003",
        "quality_tier": "poor",
        "expected_score_band": [0, 49],
        "coverage_tags": [
            "hidden_info_non_disclosure",
            "next_step_advancement",
            "scoring_evidence_binding",
        ],
        "fixture_type": "metadata_only",
    },
]


def get_roleplay_contract() -> dict[str, Any]:
    contract = _roleplay_contract_without_hash()
    contract["audit"] = {
        "contract_hash": roleplay_contract_hash(contract),
        "revision_refs": deepcopy(contract["revision_refs"]),
    }
    return contract


def get_state_card_schema() -> dict[str, Any]:
    return deepcopy(SESSION_STATE_CARD_SCHEMA)


def get_default_state_card() -> dict[str, Any]:
    return deepcopy(SESSION_STATE_CARD_DEFAULT)


def get_knowledge_visibility_rules() -> dict[str, Any]:
    return deepcopy(KNOWLEDGE_VISIBILITY_RULES)


def get_scoring_rubric() -> dict[str, Any]:
    return deepcopy(SCORING_RUBRIC)


def get_regression_sample_metadata() -> list[dict[str, Any]]:
    return deepcopy(REGRESSION_SAMPLE_METADATA)


def validate_roleplay_contract(contract: dict[str, Any]) -> None:
    if contract.get("schema_version") != "roleplay_contract_v1":
        raise ItLeaderRoleplayV1ValidationError("invalid_contract_schema")

    scope = _as_dict(contract.get("visible_information_scope"))
    visible_keys = set(_as_string_list(scope.get("initial_visible_keys")))
    hidden_keys = set(_as_string_list(scope.get("hidden_by_default_keys")))
    if not visible_keys:
        raise ItLeaderRoleplayV1ValidationError("missing_visible_scope")
    if not hidden_keys:
        raise ItLeaderRoleplayV1ValidationError("missing_hidden_scope")
    if visible_keys & hidden_keys:
        raise ItLeaderRoleplayV1ValidationError("visible_hidden_scope_overlap")
    if "scoring_coach" in visible_keys:
        raise ItLeaderRoleplayV1ValidationError("scoring_coach_visible_to_customer")

    phase_model = _as_dict(contract.get("phase_model"))
    if phase_model.get("phase_type") != "roleplay_phase":
        raise ItLeaderRoleplayV1ValidationError("phase_type_not_roleplay_phase")
    phases = _as_list(phase_model.get("phases"))
    phase_ids = [str(phase.get("id")) for phase in phases if isinstance(phase, dict)]
    if tuple(phase_ids) != ROLEPLAY_PHASE_IDS:
        raise ItLeaderRoleplayV1ValidationError("invalid_roleplay_phases")
    if any("sales_stage_id" in phase for phase in phases if isinstance(phase, dict)):
        raise ItLeaderRoleplayV1ValidationError("phase_declares_sales_stage")

    forbidden_ids = {
        str(item.get("id"))
        for item in _as_list(contract.get("forbidden_behaviors"))
        if isinstance(item, dict)
    }
    required_forbidden = {
        "leak_answer_key",
        "act_as_coach",
        "answer_for_learner",
        "reveal_scoring_rubric",
        "invent_product_capability",
    }
    if not required_forbidden.issubset(forbidden_ids):
        raise ItLeaderRoleplayV1ValidationError("missing_forbidden_behaviors")


def validate_knowledge_visibility_rules(rules: dict[str, Any]) -> None:
    layers = {
        str(layer.get("id")): layer
        for layer in _as_list(rules.get("layers"))
        if isinstance(layer, dict)
    }
    if "customer_background" not in layers or "product_facts_limited" not in layers:
        raise ItLeaderRoleplayV1ValidationError("missing_customer_visible_layers")
    if layers["customer_background"].get("realtime_customer_visible") is not True:
        raise ItLeaderRoleplayV1ValidationError("customer_background_not_visible")
    if layers["product_facts_limited"].get("realtime_customer_visible") is not True:
        raise ItLeaderRoleplayV1ValidationError("product_facts_not_visible")
    if layers.get("scoring_coach", {}).get("realtime_customer_visible") is not False:
        raise ItLeaderRoleplayV1ValidationError("scoring_coach_visibility_invalid")


def validate_scoring_rubric(rubric: dict[str, Any]) -> None:
    dimensions = _as_list(rubric.get("dimensions"))
    total = sum(
        int(dimension.get("max_score", 0))
        for dimension in dimensions
        if isinstance(dimension, dict)
    )
    if len(dimensions) != 6:
        raise ItLeaderRoleplayV1ValidationError("invalid_rubric_dimension_count")
    if total != int(rubric.get("total_score", -1)) or total != 100:
        raise ItLeaderRoleplayV1ValidationError("invalid_rubric_total")
    evidence_policy = _as_dict(rubric.get("evidence_policy"))
    if evidence_policy.get("required_source") != "learner_utterance":
        raise ItLeaderRoleplayV1ValidationError("invalid_evidence_source")
    if evidence_policy.get("forbid_ai_customer_evidence") is not True:
        raise ItLeaderRoleplayV1ValidationError("ai_customer_evidence_not_forbidden")


def validate_regression_sample_metadata(samples: list[dict[str, Any]]) -> None:
    if len(samples) != 9:
        raise ItLeaderRoleplayV1ValidationError("invalid_sample_count")
    tier_counts = Counter(str(sample.get("quality_tier")) for sample in samples)
    if tier_counts != {"excellent": 3, "average": 3, "poor": 3}:
        raise ItLeaderRoleplayV1ValidationError("invalid_sample_tier_split")
    coverage = {
        tag
        for sample in samples
        for tag in _as_string_list(sample.get("coverage_tags"))
    }
    missing = REQUIRED_SAMPLE_COVERAGE_TAGS - coverage
    if missing:
        raise ItLeaderRoleplayV1ValidationError("missing_sample_coverage_tags")


def validate_v1_assets() -> None:
    validate_roleplay_contract(get_roleplay_contract())
    validate_knowledge_visibility_rules(get_knowledge_visibility_rules())
    validate_scoring_rubric(get_scoring_rubric())
    validate_regression_sample_metadata(get_regression_sample_metadata())


def _roleplay_contract_without_hash() -> dict[str, Any]:
    return {
        "schema_version": "roleplay_contract_v1",
        "contract_version": "it_leader_roleplay_v1",
        "scenario_code": V1_SCENARIO_CODE,
        "source_track": "direct_practice_sample",
        "asset_revision": V1_ASSET_REVISION,
        "customer_identity": {
            "role_family": "国企/央企/政教医信息化负责人",
            "titles": ["信息中心主任", "信息化处负责人", "数字化建设负责人"],
            "organization_types": ["国企", "央企", "政教医"],
        },
        "scenario": {
            "visit_type": "first_visit",
            "duration_minutes": [12, 15],
            "product": "石犀数据流动治理平台",
            "training_goal": "方案可信度和需求澄清",
        },
        "relationship_context": {
            "prior_interactions": "none",
            "has_prior_meeting": False,
            "has_seen_proposal": False,
            "has_discussed_budget": False,
            "has_existing_partnership": False,
            "meeting_history_summary": None,
        },
        "visible_information_scope": {
            "initial_visible_keys": [
                "customer_background",
                "industry_common_context",
                "product_facts_limited",
            ],
            "hidden_by_default_keys": [
                "scoring_coach",
                "standard_answers",
                "internal_sales_playbook",
                "hidden_budget",
                "decision_chain",
            ],
            "visibility_rules_ref": V1_ASSET_REVISION,
        },
        "knowledge_visibility": deepcopy(KNOWLEDGE_VISIBILITY_RULES),
        "phase_model": {
            "phase_type": "roleplay_phase",
            "sales_stage_authority": "SalesStageCapability",
            "phases": [
                {
                    "id": "opening_intent",
                    "label": "开场与来意",
                    "time_window_minutes": [0, 3],
                    "customer_pressure": "确认拜访目的，避免学员直接推产品",
                },
                {
                    "id": "current_state_discovery",
                    "label": "现状澄清",
                    "time_window_minutes": [3, 7],
                    "customer_pressure": "追问系统、接口、数据流动和安全设备现状",
                },
                {
                    "id": "solution_credibility",
                    "label": "方案可信度",
                    "time_window_minutes": [7, 12],
                    "customer_pressure": "追问部署、性能、集成、误报和 PoC 指标",
                },
                {
                    "id": "next_step_advancement",
                    "label": "下一步推进",
                    "time_window_minutes": [12, 15],
                    "customer_pressure": "要求明确调研、材料或 PoC 下一步",
                },
            ],
        },
        "behavior_rules": [
            "保持谨慎、务实、专业的信息化负责人姿态",
            "围绕稳定性、安全合规、系统集成、性能影响和审计价值追问",
            "学员泛泛介绍产品时要求其回到现状、风险和可验证指标",
            "产品事实缺失时自然要求材料、指标或 PoC，不替产品补能力",
            "不主动帮助学员完成总结或销售动作",
        ],
        "forbidden_behaviors": [
            {"id": "leak_answer_key", "description": "泄露标准答案或隐藏信息"},
            {"id": "act_as_coach", "description": "以教练身份指导学员如何回答"},
            {"id": "answer_for_learner", "description": "替学员总结需求或推进方案"},
            {"id": "reveal_scoring_rubric", "description": "主动说出评分维度或分值"},
            {
                "id": "invent_product_capability",
                "description": "在缺少产品事实时臆测石犀平台能力",
            },
        ],
        "forbidden_claim_patterns": ["上次拜访", "你们已经看过方案", "评分标准是"],
        "disclosure_policy": {
            "never_disclose_keys": [
                "scoring_coach",
                "standard_answers",
                "internal_sales_playbook",
            ],
            "hidden_slice_only": True,
        },
        "runtime_violation_policy": {
            "relationship_history_contradiction": "regenerate_once",
            "hidden_information_leak": "regenerate_once",
            "forbidden_topic": "mark_and_continue",
            "coach_like_behavior": "mark_for_report",
        },
        "state_card": {
            "schema": deepcopy(SESSION_STATE_CARD_SCHEMA),
            "default": deepcopy(SESSION_STATE_CARD_DEFAULT),
        },
        "scoring_ruleset_ref": SCORING_RUBRIC["ruleset_id"],
        "revision_refs": [
            {
                "asset_type": "sample_roleplay_contract",
                "revision": V1_ASSET_REVISION,
            },
            {
                "asset_type": "sample_state_card_schema",
                "revision": V1_ASSET_REVISION,
            },
            {
                "asset_type": "sample_scoring_rubric",
                "revision": V1_ASSET_REVISION,
            },
        ],
    }


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_string_list(value: Any) -> list[str]:
    return [str(item) for item in _as_list(value)]
