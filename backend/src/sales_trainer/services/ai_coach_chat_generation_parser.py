from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from sales_trainer.ai_coach_chat_schemas import (
    AiCoachChatResponseInternalV1,
    AiCoachQuizCardPayloadInternalV1,
)
from sales_trainer.schemas import AiCoachConfig
from sales_trainer.services.ai_coach_chat_errors import AiCoachChatGenerationError


class AiCoachChatResponseParser:
    def parse_model_response(
        self,
        text: str,
        config: AiCoachConfig,
    ) -> AiCoachChatResponseInternalV1:
        raw = self.extract_json(text)
        if raw is None:
            raise AiCoachChatGenerationError(
                "[AI_COACH_INTERACTION_INVALID]",
                "AI 教练返回内容不是合法 JSON。",
                502,
            )
        try:
            parsed = AiCoachChatResponseInternalV1.model_validate(raw)
        except ValidationError as exc:
            first = exc.errors()[0]
            raise AiCoachChatGenerationError(
                f"[AI_COACH_INTERACTION_INVALID:{first['type']}]",
                "AI 教练 Chat 响应不符合契约。",
                502,
            ) from exc
        self.validate_response_against_config(parsed, config)
        return parsed

    def validate_response_against_config(
        self,
        response: AiCoachChatResponseInternalV1,
        config: AiCoachConfig,
    ) -> None:
        allowed_ui = set(self.allowed_ui_event_types(config))
        allowed_interactions = set(config.allowed_interaction_types)
        max_cards = int(config.max_cards_per_message)
        quiz_count = 0
        for event in response.ui_events:
            if event.type not in allowed_ui:
                raise AiCoachChatGenerationError(
                    "[AI_COACH_UI_EVENT_TYPE_NOT_ALLOWED]",
                    "AI 教练生成了未授权的 UI 卡片类型。",
                    502,
                )
            if event.type != "quiz_card":
                continue
            quiz_count += 1
            payload = event.payload
            if not isinstance(payload, AiCoachQuizCardPayloadInternalV1):
                raise AiCoachChatGenerationError(
                    "[AI_COACH_INTERACTION_INVALID]",
                    "quiz_card payload 非法。",
                    502,
                )
            if payload.interaction.interaction_type not in allowed_interactions:
                raise AiCoachChatGenerationError(
                    "[AI_COACH_INTERACTION_TYPE_NOT_ALLOWED]",
                    "AI 教练生成了未授权的互动题型。",
                    502,
                )
        if quiz_count > max_cards:
            raise AiCoachChatGenerationError(
                "[AI_COACH_INTERACTION_INVALID]",
                "AI 教练单轮生成卡片数量超过配置上限。",
                502,
            )

    @staticmethod
    def allowed_ui_event_types(config: AiCoachConfig) -> tuple[str, ...]:
        return tuple(str(item) for item in config.allowed_ui_event_types)

    @staticmethod
    def extract_json(text: str) -> dict[str, Any] | None:
        content = text.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[-1]
            if content.endswith("```"):
                content = content[:-3].strip()
            if content.startswith("json"):
                content = content[4:].strip()
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            start = content.find("{")
            end = content.rfind("}")
            if start < 0 or end <= start:
                return None
            try:
                parsed = json.loads(content[start : end + 1])
            except json.JSONDecodeError:
                return None
        return parsed if isinstance(parsed, dict) else None
