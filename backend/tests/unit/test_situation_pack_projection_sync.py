from __future__ import annotations

from copy import deepcopy

import pytest
from sqlalchemy import select

from admin.config_bundles.lifecycle import ConfigBundleLifecycleService
from common.business_rules.defaults import (
    DEFAULT_ROLEPLAY_SITUATION_PACKS,
    ROLEPLAY_SITUATION_PACKS_KEY,
)
from common.config import Settings
from common.db.models import User
from curriculum_practice.models import SituationPack
from curriculum_practice.services.roleplay.adapters.entity_projection_adapter import (
    EntitySituationPackProjectionAdapter,
)
from curriculum_practice.services.roleplay.situation_pack_dto import SituationPackDTO
from curriculum_practice.services.roleplay.situation_pack_hasher import (
    situation_pack_content_hash,
)
from curriculum_practice.services.roleplay.situation_pack_projection_sync import (
    SituationPackProjectionSyncService,
)


async def _admin(test_db) -> User:
    user = User(
        wechat_user_id="situation-pack-sync-admin",
        name="Situation Pack Sync Admin",
        email="situation-pack-sync-admin@example.com",
        role="admin",
    )
    test_db.add(user)
    await test_db.flush()
    return user


def _custom_snapshot(*, label_suffix: str = "") -> dict:
    snapshot = deepcopy(DEFAULT_ROLEPLAY_SITUATION_PACKS)
    snapshot["version"] = "roleplay_situation_packs_sync_test"
    snapshot["packs"] = [
        pack | {"label": f"{pack['label']}{label_suffix}"}
        if pack["code"] == "first_visit"
        else pack
        for pack in snapshot["packs"]
    ]
    return snapshot


@pytest.mark.asyncio
async def test_projection_sync_upserts_published_packs(test_db) -> None:
    service = SituationPackProjectionSyncService(test_db)
    snapshot = _custom_snapshot(label_suffix="-Sync")

    result = await service.sync_from_ruleset_snapshot(snapshot, actor_id="admin-1")
    await test_db.flush()

    rows = (
        await test_db.execute(
            select(SituationPack).where(SituationPack.code == "first_visit")
        )
    ).scalar_one()

    assert "first_visit" in result.synced_codes
    assert result.created_count >= 1
    assert rows.label == "首次拜访-Sync"
    assert rows.status == "published"
    assert rows.published_at is not None


@pytest.mark.asyncio
async def test_projection_sync_content_hash_matches_dto_hasher(test_db) -> None:
    service = SituationPackProjectionSyncService(test_db)
    snapshot = _custom_snapshot()

    await service.sync_from_ruleset_snapshot(snapshot)
    await test_db.flush()

    row = (
        await test_db.execute(
            select(SituationPack).where(SituationPack.code == "first_visit")
        )
    ).scalar_one()
    ruleset_entry = next(
        pack for pack in snapshot["packs"] if pack["code"] == "first_visit"
    )
    source_dto = SituationPackDTO.from_ruleset_entry(ruleset_entry)

    assert row.content_hash == situation_pack_content_hash(source_dto)


@pytest.mark.asyncio
async def test_projection_sync_is_idempotent(test_db) -> None:
    service = SituationPackProjectionSyncService(test_db)
    snapshot = _custom_snapshot(label_suffix="-Stable")

    first = await service.sync_from_ruleset_snapshot(snapshot)
    await test_db.flush()
    row_after_first = (
        await test_db.execute(
            select(SituationPack).where(SituationPack.code == "first_visit")
        )
    ).scalar_one()
    first_hash = row_after_first.content_hash
    first_updated_at = row_after_first.updated_at

    second = await service.sync_from_ruleset_snapshot(snapshot)
    await test_db.flush()
    row_after_second = (
        await test_db.execute(
            select(SituationPack).where(SituationPack.code == "first_visit")
        )
    ).scalar_one()

    assert first.created_count >= 1
    assert second.created_count == 0
    assert second.updated_count >= 1
    assert row_after_second.content_hash == first_hash
    assert row_after_second.updated_at >= first_updated_at


@pytest.mark.asyncio
async def test_config_bundle_publish_triggers_projection_sync(test_db) -> None:
    admin = await _admin(test_db)
    lifecycle = ConfigBundleLifecycleService(test_db)
    value = _custom_snapshot(label_suffix="-Lifecycle")

    draft = await lifecycle.create_draft(
        bundle_key=ROLEPLAY_SITUATION_PACKS_KEY,
        value=value,
        actor_id=str(admin.user_id),
        reason="sync hook draft",
    )
    publish = await lifecycle.publish(
        bundle_key=ROLEPLAY_SITUATION_PACKS_KEY,
        actor_id=str(admin.user_id),
        config_id=str(draft.version.source_config_id),
        reason="sync hook publish",
    )
    await test_db.flush()

    row = (
        await test_db.execute(
            select(SituationPack).where(SituationPack.code == "first_visit")
        )
    ).scalar_one()

    assert publish.audit is not None
    assert publish.audit.action == "publish"
    assert publish.audit.after_snapshot_json is not None
    assert publish.audit.after_snapshot_json.get("projection_sync", {}).get("status") == "ok"
    assert row.label == "首次拜访-Lifecycle"
    assert row.content_hash is not None


@pytest.mark.asyncio
async def test_entity_projection_adapter_reads_orm_when_flag_enabled(
    test_db,
    monkeypatch,
) -> None:
    sync = SituationPackProjectionSyncService(test_db)
    snapshot = _custom_snapshot(label_suffix="-ORM")
    await sync.sync_from_ruleset_snapshot(snapshot)
    await test_db.commit()

    monkeypatch.setenv("SITUATION_PACK_READ_ORM", "true")
    monkeypatch.setattr(
        "curriculum_practice.services.roleplay.adapters.entity_projection_adapter.settings",
        Settings(),
    )

    adapter = await EntitySituationPackProjectionAdapter.from_database(test_db)
    pack = adapter.get_published("first_visit")

    assert pack is not None
    assert pack.label == "首次拜访-ORM"


@pytest.mark.asyncio
async def test_entity_projection_adapter_defaults_to_config_mirror_not_orm(
    test_db,
    monkeypatch,
) -> None:
    sync = SituationPackProjectionSyncService(test_db)
    await sync.sync_from_ruleset_snapshot(_custom_snapshot(label_suffix="-StaleORM"))
    await test_db.commit()

    monkeypatch.delenv("SITUATION_PACK_READ_ORM", raising=False)
    monkeypatch.setattr(
        "curriculum_practice.services.roleplay.adapters.entity_projection_adapter.settings",
        Settings(),
    )

    adapter = await EntitySituationPackProjectionAdapter.from_database(test_db)
    pack = adapter.get_published("first_visit")

    assert pack is not None
    assert pack.label != "首次拜访-StaleORM"
