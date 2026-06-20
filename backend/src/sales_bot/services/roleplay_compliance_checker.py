from __future__ import annotations

from typing import Any

from common.roleplay_contracts import check_roleplay_output


def check_realtime_roleplay_output(
    *,
    roleplay_contract: dict[str, Any] | None,
    text: str,
    runtime_state: dict[str, Any] | None = None,
    current_visible_keys: list[str] | None = None,
    current_sales_stage: str | None = None,
) -> dict[str, Any]:
    return check_roleplay_output(
        contract=roleplay_contract or {},
        text=text,
        runtime_state=runtime_state,
        current_visible_keys=current_visible_keys,
        current_sales_stage=current_sales_stage,
    )
