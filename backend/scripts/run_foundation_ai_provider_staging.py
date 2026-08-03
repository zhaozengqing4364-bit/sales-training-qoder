#!/usr/bin/env python3
"""Run the Foundation AI gold set through a controlled real LLM provider."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ai_platform import (
    BudgetScope,
    DataClassification,
    GovernedAIInvocationService,
    GovernedAIRequest,
    InMemoryAIInvocationStore,
    OpenAICompatibleProvider,
    OpenAICompatibleProviderSettings,
    PromptCompilationService,
    PromptPreviewRequest,
    PublishedModelRoutingProfileSnapshot,
    PublishedPromptRevisionSnapshot,
    StaticPublishedModelRoutingProfileResolver,
    StaticPublishedPromptRevisionResolver,
    StrictPromptCompiler,
    compute_prompt_revision_content_hash,
)
from ai_platform.schemas import OutputSchemaRegistry
from common.ai.endpoint_policy import EndpointPolicyError, validate_provider_base_url
from common.ai.models import ModelProvider
from foundation_ai_quality import (
    DEFAULT_FOUNDATION_AI_GOLD_SET,
    FOUNDATION_AI_OUTPUT_SCHEMA_MODELS,
    FoundationAIQualityCase,
    FoundationAIQualityManifest,
    evaluate_foundation_ai_quality,
    load_foundation_ai_quality_manifest,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EVIDENCE_PATH = (
    REPO_ROOT / ".sisyphus/evidence/foundation-ai-real-provider-staging.json"
)
STAGING_INPUT_SCHEMA = "foundation-ai-provider-staging-input-v1"
STAGING_RUNTIME_CONSUMER = "foundation.ai-quality.staging.v1"


class FoundationAIProviderStagingInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str = Field(min_length=1, max_length=160)
    instruction: str = Field(min_length=1, max_length=20_000)
    allowed_evidence_refs: tuple[str, ...] = Field(max_length=500)
    transcript: str | None = Field(default=None, max_length=1_000_000)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_FOUNDATION_AI_GOLD_SET)
    parser.add_argument("--output", type=Path, default=DEFAULT_EVIDENCE_PATH)
    parser.add_argument(
        "--repeat-count",
        type=int,
        default=int(os.getenv("FOUNDATION_AI_STAGING_REPEAT_COUNT", "2")),
    )
    parser.add_argument(
        "--max-total-cost-minor-units",
        type=int,
        default=int(
            os.getenv("FOUNDATION_AI_STAGING_MAX_TOTAL_COST_MINOR_UNITS", "500")
        ),
    )
    return parser.parse_args()


def _required_environment() -> dict[str, Any]:
    if os.getenv("FOUNDATION_AI_REAL_PROVIDER_CONFIRM", "0") != "1":
        raise RuntimeError(
            "真实 Provider 门禁需要显式设置 FOUNDATION_AI_REAL_PROVIDER_CONFIRM=1。"
        )
    provider_value = os.getenv("LLM_PROVIDER", "openai").strip().lower()
    try:
        provider = ModelProvider(provider_value)
    except ValueError as exc:
        raise RuntimeError("LLM_PROVIDER 不是受支持的 OpenAI-compatible Provider。") from exc
    if provider not in {ModelProvider.OPENAI, ModelProvider.ALIBABA}:
        raise RuntimeError("真实 Provider 门禁只支持 openai 或 alibaba。")
    api_key = (os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip()
    base_url = (os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL") or "").strip()
    model = (os.getenv("LLM_MODEL") or os.getenv("OPENAI_MODEL") or "").strip()
    if not api_key or not base_url or not model:
        raise RuntimeError("真实 Provider 门禁需要 LLM_API_KEY、LLM_BASE_URL 和 LLM_MODEL。")
    try:
        endpoint = validate_provider_base_url(provider, base_url, resolve_dns=False)
    except EndpointPolicyError as exc:
        raise RuntimeError("真实 Provider Endpoint 未通过安全策略。") from exc
    return {
        "provider": provider.value,
        "api_key": api_key,
        "base_url": endpoint.base_url,
        "model": model,
        "currency": os.getenv("LLM_CURRENCY", "CNY").strip().upper(),
        "input_cost": int(
            os.getenv("LLM_INPUT_COST_MINOR_UNITS_PER_MILLION", "0")
        ),
        "output_cost": int(
            os.getenv("LLM_OUTPUT_COST_MINOR_UNITS_PER_MILLION", "0")
        ),
        "timeout_seconds": int(os.getenv("LLM_TIMEOUT_SECONDS", "60")),
        "max_output_tokens": int(os.getenv("LLM_MAX_TOKENS", "2500")),
    }


def _prompt_variables(case: FoundationAIQualityCase) -> dict[str, Any]:
    output_schema = FOUNDATION_AI_OUTPUT_SCHEMA_MODELS[case.output_schema_version]
    return {
        "instruction": case.instruction,
        "allowed_evidence_refs_json": json.dumps(
            list(case.allowed_evidence_refs),
            ensure_ascii=False,
        ),
        "transcript": case.transcript or "（本用例无转写）",
        "required_phrases_json": json.dumps(
            list(case.required_phrases),
            ensure_ascii=False,
        ),
        "forbidden_phrases_json": json.dumps(
            list(case.forbidden_phrases),
            ensure_ascii=False,
        ),
        "output_schema_json": json.dumps(
            output_schema.model_json_schema(),
            ensure_ascii=False,
            sort_keys=True,
        ),
    }


def _prompt_revision(case: FoundationAIQualityCase) -> PublishedPromptRevisionSnapshot:
    template = (
        "你正在执行新人销售基础训练的受控质量评估。\n"
        "任务：{{ instruction }}\n"
        "仅可使用这些证据标识：{{ allowed_evidence_refs_json }}\n"
        "转写或上下文：{{ transcript }}\n"
        "结果中必须逐字、原样包含这些短语至少一次（如列表为空则忽略）："
        "{{ required_phrases_json }}\n"
        "结果中禁止包含这些短语（如列表为空则忽略）：{{ forbidden_phrases_json }}\n"
        "若任务要求依据，所有依据数组都必须非空，且不得使用允许列表之外的标识。"
        "Coach 回答评估的 evidence_from_answer 必须引用任务中给出的学员回答原文。\n"
        "只返回一个符合以下 JSON Schema 的 JSON 对象，不要 Markdown："
        "{{ output_schema_json }}"
    )
    variables = (
        "instruction",
        "allowed_evidence_refs_json",
        "transcript",
        "required_phrases_json",
        "forbidden_phrases_json",
        "output_schema_json",
    )
    return PublishedPromptRevisionSnapshot(
        template_id=case.prompt_template_id,
        business_purpose=case.business_purpose,
        revision_id=case.prompt_revision_id,
        revision_no=1,
        status="published",
        template=template,
        variables=variables,
        input_schema_version=STAGING_INPUT_SCHEMA,
        output_schema_version=case.output_schema_version,
        content_hash=compute_prompt_revision_content_hash(
            template_id=case.prompt_template_id,
            business_purpose=case.business_purpose,
            revision_id=case.prompt_revision_id,
            revision_no=1,
            template=template,
            variables=variables,
            input_schema_version=STAGING_INPUT_SCHEMA,
            output_schema_version=case.output_schema_version,
        ),
    )


def _routing_profile(
    case: FoundationAIQualityCase,
    *,
    config: dict[str, Any],
) -> PublishedModelRoutingProfileSnapshot:
    profile_id = f"foundation-ai-staging-{case.capability}"
    return PublishedModelRoutingProfileSnapshot(
        profile_id=profile_id,
        business_purpose=case.business_purpose,
        revision_id=f"{profile_id}-v1",
        revision_no=1,
        status="published",
        provider=str(config["provider"]),
        model=str(config["model"]),
        temperature=0,
        max_output_tokens=int(config["max_output_tokens"]),
        timeout_seconds=int(config["timeout_seconds"]),
        timeout_policy_ref="foundation-ai-staging-timeout-v1",
        max_provider_retries=1,
        max_schema_retries=1,
        retry_policy_ref="foundation-ai-staging-retry-v1",
        requests_per_minute=120,
        rate_limit_scopes=(BudgetScope.ORGANIZATION,),
        budget_scope=BudgetScope.ORGANIZATION,
        budget_limit_minor_units=1_000_000,
        budget_reservation_minor_units=1,
        budget_window_seconds=3600,
        currency=str(config["currency"]),
        circuit_failure_threshold=3,
        circuit_recovery_seconds=30,
        calibrated_for_formal_scoring=case.formal_scoring,
        allowed_data_classifications=(DataClassification.INTERNAL,),
    )


async def run_staging(
    *,
    manifest: FoundationAIQualityManifest,
    config: dict[str, Any],
    repeat_count: int,
    max_total_cost_minor_units: int,
) -> dict[str, Any]:
    if repeat_count < 1 or repeat_count > 5:
        raise RuntimeError("repeat-count 必须在 1 到 5 之间。")
    if max_total_cost_minor_units < 0:
        raise RuntimeError("成本上限不能为负数。")
    cases = [case for case in manifest.cases if case.expected_behavior == "accept"]
    prompts = [_prompt_revision(case) for case in cases]
    profiles = [_routing_profile(case, config=config) for case in cases]
    prompt_resolver = StaticPublishedPromptRevisionResolver(prompts)
    schemas = OutputSchemaRegistry()
    schemas.register_input(STAGING_INPUT_SCHEMA, FoundationAIProviderStagingInput)
    for version, schema in FOUNDATION_AI_OUTPUT_SCHEMA_MODELS.items():
        schemas.register_output(version, schema)
    provider = OpenAICompatibleProvider(
        OpenAICompatibleProviderSettings(
            provider=str(config["provider"]),
            base_url=str(config["base_url"]),
            api_key=str(config["api_key"]),
            currency=str(config["currency"]),
            input_cost_minor_units_per_million=int(config["input_cost"]),
            output_cost_minor_units_per_million=int(config["output_cost"]),
        )
    )
    compiler = StrictPromptCompiler()
    service = GovernedAIInvocationService(
        prompt_resolver=prompt_resolver,
        routing_resolver=StaticPublishedModelRoutingProfileResolver(profiles),
        compiler=compiler,
        schemas=schemas,
        providers={str(config["provider"]): provider},
        store=InMemoryAIInvocationStore(),
    )
    outputs: dict[str, list[dict[str, Any]]] = {case.case_id: [] for case in cases}
    invocations: list[dict[str, Any]] = []
    invocation_failures: list[str] = []
    actual_cost = 0
    for case, prompt, profile in zip(cases, prompts, profiles, strict=True):
        variables = _prompt_variables(case)
        compiled = await PromptCompilationService(
            resolver=prompt_resolver,
            compiler=compiler,
        ).preview(
            PromptPreviewRequest(
                template_id=prompt.template_id,
                revision_id=prompt.revision_id,
                business_purpose=prompt.business_purpose,
                input_schema_version=STAGING_INPUT_SCHEMA,
                output_schema_version=case.output_schema_version,
                variables=variables,
                runtime_consumer=STAGING_RUNTIME_CONSUMER,
                model_routing_revision_id=profile.revision_id,
            )
        )
        for repeat_index in range(repeat_count):
            result = await service.invoke(
                GovernedAIRequest(
                    business_purpose=case.business_purpose,
                    organization_id="foundation-ai-staging",
                    actor_id="quality-gate",
                    object_type="foundation_ai_gold_case",
                    object_id=case.case_id,
                    prompt_template_id=prompt.template_id,
                    prompt_revision_id=prompt.revision_id,
                    prompt_contract_hash=compiled.contract_hash,
                    model_routing_profile_id=profile.profile_id,
                    model_routing_revision_id=profile.revision_id,
                    input_schema_version=STAGING_INPUT_SCHEMA,
                    output_schema_version=case.output_schema_version,
                    input_payload={
                        "case_id": case.case_id,
                        "instruction": case.instruction,
                        "allowed_evidence_refs": list(case.allowed_evidence_refs),
                        "transcript": case.transcript,
                    },
                    prompt_variables=variables,
                    idempotency_key=f"{case.case_id}:provider-staging:{repeat_index}",
                    data_classification=DataClassification.INTERNAL,
                    trace_id=f"foundation-ai-staging-{case.case_id}-{repeat_index}",
                    correlation_id=case.case_id,
                    causation_id=case.prompt_revision_id,
                    runtime_consumer=STAGING_RUNTIME_CONSUMER,
                    timeout_policy_ref=profile.timeout_policy_ref,
                    retry_policy_ref=profile.retry_policy_ref,
                    budget_scope=BudgetScope.ORGANIZATION,
                    formal_scoring=case.formal_scoring,
                    allow_fallback=False,
                )
            )
            actual_cost += result.usage.cost_minor_units
            invocation = {
                "case_id": case.case_id,
                "repeat_index": repeat_index,
                "invocation_id": result.invocation_id,
                "status": result.status.value,
                "provider": result.provider,
                "model": result.model,
                "latency_ms": result.latency_ms,
                "usage": result.usage.model_dump(mode="json"),
                "output_sha256": (
                    _hash(result.validated_output)
                    if result.validated_output is not None
                    else None
                ),
                "failure_code": result.failure.code if result.failure else None,
            }
            invocations.append(invocation)
            if result.validated_output is None:
                invocation_failures.append(
                    f"{case.case_id}:{result.failure.code if result.failure else 'missing_output'}"
                )
            else:
                outputs[case.case_id].append(result.validated_output)

    report: dict[str, Any] = {
        "contract_version": "foundation_ai_provider_staging_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "provider": str(config["provider"]),
        "model": str(config["model"]),
        "base_url_configured": True,
        "repeat_count": repeat_count,
        "actual_total_cost_minor_units": actual_cost,
        "currency": str(config["currency"]),
        "invocations": invocations,
    }
    if invocation_failures:
        report.update(status="failed", gate_failures=invocation_failures)
        return report

    raw = manifest.model_dump(mode="json")
    raw["thresholds"]["maximum_total_cost_minor_units"] = (
        max_total_cost_minor_units
    )
    for raw_case in raw["cases"]:
        if raw_case["expected_behavior"] != "accept":
            continue
        observed = outputs[str(raw_case["case_id"])]
        raw_case["output"] = observed[0]
        raw_case["repeat_outputs"] = observed[1:]
        usage_rows = [
            item["usage"]
            for item in invocations
            if item["case_id"] == raw_case["case_id"]
        ]
        raw_case["usage"] = {
            "input_tokens": sum(int(item["input_tokens"]) for item in usage_rows),
            "output_tokens": sum(int(item["output_tokens"]) for item in usage_rows),
            "cost_minor_units": sum(
                int(item["cost_minor_units"]) for item in usage_rows
            ),
            "currency": str(config["currency"]),
        }
        raw_case["max_cost_minor_units"] = max_total_cost_minor_units
    quality = evaluate_foundation_ai_quality(
        FoundationAIQualityManifest.model_validate(raw)
    )
    report["quality"] = quality
    report["status"] = quality["status"]
    report["gate_failures"] = quality["gate_failures"]
    return report


def _hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


async def _main() -> int:
    args = parse_args()
    try:
        config = _required_environment()
        report = await run_staging(
            manifest=load_foundation_ai_quality_manifest(args.manifest),
            config=config,
            repeat_count=args.repeat_count,
            max_total_cost_minor_units=args.max_total_cost_minor_units,
        )
    except (RuntimeError, ValueError) as exc:
        report = {
            "contract_version": "foundation_ai_provider_staging_v1",
            "status": "failed",
            "classification": "configuration_error",
            "reason": str(exc),
            "generated_at": datetime.now(UTC).isoformat(),
        }
    serialized = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(serialized, encoding="utf-8")
    print(serialized, end="")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
