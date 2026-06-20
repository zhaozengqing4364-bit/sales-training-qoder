from __future__ import annotations

from collections.abc import Callable, Iterable

from agent.services.knowledge_contributor import register_agent_knowledge_contributor
from agent.services.practice_session_contributor import (
    register_agent_practice_session_contributor,
)
from curriculum_practice.services.practice_report_contributor import (
    register_curriculum_practice_report_contributor,
)
from curriculum_practice.services.practice_session_contributor import (
    register_curriculum_practice_session_contributor,
)
from curriculum_practice.services.question_bank_provider import (
    register_curriculum_question_bank_provider,
)
from curriculum_practice.services.runtime_gate_contributor import (
    register_curriculum_practice_runtime_gate_contributors,
)
from curriculum_practice.services.support_runtime_contributor import (
    register_curriculum_practice_support_runtime_contributors,
)
from evaluation.services.practice_report_contributor import (
    register_evaluation_practice_report_contributor,
)
from presentation_coach.services.practice_session_contributor import (
    register_presentation_coach_practice_session_contributor,
)
from presentation_coach.services.support_runtime_contributor import (
    register_presentation_coach_support_runtime_contributor,
)
from sales_bot.services.practice_session_contributor import (
    register_sales_bot_practice_session_contributor,
)
from sales_bot.services.support_runtime_contributor import (
    register_sales_bot_support_runtime_contributor,
)
from support.services.knowledge_contributor import (
    register_support_knowledge_contributor,
)
from training_runtime.practice_session_contributor import (
    register_training_runtime_practice_session_contributor,
)

DomainContributorRegistration = tuple[str, Callable[[], None]]

DOMAIN_CONTRIBUTOR_REGISTRATIONS: tuple[DomainContributorRegistration, ...] = (
    ("curriculum_question_bank_provider", register_curriculum_question_bank_provider),
    ("agent_knowledge_contributor", register_agent_knowledge_contributor),
    ("agent_practice_session_contributor", register_agent_practice_session_contributor),
    ("sales_bot_support_runtime_contributor", register_sales_bot_support_runtime_contributor),
    (
        "presentation_coach_support_runtime_contributor",
        register_presentation_coach_support_runtime_contributor,
    ),
    (
        "curriculum_practice_support_runtime_contributors",
        register_curriculum_practice_support_runtime_contributors,
    ),
    (
        "curriculum_practice_runtime_gate_contributors",
        register_curriculum_practice_runtime_gate_contributors,
    ),
    (
        "sales_bot_practice_session_contributor",
        register_sales_bot_practice_session_contributor,
    ),
    (
        "presentation_coach_practice_session_contributor",
        register_presentation_coach_practice_session_contributor,
    ),
    (
        "curriculum_practice_session_contributor",
        register_curriculum_practice_session_contributor,
    ),
    (
        "curriculum_practice_report_contributor",
        register_curriculum_practice_report_contributor,
    ),
    (
        "evaluation_practice_report_contributor",
        register_evaluation_practice_report_contributor,
    ),
    ("support_knowledge_contributor", register_support_knowledge_contributor),
    (
        "training_runtime_practice_session_contributor",
        register_training_runtime_practice_session_contributor,
    ),
)


def register_domain_contributors(
    registrations: Iterable[DomainContributorRegistration] | None = None,
) -> None:
    for _, register in registrations or DOMAIN_CONTRIBUTOR_REGISTRATIONS:
        register()
