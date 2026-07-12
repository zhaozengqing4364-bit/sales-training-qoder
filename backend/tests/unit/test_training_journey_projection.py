from __future__ import annotations

from datetime import UTC, datetime

import pytest

from sales_trainer.services.journey_read_repository import JourneyLearnerProjection
from sales_trainer.services.training_journey_projection import TrainingJourneyProjection
from sales_trainer.services.training_journey_service import JourneyModule


def _module(**overrides: object) -> JourneyModule:
    values: dict[str, object] = {
        "module_key": "module-1",
        "base_module_key": "module-1",
        "title": "训练模块",
        "kind": "quiz_attempt",
        "module_type": "quiz",
        "order_index": 1,
        "required": True,
        "enabled": True,
        "completion_rule": "passed",
        "target_unit_id": "unit-1",
    }
    values.update(overrides)
    return JourneyModule(**values)  # type: ignore[arg-type]


def _learner() -> JourneyLearnerProjection:
    return JourneyLearnerProjection(
        learner_id="learner-1",
        name="Learner",
        department="销售一部",
        role="user",
        email="learner@example.com",
        wechat_user_id="learner-wechat",
        is_active=True,
        created_at=datetime(2026, 7, 11, tzinfo=UTC),
    )


def test_module_and_journey_state_cover_fail_closed_variants() -> None:
    projection = TrainingJourneyProjection()
    module = _module()

    assert projection.module_stage(module, {"status": "passed"}) == "passed"
    assert projection.module_stage(module, {"status": 42}) == "not_started"
    assert not projection.completion_satisfied(module, {"status": "in_progress"})
    assert projection.completion_satisfied(
        _module(completion_rule="submitted"),
        {"status": "scored", "submitted_at": "2026-07-11T00:00:00Z"},
    )
    assert not projection.completion_satisfied(
        _module(completion_rule="submitted"),
        {"status": "scored"},
    )
    assert projection.completion_satisfied(
        _module(completion_rule="scored"),
        {"status": "failed"},
    )
    assert not projection.completion_satisfied(
        _module(completion_rule="scored"),
        {"status": "manual_review"},
    )
    assert not projection.completion_satisfied(
        _module(completion_rule="manual"),
        {"status": "manual_review"},
    )

    realtime_action = projection.next_action(
        _module(kind="realtime_roleplay", module_type="realtime"),
        "passed",
    )
    assert realtime_action and realtime_action["label"] == "再次对练"
    assert projection.next_action(
        _module(kind="manual_review", module_type="manual"),
        "not_started",
    ) is None
    assert projection.journey_stage([], False) == "disabled"
    diagnostics = projection.journey_diagnostics(False, [])
    assert len(diagnostics) == 2


def test_quiz_action_paths_cover_business_and_generic_units() -> None:
    projection = TrainingJourneyProjection()

    business = projection.next_action(
        _module(base_module_key="business_skills"),
        "not_started",
    )
    business_without_unit = projection.next_action(
        _module(base_module_key="business_skills", target_unit_id=None),
        "not_started",
    )
    generic = projection.next_action(_module(), "not_started")
    unavailable = projection.next_action(
        _module(target_unit_id=None, target_unit_ids=()),
        "not_started",
    )
    audio = projection.next_action(
        _module(kind="audio_submission", module_type="audio"),
        "not_started",
    )
    audio_without_unit = projection.next_action(
        _module(
            kind="audio_submission",
            module_type="audio",
            target_unit_id=None,
            target_unit_ids=(),
        ),
        "not_started",
    )

    assert business and business["target_path"] == "/sales-trainer/business-skills?unitId=unit-1"
    assert business_without_unit and business_without_unit["target_path"] == "/sales-trainer/business-skills"
    assert generic and generic["target_path"] == "/sales-trainer/quiz/unit-1"
    assert unavailable and unavailable["disabled"] is True
    assert audio and audio["target_path"] == "/sales-trainer/audio/unit-1"
    assert audio_without_unit and audio_without_unit["disabled"] is True


