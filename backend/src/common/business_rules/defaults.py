"""Default contracts for governed business-rule configuration."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

ACHIEVEMENT_RULES_KEY = "growth.achievement.rules"
AI_COACH_RULES_KEY = "growth.ai_coach.rules"
NEXT_PRACTICE_RECOMMENDATION_KEY = "recommendation.next_practice.ruleset"
SALES_COMBINATION_RULES_KEY = "sales.training.combinations.ruleset"
OBJECTION_LEDGER_RULES_KEY = "sales.objection_ledger.ruleset"
ADMIN_SETTINGS_GENERAL_KEY = "admin.settings.general"
ADMIN_SETTINGS_SECURITY_KEY = "admin.settings.security"
ADMIN_SETTINGS_NOTIFICATIONS_KEY = "admin.settings.notifications"

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
