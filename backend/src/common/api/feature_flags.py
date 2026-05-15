"""Public feature flag read surface."""

from fastapi import APIRouter

from common.config import Settings, settings

router = APIRouter(prefix="/feature-flags", tags=["feature-flags"])


def read_feature_flags(source: Settings = settings) -> dict[str, dict[str, bool]]:
    """Return feature flags safe for backend and frontend consumers."""
    return {"curriculum": {"examiner": source.CURRICULUM_EXAMINER_ENABLED}}


@router.get("")
async def get_feature_flags() -> dict[str, dict[str, bool]]:
    return read_feature_flags()
