from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]


def test_legacy_free_chat_coach_writers_and_direct_scoring_service_are_removed() -> (
    None
):
    retired_files = (
        "backend/src/sales_trainer/orchestration/activities/ai_coach.py",
        "backend/src/sales_trainer/services/ai_coach_session_service.py",
        "backend/src/sales_trainer/services/ai_coach_scoring_service.py",
    )
    for filename in retired_files:
        assert not (REPO_ROOT / filename).exists()

    assert not (
        REPO_ROOT / "backend/src/sales_trainer/orchestration/learner_api.py"
    ).exists()


def test_structured_activity_command_is_the_only_formal_coach_write_surface() -> None:
    activity_api = (
        REPO_ROOT / "backend/src/newcomer_training/activity_application.py"
    ).read_text()
    learner_api = (REPO_ROOT / "backend/src/foundation_learner_api.py").read_text()
    assert '"/activities/{activity_id}/commands"' in learner_api
    for command_type in (
        "submit_coach_answer",
        "continue_coach",
        "retry_coach",
        "request_coach_assistance",
    ):
        assert command_type in activity_api

    coach_source = "\n".join(
        path.read_text()
        for path in sorted((REPO_ROOT / "backend/src/ai_coach").glob("*.py"))
    )
    assert "LLMService" not in coach_source
    assert "common.ai.llm_service" not in coach_source
    assert ".generate(" not in coach_source


def test_unscoped_foundation_environment_rollout_flags_are_retired() -> None:
    composition = (
        REPO_ROOT / "backend/src/newcomer_foundation_composition.py"
    ).read_text()

    for retired_flag in (
        "NEWCOMER_AUDIO_ASSESSMENT_ENABLED",
        "NEWCOMER_ASYNC_ASSIGNMENT_ENABLED",
        "NEWCOMER_AI_COACH_ENABLED",
    ):
        assert retired_flag not in composition
