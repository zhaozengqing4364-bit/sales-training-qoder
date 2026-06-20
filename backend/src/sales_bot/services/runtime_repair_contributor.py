from __future__ import annotations

from common.services.session_runtime_repair_service import (
    register_voice_runtime_policy_resolver_factory,
)
from sales_bot.services.voice_runtime_policy import VoiceRuntimePolicyService


def register_sales_bot_runtime_repair_contributor() -> None:
    register_voice_runtime_policy_resolver_factory(
        lambda db: VoiceRuntimePolicyService(db),
    )
