"""Root composition for every SQLAlchemy model bound to the shared metadata.

Alembic, application startup checks, and tests must call :func:`register_all_models`
instead of maintaining their own side-effect import lists. Domain modules still own
their model declarations; this module owns only root-level composition.
"""

from __future__ import annotations

from importlib import import_module

from sqlalchemy import MetaData

from common.db.model_registry.base import Base

PERSISTENCE_MODEL_MODULES: tuple[str, ...] = (
    "agent.models",
    "common.ai.models",
    "common.knowledge.models",
    "common.knowledge.rag_profile_models",
    "curriculum_practice.models",
    "task_runtime.models",
    "ai_platform.models",
    "newcomer_training.models",
    "learning.models",
    "audio_assessment.models",
    "ai_coach.models",
    "competency_evidence.models",
    "readiness.models",
    "sales_trainer.models",
    "sales_trainer.regrade_models",
)


def register_all_models() -> MetaData:
    """Import every domain-owned model module and return the shared metadata.

    Python module imports are idempotent, so callers can invoke this at each root
    composition surface without creating duplicate table declarations.
    """

    for module_name in PERSISTENCE_MODEL_MODULES:
        import_module(module_name)
    return Base.metadata


__all__ = ["PERSISTENCE_MODEL_MODULES", "register_all_models"]
