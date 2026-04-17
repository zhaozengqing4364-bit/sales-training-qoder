from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from prompt_templates.renderer import get_renderer


@dataclass
class PromptRoleContext:
    reason: str
    trigger: str
    transcript: str
    page_number: int
    required_points: list[str] = field(default_factory=list)
    forbidden_words: list[str] = field(default_factory=list)
    agent_name: str | None = None
    persona_name: str | None = None
    agent_system_prompt: str | None = None
    persona_system_prompt: str | None = None
    persona_traits: dict[str, Any] = field(default_factory=dict)


class PresentationPromptRoleResolver:
    def __init__(self) -> None:
        self.renderer = get_renderer()

    def resolve_interruption_message(
        self,
        *,
        context: PromptRoleContext,
        template_text: str | None,
    ) -> str:
        normalized_template = (template_text or "").strip()
        if normalized_template:
            rendered = self.renderer.render(
                template=normalized_template,
                variables=self._build_variables(context),
                strict=False,
            )
            if rendered.success and rendered.rendered.strip():
                return rendered.rendered.strip()

        return self._fallback_message(context)

    def _build_variables(self, context: PromptRoleContext) -> dict[str, Any]:
        data = asdict(context)
        data["required_points_text"] = "、".join(context.required_points)
        data["forbidden_words_text"] = "、".join(context.forbidden_words)
        data["agent_name"] = context.agent_name or "演讲教练"
        data["persona_name"] = context.persona_name or "评委"
        data["trigger"] = context.trigger.strip()
        return data

    def _fallback_message(self, context: PromptRoleContext) -> str:
        trigger = context.trigger.strip()
        reason = (context.reason or "").strip().lower()
        prefix = context.persona_name or context.agent_name or "教练"

        if reason == "forbidden_word":
            word = trigger or "该表达"
            return f"{prefix}提醒：请避免使用‘{word}’，换一种更专业的说法。"
        if reason == "missing_point":
            if context.required_points:
                points = "、".join(context.required_points)
                return f"{prefix}提醒：你还没有覆盖关键要点（{points}），请补充说明。"
            return f"{prefix}提醒：你还有关键要点未覆盖，请补充说明。"
        if reason == "vague_response":
            return f"{prefix}提醒：当前表达偏模糊，请用更具体的数据或案例。"

        if trigger:
            return f"{prefix}提醒：请围绕‘{trigger}’补充更清晰的表达。"
        return f"{prefix}提醒：请继续，并用更清晰具体的方式表达。"
