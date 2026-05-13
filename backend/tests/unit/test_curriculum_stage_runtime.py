from __future__ import annotations

from sales_bot.websocket.components.curriculum_stage_runtime import (
    CurriculumStageRuntime,
)


def _runtime(*, failure_policy: str = "retry_current") -> CurriculumStageRuntime:
    return CurriculumStageRuntime(
        curriculum_plan={
            "stages": [
                {
                    "template_stage_key": "template_stage_opening",
                    "order": 1,
                    "completion_policy": {
                        "min_score": 7.0,
                        "min_rounds": 2,
                        "max_duration_seconds": 60,
                    },
                    "failure_policy": failure_policy,
                },
                {
                    "template_stage_key": "template_stage_close",
                    "order": 2,
                    "completion_policy": {
                        "min_score": 8.0,
                        "min_rounds": 1,
                        "max_duration_seconds": 60,
                    },
                    "failure_policy": "allow_skip",
                },
            ]
        },
        stage_snapshots={
            "template_stage_opening": {"runtime_payload": {"name": "opening"}},
            "template_stage_close": {"runtime_payload": {"name": "close"}},
        },
        warning_lead_seconds=10,
        grace_seconds=5,
    )


def test_initializes_template_stage_context_to_first_available_stage() -> None:
    runtime = _runtime()

    result = runtime.initialize(now_seconds=100.0)

    assert result.runtime_state_patch == {
        "template_stage_context": {
            "template_stage_key": "template_stage_opening",
            "template_stage_index": 0,
            "template_stage_status": "active",
            "template_stage_started_at": 100.0,
            "template_stage_rounds": 0,
            "template_stage_version": 1,
            "template_stage_warning_sent": False,
            "template_stage_grace_started_at": None,
        }
    }
    assert result.websocket_events == [
        {
            "type": "template_stage_transition",
            "data": {
                "template_stage_key": "template_stage_opening",
                "template_stage_status": "active",
                "template_stage_previous_key": None,
                "template_stage_version": 1,
            },
        }
    ]


def test_completion_policy_transitions_when_score_and_rounds_are_satisfied() -> None:
    runtime = _runtime()
    runtime.initialize(now_seconds=100.0)

    first_turn = runtime.handle_turn(
        turn_number=1,
        template_stage_score=8.0,
        now_seconds=110.0,
    )
    second_turn = runtime.handle_turn(
        turn_number=2,
        template_stage_score=8.0,
        now_seconds=120.0,
    )

    assert first_turn.websocket_events == []
    assert second_turn.runtime_state_patch["template_stage_context"]["template_stage_key"] == "template_stage_close"
    assert second_turn.runtime_state_patch["template_stage_context"]["template_stage_version"] == 4
    assert second_turn.websocket_events == [
        {
            "type": "template_stage_transition",
            "data": {
                "template_stage_key": "template_stage_close",
                "template_stage_status": "active",
                "template_stage_previous_key": "template_stage_opening",
                "template_stage_version": 4,
            },
        }
    ]


def test_failure_policy_retry_current_keeps_active_stage() -> None:
    runtime = _runtime(failure_policy="retry_current")
    runtime.initialize(now_seconds=100.0)

    result = runtime.handle_turn(
        turn_number=1,
        template_stage_score=2.0,
        now_seconds=110.0,
        template_stage_failed=True,
    )

    context = result.runtime_state_patch["template_stage_context"]
    assert context["template_stage_key"] == "template_stage_opening"
    assert context["template_stage_status"] == "active"
    assert context["template_stage_rounds"] == 1
    assert context["template_stage_version"] == 2
    assert result.websocket_events == []


def test_failure_policy_allow_skip_advances_to_next_stage() -> None:
    runtime = _runtime(failure_policy="allow_skip")
    runtime.initialize(now_seconds=100.0)

    result = runtime.handle_turn(
        turn_number=1,
        template_stage_score=2.0,
        now_seconds=110.0,
        template_stage_failed=True,
    )

    context = result.runtime_state_patch["template_stage_context"]
    assert context["template_stage_key"] == "template_stage_close"
    assert context["template_stage_version"] == 3
    assert result.websocket_events[0]["data"]["template_stage_previous_key"] == "template_stage_opening"


