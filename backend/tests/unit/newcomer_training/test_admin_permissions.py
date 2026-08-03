from __future__ import annotations

from common.db.models import User
from foundation_admin_permissions import foundation_admin_actors


def test_learner_role_fails_closed_for_foundation_admin() -> None:
    actors = foundation_admin_actors(
        user=User(user_id="user-1", role="user"),
        organization_id="org-1",
    )

    assert actors.newcomer.capabilities == frozenset()
    assert actors.learning.capabilities == frozenset()
    assert actors.capabilities == frozenset()


def test_training_manager_receives_task_scoped_capabilities() -> None:
    actors = foundation_admin_actors(
        user=User(user_id="manager-1", role="training_manager"),
        organization_id="org-1",
    )

    assert "newcomer.path.manage" in actors.newcomer.capabilities
    assert "newcomer.path.publish" in actors.newcomer.capabilities
    assert "edit_paths" in actors.capabilities
    assert "manage_cohorts" in actors.capabilities
    assert "publish_releases" in actors.capabilities
    assert "govern_ai" not in actors.capabilities


def test_operations_role_cannot_publish_or_review_readiness() -> None:
    actors = foundation_admin_actors(
        user=User(user_id="ops-1", role="operations"),
        organization_id="org-1",
    )

    assert "newcomer.audio.regrade" in actors.newcomer.capabilities
    assert "retry_assessments" in actors.capabilities
    assert "regrade_results" in actors.capabilities
    assert "newcomer.path.publish" not in actors.newcomer.capabilities
    assert "publish_releases" not in actors.capabilities
    assert "review_readiness" not in actors.capabilities


def test_content_admin_can_prepare_content_but_cannot_publish_path() -> None:
    actors = foundation_admin_actors(
        user=User(user_id="content-1", role="content_admin"),
        organization_id="org-1",
    )

    assert "learning.content.manage" in actors.learning.capabilities
    assert "learning.question.review" in actors.learning.capabilities
    assert "learning.question.publish" not in actors.learning.capabilities
    assert "newcomer.path.publish" not in actors.newcomer.capabilities
    assert "newcomer.audio.review" not in actors.newcomer.capabilities
    assert "newcomer.audio.regrade" not in actors.newcomer.capabilities
    assert actors.capabilities == frozenset(
        {"view_overview", "edit_content", "review_questions"}
    )


def test_platform_admin_receives_organization_scoped_training_admin_capabilities() -> (
    None
):
    actors = foundation_admin_actors(
        user=User(user_id="admin-1", role="admin"),
        organization_id="org-1",
    )

    assert "newcomer.path.manage" in actors.newcomer.capabilities
    assert "newcomer.enrollment.migrate" in actors.newcomer.capabilities
    assert "newcomer.audio.review" in actors.newcomer.capabilities
    assert "newcomer.audio.regrade" in actors.newcomer.capabilities
    assert "newcomer.audio.transcript.correct" in actors.newcomer.capabilities
    assert "newcomer.audio.listen" in actors.newcomer.capabilities
    assert "newcomer.coach.review" in actors.newcomer.capabilities
    assert "learning.question.risk_review" in actors.learning.capabilities
    assert "publish_releases" in actors.capabilities
    assert "govern_ai" in actors.capabilities
    assert "view_sensitive_audit" in actors.capabilities
    assert actors.newcomer.organization_id == "org-1"
