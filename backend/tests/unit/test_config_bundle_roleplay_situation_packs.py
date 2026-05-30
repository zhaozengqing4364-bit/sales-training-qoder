from __future__ import annotations

from copy import deepcopy

import pytest

from admin.config_bundles.adapters import list_config_bundle_adapters
from admin.config_bundles.lifecycle import ConfigBundleLifecycleService
from common.business_rules.defaults import (
    DEFAULT_ROLEPLAY_SITUATION_PACKS,
    ROLEPLAY_SITUATION_PACKS_KEY,
)
from common.db.models import User


async def _admin(test_db) -> User:
    user = User(
        wechat_user_id="roleplay-config-admin",
        name="Roleplay Config Admin",
        email="roleplay-config-admin@example.com",
        role="admin",
    )
    test_db.add(user)
    await test_db.flush()
    return user


@pytest.mark.asyncio
async def test_config_bundle_lists_roleplay_situation_pack_adapter() -> None:
    keys = {adapter.bundle_key for adapter in list_config_bundle_adapters()}

    assert ROLEPLAY_SITUATION_PACKS_KEY in keys


@pytest.mark.asyncio
async def test_config_bundle_lifecycle_publishes_and_rolls_back_roleplay_packs(
    test_db,
) -> None:
    admin = await _admin(test_db)
    service = ConfigBundleLifecycleService(test_db)
    first_value = deepcopy(DEFAULT_ROLEPLAY_SITUATION_PACKS)
    first_value["version"] = "roleplay_situation_packs_v1"
    second_value = deepcopy(DEFAULT_ROLEPLAY_SITUATION_PACKS)
    second_value["version"] = "roleplay_situation_packs_v2"
    second_value["packs"] = [
        pack | {"default_forbidden_claim_patterns": [*pack["default_forbidden_claim_patterns"], "老客户"]}
        if pack["code"] == "first_visit"
        else pack
        for pack in second_value["packs"]
    ]

    first = await service.create_draft(
        bundle_key=ROLEPLAY_SITUATION_PACKS_KEY,
        value=first_value,
        actor_id=str(admin.user_id),
        reason="first draft",
    )
    await service.publish(
        bundle_key=ROLEPLAY_SITUATION_PACKS_KEY,
        actor_id=str(admin.user_id),
        config_id=str(first.version.source_config_id),
        reason="publish first",
    )
    second = await service.create_draft(
        bundle_key=ROLEPLAY_SITUATION_PACKS_KEY,
        value=second_value,
        actor_id=str(admin.user_id),
        reason="second draft",
    )
    await service.publish(
        bundle_key=ROLEPLAY_SITUATION_PACKS_KEY,
        actor_id=str(admin.user_id),
        config_id=str(second.version.source_config_id),
        reason="publish second",
    )
    rollback = await service.rollback(
        bundle_key=ROLEPLAY_SITUATION_PACKS_KEY,
        actor_id=str(admin.user_id),
        target_version=1,
        target_config_id=None,
        reason="rollback to stable roleplay packs",
    )
    await test_db.commit()

    assert rollback.version is not None
    assert rollback.version.version_number == 1
    assert rollback.version.snapshot_json["version"] == "roleplay_situation_packs_v1"
    assert rollback.audit is not None
    assert rollback.audit.action == "rollback"
    assert rollback.audit.reason == "rollback to stable roleplay packs"