def test_failure_policy_fallback_to_previous_returns_to_prior_stage() -> None:
    runtime = _runtime(failure_policy="allow_skip")
    runtime.initialize(now_seconds=100.0)
    runtime.handle_turn(
        turn_number=1,
        template_stage_score=2.0,
        now_seconds=110.0,
        template_stage_failed=True,
    )

    result = runtime.handle_turn(
        turn_number=2,
        template_stage_score=1.0,
        now_seconds=120.0,
        template_stage_failed=True,
        template_stage_failure_policy="fallback_to_previous",
    )

    context = result.runtime_state_patch["template_stage_context"]
    assert context["template_stage_key"] == "template_stage_opening"
    assert context["template_stage_version"] == 5
    assert result.websocket_events[0]["data"]["template_stage_previous_key"] == "template_stage_close"


def test_timeout_warning_emits_before_stage_limit_once() -> None:
    runtime = _runtime()
    runtime.initialize(now_seconds=100.0)

    result = runtime.handle_timing(now_seconds=151.0)
    repeated = runtime.handle_timing(now_seconds=152.0)

    context = result.runtime_state_patch["template_stage_context"]
    assert context["template_stage_key"] == "template_stage_opening"
    assert context["template_stage_warning_sent"] is True
    assert context["template_stage_version"] == 2
    assert result.websocket_events == [
        {
            "type": "template_stage_warning",
            "data": {
                "template_stage_key": "template_stage_opening",
                "template_stage_status": "active",
                "template_stage_seconds_remaining": 9.0,
                "template_stage_version": 2,
            },
        }
    ]
    assert repeated.websocket_events == []


def test_timeout_uses_bounded_grace_period_before_transition() -> None:
    runtime = _runtime(failure_policy="allow_skip")
    runtime.initialize(now_seconds=100.0)

    grace_started = runtime.handle_timing(now_seconds=160.0)
    before_grace_expires = runtime.handle_timing(now_seconds=164.0)
    transitioned = runtime.handle_timing(now_seconds=165.0)

    assert grace_started.runtime_state_patch["template_stage_context"]["template_stage_grace_started_at"] == 160.0
    assert before_grace_expires.websocket_events == []
    assert transitioned.runtime_state_patch["template_stage_context"]["template_stage_key"] == "template_stage_close"
    assert transitioned.runtime_state_patch["template_stage_context"]["template_stage_version"] == 4
    assert transitioned.websocket_events == [
        {
            "type": "template_stage_transition",
            "data": {
                "template_stage_key": "template_stage_close",
                "template_stage_status": "active",
                "template_stage_previous_key": "template_stage_opening",
                "template_stage_version": 4,
            },
        }
    ]


def test_final_stage_completion_marks_curriculum_complete() -> None:
    runtime = _runtime()
    runtime.initialize(now_seconds=100.0)
    runtime.handle_turn(turn_number=1, template_stage_score=8.0, now_seconds=110.0)
    runtime.handle_turn(turn_number=2, template_stage_score=8.0, now_seconds=120.0)

    result = runtime.handle_turn(
        turn_number=3,
        template_stage_score=9.0,
        now_seconds=130.0,
    )

    context = result.runtime_state_patch["template_stage_context"]
    assert context["template_stage_key"] == "template_stage_close"
    assert context["template_stage_status"] == "completed"
    assert context["template_stage_version"] == 6
    assert result.websocket_events == [
        {
            "type": "template_stage_transition",
            "data": {
                "template_stage_key": "template_stage_close",
                "template_stage_status": "completed",
                "template_stage_previous_key": "template_stage_close",
                "template_stage_version": 6,
            },
        }
    ]


def test_restored_template_stage_context_does_not_emit_initial_transition() -> None:
    runtime = CurriculumStageRuntime(
        curriculum_plan={"stages": []},
        stage_snapshots={"template_stage_opening": {"runtime_payload": {}}},
        runtime_state={
            "template_stage_context": {
                "template_stage_key": "template_stage_opening",
                "template_stage_index": 0,
                "template_stage_status": "active",
                "template_stage_started_at": 100.0,
                "template_stage_rounds": 1,
                "template_stage_version": 4,
                "template_stage_warning_sent": False,
                "template_stage_grace_started_at": None,
            }
        },
    )

    result = runtime.initialize(now_seconds=200.0)

    assert result.websocket_events == []
    assert result.runtime_state_patch["template_stage_context"]["template_stage_version"] == 4
