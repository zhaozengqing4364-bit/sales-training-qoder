"""Central registry for non-WebSocket API routers."""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI
from fastapi.routing import APIRoute

from admin.api.admin import router as admin_presentations_router
from admin.api.analytics import router as admin_analytics_router
from admin.api.audit_trail import router as audit_trail_router
from admin.api.business_rules import router as business_rules_router
from admin.api.config_bundles import router as config_bundles_router
from admin.api.config_center import router as config_center_router
from admin.api.governance import ai_governance_router
from admin.api.governance import router as admin_governance_router
from admin.api.interventions import router as admin_interventions_router
from admin.api.knowledge_answer_config import router as knowledge_answer_config_router
from admin.api.model_configs import router as model_configs_router
from admin.api.presentation_ai import router as presentation_ai_router
from admin.api.rag_profiles import router as rag_profiles_router
from admin.api.release_verification import router as release_verification_router
from admin.api.settings import router as admin_settings_router
from admin.api.system_logs import router as admin_system_logs_router
from admin.api.training_records import router as admin_training_records_router
from admin.api.users import router as admin_users_router
from admin.api.voice_runtime import router as voice_runtime_router
from agent.api.agent_personas import admin_router as agent_persona_admin_router
from agent.api.agents import admin_router as agent_admin_router
from agent.api.agents import user_router as agent_user_router
from agent.api.personas import admin_router as persona_admin_router
from common.api import (
    analytics,
    business_rules,
    dashboard,
    growth,
    practice,
    training,
    training_tasks,
    users,
)
from common.api.knowledge_debug import router as knowledge_debug_router
from common.auth.api import router as auth_router
from common.auth.service import (
    get_current_admin_user,
    get_current_admin_user_for_app_routes,
    require_role,
)
from common.conversation.api import router as replay_router
from common.knowledge.api import admin_router as knowledge_admin_router
from common.knowledge.api import internal_router as knowledge_internal_router
from evaluation.api import router as evaluation_router
from presentation_coach.api import presentations
from prompt_templates.api.routes import router as prompt_templates_router
from prompt_templates.api.routes import scenario_router as scenario_prompts_router
from sales_bot.api.scenarios import router as scenarios_router
from supervisor.api import router as supervisor_router
from support.api.runtime_status import router as support_runtime_router


def _build_knowledge_bases_alias_router() -> APIRouter:
    """Mirror knowledge admin routes under the legacy knowledge-bases alias."""
    knowledge_bases_alias_router = APIRouter(
        prefix="/admin/knowledge-bases", tags=["admin-knowledge-bases"]
    )

    for route in knowledge_admin_router.routes:
        if not isinstance(route, APIRoute):
            continue

        alias_path = route.path
        if alias_path.startswith("/admin/knowledge"):
            alias_path = alias_path.replace("/admin/knowledge", "", 1)

        knowledge_bases_alias_router.add_api_route(
            alias_path,
            route.endpoint,
            methods=route.methods,
            status_code=route.status_code,
        )

    return knowledge_bases_alias_router


