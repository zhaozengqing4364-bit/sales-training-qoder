from __future__ import annotations

from sales_bot.services.it_leader_roleplay_scoring import (
    RUBRIC_TOTAL_SCORE,
    V1_RUBRIC,
    EvidenceQuote,
    OfflineScoringDraft,
    RubricScore,
    build_admin_projection,
    build_learner_projection,
    validate_offline_scoring_report,
)


def _valid_draft(*, confidence: float = 0.86) -> OfflineScoringDraft:
    evidence = (
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
    )
    scores = (
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
    )
    return OfflineScoringDraft(
        total_score=85,
        dimension_scores=scores,
        evidence_quotes=evidence,
        suggestions=("下次先画出客户现有系统边界，再提出 PoC 指标。",),
        strengths=("开场克制", "可信度回应较稳"),
        confidence=confidence,
        scoring_json={"model": "offline-fake", "rubric_version": "it_leader_roleplay_v1"},
        state_card={"current_stage": "next_step", "state_card_version": 4},
        roleplay_contract_hash="sha256:contract-v1",
        quality_flags=("knowledge_timeout_count:0",),
    )


def test_should_define_six_item_one_hundred_point_v1_rubric() -> None:
    # Arrange
    rubric_ids = {item.rubric_id for item in V1_RUBRIC}

    # Act
    total_score = RUBRIC_TOTAL_SCORE

    # Assert
    assert len(V1_RUBRIC) == 6
    assert total_score == 100
    assert rubric_ids == {
        "opening_intent",
        "current_state_discovery",
        "risk_identification",
        "value_explanation",
        "credibility_response",
        "next_step_advancement",
    }


def test_should_accept_report_and_project_separate_views_when_report_is_consistent() -> None:
    # Arrange
    draft = _valid_draft()

    # Act
    result = validate_offline_scoring_report(draft)

    # Assert
    assert result.accepted_report is not None
    assert result.rejected_report is None
    report = result.accepted_report
    assert report.total_score == 85
    assert report.manual_review_required is False

    learner = build_learner_projection(report)
    assert set(learner) == {
        "total_score",
        "dimension_scores",
        "suggestions",
        "evidence",
    }
    assert learner["total_score"] == 85
    assert {item["speaker"] for item in learner["evidence"]} == {"learner"}
    assert "scoring_json" not in learner
    assert "state_card" not in learner
    assert "roleplay_contract_hash" not in learner
    assert "quality_flags" not in learner

    admin = build_admin_projection(report)
    assert admin["scoring_json"] == draft.scoring_json
    assert admin["state_card"] == draft.state_card
    assert admin["roleplay_contract_hash"] == "sha256:contract-v1"
    assert admin["quality_flags"] == ("knowledge_timeout_count:0",)
    assert admin["scoring_confidence"] == 0.86


def test_should_reject_report_when_dimension_evidence_uses_ai_customer_quote() -> None:
    # Arrange
    draft = _valid_draft()
    ai_evidence = EvidenceQuote(
        quote_id="q-ai",
        speaker="ai_customer",
        text="你应该先问我们的系统现状。",
        turn_index=2,
    )
    dimension_scores = (
        RubricScore(
            rubric_id="opening_intent",
            score=12,
            evidence_quote_ids=("q-ai",),
            suggestion="不能用 AI 客户原话给学员评分。",
        ),
        *draft.dimension_scores[1:],
    )
    bad_draft = OfflineScoringDraft(
        total_score=draft.total_score,
        dimension_scores=dimension_scores,
        evidence_quotes=(*draft.evidence_quotes, ai_evidence),
        suggestions=draft.suggestions,
        strengths=draft.strengths,
        confidence=draft.confidence,
        scoring_json=draft.scoring_json,
        state_card=draft.state_card,
        roleplay_contract_hash=draft.roleplay_contract_hash,
        quality_flags=draft.quality_flags,
    )

    # Act
    result = validate_offline_scoring_report(bad_draft)

    # Assert
    assert result.accepted_report is None
    assert result.rejected_report is not None
    assert "ai_customer_evidence" in result.rejected_report.reason_codes


def test_should_reject_report_when_total_score_mismatches_dimension_sum() -> None:
    # Arrange
    draft = _valid_draft()
    bad_draft = OfflineScoringDraft(
        total_score=84,
        dimension_scores=draft.dimension_scores,
        evidence_quotes=draft.evidence_quotes,
        suggestions=draft.suggestions,
        strengths=draft.strengths,
        confidence=draft.confidence,
        scoring_json=draft.scoring_json,
        state_card=draft.state_card,
        roleplay_contract_hash=draft.roleplay_contract_hash,
        quality_flags=draft.quality_flags,
    )

    # Act
    result = validate_offline_scoring_report(bad_draft)

    # Assert
    assert result.accepted_report is None
    assert result.rejected_report is not None
    assert "total_score_mismatch" in result.rejected_report.reason_codes


def test_should_mark_manual_review_when_confidence_is_low() -> None:
    # Arrange
    draft = _valid_draft(confidence=0.54)

    # Act
    result = validate_offline_scoring_report(draft)

    # Assert
    assert result.accepted_report is not None
    assert result.accepted_report.manual_review_required is True
    assert result.accepted_report.manual_review_reasons == ("low_confidence",)
