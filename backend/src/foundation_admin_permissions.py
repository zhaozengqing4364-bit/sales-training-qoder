"""Application-root role-to-capability projection for foundation administration."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from common.auth.roles import (
    CONTENT_ADMIN_ROLES,
    OPERATIONS_ROLES,
    PLATFORM_ADMIN_ROLES,
    READONLY_AUDITOR_ROLES,
    TRAINING_MANAGER_ROLES,
    normalize_role,
)
from common.db.models import User
from learning.contracts import LearningActor
from newcomer_training.application import CommandActor


class FoundationAdminActors(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    newcomer: CommandActor
    learning: LearningActor
    capabilities: frozenset[str] = frozenset()


FOUNDATION_ADMIN_CAPABILITIES = frozenset(
    {
        "view_overview",
        "edit_paths",
        "edit_content",
        "review_questions",
        "manage_cohorts",
        "retry_assessments",
        "regrade_results",
        "review_readiness",
        "publish_releases",
        "govern_ai",
        "view_sensitive_audit",
    }
)


_CONTENT_CAPABILITIES = frozenset(
    {
        "learning.source.manage",
        "learning.content.manage",
        "learning.question.generate",
        "learning.question.manage",
        "learning.question.review",
        "learning.quiz.manage",
    }
)

_TRAINING_ADMIN_CAPABILITIES = frozenset(
    {
        "newcomer.path.manage",
        "newcomer.path.publish",
        "newcomer.cohort.manage",
        "newcomer.enrollment.manage",
        "newcomer.enrollment.migrate",
        "newcomer.activity.invalidate",
        "newcomer.audio.review",
        "newcomer.audio.regrade",
        "newcomer.audio.transcript.correct",
        "newcomer.audio.listen",
        "newcomer.coach.review",
        "learning.lesson.invalidate",
        "learning.question.publish",
        "learning.question.risk_review",
    }
)

_UI_CAPABILITIES_BY_ROLE_GROUP = {
    "content": frozenset(
        {"view_overview", "edit_content", "review_questions"}
    ),
    "training": frozenset(
        {
            "view_overview",
            "edit_paths",
            "manage_cohorts",
            "review_readiness",
            "publish_releases",
        }
    ),
    "operations": frozenset(
        {
            "view_overview",
            "manage_cohorts",
            "retry_assessments",
            "regrade_results",
        }
    ),
    "auditor": frozenset({"view_overview", "view_sensitive_audit"}),
}


def foundation_admin_actors(
    *,
    user: User,
    organization_id: str,
    trace_id: str | None = None,
) -> FoundationAdminActors:
    """Project existing trusted roles into the frozen capability vocabulary.

    This is deliberately fail-closed. The current identity schema has no separate
    training-admin role, so platform-admin roles carry the organization-scoped
    training-admin capabilities until identity/access governance is completed.
    """

    role = normalize_role(getattr(user, "role", None), default="")
    learning_capabilities: set[str] = set()
    newcomer_capabilities: set[str] = set()
    ui_capabilities: set[str] = set()
    if role in CONTENT_ADMIN_ROLES:
        learning_capabilities.update(_CONTENT_CAPABILITIES)
        ui_capabilities.update(_UI_CAPABILITIES_BY_ROLE_GROUP["content"])
    if role in TRAINING_MANAGER_ROLES:
        ui_capabilities.update(_UI_CAPABILITIES_BY_ROLE_GROUP["training"])
        newcomer_capabilities.update(
            capability
            for capability in _TRAINING_ADMIN_CAPABILITIES
            if capability.startswith("newcomer.")
        )
        learning_capabilities.update(
            capability
            for capability in _TRAINING_ADMIN_CAPABILITIES
            if capability.startswith("learning.")
        )
    if role in OPERATIONS_ROLES:
        ui_capabilities.update(_UI_CAPABILITIES_BY_ROLE_GROUP["operations"])
        newcomer_capabilities.update(
            {
                "newcomer.cohort.manage",
                "newcomer.enrollment.manage",
                "newcomer.activity.invalidate",
                "newcomer.audio.review",
                "newcomer.audio.regrade",
                "newcomer.audio.transcript.correct",
                "newcomer.audio.listen",
                "newcomer.coach.review",
            }
        )
    if role in READONLY_AUDITOR_ROLES:
        ui_capabilities.update(_UI_CAPABILITIES_BY_ROLE_GROUP["auditor"])
    if role in PLATFORM_ADMIN_ROLES:
        ui_capabilities.update(FOUNDATION_ADMIN_CAPABILITIES)
        learning_capabilities.update(_CONTENT_CAPABILITIES)
        learning_capabilities.update(
            capability
            for capability in _TRAINING_ADMIN_CAPABILITIES
            if capability.startswith("learning.")
        )
        newcomer_capabilities.update(
            capability
            for capability in _TRAINING_ADMIN_CAPABILITIES
            if capability.startswith("newcomer.")
        )
    actor_id = str(user.user_id)
    return FoundationAdminActors(
        newcomer=CommandActor(
            organization_id=organization_id,
            actor_id=actor_id,
            capabilities=frozenset(newcomer_capabilities),
            trace_id=trace_id,
        ),
        learning=LearningActor(
            organization_id=organization_id,
            actor_id=actor_id,
            capabilities=frozenset(learning_capabilities),
            trace_id=trace_id,
        ),
        capabilities=frozenset(ui_capabilities),
    )


__all__ = [
    "FOUNDATION_ADMIN_CAPABILITIES",
    "FoundationAdminActors",
    "foundation_admin_actors",
]
