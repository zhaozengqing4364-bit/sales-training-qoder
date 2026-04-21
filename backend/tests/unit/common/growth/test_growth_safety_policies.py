from types import SimpleNamespace

import pytest

from common.growth.safety_policies import GrowthSafetyPolicyService


def _session(**overrides):
    values = {
        "session_id": "session-growth-1",
        "status": "completed",
        "logic_score": 88,
        "accuracy_score": 84,
        "completeness_score": 82,
        "effectiveness_snapshot": {"evaluable": True},
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_adaptive_difficulty_defaults_to_disabled_without_mutating_training():
    payload = GrowthSafetyPolicyService().evaluate_adaptive_difficulty(_session()).value

    assert payload["feature"] == "adaptive_difficulty"
    assert payload["status"] == "disabled"
    assert payload["enabled"] is False
    assert payload["suggested_adjustment"] == "none"
    assert payload["score_basis"] == "session_evidence_projection_evaluable_only"
    assert payload["rollback_strategy"] == "keep_current_difficulty"


@pytest.mark.parametrize(
    "session_overrides",
    [
        {"status": "in_progress"},
        {"effectiveness_snapshot": {"evaluable": False}},
    ],
)
def test_adaptive_difficulty_blocks_incomplete_or_not_evaluable_sessions(
    session_overrides,
):
    payload = GrowthSafetyPolicyService(
        adaptive_policy={
            "version": "adaptive_test_v1",
            "enabled": True,
            "mode": "dry_run",
        }
    ).evaluate_adaptive_difficulty(_session(**session_overrides)).value

    assert payload["status"] == "blocked_by_evidence"
    assert payload["enabled"] is False
    assert "completed 且 evaluable" in payload["explanation"]


def test_adaptive_difficulty_dry_run_explains_adjustment_from_scores():
    payload = GrowthSafetyPolicyService(
        adaptive_policy={
            "version": "adaptive_test_v1",
            "enabled": True,
            "mode": "dry_run",
            "lower_score_threshold": 55,
            "raise_score_threshold": 85,
            "max_adjustment_step": 1,
        }
    ).evaluate_adaptive_difficulty(_session(overall_score=91)).value

    assert payload["status"] == "dry_run"
    assert payload["suggested_adjustment"] == "increase"
    assert payload["overall_score"] == 91.0
    assert payload["policy_version"] == "adaptive_test_v1"


def test_adaptive_policy_invalid_env_falls_back_to_safe_default(monkeypatch):
    monkeypatch.setenv(
        "GROWTH_ADAPTIVE_DIFFICULTY_POLICY_JSON",
        '{"version":"bad","enabled":true,"lower_score_threshold":95,"raise_score_threshold":20}',
    )

    payload = GrowthSafetyPolicyService().evaluate_adaptive_difficulty(
        _session(overall_score=99)
    ).value

    assert payload["status"] == "disabled"
    assert payload["policy_source"] == "default"
    assert payload["enabled"] is False


def test_wecom_share_defaults_to_governance_block_for_completed_sessions():
    payload = GrowthSafetyPolicyService().evaluate_wecom_share(_session()).value

    assert payload["feature"] == "wecom_share"
    assert payload["status"] == "blocked_by_governance"
    assert payload["enabled"] is False
    assert "ADR" in payload["explanation"]
    assert payload["rollback_strategy"] == "disable_share_links"


def test_wecom_share_blocks_incomplete_sessions_before_governance():
    payload = GrowthSafetyPolicyService(
        wecom_share_policy={
            "version": "wecom_test_v1",
            "enabled": True,
            "adr_approved": True,
            "allowed_domains": ["example.com"],
        }
    ).evaluate_wecom_share(_session(status="in_progress")).value

    assert payload["status"] == "blocked_by_evidence"
    assert payload["enabled"] is False


def test_wecom_share_requires_adr_and_allowed_domains_when_enabled():
    payload = GrowthSafetyPolicyService(
        wecom_share_policy={
            "version": "wecom_test_v1",
            "enabled": True,
            "adr_approved": True,
            "ttl_days": 14,
            "allowed_domains": ["share.example.com"],
        }
    ).evaluate_wecom_share(_session()).value

    assert payload["status"] == "available"
    assert payload["enabled"] is True
    assert payload["ttl_days"] == 14
    assert payload["allowed_domains"] == ["share.example.com"]
