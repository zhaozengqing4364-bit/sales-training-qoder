"""Exact retirement contract for newcomer-training v2 clean cut."""

from __future__ import annotations

from app_factory import create_app


def _operation_set() -> set[tuple[str, str]]:
    schema = create_app().openapi()
    return {
        (method.upper(), path)
        for path, operations in schema["paths"].items()
        for method in operations
        if method != "parameters"
    }


def test_newcomer_v2_openapi_exposes_no_retired_operations() -> None:
    nt = "/api/v1/newcomer-training"
    nta = "/api/v1/admin/newcomer-training"
    sta = "/api/v1/admin/sales-trainer"
    retired = {
        ("GET", f"{nta}/path/"),
        ("PUT", f"{nta}/path/draft"),
        ("DELETE", f"{nta}/path/draft"),
        *{
            ("POST", f"{nta}/path/{command}")
            for command in (
                "validate",
                "validate-candidate",
                "publish",
                "publish-candidate",
            )
        },
        *{
            ("GET", f"{nta}/path/{resource}")
            for resource in (
                "revisions",
                "activity-types",
                "coach-profiles",
                "scoring-rubrics",
            )
        },
        ("POST", f"{nta}/path/revisions/{{revision_id}}/restore"),
        ("POST", f"{nta}/path/scoring-rubrics"),
        ("GET", f"{nt}/modules/{{module_id}}"),
        ("POST", f"{nt}/activities/{{activity_id}}/lesson/confirm"),
        (
            "POST",
            f"{nt}/activities/{{activity_id}}/lesson/chapters/"
            "{chapter_id}/complete",
        ),
        ("POST", f"{nt}/activities/{{activity_id}}/quiz/attempts"),
        ("POST", f"{nt}/activities/{{activity_id}}/audio/submissions"),
        ("POST", f"{nt}/activities/{{activity_id}}/ai-coach/sessions"),
        (
            "POST",
            f"{nt}/activities/{{activity_id}}/ai-coach/sessions/"
            "{session_id}/turns",
        ),
        (
            "POST",
            f"{nt}/activities/{{activity_id}}/ai-coach/sessions/"
            "{session_id}/turns/stream",
        ),
        ("POST", f"{nt}/activities/{{activity_id}}/assignments"),
        ("POST", f"{nt}/activities/{{activity_id}}/realtime/sessions"),
        ("GET", f"{nt}/papers/{{paper_id}}"),
        ("POST", f"{nt}/paper-attempts"),
        ("GET", f"{nta}/papers"),
        ("POST", f"{nta}/papers"),
        ("GET", f"{nta}/units"),
        ("POST", f"{nta}/units"),
        (
            "POST",
            f"{nta}/resources/{{resource_type}}/{{resource_id}}/commands/publish",
        ),
        ("GET", f"{nta}/journeys"),
        ("GET", f"{nta}/journeys/{{learner_id}}"),
        ("GET", f"{nta}/readiness/workbench"),
        ("GET", f"{nta}/readiness/dossiers/{{learner_id}}"),
        (
            "POST",
            f"{nta}/readiness/dossiers/{{learner_id}}/review-actions",
        ),
        *{
            ("POST", f"{prefix}/quiz-attempts/{{attempt_id}}/{command}")
            for prefix in (f"{nta}/regrades", f"{sta}/regrades")
            for command in ("preview", "run")
        },
        ("GET", f"{sta}/audio-submissions"),
        ("GET", f"{sta}/audio-submissions/{{submission_id}}"),
        ("GET", f"{sta}/audio-submissions/{{submission_id}}/file"),
        ("POST", f"{sta}/audio-submissions/{{submission_id}}/retry-transcription"),
        ("POST", f"{sta}/audio-submissions/{{submission_id}}/retry-scoring"),
        ("GET", f"{sta}/score-results"),
        ("GET", f"{sta}/training-records"),
        ("GET", f"{sta}/training-records/audio/{{submission_id}}"),
        (
            "GET",
            f"{sta}/training-records/detail/{{record_type}}/{{record_id}}",
        ),
        (
            "GET",
            f"{sta}/training-records/detail/{{record_type}}/{{record_id}}/"
            "materials/{version_id}/file",
        ),
        (
            "GET",
            f"{sta}/training-records/realtime-roleplay/{{session_id}}/observations",
        ),
        ("GET", f"{sta}/quiz-attempts"),
        ("GET", f"{sta}/quiz-attempts/{{attempt_id}}"),
    }

    remaining = retired & _operation_set()

    assert remaining == set(), sorted(remaining)
