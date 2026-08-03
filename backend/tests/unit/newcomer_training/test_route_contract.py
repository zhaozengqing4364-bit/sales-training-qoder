from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from typing import Any

from app_factory import create_app


def _registered_paths(routes: Iterable[Any], prefix: str = "") -> Iterable[str]:
    for route in routes:
        original_router = getattr(route, "original_router", None)
        include_context = getattr(route, "include_context", None)
        if original_router is not None and include_context is not None:
            yield from _registered_paths(
                original_router.routes,
                prefix=f"{prefix}{include_context.prefix}",
            )
            continue
        path = getattr(route, "path", None)
        if path is not None:
            yield f"{prefix}{path}"


def test_newcomer_training_has_one_canonical_learner_surface() -> None:
    app = create_app()
    schema = app.openapi()
    paths = schema["paths"]

    counts = Counter(_registered_paths(app.routes))
    assert counts["/api/v1/newcomer-training/journey"] == 1
    assert "/api/v1/newcomer-training/activities/{activity_id}" in paths
    assert "/api/v1/newcomer-training/activities/{activity_id}/commands" in paths
    assert "/api/v1/newcomer-training/tasks/{task_id}" in paths
    assert "/api/v1/newcomer-training/tasks/{task_id}/commands/request-cancel" in paths
    assert (
        "/api/v1/newcomer-training/audio-upload-sessions/"
        "{upload_session_id}/parts/{part_number}/content"
    ) in paths
    assert "/api/v1/newcomer-training/audio-artifacts/{artifact_id}/playback" in paths

    retired_paths = {
        "/api/v1/newcomer-training/modules/{module_id}",
        "/api/v1/newcomer-training/activities/{activity_id}/lesson/confirm",
        "/api/v1/newcomer-training/activities/{activity_id}/quiz/attempts",
        "/api/v1/newcomer-training/activities/{activity_id}/realtime/sessions",
        "/api/v1/newcomer-training/papers",
    }
    assert retired_paths.isdisjoint(paths)


def test_newcomer_training_has_one_governed_admin_surface() -> None:
    paths = create_app().openapi()["paths"]

    required_paths = {
        "/api/v1/admin/newcomer-training/capabilities",
        "/api/v1/admin/newcomer-training/workspace",
        "/api/v1/admin/newcomer-training/paths",
        "/api/v1/admin/newcomer-training/paths/{path_id}/workspace",
        "/api/v1/admin/newcomer-training/paths/{path_id}/working-revision",
        "/api/v1/admin/newcomer-training/paths/{path_id}/commands/validate",
        "/api/v1/admin/newcomer-training/path-revisions/{revision_id}/commands/publish",
        "/api/v1/admin/newcomer-training/release-plans/preview",
        "/api/v1/admin/newcomer-training/release-plans",
        "/api/v1/admin/newcomer-training/release-plans/{release_plan_id}/commands/publish",
        "/api/v1/admin/newcomer-training/release-plans/{release_plan_id}/rollback-preview",
        "/api/v1/admin/newcomer-training/release-plans/{release_plan_id}/commands/rollback",
        "/api/v1/admin/newcomer-training/cohorts",
        "/api/v1/admin/newcomer-training/cohorts/{cohort_id}/workspace",
        "/api/v1/admin/newcomer-training/cohorts/{cohort_id}/enrollments",
        "/api/v1/admin/newcomer-training/cohorts/{cohort_id}/enrollment-imports/preview",
        "/api/v1/admin/newcomer-training/enrollment-imports/commands/confirm",
        "/api/v1/admin/newcomer-training/enrollments/{enrollment_id}/revision-migrations/preview",
        "/api/v1/admin/newcomer-training/enrollments/{enrollment_id}/commands/migrate-revision",
        "/api/v1/admin/newcomer-training/enrollment-revision-migrations/preview",
        "/api/v1/admin/newcomer-training/enrollment-revision-migrations/commands/confirm",
        "/api/v1/admin/newcomer-training/resources",
        "/api/v1/admin/newcomer-training/resources/source_document/uploads",
        "/api/v1/admin/newcomer-training/resources/{resource_type}/{resource_id}/working-revision",
        "/api/v1/admin/newcomer-training/resources/{resource_type}/{resource_id}/commands/validate",
        "/api/v1/admin/newcomer-training/source-revisions/{revision_id}/anchors",
        "/api/v1/admin/newcomer-training/question-generation-options",
        "/api/v1/admin/newcomer-training/question-generation-batches",
        "/api/v1/admin/newcomer-training/question-candidates/bulk-review/preview",
        "/api/v1/admin/newcomer-training/question-candidates/bulk-review/commands/confirm",
        "/api/v1/admin/newcomer-training/question-candidates/commands/bulk-review",
        "/api/v1/admin/newcomer-training/assessment-tasks",
        "/api/v1/admin/newcomer-training/audits",
        "/api/v1/admin/newcomer-training/audio-assessments/queue",
        "/api/v1/admin/newcomer-training/audio-submissions/{submission_id}/commands/repair",
        "/api/v1/admin/newcomer-training/audio-submissions/{submission_id}/regrade/preview",
        "/api/v1/admin/newcomer-training/audio-submissions/{submission_id}/regrade/confirm",
        "/api/v1/admin/newcomer-training/audio-submissions/{submission_id}/transcript-correction/preview",
        "/api/v1/admin/newcomer-training/audio-submissions/{submission_id}/transcript-correction/confirm",
        "/api/v1/admin/newcomer-training/audio-submissions/{submission_id}/invalidation/preview",
        "/api/v1/admin/newcomer-training/audio-submissions/{submission_id}/invalidation/confirm",
        "/api/v1/admin/newcomer-training/coach-sessions/help-queue",
        "/api/v1/admin/newcomer-training/coach-sessions/{session_id}/help-detail",
        "/api/v1/admin/newcomer-training/coach-sessions/{session_id}/commands/intervene",
    }
    assert required_paths.issubset(paths)

    retired_paths = {
        "/api/v1/admin/newcomer-training/path/",
        "/api/v1/admin/newcomer-training/papers",
        "/api/v1/admin/newcomer-training/units",
        "/api/v1/admin/newcomer-training/regrades",
        "/api/v1/admin/newcomer-training/journey/manager",
    }
    assert retired_paths.isdisjoint(paths)
