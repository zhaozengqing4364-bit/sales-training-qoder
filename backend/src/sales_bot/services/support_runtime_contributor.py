from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from sales_bot.services.voice_runtime_policy import VoiceRuntimePolicyService
from support.services.runtime_contributors import (
    register_voice_policy_tool_types_contributor,
)

SALES_BOT_SUPPORT_RUNTIME_CONTRIBUTOR = "sales_bot.voice_runtime_policy"


async def build_sales_bot_voice_policy_tool_types(
    db: AsyncSession,
    snapshot: dict[str, Any],
) -> list[str]:
    preview_tools = VoiceRuntimePolicyService(db).build_stepfun_tools(snapshot)
    return [
        str(tool.get("type") or "")
        for tool in preview_tools
        if isinstance(tool, dict)
    ]


def register_sales_bot_support_runtime_contributor() -> None:
    register_voice_policy_tool_types_contributor(
        SALES_BOT_SUPPORT_RUNTIME_CONTRIBUTOR,
        build_sales_bot_voice_policy_tool_types,
    )
