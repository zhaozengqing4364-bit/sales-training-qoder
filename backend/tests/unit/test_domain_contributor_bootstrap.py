from __future__ import annotations

from collections.abc import Callable

import domain_contributor_bootstrap
import router_registry


def test_should_keep_domain_contributor_registration_order_pinned() -> None:
    assert [
        name
        for name, _ in domain_contributor_bootstrap.DOMAIN_CONTRIBUTOR_REGISTRATIONS
    ] == [
        "curriculum_question_bank_provider",
        "agent_knowledge_contributor",
        "agent_practice_session_contributor",
        "sales_bot_support_runtime_contributor",
        "presentation_coach_support_runtime_contributor",
        "curriculum_practice_support_runtime_contributors",
        "curriculum_practice_runtime_gate_contributors",
        "sales_bot_practice_session_contributor",
        "presentation_coach_practice_session_contributor",
        "curriculum_practice_session_contributor",
        "curriculum_practice_report_contributor",
        "evaluation_practice_report_contributor",
        "support_knowledge_contributor",
        "training_runtime_practice_session_contributor",
    ]


def test_register_domain_contributors_calls_registrars_in_order() -> None:
    calls: list[str] = []

    def registrar(name: str) -> Callable[[], None]:
        return lambda: calls.append(name)

    domain_contributor_bootstrap.register_domain_contributors(
        (
            ("sales", registrar("sales")),
            ("curriculum", registrar("curriculum")),
            ("training", registrar("training")),
        )
    )

    assert calls == ["sales", "curriculum", "training"]


def test_register_routers_runs_domain_bootstrap_before_mounting_routes(
    monkeypatch,
) -> None:
    events: list[str] = []

    class AppStub:
        def include_router(self, *_args, **_kwargs) -> None:
            events.append("include_router")

    monkeypatch.setattr(
        router_registry,
        "register_domain_contributors",
        lambda: events.append("domain_bootstrap"),
    )

    router_registry.register_routers(AppStub())

    assert events[0] == "domain_bootstrap"
    assert "include_router" in events[1:]
