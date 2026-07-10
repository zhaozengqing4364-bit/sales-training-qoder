from __future__ import annotations

from fastapi import Depends, FastAPI

from common.auth.service import require_role
from sales_trainer.ai_coach_admin_api import router as ai_coach_admin_router
from sales_trainer.ai_coach_api import router as ai_coach_router
from sales_trainer.api import admin_router as sales_trainer_admin_router
from sales_trainer.api import router as sales_trainer_router
from sales_trainer.article_api import (
    newcomer_admin_article_router,
    newcomer_article_router,
)
from sales_trainer.business_etiquette_api import (
    business_etiquette_admin_router,
    business_etiquette_router,
)
from sales_trainer.customer_faq_api import customer_faq_router
from sales_trainer.dashboard_recommendation import (
    register_sales_trainer_dashboard_recommendation_provider,
)
from sales_trainer.material_upload_api import sales_trainer_admin_material_upload_router
from sales_trainer.paper_api import (
    newcomer_admin_paper_router,
    newcomer_paper_router,
    sales_trainer_admin_paper_router,
    sales_trainer_paper_router,
)
from sales_trainer.path_config_api import newcomer_admin_path_config_router
from sales_trainer.regrade_api import (
    newcomer_admin_regrade_router,
    sales_trainer_admin_regrade_router,
)
from sales_trainer.services.asset_revision_lineage_provider import (
    register_sales_trainer_asset_revision_lineage_provider,
)
from sales_trainer.unit_api import (
    newcomer_admin_unit_router,
    sales_trainer_admin_unit_revision_router,
)


def register_sales_trainer_routers(app: FastAPI) -> None:
    register_sales_trainer_dashboard_recommendation_provider()
    register_sales_trainer_asset_revision_lineage_provider()
    app.include_router(
        sales_trainer_router,
        prefix="/api/v1",
        tags=["sales-trainer"],
        dependencies=[Depends(require_role(["admin", "user"]))],
    )
    app.include_router(
        sales_trainer_paper_router,
        prefix="/api/v1",
        tags=["sales-trainer-papers"],
        dependencies=[Depends(require_role(["admin", "user"]))],
    )
    app.include_router(
        sales_trainer_admin_router,
        prefix="/api/v1",
        tags=["admin-sales-trainer"],
    )
    app.include_router(
        sales_trainer_admin_material_upload_router,
        prefix="/api/v1",
        tags=["admin-sales-trainer-materials"],
    )
    app.include_router(
        sales_trainer_admin_paper_router,
        prefix="/api/v1",
        tags=["admin-sales-trainer-papers"],
    )
    app.include_router(
        sales_trainer_admin_unit_revision_router,
        prefix="/api/v1",
        tags=["admin-sales-trainer-unit-revisions"],
    )
    app.include_router(
        newcomer_paper_router,
        prefix="/api/v1",
        tags=["newcomer-training"],
        dependencies=[Depends(require_role(["admin", "user"]))],
    )
    app.include_router(
        newcomer_article_router,
        prefix="/api/v1",
        tags=["newcomer-training-articles"],
        dependencies=[Depends(require_role(["admin", "user"]))],
    )
    app.include_router(
        business_etiquette_router,
        prefix="/api/v1",
        tags=["newcomer-training-business-etiquette"],
        dependencies=[Depends(require_role(["admin", "user"]))],
    )
    app.include_router(
        customer_faq_router,
        prefix="/api/v1",
        tags=["newcomer-training-customer-faq"],
        dependencies=[Depends(require_role(["admin", "user"]))],
    )
    app.include_router(
        newcomer_admin_article_router,
        prefix="/api/v1",
        tags=["admin-newcomer-training-articles"],
    )
    app.include_router(
        business_etiquette_admin_router,
        prefix="/api/v1",
        tags=["admin-newcomer-training-business-etiquette"],
    )
    app.include_router(
        newcomer_admin_paper_router,
        prefix="/api/v1",
        tags=["admin-newcomer-training"],
    )
    app.include_router(
        newcomer_admin_path_config_router,
        prefix="/api/v1",
        tags=["admin-newcomer-training-path-config"],
    )
    app.include_router(
        sales_trainer_admin_regrade_router,
        prefix="/api/v1",
        tags=["admin-sales-trainer-regrades"],
    )
    app.include_router(
        newcomer_admin_regrade_router,
        prefix="/api/v1",
        tags=["admin-newcomer-training-regrades"],
    )
    app.include_router(
        newcomer_admin_unit_router,
        prefix="/api/v1",
        tags=["admin-newcomer-training-units"],
    )
    app.include_router(
        ai_coach_router,
        prefix="/api/v1",
        tags=["newcomer-training-ai-coach"],
        dependencies=[Depends(require_role(["admin", "user"]))],
    )
    app.include_router(
        ai_coach_admin_router,
        prefix="/api/v1",
        tags=["admin-newcomer-training-ai-coach"],
    )
