from common.db.models import PracticeSession, Scenario, SessionStatus
from common.recommendations.next_practice import NextPracticeRecommendationService


def _sales_session(**overrides):
    scenario = Scenario(
        scenario_id="scenario-sales",
        scenario_type="sales",
        name="销售对练",
    )
    values = {
        "session_id": "session-recommendation",
        "user_id": "user-1",
        "scenario_id": "scenario-sales",
        "status": SessionStatus.COMPLETED.value,
        "logic_score": 78,
        "accuracy_score": 55,
        "completeness_score": 84,
        "effectiveness_snapshot": {"evaluable": True},
    }
    values.update(overrides)
    session = PracticeSession(**values)
    session.scenario = scenario
    return session


def test_next_practice_recommendation_targets_product_knowledge_when_score_low():
    result = NextPracticeRecommendationService().build_for_session(_sales_session())

    assert result.is_success
    payload = result.value
    assert payload["recommendation_kind"] == "next_practice_ruleset"
    assert payload["weak_dimension"] == "product_knowledge"
    assert payload["source_session_id"] == "session-recommendation"
    assert payload["rule_version"] == "growth_recommendation_rules_v1"
    assert "55" in payload["explanation"]
    assert payload["evidence_summary"]["score_field"] == "accuracy_score"
    assert payload["evidence_summary"]["score_basis"] == (
        "session_evidence_projection_evaluable_only"
    )
    assert payload["growth_safety"]["adaptive_difficulty"]["status"] == "disabled"
    assert payload["growth_safety"]["wecom_share"]["status"] == "blocked_by_governance"


def test_next_practice_recommendation_targets_objection_handling_when_lowest():
    result = NextPracticeRecommendationService().build_for_session(
        _sales_session(accuracy_score=72, completeness_score=45)
    )

    assert result.is_success
    payload = result.value
    assert payload["weak_dimension"] == "objection_handling"
    assert "异议" in payload["title"]
    assert payload["evidence_summary"]["score"] == 45.0


def test_next_practice_recommendation_reports_insufficient_evidence_without_claims():
    result = NextPracticeRecommendationService().build_for_session(
        _sales_session(
            status=SessionStatus.IN_PROGRESS.value,
            effectiveness_snapshot={"evaluable": False},
        )
    )

    assert result.is_success
    payload = result.value
    assert payload["recommendation_kind"] == "insufficient_evidence"
    assert payload["source_session_id"] == "session-recommendation"
    assert "完成且可评估" in payload["explanation"]
    assert (
        payload["growth_safety"]["adaptive_difficulty"]["status"]
        == "blocked_by_evidence"
    )
