"""
Migrate legacy agent/persona prompt+KB settings into persona_policy.

Usage:
    python -m agent.migrations.migrate_persona_policy          # dry-run
    python -m agent.migrations.migrate_persona_policy --apply  # persist changes
"""

from __future__ import annotations

import argparse
import asyncio
from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from agent.models import AgentPersona, AgentVoicePolicy, Persona
from agent.services.persona_policy import (
    resolve_persona_policy,
    sync_legacy_persona_fields,
)
from common.db.session import AsyncSessionLocal
from common.monitoring.logger import get_logger

logger = get_logger(__name__)


def _as_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    deduped: list[str] = []
    seen: set[str] = set()
    for item in value:
        normalized = str(item).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


async def migrate_persona_policy(db: AsyncSession, *, apply_changes: bool) -> dict[str, Any]:
    personas_result = await db.execute(
        select(Persona).options(
            selectinload(Persona.agent_personas).selectinload(AgentPersona.agent)
        )
    )
    personas = personas_result.scalars().all()

    agent_policy_result = await db.execute(select(AgentVoicePolicy))
    agent_policies = {
        str(policy.agent_id): policy for policy in agent_policy_result.scalars().all()
    }

    updated_count = 0
    skipped_count = 0
    conflict_report: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for persona in personas:
        base_policy = resolve_persona_policy(persona)
        base_kb_ids = _as_list(base_policy.get("knowledge_base_ids"))
        base_tool_policy = _as_dict(base_policy.get("tool_policy"))

        kb_variants: set[tuple[str, ...]] = set()
        kb_variant_agents: dict[tuple[str, ...], list[str]] = defaultdict(list)
        kb_grounding_variants: set[bool] = set()
        kb_grounding_agents: dict[bool, list[str]] = defaultdict(list)

        linked_agents = list(persona.agent_personas or [])
        for agent_link in linked_agents:
            agent = getattr(agent_link, "agent", None)
            if agent is None:
                continue

            merged_kb_ids = sorted(
                set(base_kb_ids + _as_list(getattr(agent, "default_knowledge_base_ids", [])))
            )
            kb_signature = tuple(merged_kb_ids)
            kb_variants.add(kb_signature)
            kb_variant_agents[kb_signature].append(str(agent.id))

            policy = agent_policies.get(str(agent.id))
            policy_override = _as_dict(
                getattr(policy, "tool_policy_override", {}) if policy else {}
            )
            requires_kb_grounding = bool(policy_override.get("require_kb_grounding", False))
            kb_grounding_variants.add(requires_kb_grounding)
            kb_grounding_agents[requires_kb_grounding].append(str(agent.id))

        has_kb_conflict = len(kb_variants) > 1
        has_grounding_conflict = len(kb_grounding_variants) > 1

        if has_kb_conflict or has_grounding_conflict:
            skipped_count += 1
            conflict_report[str(persona.id)].append(
                {
                    "persona_name": persona.name,
                    "kb_variants": {
                        ",".join(signature): agents
                        for signature, agents in kb_variant_agents.items()
                    },
                    "require_kb_grounding_variants": kb_grounding_agents,
                    "recommendation": "split_persona_or_manual_policy_resolution",
                }
            )
            continue

        target_kb_ids = list(next(iter(kb_variants), tuple(base_kb_ids)))
        target_require_kb_grounding = bool(
            next(iter(kb_grounding_variants), bool(base_tool_policy.get("require_kb_grounding", False)))
        )

        next_policy = {
            **base_policy,
            "knowledge_base_ids": target_kb_ids,
            "tool_policy": {
                **base_tool_policy,
                "require_kb_grounding": target_require_kb_grounding,
            },
        }

        if next_policy == _as_dict(getattr(persona, "persona_policy", {})):
            continue

        if apply_changes:
            persona.persona_policy = next_policy
            sync_legacy_persona_fields(persona, next_policy)
        updated_count += 1

    if apply_changes:
        await db.commit()

    return {
        "total_personas": len(personas),
        "updated_personas": updated_count,
        "skipped_personas": skipped_count,
        "conflicts": conflict_report,
        "apply_changes": apply_changes,
    }


async def _run(apply_changes: bool) -> None:
    async with AsyncSessionLocal() as db:
        summary = await migrate_persona_policy(db, apply_changes=apply_changes)
        logger.info(
            "Persona policy migration finished",
            total_personas=summary["total_personas"],
            updated_personas=summary["updated_personas"],
            skipped_personas=summary["skipped_personas"],
            apply_changes=apply_changes,
            conflicts=dict(summary["conflicts"]),
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Persist migration changes (default is dry-run).",
    )
    args = parser.parse_args()
    asyncio.run(_run(apply_changes=bool(args.apply)))


if __name__ == "__main__":
    main()

