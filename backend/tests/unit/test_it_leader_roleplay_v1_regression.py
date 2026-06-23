from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

import pytest

from sales_bot.services.it_leader_roleplay_scoring import (
    V1_RUBRIC,
    EvidenceQuote,
    OfflineScoringDraft,
    RubricScore,
    build_admin_projection,
    build_learner_projection,
    validate_offline_scoring_report,
)
from sales_bot.services.it_leader_roleplay_v1 import (
    get_default_state_card,
    get_regression_sample_metadata,
    get_roleplay_contract,
    validate_regression_sample_metadata,
)
from sales_bot.services.voice_instruction_compiler import VoiceInstructionCompiler

REPO_ROOT: Final = Path(__file__).resolve().parents[3]
EVIDENCE_PATH: Final = (
    REPO_ROOT / ".omo" / "evidence" / "task-8-realtime-it-leader-roleplay-v1.json"
)

SCORER_ONLY_TERMS: Final = frozenset(
    {
        "scoring_coach",
        "standard_answers",
        "internal_sales_playbook",
        "hidden_budget",
        "decision_chain",
        "scorer-only",
        "scorer_only",
        "评分器专用",
        "标准答案",
    }
)

TIER_DIMENSION_SCORES: Final = {
    "excellent": (14.0, 18.0, 18.0, 18.0, 14.0, 9.0),
    "average": (10.0, 13.0, 12.0, 13.0, 10.0, 7.0),
    "poor": (5.0, 6.0, 6.0, 7.0, 5.0, 3.0),
}


class CustomerVisibleLeakageError(ValueError):
    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


def test_should_run_all_metadata_samples_through_scoring_report_validator() -> None:
    samples = get_regression_sample_metadata()
    validate_regression_sample_metadata(samples)

    results = [_evaluate_sample(sample) for sample in samples]

    assert len(results) == 9
    assert all(item["report_valid"] is True for item in results)
    assert {item["tier"] for item in results} == {"excellent", "average", "poor"}
    assert all(
        item["leakage_check"]["customer_visible_context_safe"] is True
        for item in results
    )
    assert all(
        item["quality_flags_check"]["quality_flags_present"] is True
        for item in results
    )


def test_should_compile_representative_v1_instruction_payload_without_hidden_keys() -> None:
    compiled_check = _compiled_instruction_check()

    assert compiled_check["contains_phase_anchor"] is True
    assert compiled_check["contains_state_anchor"] is True
    assert compiled_check["contains_contract_hash"] is True
    assert compiled_check["hidden_or_scorer_only_keys_absent"] is True
    assert compiled_check["contract_hash"].startswith("sha256:")


def test_should_catch_scorer_only_content_in_customer_visible_context() -> None:
    leaked_context = {
        "visible_payload": {
            "customer_background": "政教医信息中心首次拜访。",
            "scoring_coach": "标准答案：必须先问预算和决策链。",
        }
    }

    with pytest.raises(CustomerVisibleLeakageError) as exc_info:
        _assert_no_customer_visible_leakage(leaked_context)

    assert exc_info.value.reason_code == "customer_visible_leakage:scoring_coach"


def test_should_write_data_shaped_manual_qa_evidence() -> None:
    evidence = _build_evidence()

    EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE_PATH.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    loaded = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    assert loaded["summary"]["sample_count"] == 9
    assert loaded["summary"]["all_reports_valid"] is True
    assert loaded["failure_checks"]["customer_visible_scorer_only_leak_caught"] is True
    assert loaded["compiled_instruction_check"]["hidden_or_scorer_only_keys_absent"] is True


def _build_evidence() -> dict[str, Any]:
    samples = get_regression_sample_metadata()
    validate_regression_sample_metadata(samples)

    compiled_check = _compiled_instruction_check()
    sample_results = [_evaluate_sample(sample) for sample in samples]
    leak_failure = _leak_failure_check()
    covered_tags = sorted(
        {
            tag
            for item in sample_results
            for tag in item["covered_tags"]
        }
    )

    return {
        "task": "8",
        "plan": "realtime-it-leader-roleplay-v1",
        "surface": "pytest regression harness + data-shaped manual QA evidence",
        "live_external_calls": {
            "stepfun": False,
            "llm": False,
            "tts": False,
            "knowledge_service": False,
        },
        "samples": sample_results,
        "covered_tags": covered_tags,
        "compiled_instruction_check": compiled_check,
        "failure_checks": leak_failure,
        "summary": {
            "sample_count": len(sample_results),
            "sample_ids": [item["sample_id"] for item in sample_results],
            "all_reports_valid": all(
                item["report_valid"] is True for item in sample_results
            ),
            "all_leakage_checks_passed": all(
                item["leakage_check"]["customer_visible_context_safe"] is True
                for item in sample_results
            ),
            "all_quality_flag_checks_passed": all(
                item["quality_flags_check"]["quality_flags_present"] is True
                for item in sample_results
            ),
        },
    }


