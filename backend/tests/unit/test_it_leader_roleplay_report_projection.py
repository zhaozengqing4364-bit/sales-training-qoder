from __future__ import annotations

from sales_bot.services.it_leader_roleplay_scoring import (
    EvidenceQuote,
    OfflineScoringDraft,
    RubricScore,
    build_permissioned_report_projection,
    validate_offline_scoring_report,
)


def _accepted_report():
    draft = OfflineScoringDraft(
        total_score=85,
        dimension_scores=(
            RubricScore(
                rubric_id="opening_intent",
                score=12,
                evidence_quote_ids=("q-opening",),
                suggestion="开场目的明确，可以更快说明不急于推产品。",
            ),
            RubricScore(
                rubric_id="current_state_discovery",
                score=17,
                evidence_quote_ids=("q-discovery",),
                suggestion="继续追问系统边界和责任部门。",
            ),
            RubricScore(
                rubric_id="risk_identification",
                score=16,
                evidence_quote_ids=("q-risk",),
                suggestion="补充合规、稳定性和权限边界风险。",
            ),
            RubricScore(
                rubric_id="value_explanation",
                score=18,
                evidence_quote_ids=("q-value",),
                suggestion="价值说明清楚，后续补一两个行业例子。",
            ),
            RubricScore(
                rubric_id="credibility_response",
                score=13,
                evidence_quote_ids=("q-trust",),
                suggestion="保持克制，用 PoC 指标替代泛泛保证。",
            ),
            RubricScore(
                rubric_id="next_step_advancement",
                score=9,
                evidence_quote_ids=("q-next",),
                suggestion="下一步较具体，可补充会议产出物。",
            ),
        ),
        evidence_quotes=(
            EvidenceQuote(
                quote_id="q-opening",
                speaker="learner",
                text="今天想先了解贵单位的数据流动和接口现状，再判断我们能否帮上忙。",
                turn_index=1,
            ),
            EvidenceQuote(
                quote_id="q-discovery",
                speaker="learner",
                text="现有 API 网关、数据交换平台和审计系统分别由哪些部门负责？",
                turn_index=3,
            ),
            EvidenceQuote(
                quote_id="q-risk",
                speaker="learner",
                text="我会先确认不影响现网稳定性的边界，再看哪些链路需要治理。",
                turn_index=5,
            ),
            EvidenceQuote(
                quote_id="q-value",
                speaker="learner",
                text="石犀更关注跨系统数据流动的可见性、审计和风险治理，不替代现有网关。",
                turn_index=7,
            ),
            EvidenceQuote(
                quote_id="q-trust",
                speaker="learner",
                text="部署和性能我们不口头承诺，建议用 PoC 指标验证吞吐、延迟和误报。",
                turn_index=9,
            ),
            EvidenceQuote(
                quote_id="q-next",
                speaker="learner",
                text="下一步可以先梳理三条典型链路，再约技术同事做 PoC 方案评审。",
                turn_index=11,
            ),
        ),
        suggestions=("下次先画出客户现有系统边界，再提出 PoC 指标。",),
        strengths=("开场克制", "可信度回应较稳"),
        confidence=0.86,
        scoring_json={"model": "offline-fake", "rubric_version": "it_leader_roleplay_v1"},
        state_card={"current_stage": "next_step", "state_card_version": 4},
        roleplay_contract_hash="sha256:contract-v1",
        quality_flags=("knowledge_timeout_count:1", "roleplay_drift_detected"),
        transcript=(
            {"speaker": "ai_customer", "text": "你们先介绍一下来意。", "turn_index": 0},
            {
                "speaker": "learner",
                "text": "今天想先了解贵单位的数据流动和接口现状。",
                "turn_index": 1,
            },
        ),
        ai_quality={
            "roleplay_drift_count": 1,
            "hidden_information_leakage_count": 0,
            "manual_review_recommended": True,
        },
        ops_metrics={
            "knowledge_timeout_count": 1,
            "scoring_latency_ms": 320,
        },
        redacted_logs=("[trace] knowledge lookup timeout; transcript redacted",),
    )
    result = validate_offline_scoring_report(draft)
    assert result.accepted_report is not None
    return result.accepted_report


def test_should_return_learner_safe_projection_when_role_is_learner() -> None:
    # Arrange
    report = _accepted_report()

    # Act
    result = build_permissioned_report_projection(report, viewer_role="learner")

    # Assert
    assert result.allowed is True
    assert result.projection is not None
    assert set(result.projection) == {
        "total_score",
        "dimension_scores",
        "suggestions",
        "evidence",
    }
    assert {item["speaker"] for item in result.projection["evidence"]} == {"learner"}
    assert "transcript" not in result.projection
    assert "scoring_json" not in result.projection
    assert "state_card" not in result.projection
    assert "roleplay_contract_hash" not in result.projection
    assert "ai_quality" not in result.projection


