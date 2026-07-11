"""Default contracts for governed business-rule configuration."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from roleplay.defaults import (
    DEFAULT_ROLEPLAY_EVAL_RELEASE_GATE,
    DEFAULT_ROLEPLAY_SITUATION_PACKS,
    ROLEPLAY_EVAL_RELEASE_GATE_KEY,
    ROLEPLAY_SITUATION_PACKS_KEY,
)

ACHIEVEMENT_RULES_KEY = "growth.achievement.rules"
AI_COACH_RULES_KEY = "growth.ai_coach.rules"
NEXT_PRACTICE_RECOMMENDATION_KEY = "recommendation.next_practice.ruleset"
SALES_COMBINATION_RULES_KEY = "sales.training.combinations.ruleset"
OBJECTION_LEDGER_RULES_KEY = "sales.objection_ledger.ruleset"
_LEGACY_ROLEPLAY_SITUATION_PACKS_KEY = "roleplay.situation_packs.ruleset"
_LEGACY_ROLEPLAY_EVAL_RELEASE_GATE_KEY = "roleplay.eval.release_gate"
ADMIN_SETTINGS_GENERAL_KEY = "admin.settings.general"
ADMIN_SETTINGS_SECURITY_KEY = "admin.settings.security"
ADMIN_SETTINGS_NOTIFICATIONS_KEY = "admin.settings.notifications"
SALES_TRAINER_PHASE2_CLOSED_LOOP_POLICY_KEY = (
    "sales_trainer.phase2.closed_loop_policy"
)
SALES_TRAINER_LEARNER_LEVEL_POLICY_KEY = "sales_trainer.learner_level.policy"
SALES_TRAINER_ROLE_LEVEL_POLICY_KEY = "sales_trainer.role_level.policy"
SALES_TRAINER_REALTIME_PROVIDER_REGISTRY_KEY = (
    "sales_trainer.realtime_provider.registry"
)

BUSINESS_RULE_SCHEMA_VERSION = "business_rule_config_v1"

DEFAULT_ADMIN_GENERAL_SETTINGS: dict[str, Any] = {
    "version": "admin_general_settings_v1",
    "enabled": True,
    "platform_name": "Intelligent Coach AI",
    "support_email": "support@company.com",
    "welcome_message": "欢迎使用高级训练平台，开启您的学习之旅！",
    "default_language": "zh-CN",
    "timezone": "Asia/Shanghai",
    "date_format": "YYYY-MM-DD",
}

DEFAULT_ADMIN_SECURITY_SETTINGS: dict[str, Any] = {
    "version": "admin_security_settings_v1",
    "enabled": True,
    "enforce_admin_2fa": True,
    "new_device_login_alert": True,
    "password_min_length": 8,
    "password_expiry_days": 90,
}

DEFAULT_ADMIN_NOTIFICATION_SETTINGS: dict[str, Any] = {
    "version": "admin_notification_settings_v1",
    "enabled": True,
    "email_notifications": {
        "user_registration_admin": True,
        "system_exception_alert": True,
        "weekly_report": False,
        "knowledge_base_update": False,
    },
}

DEFAULT_SALES_TRAINER_PHASE2_POLICY: dict[str, Any] = {
    "version": "sales_trainer_phase2_closed_loop_policy_v1",
    "enabled": True,
    "low_score_threshold": 70.0,
    "repeat_practice_threshold": 2,
    "dashboard_record_limit": 500,
    "manager_actions": [
        {"code": "not_passed", "label": "打回并安排补救训练", "priority": "high"},
        {"code": "low_score", "label": "指定弱项复习", "priority": "medium"},
        {"code": "repeated_practice", "label": "主管介入陪练", "priority": "medium"},
        {"code": "fallback", "label": "查看训练记录", "priority": "low"},
    ],
    "remediation_actions": [
        {
            "record_type": "audio_submission",
            "action_label": "安排重录",
            "reason_template": "最近一次训练未达通过标准，需要主管跟进补救。",
            "target_path_template": "/sales-trainer/audio/{unit_id}",
            "priority": "high",
        },
        {
            "record_type": "quiz_attempt",
            "action_label": "安排错题复习",
            "reason_template": "当前有效分低于弱项阈值，需要安排针对性复练。",
            "target_path_template": "/sales-trainer/quiz/{unit_id}",
            "priority": "medium",
        },
        {
            "record_type": "business_etiquette_quiz_attempt",
            "action_label": "复习后重做小测",
            "reason_template": "商务礼仪小测存在薄弱能力点，需要回看对应章节后重做。",
            "target_path_template": "/sales-trainer/business-skills?learningUnitKey={unit_id}",
            "priority": "medium",
        },
        {
            "record_type": "ai_coach_session",
            "action_label": "继续 AI 教练训练",
            "reason_template": "AI 教练训练尚未完成或未达到掌握状态，需要继续训练。",
            "target_path_template": "/sales-trainer/business-skills/coach",
            "priority": "medium",
        },
        {
            "record_type": "default",
            "action_label": "查看训练记录",
            "reason_template": "训练尚未形成可用评分，需要先完成评分或排查失败任务。",
            "target_path_template": "/sales-trainer",
            "priority": "medium",
        },
        {
            "record_type": "no_action",
            "action_label": "查看结果",
            "reason_template": "当前记录已达标，建议进入下一任务或回看结果。",
            "target_path_template": "{result_path}",
            "priority": "low",
        },
    ],
}

DEFAULT_SALES_TRAINER_LEARNER_LEVEL_POLICY: dict[str, Any] = {
    "version": "sales_trainer_learner_level_policy_v1",
    "enabled": True,
    "default_level": {
        "key": "unassigned",
        "label": "未分层",
        "rank": 0,
        "description": "未发布学员等级规则时的安全默认分层。",
    },
    "levels": [
        {
            "key": "unassigned",
            "label": "未分层",
            "rank": 0,
            "description": "未发布学员等级规则时的安全默认分层。",
        }
    ],
    "rules": [],
}

DEFAULT_SALES_TRAINER_ROLE_LEVEL_POLICY: dict[str, Any] = {
    "version": "sales_trainer_role_level_policy_v1",
    "enabled": True,
    "default_level": {
        "key": "learner",
        "label": "普通学员",
        "rank": 0,
        "description": "未发布组织角色等级规则时的安全默认角色等级。",
    },
    "levels": [
        {
            "key": "learner",
            "label": "普通学员",
            "rank": 0,
            "description": "未发布组织角色等级规则时的安全默认角色等级。",
        }
    ],
    "rules": [
        {
            "key": "default_user_role",
            "level_key": "learner",
            "priority": 1,
            "enabled": True,
            "conditions": {"role_in": ["user"]},
        }
    ],
}

DEFAULT_SALES_TRAINER_REALTIME_PROVIDER_REGISTRY: dict[str, Any] = {
    "version": "sales_trainer_realtime_provider_registry_v1",
    "enabled": False,
    "descriptors": [
        {
            "descriptor_id": "newcomer-realtime-runtime",
            "label": "新人训练实时对练",
            "provider": "stepfun_realtime",
            "runtime_owner": "training_runtime",
            "enabled": False,
            "runtime_profile_id": None,
            "config_revision_id": "default-disabled",
            "rollback_to_descriptor_id": None,
            "readiness": {
                "ready": False,
                "checked_at": None,
                "failure_code": "REGISTRY_DISABLED",
                "failure_message": "实时对练 provider registry 尚未发布启用。",
            },
        }
    ],
}

DEFAULT_ACHIEVEMENT_RULESET: dict[str, Any] = {
    "version": "growth_achievement_rules_v1",
    "enabled": True,
    "achievements": [
        {
            "code": "first_evaluable_session",
            "name": "首次有效训练",
            "description": "完成第一场可评估训练。",
            "icon_key": "trophy",
            "condition": {"type": "evaluable_session_count", "min": 1},
        },
        {
            "code": "score_breakthrough_80",
            "name": "突破 80 分",
            "description": "任意一场可评估训练综合分达到 80 分。",
            "icon_key": "sparkles",
            "condition": {"type": "max_overall_score", "min": 80},
        },
    ],
}

DEFAULT_AI_COACH_RULESET: dict[str, Any] = {
    "version": "growth_ai_coach_rules_v1",
    "enabled": True,
    "weak_score_threshold": 60.0,
    "dimensions": [
        {"key": "value_logic", "label": "价值逻辑", "score_field": "logic_score"},
        {
            "key": "product_knowledge",
            "label": "产品知识与证据",
            "score_field": "accuracy_score",
        },
        {
            "key": "objection_handling",
            "label": "异议处理",
            "score_field": "completeness_score",
        },
    ],
    "notification_template": {
        "title_template": "AI 教练建议：先练{label}",
        "content_template": (
            "最近一次可评估训练中，{label}为 {score:.0f} 分，低于 "
            "{threshold:.0f} 分阈值。建议下一轮先做 10 分钟专项训练。"
        ),
        "action_label": "按建议训练",
        "action_path_template": "/practice/{source_session_id}/report",
    },
}

DEFAULT_RECOMMENDATION_RULESET: dict[str, Any] = {
    "version": "growth_recommendation_rules_v1",
    "enabled": True,
    "weak_score_threshold": 60.0,
    "dimensions": {
        "product_knowledge": {
            "score_field": "accuracy_score",
            "label": "产品知识与证据",
            "title": "补强产品知识与证据表达",
            "reason_template": "上次可评估训练中「{label}」为 {score:.0f} 分，低于 {threshold:.0f} 分阈值，建议下一轮先补充案例、数据或 ROI 证据。",
            "action_label": "练产品知识专项",
            "target_path": "/training/sales?focus=product_knowledge",
        },
        "objection_handling": {
            "score_field": "completeness_score",
            "label": "异议处理",
            "title": "练一轮异议处理专项",
            "reason_template": "上次可评估训练中「{label}」为 {score:.0f} 分，低于 {threshold:.0f} 分阈值，建议下一轮重点承接客户顾虑并推动下一步。",
            "action_label": "练异议处理",
            "target_path": "/training/sales?focus=objection_handling",
        },
        "value_logic": {
            "score_field": "logic_score",
            "label": "价值逻辑",
            "title": "梳理价值表达逻辑",
            "reason_template": "上次可评估训练中「{label}」为 {score:.0f} 分，低于 {threshold:.0f} 分阈值，建议下一轮先把能力、收益和下一步说清楚。",
            "action_label": "练价值表达",
            "target_path": "/training/sales?focus=value_logic",
        },
    },
    "fallback": {
        "title": "保持复练节奏",
        "reason": "上次可评估训练没有明显低于阈值的维度，建议延续当前训练节奏并尝试更完整的场景。",
        "action_label": "继续练习",
        "target_path": "/training",
    },
}

DEFAULT_SALES_COMBINATION_RULESET: dict[str, Any] = {
    "rule_set_id": "sales-training-combinations-default-v1",
    "version": "sales_training_combinations_v1",
    "enabled": True,
    "fallback_policy": "client_default_v1",
    "combinations": [
        {
            "id": "c1",
            "capability": "破冰建立信任",
            "role": "冷淡型客户",
            "priority": 1,
            "enabled": True,
            "required_agent_match": [],
            "required_persona_match": [],
        },
        {
            "id": "c2",
            "capability": "破冰建立信任",
            "role": "强势质疑型客户",
            "priority": 2,
            "enabled": True,
            "required_agent_match": [],
            "required_persona_match": [],
        },
        {
            "id": "c3",
            "capability": "需求挖掘",
            "role": "价格敏感型客户",
            "priority": 3,
            "enabled": True,
            "required_agent_match": [],
            "required_persona_match": [],
        },
        {
            "id": "c4",
            "capability": "需求挖掘",
            "role": "拖延决策型客户",
            "priority": 4,
            "enabled": True,
            "required_agent_match": [],
            "required_persona_match": [],
        },
        {
            "id": "c5",
            "capability": "价值表达",
            "role": "竞品比较型客户",
            "priority": 5,
            "enabled": True,
            "required_agent_match": [],
            "required_persona_match": [],
        },
        {
            "id": "c6",
            "capability": "价值表达",
            "role": "价格敏感型客户",
            "priority": 6,
            "enabled": True,
            "required_agent_match": [],
            "required_persona_match": [],
        },
        {
            "id": "c7",
            "capability": "异议处理",
            "role": "强势质疑型客户",
            "priority": 7,
            "enabled": True,
            "required_agent_match": [],
            "required_persona_match": [],
        },
        {
            "id": "c8",
            "capability": "异议处理",
            "role": "竞品比较型客户",
            "priority": 8,
            "enabled": True,
            "required_agent_match": [],
            "required_persona_match": [],
        },
        {
            "id": "c9",
            "capability": "推进下一步行动",
            "role": "拖延决策型客户",
            "priority": 9,
            "enabled": True,
            "required_agent_match": [],
            "required_persona_match": [],
        },
        {
            "id": "c10",
            "capability": "推进下一步行动",
            "role": "冷淡型客户",
            "priority": 10,
            "enabled": True,
            "required_agent_match": [],
            "required_persona_match": [],
        },
    ],
}

DEFAULT_OBJECTION_LEDGER_RULESET: dict[str, Any] = {
    "rule_set_id": "sales-objection-ledger-default-v1",
    "version": "sales_objection_ledger_v1",
    "enabled": True,
    "ack_patterns": [
        "没有",
        "暂无",
        "还没",
        "暂时没有",
        "无法",
        "不能",
        "做不到",
        "不确定",
        "回去确认",
        "后面再给",
        "之后再给",
        "稍后再给",
    ],
    "open_stage_names": ["objection", "异议处理", "价格博弈"],
    "numeric_evidence_tokens": [
        "benchmark",
        "%",
        "提升",
        "下降",
        "回本周期",
        "回收周期",
        "月内",
        "周内",
    ],
    "families": {
        "roi_proof": {
            "focus_dimension": "证据使用",
            "promised_proof": "补充同类客户 ROI 案例",
            "next_expected_evidence": "给出 6 个月回本测算",
            "detect_any": [
                "roi",
                "回本",
                "收益",
                "回报",
                "案例",
                "数据",
                "benchmark",
                "证据",
            ],
            "evidence_any": [
                "roi",
                "回本",
                "收益",
                "案例",
                "客户",
                "数据",
                "benchmark",
                "证据",
                "%",
                "提升",
                "下降",
            ],
            "open_pressure_any": [
                "证明",
                "凭什么",
                "没有",
                "缺",
                "不足",
                "担心",
                "顾虑",
                "怎么",
                "为何",
            ],
            "open_pressure_requires_any": ["roi", "回本", "案例", "数据", "证据", "收益"],
        },
        "price_pressure": {
            "focus_dimension": "异议处理",
            "promised_proof": "补充报价依据和版本差异",
            "next_expected_evidence": "说明报价逻辑、预算回收或折扣边界",
            "detect_any": ["价格", "报价", "预算", "折扣", "成本", "price", "budget"],
            "evidence_any": [
                "价格",
                "报价",
                "预算",
                "折扣",
                "席位",
                "版本",
                "回收",
                "回本",
                "%",
                "元",
            ],
            "open_pressure_any": [
                "价格",
                "报价",
                "预算",
                "折扣",
                "贵",
                "成本",
                "担心",
                "顾虑",
            ],
            "open_pressure_requires_any": [],
        },
        "competitor_alternative": {
            "focus_dimension": "异议处理",
            "promised_proof": "补充竞品差异和替代依据",
            "next_expected_evidence": "说明为什么比现有方案更稳妥",
            "detect_any": ["竞品", "竞对", "对比", "替代", "差异", "competitor"],
            "evidence_any": [
                "竞品",
                "对比",
                "替代",
                "差异",
                "迁移",
                "案例",
                "SLA",
                "成本",
                "收益",
            ],
            "open_pressure_any": ["竞品", "竞对", "替代", "对比", "差异", "担心", "顾虑"],
            "open_pressure_requires_any": [],
        },
        "implementation_risk": {
            "focus_dimension": "异议处理",
            "promised_proof": "补充实施排期和服务边界",
            "next_expected_evidence": "确认试点范围、负责人和风险兜底",
            "detect_any": ["实施", "落地", "上线", "风险", "排期", "交付", "服务", "试点"],
            "evidence_any": [
                "实施",
                "落地",
                "上线",
                "排期",
                "试点",
                "负责人",
                "服务",
                "SLA",
                "里程碑",
                "周",
                "天",
                "月",
            ],
            "open_pressure_any": [
                "实施",
                "落地",
                "上线",
                "排期",
                "试点",
                "风险",
                "担心",
                "顾虑",
            ],
            "open_pressure_requires_any": ["实施", "落地", "上线", "排期", "试点", "风险"],
        },
    },
    "synthetic_dimensions_by_focus": {
        "证据使用": {
            "价值表达": 78.0,
            "客户收益连接": 76.0,
            "证据使用": 48.0,
            "异议处理": 68.0,
            "推进下一步": 62.0,
        },
        "异议处理": {
            "价值表达": 78.0,
            "客户收益连接": 76.0,
            "证据使用": 66.0,
            "异议处理": 48.0,
            "推进下一步": 62.0,
        },
    },
    "management_backlog": (
        "基于当前提供的代码，暂无法确认现有配置体系，需要补充配置模块、"
        "后台管理模块、字典表、权限模块或系统设置相关代码。"
    ),
}

_ROLEPLAY_COMMON_VIOLATION_POLICY: dict[str, str] = {
    "relationship_history_contradiction": "cancel_or_regenerate_once",
    "hidden_information_leak": "cancel_or_regenerate_once",
    "forbidden_topic": "mark_and_continue",
    "persona_style_drift": "mark_for_report",
}

_LEGACY_DEFAULT_ROLEPLAY_SITUATION_PACKS: dict[str, Any] = {
    "version": "roleplay_situation_packs_v1",
    "enabled": True,
    "packs": [
        {
            "code": "general_practice",
            "label": "通用对练",
            "version": "legacy_default",
            "status": "published",
            "default_relationship_context": {"prior_interactions": "unspecified"},
            "default_visible_information_scope": {
                "initial_visible_keys": [],
                "conditionally_visible_keys": [],
                "hidden_by_default_keys": [],
            },
            "default_forbidden_claim_patterns": [],
            "default_forbidden_topic_codes": [],
            "default_forbidden_stage_codes": [],
            "default_conflict_response_strategy": "neutral_clarification",
            "default_runtime_violation_policy": {
                **_ROLEPLAY_COMMON_VIOLATION_POLICY,
                "relationship_history_contradiction": "mark_for_report",
            },
            "compatible_practice_modes": ["customer_roleplay"],
            "compatible_scenario_types": ["sales"],
        },
        {
            "code": "first_visit",
            "label": "首次拜访",
            "version": "v1",
            "status": "published",
            "initial_stage_hint": "opening",
            "default_relationship_context": {
                "prior_interactions": "none",
                "has_prior_meeting": False,
                "has_seen_proposal": False,
                "has_discussed_budget": False,
                "has_existing_partnership": False,
                "meeting_history_summary": None,
            },
            "default_visible_information_scope": {
                "initial_visible_keys": [
                    "industry",
                    "company_profile",
                    "customer_role",
                    "pain_points",
                    "objections",
                    "success_criteria",
                ],
                "conditionally_visible_keys": ["hidden_information"],
                "hidden_by_default_keys": [
                    "hidden_information",
                    "budget",
                    "decision_chain",
                    "competitor_quote",
                ],
            },
            "default_forbidden_claim_patterns": [
                "上次拜访",
                "之前我们聊",
                "上次方案",
                "之前报价",
                "之前合作",
                "上次沟通",
                "上次见面",
                "之前你给",
            ],
            "default_forbidden_topic_codes": ["contract_closing"],
            "default_forbidden_stage_codes": ["price_negotiation", "contract_closing"],
            "default_conflict_response_strategy": "customer_confused_correction",
            "default_runtime_violation_policy": _ROLEPLAY_COMMON_VIOLATION_POLICY,
            "compatible_practice_modes": ["customer_roleplay"],
            "compatible_scenario_types": ["sales"],
        },
        {
            "code": "follow_up",
            "label": "复访跟进",
            "version": "v1",
            "status": "published",
            "default_relationship_context": {
                "prior_interactions": "one_meeting",
                "has_prior_meeting": True,
                "has_seen_proposal": False,
                "has_discussed_budget": False,
                "has_existing_partnership": False,
                "meeting_history_summary": None,
            },
            "default_visible_information_scope": {
                "initial_visible_keys": [
                    "industry",
                    "company_profile",
                    "customer_role",
                    "pain_points",
                    "objections",
                ],
                "conditionally_visible_keys": ["success_criteria", "hidden_information"],
                "hidden_by_default_keys": [
                    "hidden_information",
                    "budget",
                    "decision_chain",
                ],
            },
            "default_forbidden_claim_patterns": [],
            "default_forbidden_topic_codes": ["contract_closing"],
            "default_forbidden_stage_codes": ["contract_closing"],
            "default_conflict_response_strategy": "neutral_clarification",
            "default_runtime_violation_policy": _ROLEPLAY_COMMON_VIOLATION_POLICY,
            "compatible_practice_modes": ["customer_roleplay"],
            "compatible_scenario_types": ["sales"],
        },
        {
            "code": "proposal_review",
            "label": "方案评审",
            "version": "v1",
            "status": "published",
            "default_relationship_context": {
                "prior_interactions": "one_meeting",
                "has_prior_meeting": True,
                "has_seen_proposal": True,
                "has_discussed_budget": False,
                "has_existing_partnership": False,
                "meeting_history_summary": None,
            },
            "default_visible_information_scope": {
                "initial_visible_keys": [
                    "industry",
                    "company_profile",
                    "customer_role",
                    "pain_points",
                    "objections",
                    "success_criteria",
                ],
                "conditionally_visible_keys": ["hidden_information"],
                "hidden_by_default_keys": [
                    "hidden_information",
                    "decision_chain",
                    "competitor_quote",
                ],
            },
            "default_forbidden_claim_patterns": ["之前合作"],
            "default_forbidden_topic_codes": ["contract_closing"],
            "default_forbidden_stage_codes": ["contract_closing"],
            "default_conflict_response_strategy": "neutral_clarification",
            "default_runtime_violation_policy": _ROLEPLAY_COMMON_VIOLATION_POLICY,
            "compatible_practice_modes": ["customer_roleplay"],
            "compatible_scenario_types": ["sales"],
        },
        {
            "code": "price_negotiation",
            "label": "价格谈判",
            "version": "v1",
            "status": "published",
            "default_relationship_context": {
                "prior_interactions": "multiple_meetings",
                "has_prior_meeting": True,
                "has_seen_proposal": True,
                "has_discussed_budget": True,
                "has_existing_partnership": False,
                "meeting_history_summary": None,
            },
            "default_visible_information_scope": {
                "initial_visible_keys": [
                    "industry",
                    "company_profile",
                    "customer_role",
                    "pain_points",
                    "objections",
                    "success_criteria",
                ],
                "conditionally_visible_keys": ["hidden_information"],
                "hidden_by_default_keys": [
                    "hidden_information",
                    "internal_floor_price",
                    "decision_chain",
                ],
            },
            "default_forbidden_claim_patterns": [
                "已经接受报价",
                "已经同意合同",
                "之前合作",
            ],
            "default_forbidden_topic_codes": [],
            "default_forbidden_stage_codes": ["contract_closing"],
            "default_conflict_response_strategy": "neutral_clarification",
            "default_runtime_violation_policy": _ROLEPLAY_COMMON_VIOLATION_POLICY,
            "compatible_practice_modes": ["customer_roleplay"],
            "compatible_scenario_types": ["sales"],
        },
        {
            "code": "renewal",
            "label": "续约沟通",
            "version": "v1",
            "status": "published",
            "default_relationship_context": {
                "prior_interactions": "existing_customer",
                "has_prior_meeting": True,
                "has_seen_proposal": False,
                "has_discussed_budget": False,
                "has_existing_partnership": True,
                "meeting_history_summary": None,
            },
            "default_visible_information_scope": {
                "initial_visible_keys": [
                    "industry",
                    "company_profile",
                    "customer_role",
                    "pain_points",
                    "objections",
                ],
                "conditionally_visible_keys": ["success_criteria", "hidden_information"],
                "hidden_by_default_keys": [
                    "hidden_information",
                    "renewal_risk",
                    "decision_chain",
                ],
            },
            "default_forbidden_claim_patterns": ["默认满意续约", "已经决定续约"],
            "default_forbidden_topic_codes": [],
            "default_forbidden_stage_codes": ["contract_closing"],
            "default_conflict_response_strategy": "neutral_clarification",
            "default_runtime_violation_policy": _ROLEPLAY_COMMON_VIOLATION_POLICY,
            "compatible_practice_modes": ["customer_roleplay"],
            "compatible_scenario_types": ["sales"],
        },
        {
            "code": "complaint_recovery",
            "label": "投诉安抚",
            "version": "v1",
            "status": "published",
            "default_relationship_context": {
                "prior_interactions": "existing_customer",
                "has_prior_meeting": True,
                "has_seen_proposal": False,
                "has_discussed_budget": False,
                "has_existing_partnership": True,
                "meeting_history_summary": None,
            },
            "default_visible_information_scope": {
                "initial_visible_keys": [
                    "industry",
                    "company_profile",
                    "customer_role",
                    "pain_points",
                    "objections",
                ],
                "conditionally_visible_keys": ["success_criteria", "hidden_information"],
                "hidden_by_default_keys": [
                    "hidden_information",
                    "compensation_boundary",
                    "decision_chain",
                ],
            },
            "default_forbidden_claim_patterns": [
                "无条件赔偿",
                "马上全额退款",
                "已经批准赔偿",
            ],
            "default_forbidden_topic_codes": ["unauthorized_compensation"],
            "default_forbidden_stage_codes": ["contract_closing"],
            "default_conflict_response_strategy": "neutral_clarification",
            "default_runtime_violation_policy": _ROLEPLAY_COMMON_VIOLATION_POLICY,
            "compatible_practice_modes": ["customer_roleplay"],
            "compatible_scenario_types": ["sales"],
        },
    ],
}

_LEGACY_DEFAULT_ROLEPLAY_EVAL_RELEASE_GATE: dict[str, Any] = {
    "version": "roleplay_eval_release_gate_v1",
    "enabled": True,
    "deterministic_gate_mode": "blocking",
    "llm_grader_mode": "warn_only",
    "blocking_violation_codes": [
        "ROLEPLAY_HISTORY_CONTRADICTION",
        "ROLEPLAY_HIDDEN_INFORMATION_LEAK",
        "ROLEPLAY_FORBIDDEN_STAGE",
    ],
    "artifact_retention_days": 30,
}


@dataclass(frozen=True)
class BusinessRuleDefinition:
    key: str
    domain: str
    schema_version: str
    default_value: dict[str, Any]
    type: str
    range_or_allowlist: dict[str, Any]
    read_path: str
    admin_entry: str
    permission: str
    audit_policy: str
    fallback_policy: str
    rollback_policy: str

    def metadata(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "schema_version": self.schema_version,
            "default_value": deepcopy(self.default_value),
            "type": self.type,
            "range_or_allowlist": deepcopy(self.range_or_allowlist),
            "read_path": self.read_path,
            "admin_entry": self.admin_entry,
            "permission": self.permission,
            "audit_policy": self.audit_policy,
            "fallback_policy": self.fallback_policy,
            "rollback_policy": self.rollback_policy,
        }


_BUSINESS_RULE_DEFINITIONS = {
    ACHIEVEMENT_RULES_KEY: BusinessRuleDefinition(
        key=ACHIEVEMENT_RULES_KEY,
        domain="growth_achievement",
        schema_version=BUSINESS_RULE_SCHEMA_VERSION,
        default_value=DEFAULT_ACHIEVEMENT_RULESET,
        type="rule_json",
        range_or_allowlist={
            "condition_types": ["evaluable_session_count", "max_overall_score"],
            "score_fields": ["logic_score", "accuracy_score", "completeness_score"],
        },
        read_path="common.growth.growth_service.GrowthCenterService",
        admin_entry="/admin/business-rules/growth-achievements",
        permission="admin_publish_only",
        audit_policy="publish/rollback/disable require actor, before/after version, reason, trace_id",
        fallback_policy="use bundled default ruleset when database config is missing or invalid",
        rollback_policy="restore a prior archived/published version for this key",
    ),
    AI_COACH_RULES_KEY: BusinessRuleDefinition(
        key=AI_COACH_RULES_KEY,
        domain="ai_coach",
        schema_version=BUSINESS_RULE_SCHEMA_VERSION,
        default_value=DEFAULT_AI_COACH_RULESET,
        type="rule_json",
        range_or_allowlist={
            "score_fields": ["logic_score", "accuracy_score", "completeness_score"],
            "weak_score_threshold": {"min_exclusive": 0, "max_inclusive": 100},
        },
        read_path="common.growth.growth_service.GrowthCenterService.generate_ai_coach_notification",
        admin_entry="/admin/business-rules/ai-coach",
        permission="admin_publish_only",
        audit_policy="publish/rollback/disable require actor, before/after version, reason, trace_id",
        fallback_policy="use bundled default ruleset; disabled active config sends no notification",
        rollback_policy="restore a prior archived/published version for this key",
    ),
    NEXT_PRACTICE_RECOMMENDATION_KEY: BusinessRuleDefinition(
        key=NEXT_PRACTICE_RECOMMENDATION_KEY,
        domain="next_practice_recommendation",
        schema_version=BUSINESS_RULE_SCHEMA_VERSION,
        default_value=DEFAULT_RECOMMENDATION_RULESET,
        type="rule_json",
        range_or_allowlist={
            "score_fields": ["logic_score", "accuracy_score", "completeness_score"],
            "weak_score_threshold": {"min_exclusive": 0, "max_inclusive": 100},
        },
        read_path="common.recommendations.next_practice.NextPracticeRecommendationService",
        admin_entry="/admin/business-rules/next-practice-recommendations",
        permission="admin_publish_only",
        audit_policy="publish/rollback/disable require actor, before/after version, reason, trace_id",
        fallback_policy="use bundled default ruleset and expose ruleset_source in payload",
        rollback_policy="restore a prior archived/published version for this key",
    ),
    SALES_COMBINATION_RULES_KEY: BusinessRuleDefinition(
        key=SALES_COMBINATION_RULES_KEY,
        domain="sales_training_combinations",
        schema_version=BUSINESS_RULE_SCHEMA_VERSION,
        default_value=DEFAULT_SALES_COMBINATION_RULESET,
        type="rule_json",
        range_or_allowlist={
            "fallback_policy": ["client_default_v1", "hide_all"],
            "combination_fields": [
                "id",
                "capability",
                "role",
                "priority",
                "enabled",
                "required_agent_match",
                "required_persona_match",
            ],
        },
        read_path="common.api.business_rules.get_active_sales_combination_ruleset",
        admin_entry="/admin/business-rules/sales-combinations",
        permission="admin_publish_only",
        audit_policy="draft/validate/preview/publish/rollback require actor, before/after version, reason, trace_id",
        fallback_policy="use bundled default sales combinations when database config is missing or invalid; hide_all may intentionally expose no combinations",
        rollback_policy="restore a prior archived/published sales-combination ruleset",
    ),
    OBJECTION_LEDGER_RULES_KEY: BusinessRuleDefinition(
        key=OBJECTION_LEDGER_RULES_KEY,
        domain="sales_objection_ledger",
        schema_version=BUSINESS_RULE_SCHEMA_VERSION,
        default_value=DEFAULT_OBJECTION_LEDGER_RULESET,
        type="rule_json",
        range_or_allowlist={
            "family_fields": [
                "focus_dimension",
                "promised_proof",
                "next_expected_evidence",
                "detect_any",
                "evidence_any",
                "open_pressure_any",
                "open_pressure_requires_any",
            ],
            "score_range": {"min_inclusive": 0, "max_inclusive": 100},
        },
        read_path="sales_bot.websocket.components.objection_ledger_helpers",
        admin_entry="/admin/business-rules/objection-ledger",
        permission="admin_publish_only",
        audit_policy="draft/validate/preview/publish/rollback require actor, before/after version, reason, trace_id",
        fallback_policy="use bundled default objection-ledger ruleset when database config is missing, invalid, or disabled",
        rollback_policy="restore a prior archived/published objection-ledger ruleset",
    ),
    ROLEPLAY_SITUATION_PACKS_KEY: BusinessRuleDefinition(
        key=ROLEPLAY_SITUATION_PACKS_KEY,
        domain="roleplay_situation_packs",
        schema_version=BUSINESS_RULE_SCHEMA_VERSION,
        default_value=DEFAULT_ROLEPLAY_SITUATION_PACKS,
        type="rule_json",
        range_or_allowlist={
            "required_published_codes": [
                "first_visit",
                "follow_up",
                "proposal_review",
                "price_negotiation",
                "renewal",
                "complaint_recovery",
            ],
            "statuses": ["draft", "published", "archived"],
            "runtime_violation_actions": [
                "cancel_or_regenerate_once",
                "regenerate_once",
                "cancel_stream",
                "hard_fail",
                "mark_and_continue",
                "mark_for_report",
            ],
        },
        read_path="curriculum_practice.services.roleplay.situation_pack_repository.SituationPackRepository.from_database",
        admin_entry="/admin/curriculum-practice/roleplay-situation-packs",
        permission="config_bundle.publish",
        audit_policy="draft/validate/preview/publish/rollback require actor, before/after version, reason, trace_id",
        fallback_policy="use bundled default published packs when database config is missing or invalid; invalid pack blocks new template publish",
        rollback_policy="restore a prior archived/published roleplay situation pack bundle",
    ),
    ROLEPLAY_EVAL_RELEASE_GATE_KEY: BusinessRuleDefinition(
        key=ROLEPLAY_EVAL_RELEASE_GATE_KEY,
        domain="roleplay_eval_release_gate",
        schema_version=BUSINESS_RULE_SCHEMA_VERSION,
        default_value=DEFAULT_ROLEPLAY_EVAL_RELEASE_GATE,
        type="rule_json",
        range_or_allowlist={
            "gate_modes": ["blocking", "warn_only", "disabled"],
            "grader_modes": ["blocking", "warn_only", "disabled"],
            "artifact_retention_days": {"min_inclusive": 1, "max_inclusive": 365},
        },
        read_path="evaluation.services.roleplay_contract_eval.RoleplayEvalReleaseGateConfig",
        admin_entry="/admin/governance",
        permission="config_bundle.publish",
        audit_policy="draft/validate/preview/publish/rollback require actor, before/after version, reason, trace_id",
        fallback_policy="use bundled default: deterministic blocking, LLM grader warn_only",
        rollback_policy="restore a prior archived/published roleplay eval release gate config",
    ),
    ADMIN_SETTINGS_GENERAL_KEY: BusinessRuleDefinition(
        key=ADMIN_SETTINGS_GENERAL_KEY,
        domain="admin_settings",
        schema_version=BUSINESS_RULE_SCHEMA_VERSION,
        default_value=DEFAULT_ADMIN_GENERAL_SETTINGS,
        type="settings_json",
        range_or_allowlist={
            "default_language": ["zh-CN", "en-US"],
            "timezone": ["Asia/Shanghai", "UTC"],
            "date_format": ["YYYY-MM-DD", "MM/DD/YYYY"],
        },
        read_path="admin.api.settings.get_admin_settings_surface:general",
        admin_entry="/admin/settings?tab=general",
        permission="admin_settings_manage",
        audit_policy="draft/validate/preview/publish/rollback require actor, before/after version, reason, trace_id",
        fallback_policy="use bundled safe defaults when database settings are missing or invalid",
        rollback_policy="restore a prior archived/published general settings version",
    ),
    ADMIN_SETTINGS_SECURITY_KEY: BusinessRuleDefinition(
        key=ADMIN_SETTINGS_SECURITY_KEY,
        domain="admin_settings",
        schema_version=BUSINESS_RULE_SCHEMA_VERSION,
        default_value=DEFAULT_ADMIN_SECURITY_SETTINGS,
        type="settings_json",
        range_or_allowlist={
            "password_min_length": {"min_inclusive": 8, "max_inclusive": 128},
            "password_expiry_days": {"min_inclusive": 0, "max_inclusive": 365},
        },
        read_path="admin.api.settings.get_admin_settings_surface:security",
        admin_entry="/admin/settings?tab=security",
        permission="admin_settings_manage",
        audit_policy="draft/validate/preview/publish/rollback require actor, before/after version, reason, trace_id",
        fallback_policy="use bundled safe defaults; security runtime baselines stay code-owned until explicitly wired",
        rollback_policy="restore a prior archived/published security settings version",
    ),
    ADMIN_SETTINGS_NOTIFICATIONS_KEY: BusinessRuleDefinition(
        key=ADMIN_SETTINGS_NOTIFICATIONS_KEY,
        domain="admin_settings",
        schema_version=BUSINESS_RULE_SCHEMA_VERSION,
        default_value=DEFAULT_ADMIN_NOTIFICATION_SETTINGS,
        type="settings_json",
        range_or_allowlist={
            "email_notifications": [
                "user_registration_admin",
                "system_exception_alert",
                "weekly_report",
                "knowledge_base_update",
            ],
        },
        read_path="admin.api.settings.get_admin_settings_surface:notifications",
        admin_entry="/admin/settings?tab=notifications",
        permission="admin_settings_manage",
        audit_policy="draft/validate/preview/publish/rollback require actor, before/after version, reason, trace_id",
        fallback_policy="use bundled defaults; disabled active config prevents notification automation from enabling new sends",
        rollback_policy="restore a prior archived/published notification settings version",
    ),
    SALES_TRAINER_PHASE2_CLOSED_LOOP_POLICY_KEY: BusinessRuleDefinition(
        key=SALES_TRAINER_PHASE2_CLOSED_LOOP_POLICY_KEY,
        domain="sales_trainer",
        schema_version=BUSINESS_RULE_SCHEMA_VERSION,
        default_value=DEFAULT_SALES_TRAINER_PHASE2_POLICY,
        type="rule_json",
        range_or_allowlist={
            "low_score_threshold": {"min_inclusive": 0, "max_inclusive": 100},
            "repeat_practice_threshold": {"min_inclusive": 1, "max_inclusive": 20},
            "dashboard_record_limit": {"min_inclusive": 1, "max_inclusive": 5000},
            "manager_action_codes": [
                "not_passed",
                "low_score",
                "repeated_practice",
                "fallback",
            ],
            "remediation_record_types": [
                "audio_submission",
                "quiz_attempt",
                "business_etiquette_quiz_attempt",
                "ai_coach_session",
                "default",
                "no_action",
            ],
        },
        read_path="sales_trainer.services.phase2_policy.resolve_phase2_policy",
        admin_entry="/admin/business-rules/sales-trainer-phase2",
        permission="admin_publish_only",
        audit_policy="draft/validate/preview/publish/rollback require actor, before/after version, reason, trace_id",
        fallback_policy="use bundled default phase-2 policy when database config is missing, invalid, or disabled",
        rollback_policy="restore a prior archived/published phase-2 policy version",
    ),
    SALES_TRAINER_LEARNER_LEVEL_POLICY_KEY: BusinessRuleDefinition(
        key=SALES_TRAINER_LEARNER_LEVEL_POLICY_KEY,
        domain="sales_trainer",
        schema_version=BUSINESS_RULE_SCHEMA_VERSION,
        default_value=DEFAULT_SALES_TRAINER_LEARNER_LEVEL_POLICY,
        type="rule_json",
        range_or_allowlist={
            "level_key": "admin-defined stable string",
            "condition_fields": [
                "training_stage_in",
                "department_in",
                "min_pass_rate",
                "max_pass_rate",
                "min_completed_modules",
                "min_passed_modules",
                "max_failed_modules",
            ],
        },
        read_path="sales_trainer.services.training_journey_service.TrainingJourneyService._learner_level",
        admin_entry="/admin/business-rules/sales-trainer-learner-level",
        permission="admin_publish_only",
        audit_policy="draft/validate/preview/publish/rollback require actor, before/after version, reason, trace_id",
        fallback_policy="use bundled unassigned level when database config is missing, invalid, or disabled; expose fallback_applied/fallback_reason",
        rollback_policy="restore a prior archived/published learner-level policy version",
    ),
    SALES_TRAINER_ROLE_LEVEL_POLICY_KEY: BusinessRuleDefinition(
        key=SALES_TRAINER_ROLE_LEVEL_POLICY_KEY,
        domain="sales_trainer",
        schema_version=BUSINESS_RULE_SCHEMA_VERSION,
        default_value=DEFAULT_SALES_TRAINER_ROLE_LEVEL_POLICY,
        type="rule_json",
        range_or_allowlist={
            "level_key": "admin-defined stable string",
            "condition_fields": [
                "role_in",
                "department_in",
                "training_stage_in",
                "min_pass_rate",
                "max_pass_rate",
                "min_completed_modules",
                "min_passed_modules",
                "max_failed_modules",
            ],
        },
        read_path="sales_trainer.services.training_journey_service.TrainingJourneyService._role_level",
        admin_entry="/admin/business-rules/sales-trainer-role-level",
        permission="admin_publish_only",
        audit_policy="draft/validate/preview/publish/rollback require actor, before/after version, reason, trace_id",
        fallback_policy="use bundled learner level when database config is missing, invalid, or disabled; expose fallback_applied/fallback_reason",
        rollback_policy="restore a prior archived/published role-level policy version",
    ),
    SALES_TRAINER_REALTIME_PROVIDER_REGISTRY_KEY: BusinessRuleDefinition(
        key=SALES_TRAINER_REALTIME_PROVIDER_REGISTRY_KEY,
        domain="sales_trainer",
        schema_version=BUSINESS_RULE_SCHEMA_VERSION,
        default_value=DEFAULT_SALES_TRAINER_REALTIME_PROVIDER_REGISTRY,
        type="rule_json",
        range_or_allowlist={
            "descriptor_id": "stable runtime descriptor id referenced by path runtime_binding",
            "provider": ["stepfun_realtime", "phase4_local_stepfun", "mock"],
            "runtime_owner": ["training_runtime", "sales_bot"],
        },
        read_path="sales_trainer.services.realtime_roleplay_start_service.RealtimeRoleplayStartService.start",
        admin_entry="/admin/config-bundles/sales_trainer.realtime_provider.registry",
        permission="admin_publish_only",
        audit_policy="draft/validate/preview/publish/rollback/disable require actor, before/after version, reason, trace_id",
        fallback_policy="default registry is disabled and fails closed when database config is missing, invalid, or disabled",
        rollback_policy="restore a prior published realtime provider registry version through ConfigBundleLifecycleService.rollback",
    ),
}


def get_business_rule_definition(key: str) -> BusinessRuleDefinition:
    try:
        return _BUSINESS_RULE_DEFINITIONS[key]
    except KeyError as exc:
        raise KeyError(f"Unsupported business rule key: {key}") from exc


def get_default_business_rule_value(key: str) -> dict[str, Any]:
    return deepcopy(get_business_rule_definition(key).default_value)


def list_business_rule_definitions() -> list[BusinessRuleDefinition]:
    return list(_BUSINESS_RULE_DEFINITIONS.values())


def supported_business_rule_keys() -> set[str]:
    return set(_BUSINESS_RULE_DEFINITIONS)
