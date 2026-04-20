from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import agent.models  # noqa: F401
from common.auth.service import create_access_token
from common.db.models import (
    KnowledgeAnswerabilityProfile,
    KnowledgeConfigVersion,
    KnowledgeEntityAlias,
    KnowledgeIntentRule,
    KnowledgeQueryProfile,
    KnowledgeRankingProfile,
    User,
)


def _headers_for(user_id: str) -> dict[str, str]:
    token = create_access_token(data={"sub": str(user_id)})
    return {"Authorization": f"Bearer {token}"}


async def _create_user(
    db_session: AsyncSession,
    *,
    role: str,
    email_prefix: str,
) -> User:
    user = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"wechat_{email_prefix}_{uuid.uuid4().hex[:8]}",
        name=f"{role.title()} User",
        email=f"{email_prefix}_{uuid.uuid4().hex[:8]}@example.com",
        role=role,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def _seed_config_version(
    db_session: AsyncSession,
    *,
    version_name: str,
    status: str,
    enabled: bool,
) -> KnowledgeConfigVersion:
    version = KnowledgeConfigVersion(
        id=str(uuid.uuid4()),
        version_name=version_name,
        status=status,
        enabled=enabled,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(version)
    await db_session.commit()
    await db_session.refresh(version)
    return version


async def _seed_profiles(db_session: AsyncSession, *, config_version_id: str) -> None:
    db_session.add_all(
        [
            KnowledgeQueryProfile(
                id=str(uuid.uuid4()),
                config_version_id=config_version_id,
                profile_key="intro_v1",
                description="产品介绍",
                rewrite_strategy="entity_first",
                max_rewrite_queries=3,
                stop_after_first_success=True,
                enabled=True,
            ),
            KnowledgeIntentRule(
                id=str(uuid.uuid4()),
                config_version_id=config_version_id,
                intent_key="company_intro",
                priority=10,
                match_type="keyword_contains",
                pattern="介绍|公司",
                profile_key="intro_v1",
                enabled=True,
            ),
            KnowledgeEntityAlias(
                id=str(uuid.uuid4()),
                config_version_id=config_version_id,
                canonical_entity="石犀科技",
                alias="世袭科技",
                entity_type="company",
                confidence=1.0,
                enabled=True,
            ),
            KnowledgeRankingProfile(
                id=str(uuid.uuid4()),
                config_version_id=config_version_id,
                profile_key="default_rank",
                title_exact_boost=1.2,
                entity_match_boost=1.5,
                doc_type_weights_json={"product": 1.0},
                section_weights_json={"intro": 1.0},
                min_pass_score=0.5,
                min_pass_score_keyword=0.7,
                enabled=True,
            ),
            KnowledgeAnswerabilityProfile(
                id=str(uuid.uuid4()),
                config_version_id=config_version_id,
                profile_key="default_answerability",
                required_slots_json=["company_name"],
                optional_slots_json=["pricing"],
                sufficient_threshold=1.0,
                partial_threshold=0.5,
                enabled=True,
            ),
        ]
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_get_admin_knowledge_answer_config_returns_active_snapshot(
    async_client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
):
    test_user.role = "admin"
    await test_db.commit()

    archived = await _seed_config_version(
        test_db,
        version_name="archived-v1",
        status="archived",
        enabled=True,
    )
    active = await _seed_config_version(
        test_db,
        version_name="rollout-v1",
        status="active",
        enabled=True,
    )
    await _seed_profiles(test_db, config_version_id=active.id)
    await _seed_profiles(test_db, config_version_id=archived.id)

    response = await async_client.get(
        "/api/v1/admin/knowledge-answer/config",
        headers=_headers_for(str(test_user.user_id)),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["trace_id"]
    data = body["data"]
    assert data["active_version"]["id"] == active.id
    assert data["active_version"]["version_name"] == "rollout-v1"
    assert data["active_version"]["status"] == "active"
    assert data["profile_source"] == "database"
    assert data["summary"]["query_profile_count"] == 1
    assert data["summary"]["intent_rule_count"] == 1
    assert data["summary"]["entity_alias_count"] == 1
    assert data["summary"]["ranking_profile_count"] == 1
    assert data["summary"]["answerability_profile_count"] == 1
    assert data["selected_profiles"]["query_profile_keys"] == ["intro_v1"]
    assert data["selected_profiles"]["ranking_profile_keys"] == ["default_rank"]
    assert data["selected_profiles"]["answerability_profile_keys"] == ["default_answerability"]


@pytest.mark.asyncio
async def test_get_admin_knowledge_answer_config_options_lists_enabled_versions(
    async_client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
):
    test_user.role = "admin"
    await test_db.commit()

    active = await _seed_config_version(
        test_db,
        version_name="rollout-v1",
        status="active",
        enabled=True,
    )
    draft = await _seed_config_version(
        test_db,
        version_name="draft-v2",
        status="draft",
        enabled=True,
    )
    await _seed_config_version(
        test_db,
        version_name="disabled-v3",
        status="draft",
        enabled=False,
    )

    response = await async_client.get(
        "/api/v1/admin/knowledge-answer/config/options",
        headers=_headers_for(str(test_user.user_id)),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    options = body["data"]["versions"]
    assert [item["id"] for item in options] == [draft.id, active.id]
    assert [item["version_name"] for item in options] == ["draft-v2", "rollout-v1"]
    assert all(item["enabled"] is True for item in options)


@pytest.mark.asyncio
async def test_put_admin_knowledge_answer_config_switches_active_version(
    async_client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
):
    test_user.role = "admin"
    await test_db.commit()

    current = await _seed_config_version(
        test_db,
        version_name="rollout-v1",
        status="active",
        enabled=True,
    )
    target = await _seed_config_version(
        test_db,
        version_name="rollout-v2",
        status="draft",
        enabled=True,
    )
    await _seed_profiles(test_db, config_version_id=target.id)

    response = await async_client.put(
        "/api/v1/admin/knowledge-answer/config",
        headers=_headers_for(str(test_user.user_id)),
        json={"config_version_id": target.id},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["active_version"]["id"] == target.id
    assert body["data"]["active_version"]["version_name"] == "rollout-v2"
    assert body["data"]["active_version"]["status"] == "active"

    rows = (
        await test_db.execute(
            select(KnowledgeConfigVersion).where(KnowledgeConfigVersion.id.in_([current.id, target.id]))
        )
    ).scalars().all()
    status_by_id = {row.id: row.status for row in rows}
    assert status_by_id[current.id] == "archived"
    assert status_by_id[target.id] == "active"


@pytest.mark.asyncio
async def test_put_admin_knowledge_answer_config_returns_not_found_for_missing_version(
    async_client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
):
    test_user.role = "admin"
    await test_db.commit()

    response = await async_client.put(
        "/api/v1/admin/knowledge-answer/config",
        headers=_headers_for(str(test_user.user_id)),
        json={"config_version_id": str(uuid.uuid4())},
    )

    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["error"] == "[KNOWLEDGE_CONFIG_NOT_FOUND]"


@pytest.mark.asyncio
async def test_admin_knowledge_answer_config_requires_admin_role(
    async_client: AsyncClient,
    test_db: AsyncSession,
):
    learner = await _create_user(test_db, role="user", email_prefix="learner_kqa")

    response = await async_client.get(
        "/api/v1/admin/knowledge-answer/config",
        headers=_headers_for(str(learner.user_id)),
    )

    assert response.status_code in {401, 403}