def register_routers(app: FastAPI) -> None:
    """Mount all non-WebSocket API routers on the FastAPI app."""
    app.include_router(
        presentations.router,
        prefix="/api/v1",
        tags=["presentations"],
        dependencies=[Depends(require_role(["admin", "user"]))],
    )
    app.include_router(
        practice.router,
        prefix="/api/v1",
        tags=["practice"],
        dependencies=[Depends(require_role(["admin", "user"]))],
    )
    app.include_router(analytics.router, prefix="/api/v1", tags=["analytics"])
    app.include_router(dashboard.router, prefix="/api/v1", tags=["dashboard"])
    app.include_router(
        growth.router,
        prefix="/api/v1",
        tags=["growth"],
        dependencies=[Depends(require_role(["admin", "user"]))],
    )
    app.include_router(
        training.router,
        prefix="/api/v1",
        tags=["training"],
        dependencies=[Depends(require_role(["admin", "user"]))],
    )
    app.include_router(
        training_tasks.router,
        prefix="/api/v1",
        tags=["training-tasks"],
        dependencies=[Depends(require_role(["admin", "support", "user"]))],
    )
    app.include_router(
        business_rules.router,
        prefix="/api/v1",
        tags=["business-rules"],
        dependencies=[Depends(require_role(["admin", "user"]))],
    )
    app.include_router(
        scenarios_router,
        prefix="/api/v1",
        tags=["scenarios"],
        dependencies=[Depends(require_role(["admin", "user"]))],
    )
    app.include_router(
        admin_presentations_router,
        prefix="/api/v1",
        tags=["admin-presentations"],
        dependencies=[Depends(get_current_admin_user_for_app_routes)],
    )
    app.include_router(users.router, prefix="/api/v1", tags=["users"])

    app.include_router(auth_router, prefix="/api/v1", tags=["auth"])

    app.include_router(agent_admin_router, prefix="/api/v1", tags=["admin-agents"])
    app.include_router(agent_user_router, prefix="/api/v1", tags=["agents"])
    app.include_router(persona_admin_router, prefix="/api/v1", tags=["admin-personas"])
    app.include_router(
        agent_persona_admin_router, prefix="/api/v1", tags=["admin-agent-personas"]
    )

    app.include_router(
        knowledge_admin_router,
        prefix="/api/v1",
        tags=["admin-knowledge"],
        dependencies=[Depends(get_current_admin_user_for_app_routes)],
    )
    app.include_router(
        knowledge_internal_router, prefix="/api/v1", tags=["internal-knowledge"]
    )
    app.include_router(
        _build_knowledge_bases_alias_router(),
        prefix="/api/v1",
        tags=["admin-knowledge-bases"],
        dependencies=[Depends(get_current_admin_user_for_app_routes)],
    )

    app.include_router(replay_router, prefix="/api/v1", tags=["replay"])

    app.include_router(
        admin_users_router,
        prefix="/api/v1",
        tags=["admin-users"],
        dependencies=[Depends(get_current_admin_user)],
    )
    app.include_router(
        admin_training_records_router,
        prefix="/api/v1",
        tags=["admin-training-records"],
        dependencies=[Depends(get_current_admin_user)],
    )
    app.include_router(
        business_rules_router,
        prefix="/api/v1/admin",
        tags=["admin-business-rules"],
    )
    app.include_router(
        config_bundles_router,
        prefix="/api/v1/admin",
        tags=["admin-config-bundles"],
    )
    app.include_router(
        config_center_router,
        prefix="/api/v1/admin",
        tags=["admin-config-center"],
    )
    app.include_router(
        audit_trail_router,
        prefix="/api/v1/admin",
        tags=["admin-audit-trail"],
    )
    app.include_router(
        admin_analytics_router,
        prefix="/api/v1",
        tags=["admin-analytics"],
        dependencies=[Depends(get_current_admin_user_for_app_routes)],
    )
    app.include_router(
        admin_governance_router,
        prefix="/api/v1/admin",
        tags=["admin-governance"],
        dependencies=[Depends(get_current_admin_user)],
    )
    app.include_router(
        ai_governance_router,
        prefix="/api/v1/admin",
        tags=["admin-ai-governance"],
        dependencies=[Depends(get_current_admin_user)],
    )
    app.include_router(
        admin_settings_router,
        prefix="/api/v1/admin",
        tags=["admin-settings"],
    )
    app.include_router(
        admin_interventions_router,
        prefix="/api/v1",
        tags=["admin-interventions"],
        dependencies=[Depends(get_current_admin_user)],
    )
    app.include_router(
        admin_system_logs_router,
        prefix="/api/v1",
        tags=["admin-system-logs"],
    )
    app.include_router(
        knowledge_answer_config_router,
        prefix="/api/v1/admin",
        tags=["admin-knowledge-answer"],
    )
    app.include_router(
        rag_profiles_router,
        prefix="/api/v1/admin",
        tags=["admin-rag-profiles"],
    )

    app.include_router(
        support_runtime_router,
        prefix="/api/v1",
        tags=["support-runtime"],
        dependencies=[Depends(require_role(["admin", "support"]))],
    )
    app.include_router(
        knowledge_debug_router,
        prefix="/api/v1",
        tags=["knowledge-debug"],
        dependencies=[Depends(require_role(["admin", "support"]))],
    )

    app.include_router(
        model_configs_router, prefix="/api/v1/admin", tags=["admin-model-configs"]
    )
    app.include_router(
        voice_runtime_router, prefix="/api/v1/admin", tags=["admin-voice-runtime"]
    )
    app.include_router(
        presentation_ai_router, prefix="/api/v1/admin", tags=["admin-presentation-ai"]
    )
    app.include_router(
        release_verification_router,
        prefix="/api/v1",
        tags=["release-verification"],
    )

    app.include_router(prompt_templates_router, tags=["prompt-templates"])
    app.include_router(scenario_prompts_router, tags=["scenario-prompts"])

    app.include_router(evaluation_router, prefix="/api/v1", tags=["evaluation"])
    app.include_router(supervisor_router, prefix="/api/v1", tags=["supervisor"])
