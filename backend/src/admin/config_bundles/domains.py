"""Domain registry for Admin Config Center information architecture."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DomainLegacyPage:
    """A legacy admin page still in use for a domain."""

    path: str
    label: str


@dataclass(frozen=True)
class DomainInfo:
    """Information architecture entry for one config domain."""

    domain: str
    display_name: str
    description: str
    migration_status: str  # "not_started" | "read_only" | "versioned" | "fully_migrated"
    legacy_pages: list[DomainLegacyPage]
    bundles: list[str]
    active_version_summary: dict[str, Any] | None = field(default=None)


DOMAIN_REGISTRY: list[DomainInfo] = [
    DomainInfo(
        domain="training_content",
        display_name="训练内容",
        description="训练场景、客户角色、PPT 演练内容管理。",
        migration_status="not_started",
        legacy_pages=[
            DomainLegacyPage(path="/admin/agents", label="智能体管理"),
            DomainLegacyPage(path="/admin/personas", label="角色管理"),
            DomainLegacyPage(path="/admin/presentations", label="PPT 演练管理"),
        ],
        bundles=[],
    ),
    DomainInfo(
        domain="customer_simulation",
        display_name="客户模拟",
        description="对话策略、模拟参数、追问配置。",
        migration_status="not_started",
        legacy_pages=[
            DomainLegacyPage(path="/admin/prompts", label="提示词管理"),
        ],
        bundles=[],
    ),
    DomainInfo(
        domain="scoring",
        display_name="评分",
        description="评分规则集、权重、不可评估原因定义。",
        migration_status="read_only",
        legacy_pages=[
            DomainLegacyPage(path="/admin/scoring-rulesets", label="评分规则集"),
        ],
        bundles=["scoring.rulesets"],
    ),
    DomainInfo(
        domain="business_rules",
        display_name="业务规则",
        description="销售组合规则、异议台账、成就徽章、AI 教练、练后推荐等业务配置。",
        migration_status="read_only",
        legacy_pages=[
            DomainLegacyPage(
                path="/admin/business-rules/sales-combinations",
                label="销售训练组合规则",
            ),
            DomainLegacyPage(
                path="/admin/business-rules/growth-achievements",
                label="成就徽章规则",
            ),
            DomainLegacyPage(
                path="/admin/business-rules/ai-coach",
                label="AI 教练规则",
            ),
            DomainLegacyPage(
                path="/admin/business-rules/next-practice-recommendations",
                label="练后推荐规则",
            ),
            DomainLegacyPage(
                path="/admin/business-rules/objection-ledger",
                label="异议台账规则",
            ),
        ],
        bundles=["sales.training.combinations.ruleset"],
    ),
    DomainInfo(
        domain="ai_analysis",
        display_name="AI 分析",
        description="提示词模板、RAG profile、AI 推理配置。",
        migration_status="not_started",
        legacy_pages=[
            DomainLegacyPage(path="/admin/prompts", label="提示词管理"),
            DomainLegacyPage(path="/admin/retrieval-strategies", label="检索策略"),
            DomainLegacyPage(path="/admin/knowledge", label="知识库管理"),
        ],
        bundles=[],
    ),
    DomainInfo(
        domain="model_and_voice",
        display_name="模型与语音",
        description="LLM 模型配置、语音策略、PPT AI 配置。",
        migration_status="not_started",
        legacy_pages=[
            DomainLegacyPage(path="/admin/voice-runtime", label="语音策略"),
            DomainLegacyPage(path="/admin/presentation-ai", label="PPT AI 策略"),
        ],
        bundles=[],
    ),
    DomainInfo(
        domain="knowledge_rag",
        display_name="知识库与 RAG",
        description="知识库管理、检索策略、RAG 配置。",
        migration_status="not_started",
        legacy_pages=[
            DomainLegacyPage(path="/admin/knowledge", label="知识库管理"),
            DomainLegacyPage(path="/admin/retrieval-strategies", label="检索策略"),
        ],
        bundles=[],
    ),
    DomainInfo(
        domain="report_rules",
        display_name="报告规则",
        description="训练报告生成规则、快照口径定义。",
        migration_status="not_started",
        legacy_pages=[],
        bundles=[],
    ),
    DomainInfo(
        domain="release_governance",
        display_name="发布治理",
        description="配置版本发布、回滚、审批流程与审计迹。",
        migration_status="not_started",
        legacy_pages=[
            DomainLegacyPage(path="/admin/governance", label="治理矩阵"),
        ],
        bundles=[],
    ),
    DomainInfo(
        domain="audit",
        display_name="审计追踪",
        description="统一审计日志、配置变更追踪。",
        migration_status="not_started",
        legacy_pages=[
            DomainLegacyPage(path="/admin/logs", label="操作日志"),
        ],
        bundles=[],
    ),
]
