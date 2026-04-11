"""Code-owned admin RBAC inventory for M016/S03.

This module is intentionally data-only: future agents can inspect one place to see
which admin route families already prove admin-only access, which ones still only
require generic authentication, and which surfaces should be fixed first.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

PermissionRisk = Literal["high", "medium", "baseline"]
PriorityClass = Literal["fix-first", "watch", "baseline"]


@dataclass(frozen=True)
class AdminRoutePermissionEntry:
    """One admin route family and the proof currently attached to it."""

    route_family: str
    auth_surface: str
    routes: tuple[str, ...]
    allowed_roles: tuple[str, ...]
    non_admin_deny_path: str
    current_evidence: tuple[str, ...]
    risk: PermissionRisk
    priority: PriorityClass
    rationale: str


ADMIN_ROUTE_PERMISSION_MATRIX: tuple[AdminRoutePermissionEntry, ...] = (
    AdminRoutePermissionEntry(
        route_family="admin.api.admin",
        auth_surface="Depends(get_current_user)",
        routes=(
            "POST /admin/presentations",
            "POST /admin/presentations/upload",
            "GET /admin/presentations*",
            "DELETE /admin/presentations/{presentation_id}",
            "PUT /admin/presentations/{presentation_id}/pages/{page_number}",
            "POST /admin/presentations/{presentation_id}/pages/{page_number}/talking-points",
            "DELETE /admin/talking-points/{point_id}",
            "POST /admin/presentations/{presentation_id}/forbidden-words",
            "DELETE /admin/forbidden-words/{word_id}",
        ),
        allowed_roles=("any authenticated active user",),
        non_admin_deny_path="missing role denial: get_current_user only rejects anonymous/disabled callers",
        current_evidence=(
            "backend/src/admin/api/admin.py",
            "No focused non-admin denial proof under backend/tests/* yet",
        ),
        risk="high",
        priority="fix-first",
        rationale="Shared training content CRUD still sits behind plain authentication even though the URL family is admin-scoped.",
    ),
    AdminRoutePermissionEntry(
        route_family="admin.api.analytics",
        auth_surface="Depends(get_current_user)",
        routes=(
            "GET /admin/analytics/overview",
            "GET /admin/analytics/trends",
            "GET /admin/analytics/agents",
            "GET /admin/analytics/leaderboard",
            "GET /admin/analytics/operating-pack",
            "GET /admin/analytics/runtime-metrics",
            "GET /admin/analytics/policy-effectiveness",
            "GET /admin/analytics/voice-mode-comparison",
            "GET /admin/analytics/fallback-metrics",
            "GET /admin/analytics/export",
        ),
        allowed_roles=("any authenticated active user",),
        non_admin_deny_path="missing role denial: get_current_user only rejects anonymous/disabled callers",
        current_evidence=(
            "backend/src/admin/api/analytics.py",
            "No focused non-admin denial proof under backend/tests/* yet",
        ),
        risk="high",
        priority="fix-first",
        rationale="System-wide analytics and export endpoints expose cross-user aggregates without an admin-only guard.",
    ),
    AdminRoutePermissionEntry(
        route_family="admin.api.release_verification",
        auth_surface="Depends(get_current_user)",
        routes=(
            "POST /admin/release-verification/candidates",
            "GET /admin/release-verification/candidates*",
            "PUT /admin/release-verification/checks/{record_id}",
            "POST /admin/release-verification/candidates/{release_candidate_id}/decision",
            "POST /admin/release-verification/candidates/{release_candidate_id}/run-verification",
            "POST /admin/release-verification/candidates/{release_candidate_id}/auto-decision",
        ),
        allowed_roles=("any authenticated active user",),
        non_admin_deny_path="missing role denial: get_current_user only rejects anonymous/disabled callers",
        current_evidence=(
            "backend/src/admin/api/release_verification.py",
            "No focused non-admin denial proof under backend/tests/* yet",
        ),
        risk="high",
        priority="fix-first",
        rationale="Release gate creation and decision endpoints are operationally privileged but still use generic auth.",
    ),
    AdminRoutePermissionEntry(
        route_family="admin.api.system_logs",
        auth_surface="Depends(get_current_user)",
        routes=(
            "GET /admin/system-logs",
            "GET /admin/system-logs/{log_id}",
        ),
        allowed_roles=("any authenticated active user",),
        non_admin_deny_path="missing role denial: get_current_user only rejects anonymous/disabled callers",
        current_evidence=(
            "backend/src/admin/api/system_logs.py",
            "No focused non-admin denial proof under backend/tests/* yet",
        ),
        risk="high",
        priority="fix-first",
        rationale="Audit-log read access is both cross-user and likely to surface sensitive operational details.",
    ),
    AdminRoutePermissionEntry(
        route_family="admin.api.training_records",
        auth_surface="Depends(get_current_user)",
        routes=(
            "GET /admin/training-records",
            "GET /admin/training-records/{record_id}",
            "DELETE /admin/training-records/{record_id}",
        ),
        allowed_roles=("any authenticated active user",),
        non_admin_deny_path="missing role denial: get_current_user only rejects anonymous/disabled callers",
        current_evidence=(
            "backend/src/admin/api/training_records.py",
            "No focused non-admin denial proof under backend/tests/* yet",
        ),
        risk="high",
        priority="fix-first",
        rationale="This route family can enumerate and delete other users' sessions while only checking for a valid login.",
    ),
    AdminRoutePermissionEntry(
        route_family="admin.api.users",
        auth_surface="Depends(get_current_admin_user)",
        routes=(
            "GET /admin/users*",
            "POST /admin/users",
            "PUT /admin/users/{user_id}",
            "PUT /admin/users/{user_id}/role",
            "POST /admin/users/{user_id}/suspend",
            "POST /admin/users/{user_id}/activate",
            "DELETE /admin/users/{user_id}",
            "GET /admin/users/export",
        ),
        allowed_roles=("admin",),
        non_admin_deny_path="common.auth.service.get_current_admin_user -> 403 [ROLE_REQUIRED]",
        current_evidence=(
            "backend/src/admin/api/users.py",
            "backend/tests/integration/test_admin_users_api.py::test_non_admin_cannot_access_admin_users_api",
            "backend/tests/integration/test_admin_users_api.py::test_non_admin_cannot_update_user_role",
        ),
        risk="baseline",
        priority="baseline",
        rationale="This is the current positive-control route family for admin-only guard behavior and audit-log masking.",
    ),
    AdminRoutePermissionEntry(
        route_family="admin.api.interventions",
        auth_surface="Depends(get_current_admin_user)",
        routes=(
            "GET /admin/interventions/lists",
            "GET /admin/interventions",
            "POST /admin/interventions",
            "PATCH /admin/interventions/{intervention_id}",
            "POST /admin/interventions/remind",
        ),
        allowed_roles=("admin",),
        non_admin_deny_path="common.auth.service.get_current_admin_user -> 403 [ROLE_REQUIRED]",
        current_evidence=(
            "backend/src/admin/api/interventions.py",
            "Route family already uses the admin dependency at each entrypoint",
        ),
        risk="baseline",
        priority="watch",
        rationale="RBAC is explicit here, but reminder logging still deserves follow-up redaction review because payload.note is freeform.",
    ),
    AdminRoutePermissionEntry(
        route_family="admin.api.knowledge_answer_config",
        auth_surface="router dependencies=[Depends(get_current_admin_user)] + endpoint admin writes",
        routes=(
            "GET/PUT /admin/knowledge-answer-config/config",
            "GET/POST/PUT/DELETE /admin/knowledge-answer-config/versions/**",
            "POST /admin/knowledge-answer-config/debug/trigger",
        ),
        allowed_roles=("admin",),
        non_admin_deny_path="router-level get_current_admin_user -> 403 [ROLE_REQUIRED]",
        current_evidence=(
            "backend/src/admin/api/knowledge_answer_config.py",
            "Route family is guarded at router level for reads and endpoint level for writes",
        ),
        risk="baseline",
        priority="watch",
        rationale="Config control-plane is already on the correct admin-only seam.",
    ),
    AdminRoutePermissionEntry(
        route_family="admin.api.model_configs",
        auth_surface="router dependencies=[Depends(get_current_admin_user)] + endpoint admin writes",
        routes=(
            "GET/POST/DELETE /admin/model-configs",
            "POST /admin/model-configs/test",
            "POST /admin/model-configs/tts/preview",
        ),
        allowed_roles=("admin",),
        non_admin_deny_path="router-level get_current_admin_user -> 403 [ROLE_REQUIRED]",
        current_evidence=(
            "backend/src/admin/api/model_configs.py",
            "Route family is guarded at router level for reads and endpoint level for writes",
        ),
        risk="baseline",
        priority="watch",
        rationale="Model config control-plane already uses explicit admin dependencies; later work should focus on secret-safe logging instead of RBAC shape.",
    ),
    AdminRoutePermissionEntry(
        route_family="admin.api.presentation_ai",
        auth_surface="router dependencies=[Depends(get_current_admin_user)] + endpoint admin writes",
        routes=(
            "GET /admin/presentation-ai/policy",
            "PUT /admin/presentation-ai/policy",
            "POST /admin/presentation-ai/policy/preview",
            "GET /admin/presentation-ai/policy/effective",
        ),
        allowed_roles=("admin",),
        non_admin_deny_path="router-level get_current_admin_user -> 403 [ROLE_REQUIRED]",
        current_evidence=(
            "backend/src/admin/api/presentation_ai.py",
            "Route family is guarded at router level for reads and endpoint level for writes",
        ),
        risk="baseline",
        priority="watch",
        rationale="Presentation AI policy endpoints already follow the intended admin-only pattern.",
    ),
    AdminRoutePermissionEntry(
        route_family="admin.api.rag_profiles + voice_runtime",
        auth_surface="router dependencies=[Depends(get_current_admin_user)] + endpoint admin writes",
        routes=(
            "GET/POST/PUT/DELETE /admin/rag-profiles/**",
            "GET/POST/PUT/DELETE /admin/voice-runtime/**",
        ),
        allowed_roles=("admin",),
        non_admin_deny_path="router-level get_current_admin_user -> 403 [ROLE_REQUIRED]",
        current_evidence=(
            "backend/src/admin/api/rag_profiles.py",
            "backend/src/admin/api/voice_runtime.py",
        ),
        risk="baseline",
        priority="watch",
        rationale="These route families already use router-scoped admin protection and form the target seam for the legacy families above.",
    ),
)


FIX_FIRST_ADMIN_ROUTE_FAMILIES: tuple[str, ...] = tuple(
    entry.route_family
    for entry in ADMIN_ROUTE_PERMISSION_MATRIX
    if entry.priority == "fix-first"
)


ADMIN_PERMISSION_POSITIVE_CONTROL: tuple[str, ...] = (
    "admin.api.users",
    "admin.api.interventions",
    "admin.api.knowledge_answer_config",
    "admin.api.model_configs",
    "admin.api.presentation_ai",
    "admin.api.rag_profiles + voice_runtime",
)


__all__ = [
    "AdminRoutePermissionEntry",
    "ADMIN_ROUTE_PERMISSION_MATRIX",
    "ADMIN_PERMISSION_POSITIVE_CONTROL",
    "FIX_FIRST_ADMIN_ROUTE_FAMILIES",
]