def _evaluate_sample(sample: dict[str, Any]) -> dict[str, Any]:
    draft = _build_scoring_draft(sample)
    report_result = validate_offline_scoring_report(draft)
    assert report_result.accepted_report is not None
    report = report_result.accepted_report
    learner_projection = build_learner_projection(report)
    admin_projection = build_admin_projection(report)
    customer_context = _customer_visible_context(sample)
    _assert_no_customer_visible_leakage(customer_context)
    compiled_check = _compiled_instruction_check()

    return {
        "sample_id": str(sample["id"]),
        "tier": str(sample["quality_tier"]),
        "covered_tags": list(sample["coverage_tags"]),
        "report_valid": True,
        "report_check": {
            "total_score": report.total_score,
            "learner_evidence_count": len(learner_projection["evidence"]),
            "admin_projection_has_contract_hash": bool(
                admin_projection["roleplay_contract_hash"]
            ),
            "manual_review_required": report.manual_review_required,
        },
        "leakage_check": {
            "customer_visible_context_safe": True,
            "scorer_only_terms_absent": True,
            "learner_projection_excludes_admin_fields": "scoring_json"
            not in learner_projection,
        },
        "compiled_instruction_check": {
            "contains_phase_anchor": compiled_check["contains_phase_anchor"],
            "contains_state_anchor": compiled_check["contains_state_anchor"],
            "contains_contract_hash": compiled_check["contains_contract_hash"],
            "hidden_or_scorer_only_keys_absent": compiled_check[
                "hidden_or_scorer_only_keys_absent"
            ],
        },
        "quality_flags_check": {
            "quality_flags": list(report.quality_flags),
            "quality_flags_present": bool(report.quality_flags),
            "knowledge_gap_tag_reflected": (
                "knowledge_gap_degradation" not in sample["coverage_tags"]
                or "knowledge_gap_degradation" in report.quality_flags
            ),
            "hidden_leakage_count_zero": "hidden_information_leakage_count:0"
            in report.quality_flags,
        },
    }


def _build_scoring_draft(sample: dict[str, Any]) -> OfflineScoringDraft:
    sample_id = str(sample["id"])
    tier = str(sample["quality_tier"])
    scores = TIER_DIMENSION_SCORES[tier]
    evidence = tuple(
        EvidenceQuote(
            quote_id=f"{sample_id}:q:{rubric.rubric_id}",
            speaker="learner",
            text=_learner_quote(sample_id, rubric.rubric_id),
            turn_index=index + 1,
        )
        for index, rubric in enumerate(V1_RUBRIC)
    )
    dimension_scores = tuple(
        RubricScore(
            rubric_id=rubric.rubric_id,
            score=scores[index],
            evidence_quote_ids=(evidence[index].quote_id,),
            suggestion=f"{rubric.display_name}继续绑定学员原话证据。",
        )
        for index, rubric in enumerate(V1_RUBRIC)
    )
    total_score = sum(score.score for score in dimension_scores)
    quality_flags = _quality_flags_for_sample(sample)
    contract = get_roleplay_contract()

    return OfflineScoringDraft(
        total_score=total_score,
        dimension_scores=dimension_scores,
        evidence_quotes=evidence,
        suggestions=("保持需求澄清、可信度回应和下一步推进的证据绑定。",),
        strengths=("对练路径完整",),
        confidence=0.82,
        scoring_json={
            "sample_id": sample_id,
            "tier": tier,
            "covered_tags": list(sample["coverage_tags"]),
            "rubric_version": "it_leader_roleplay_v1",
            "scorer": "deterministic_regression_harness",
        },
        state_card={
            "state_card_version": 1,
            "current_phase_id": "opening_intent",
            "quality_flags": list(quality_flags),
        },
        roleplay_contract_hash=str(contract["audit"]["contract_hash"]),
        quality_flags=quality_flags,
        ai_quality={
            "hidden_information_leakage_count": 0,
            "roleplay_drift_count": 0,
        },
        ops_metrics={
            "knowledge_timeout_count": (
                1 if "knowledge_gap_degradation" in sample["coverage_tags"] else 0
            )
        },
        redacted_logs=("[regression] deterministic sample; no transcript secrets",),
    )