class _IsoDate:
    def isoformat(self) -> str:
        return "2026-07-09T12:00:00+00:00"


def test_analytics_cover_malformed_topics_dates_and_risk_reasons() -> None:
    projection = TrainingJourneyProjection()
    topics = projection.analytics_learning_topics(
        [
            {
                "learning_topics": [
                    {
                        "topic_key": "topic-1",
                        "status": "needs_remediation",
                        "units": ["legacy", {"score": 80}],
                    }
                ]
            }
        ]
    )
    assert topics[0]["needs_remediation_count"] == 1
    assert topics[0]["average_unit_score"] == 80.0

    trend = projection.analytics_trend(
        [
            {
                "learner_id": "",
                "modules": [
                    {
                        "outcome_history": [
                            {"completed_at": None},
                            {"completed_at": " "},
                            {"completed_at": "x"},
                            {"completed_at": object()},
                            {"completed_at": _IsoDate(), "passed": False},
                        ]
                    }
                ],
            },
            {
                "learner_id": "learner-1",
                "modules": [
                    {
                        "outcome_history": [
                            {
                                "completed_at": datetime(2026, 7, 10, tzinfo=UTC),
                                "passed": True,
                                "score": 90,
                            }
                        ]
                    }
                ],
            },
        ]
    )
    assert {item["date"] for item in trend} == {"x", "2026-07-09", "2026-07-10"}

    risks = projection.analytics_risk_learners(
        [
            {
                "learner_id": "learner-1",
                "modules": [
                    {"module_key": "quiz", "passed": False, "status": "failed"},
                    {"module_key": "audio", "passed": None, "status": "error_terminal"},
                ],
            }
        ]
    )
    assert risks[0]["risk_reasons"] == [
        "quiz:not_passed",
        "audio:status:error_terminal",
    ]


@pytest.mark.parametrize(
    ("conditions", "overall"),
    [
        ({"department_in": ["销售二部"]}, {}),
        ({"min_pass_rate": 80}, {"total_modules": 2, "passed_modules": 1}),
        ({"max_pass_rate": 40}, {"total_modules": 2, "passed_modules": 1}),
        ({"min_completed_modules": 2}, {"completed_modules": 1}),
        ({"min_passed_modules": 2}, {"passed_modules": 1}),
        ({"max_failed_modules": 0}, {"failed_modules": 1}),
    ],
)
def test_learner_level_condition_boundaries_fail_closed(
    conditions: dict[str, object],
    overall: dict[str, object],
) -> None:
    projection = TrainingJourneyProjection()
    policy = {
        "default_level": "legacy",
        "levels": [{"key": "advanced", "label": "进阶"}],
        "rules": [
            "legacy",
            {"enabled": False},
            {"conditions": "legacy"},
            {"conditions": conditions, "level_key": "advanced"},
        ],
    }

    result = projection.match_learner_level(
        policy=policy,
        learner=_learner(),
        training_stage="in_progress",
        overall=overall,
    )

    assert result["key"] == "unassigned"


def test_learner_level_matching_accepts_all_satisfied_boundaries() -> None:
    projection = TrainingJourneyProjection()
    result = projection.match_learner_level(
        policy={
            "default_level": {"key": "base"},
            "levels": [{"key": "advanced", "label": "进阶"}],
            "rules": [
                {
                    "enabled": True,
                    "level_key": "advanced",
                    "conditions": {
                        "training_stage_in": ["passed"],
                        "department_in": ["销售一部"],
                        "role_in": ["user"],
                        "min_pass_rate": 50,
                        "max_pass_rate": 100,
                        "min_completed_modules": 2,
                        "min_passed_modules": 1,
                        "max_failed_modules": 1,
                    },
                }
            ],
        },
        learner=_learner(),
        training_stage="passed",
        overall={
            "total_modules": 2,
            "completed_modules": 2,
            "passed_modules": 2,
            "failed_modules": 0,
        },
    )

    assert result["key"] == "advanced"
