from presentation_coach.services.prompt_role_resolver import (
    PresentationPromptRoleResolver,
    PromptRoleContext,
)


def _build_context(**overrides):
    base = PromptRoleContext(
        reason="forbidden_word",
        trigger="大概",
        transcript="我们大概可以这样做",
        page_number=2,
        required_points=["客户痛点", "价值证明"],
        forbidden_words=["大概", "可能"],
        agent_name="演讲教练",
        persona_name="严格评委",
        agent_system_prompt="你是专业演讲教练",
        persona_system_prompt="你要严格、简洁",
        persona_traits={"style": "strict"},
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def test_resolve_interruption_message_prefers_template_rendering():
    resolver = PresentationPromptRoleResolver()
    context = _build_context()

    message = resolver.resolve_interruption_message(
        context=context,
        template_text="{{ persona_name }}提醒：请不要使用‘{{ trigger }}’",
    )

    assert message == "严格评委提醒：请不要使用‘大概’"


def test_resolve_interruption_message_falls_back_when_template_invalid():
    resolver = PresentationPromptRoleResolver()
    context = _build_context()

    message = resolver.resolve_interruption_message(
        context=context,
        template_text="{{",
    )

    assert "大概" in message


def test_resolve_interruption_message_uses_reason_specific_fallback():
    resolver = PresentationPromptRoleResolver()
    context = _build_context(reason="missing_point", trigger="")

    message = resolver.resolve_interruption_message(
        context=context,
        template_text=None,
    )

    assert "要点" in message