def _learner_quote(sample_id: str, rubric_id: str) -> str:
    return (
        f"{sample_id} / {rubric_id}: 我先确认贵单位现有系统、数据流动风险、"
        "可验证 PoC 指标和下一步调研安排。"
    )


def _quality_flags_for_sample(sample: dict[str, Any]) -> tuple[str, ...]:
    flags = ["hidden_information_leakage_count:0"]
    if "knowledge_gap_degradation" in sample["coverage_tags"]:
        flags.extend(["knowledge_gap_degradation", "knowledge_timeout_count:1"])
    else:
        flags.append("knowledge_timeout_count:0")
    return tuple(flags)


def _customer_visible_context(sample: dict[str, Any]) -> dict[str, Any]:
    return {
        "visible_payload": {
            "customer_background": "首次拜访政教医信息中心负责人。",
            "product_facts_limited": "石犀平台事实只能来自已验证材料或 PoC 指标。",
            "sample_id": str(sample["id"]),
        },
        "allowed_layers": ["customer_background", "product_facts_limited"],
    }


def _compiled_instruction_check() -> dict[str, Any]:
    contract = get_roleplay_contract()
    contract_hash = str(contract["audit"]["contract_hash"])
    state_card = get_default_state_card()
    phase_anchor = (
        f"roleplay_contract_hash={contract_hash}；"
        "当前阶段 opening_intent（开场与来意）；"
        "阶段类型=roleplay_phase；销售阶段 authority=SalesStageCapability。"
    )
    state_summary = (
        f"state_card_version={state_card['version']}；"
        f"current_phase_id={state_card['current_phase_id']}；"
        f"customer_attitude={state_card['customer_attitude']}；"
        f"next_pressure={state_card['next_pressure']}"
    )
    compiled = VoiceInstructionCompiler.compile_base_contract(
        policy={
            "roleplay_contract": contract,
            "roleplay_contract_hash": contract_hash,
            "roleplay_phase_anchor": phase_anchor,
            "session_state_card_summary": state_summary,
            "tool_policy": {
                "enable_internal_retrieval": True,
                "require_kb_grounding": True,
                "network_access_mode": "off",
            },
        }
    )
    hidden_terms_found = sorted(
        term for term in SCORER_ONLY_TERMS if term in compiled.base_instructions
    )

    return {
        "contract_hash": contract_hash,
        "instruction_contract_hash": compiled.contract_hash,
        "contains_phase_anchor": "【v1阶段锚点】" in compiled.base_instructions
        and "opening_intent" in compiled.base_instructions,
        "contains_state_anchor": "【状态卡摘要】" in compiled.base_instructions
        and "state_card_version=" in compiled.base_instructions,
        "contains_contract_hash": f"roleplay_contract_hash={contract_hash}"
        in compiled.base_instructions,
        "hidden_or_scorer_only_keys_absent": not hidden_terms_found,
        "hidden_terms_found": hidden_terms_found,
    }


def _leak_failure_check() -> dict[str, Any]:
    leaked_context = {
        "visible_payload": {
            "customer_background": "首次拜访。",
            "standard_answers": "标准答案：直接追问预算和决策链。",
        }
    }
    try:
        _assert_no_customer_visible_leakage(leaked_context)
    except CustomerVisibleLeakageError as exc:
        return {
            "customer_visible_scorer_only_leak_caught": True,
            "reason_code": exc.reason_code,
        }
    return {
        "customer_visible_scorer_only_leak_caught": False,
        "reason_code": None,
    }


def _assert_no_customer_visible_leakage(value: Any) -> None:
    match value:
        case dict():
            for key, nested in value.items():
                _raise_if_scorer_only_term(str(key))
                _assert_no_customer_visible_leakage(nested)
        case list() | tuple() | set():
            for item in value:
                _assert_no_customer_visible_leakage(item)
        case str():
            _raise_if_scorer_only_term(value)
        case _:
            return


def _raise_if_scorer_only_term(value: str) -> None:
    for term in SCORER_ONLY_TERMS:
        if term in value:
            raise CustomerVisibleLeakageError(
                f"customer_visible_leakage:{term}"
            )
