from __future__ import annotations

from typing import Any

from common.db.models import PracticeSession
from common.services.practice_report_contributors import (
    register_roleplay_compliance_summary_contributor,
)
from curriculum_practice.services.roleplay_contracts import (
    roleplay_compliance_summary_from_session,
)

CURRICULUM_PRACTICE_REPORT_CONTRIBUTOR = "curriculum_practice.practice_report"


def build_curriculum_roleplay_compliance_summary(
    session: PracticeSession,
) -> dict[str, Any]:
    return roleplay_compliance_summary_from_session(
        curriculum_snapshot=getattr(session, "curriculum_snapshot", None),
        voice_policy_snapshot=getattr(session, "voice_policy_snapshot", None),
        runtime_state=getattr(session, "runtime_state", None),
    )


def register_curriculum_practice_report_contributor() -> None:
    register_roleplay_compliance_summary_contributor(
        CURRICULUM_PRACTICE_REPORT_CONTRIBUTOR,
        build_curriculum_roleplay_compliance_summary,
    )