def test_should_return_admin_quality_projection_when_role_is_supervisor() -> None:
    # Arrange
    report = _accepted_report()

    # Act
    result = build_permissioned_report_projection(report, viewer_role="supervisor")

    # Assert
    assert result.allowed is True
    assert result.projection is not None
    assert result.projection["transcript"][0]["speaker"] == "ai_customer"
    assert result.projection["scoring_json"] == {
        "model": "offline-fake",
        "rubric_version": "it_leader_roleplay_v1",
    }
    assert result.projection["state_card"] == {
        "current_stage": "next_step",
        "state_card_version": 4,
    }
    assert result.projection["roleplay_contract_hash"] == "sha256:contract-v1"
    assert result.projection["ai_quality"] == {
        "roleplay_drift_count": 1,
        "hidden_information_leakage_count": 0,
        "manual_review_recommended": True,
    }


def test_should_return_ops_only_redacted_logs_and_metrics_when_role_is_ops() -> None:
    # Arrange
    report = _accepted_report()

    # Act
    result = build_permissioned_report_projection(report, viewer_role="ops")

    # Assert
    assert result.allowed is True
    assert result.projection is not None
    assert set(result.projection) == {"quality_flags", "metrics", "redacted_logs"}
    assert result.projection["metrics"] == {
        "knowledge_timeout_count": 1,
        "scoring_latency_ms": 320,
    }
    assert result.projection["redacted_logs"] == (
        "[trace] knowledge lookup timeout; transcript redacted",
    )
    assert "transcript" not in result.projection
    assert "dimension_scores" not in result.projection
    assert "scoring_json" not in result.projection


def test_should_deny_projection_when_role_is_unknown() -> None:
    # Arrange
    report = _accepted_report()

    # Act
    result = build_permissioned_report_projection(report, viewer_role="guest")

    # Assert
    assert result.allowed is False
    assert result.projection is None
    assert result.reason_code == "report_projection_role_denied"


def test_should_reject_report_when_evidence_source_is_ai_customer() -> None:
    # Arrange
    draft = OfflineScoringDraft(
        total_score=85,
        dimension_scores=(
            RubricScore(
                rubric_id="opening_intent",
                score=12,
                evidence_quote_ids=("q-ai",),
                suggestion="不能用 AI 客户原话给学员评分。",
            ),
            RubricScore(
                rubric_id="current_state_discovery",
                score=17,
                evidence_quote_ids=("q-discovery",),
                suggestion="继续追问系统边界和责任部门。",
            ),
            RubricScore(
                rubric_id="risk_identification",
                score=16,
                evidence_quote_ids=("q-risk",),
                suggestion="补充合规、稳定性和权限边界风险。",
            ),
            RubricScore(
                rubric_id="value_explanation",
                score=18,
                evidence_quote_ids=("q-value",),
                suggestion="价值说明清楚，后续补一两个行业例子。",
            ),
            RubricScore(
                rubric_id="credibility_response",
                score=13,
                evidence_quote_ids=("q-trust",),
                suggestion="保持克制，用 PoC 指标替代泛泛保证。",
            ),
            RubricScore(
                rubric_id="next_step_advancement",
                score=9,
                evidence_quote_ids=("q-next",),
                suggestion="下一步较具体，可补充会议产出物。",
            ),
        ),
        evidence_quotes=(
            EvidenceQuote(
                quote_id="q-ai",
                speaker="ai_customer",
                text="你应该问我们现有 API 网关和审计系统。",
                turn_index=2,
            ),
            EvidenceQuote(
                quote_id="q-discovery",
                speaker="learner",
                text="现有 API 网关、数据交换平台和审计系统分别由哪些部门负责？",
                turn_index=3,
            ),
            EvidenceQuote(
                quote_id="q-risk",
                speaker="learner",
                text="我会先确认不影响现网稳定性的边界。",
                turn_index=5,
            ),
            EvidenceQuote(
                quote_id="q-value",
                speaker="learner",
                text="石犀更关注跨系统数据流动的可见性、审计和风险治理。",
                turn_index=7,
            ),
            EvidenceQuote(
                quote_id="q-trust",
                speaker="learner",
                text="建议用 PoC 指标验证吞吐、延迟和误报。",
                turn_index=9,
            ),
            EvidenceQuote(
                quote_id="q-next",
                speaker="learner",
                text="下一步可以先梳理三条典型链路。",
                turn_index=11,
            ),
        ),
        suggestions=("证据必须来自学员原话。",),
        strengths=(),
        confidence=0.86,
        scoring_json={"model": "offline-fake"},
        state_card={"state_card_version": 4},
        roleplay_contract_hash="sha256:contract-v1",
    )

    # Act
    result = validate_offline_scoring_report(draft)

    # Assert
    assert result.accepted_report is None
    assert result.rejected_report is not None
    assert "ai_customer_evidence" in result.rejected_report.reason_codes
