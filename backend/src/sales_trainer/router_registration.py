from __future__ import annotations

from fastapi import Depends, FastAPI

from common.auth.service import require_role
from sales_trainer.api import admin_router as sales_trainer_admin_router
from sales_trainer.api import router as sales_trainer_router
from sales_trainer.material_upload_api import sales_trainer_admin_material_upload_router
from sales_trainer.paper_api import (
    sales_trainer_admin_paper_router,
    sales_trainer_paper_router,
)
from sales_trainer.services.asset_revision_lineage_provider import (
    register_sales_trainer_asset_revision_lineage_provider,
)
from sales_trainer.unit_api import (
    sales_trainer_admin_unit_revision_router,
)


def register_sales_trainer_routers(app: FastAPI) -> None:
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
