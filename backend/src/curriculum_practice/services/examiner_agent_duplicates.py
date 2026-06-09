from __future__ import annotations

import uuid

from curriculum_practice.models import ExaminerAgent
from curriculum_practice.services.content_assets import _copy_suffix


def build_examiner_agent_duplicate(
    agent: ExaminerAgent,
    *,
    actor_id: str | None,
) -> ExaminerAgent:
    return ExaminerAgent(
        examiner_agent_id=str(uuid.uuid4()),
        name=_copy_suffix(agent.name),
        description=agent.description,
        question_source_ids=list(agent.question_source_ids or []),
        learner_level_strategy=dict(agent.learner_level_strategy or {}),
        scoring_policy_id=agent.scoring_policy_id,
        timeout_config=dict(agent.timeout_config or {}),
        safety_config=dict(agent.safety_config or {}),
        prompt_config=dict(agent.prompt_config or {}),
        simulation_config=dict(agent.simulation_config or {}),
        status="draft",
        version=1,
        content_hash=None,
        created_by=actor_id,
        updated_by=actor_id,
    )
