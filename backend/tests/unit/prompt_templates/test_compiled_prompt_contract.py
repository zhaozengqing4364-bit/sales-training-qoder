from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from prompt_templates.models import PromptTemplate, PromptType
from prompt_templates.service import PromptTemplateService


class _StubConfigManager:
    def get_effective_config(self, model_type):
        return {
            "provider": "openai",
            "model_name": "gpt-4o",
            "base_url": "https://api.openai.com/v1",
        }

    def describe_runtime_policy(self, model_type, config=None):
        return {
            "provider": "openai",
            "model_name": "gpt-4o",
            "base_url": "https://api.openai.com/v1",
            "base_url_required": True,
            "base_url_status": "configured",
        }


def _build_prompt_template(template: str, *, prompt_type: PromptType = PromptType.REPORT) -> PromptTemplate:
    now = datetime.now(UTC)
    return PromptTemplate(
        id=uuid4(),
        name="Runtime Prompt",
        prompt_type=prompt_type,
        category="sales",
        template=template,
        variables=[],
        is_active=True,
        is_default=True,
        is_system=False,
        created_at=now,
        updated_at=now,
    )


def test_compile_runtime_prompt_contract_includes_hash_runtime_consumer_and_base_url_policy(monkeypatch):
    service = PromptTemplateService(db_session=None)
    template = _build_prompt_template(
        "请基于以下内容生成反馈：{{ overall_summary }}",
    )

    monkeypatch.setattr(
        "prompt_templates.service.get_config_manager",
        lambda: _StubConfigManager(),
    )

    result = service.compile_runtime_prompt_contract(
        template=template,
        variables={"overall_summary": "客户价值表达不足"},
        runtime_consumer="evaluation.services.comprehensive_report.ComprehensiveReportService._generate_detailed_feedback",
        system_message="你是销售教练。",
    )

    assert result.is_success
    contract = result.value
    assert contract.prompt_source == "prompt_template_service"
    assert contract.runtime_consumer.endswith("_generate_detailed_feedback")
    assert contract.rendered_prompt == "请基于以下内容生成反馈：客户价值表达不足"
    assert contract.system_message == "你是销售教练。"
    assert isinstance(contract.contract_hash, str)
    assert len(contract.contract_hash) == 16
    assert contract.base_url_policy == "required_configured"
    assert {item.code for item in contract.diagnostics} >= {"PROMPT_TEMPLATE_RENDERED", "LLM_BASE_URL_POLICY"}


def test_compile_runtime_prompt_contract_fails_closed_on_missing_variables(monkeypatch):
    service = PromptTemplateService(db_session=None)
    template = _build_prompt_template(
        "阶段：{{ stage_name }}\n对话：{{ conversation }}",
        prompt_type=PromptType.STAGE,
    )

    monkeypatch.setattr(
        "prompt_templates.service.get_config_manager",
        lambda: _StubConfigManager(),
    )

    result = service.compile_runtime_prompt_contract(
        template=template,
        variables={"stage_name": "开场"},
        runtime_consumer="evaluation.services.staged_evaluation.StagedEvaluationService.evaluate_stage",
        system_message="你是评估专家。",
    )

    assert not result.is_success
    assert "PROMPT_CONTRACT_MISSING_VARIABLES" in (result.fallback or "")
