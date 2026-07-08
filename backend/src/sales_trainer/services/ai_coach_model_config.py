from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.ai.config_manager import get_config_manager
from common.ai.models import ModelConfig, ModelType


class AiCoachModelConfigError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def resolve_ai_coach_llm_model_config(model_name: str | None) -> ModelConfig | None:
    normalized = str(model_name or "").strip()
    if not normalized:
        return None
    for config in get_config_manager().get_all_configs(ModelType.LLM):
        if str(config.id) == normalized or str(config.model_name) == normalized:
            return config
    raise AiCoachModelConfigError(
        "[AI_COACH_MODEL_CONFIG_NOT_FOUND]",
        f"AI 教练模型配置不存在或未启用：{normalized}",
    )


async def resolve_ai_coach_llm_model_config_from_db(
    db: AsyncSession,
    model_name: str | None,
) -> ModelConfig | None:
    normalized = str(model_name or "").strip()
    if not normalized:
        return None
    result = await db.execute(
        select(ModelConfig)
        .where(
            ModelConfig.model_type == ModelType.LLM.value,
            (ModelConfig.id == normalized) | (ModelConfig.model_name == normalized),
            ModelConfig.is_active.is_(True),
        )
        .order_by(ModelConfig.is_default.desc(), ModelConfig.updated_at.desc())
        .limit(1)
    )
    config = result.scalar_one_or_none()
    if config is not None:
        return config
    return resolve_ai_coach_llm_model_config(normalized)


def model_config_contract_payload(config: Any | None) -> dict[str, Any] | None:
    if config is None:
        return None
    extra_config = getattr(config, "extra_config", None)
    return {
        "provider": str(getattr(config, "provider", "") or ""),
        "base_url": str(getattr(config, "base_url", "") or ""),
        "model_name": str(getattr(config, "model_name", "") or ""),
        "extra_config": extra_config if isinstance(extra_config, dict) else {},
    }


def model_config_id(config: Any | None) -> str | None:
    if config is None:
        return None
    raw_id = getattr(config, "id", None)
    return str(raw_id) if raw_id is not None else None
