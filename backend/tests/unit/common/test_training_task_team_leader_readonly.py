from __future__ import annotations

from types import SimpleNamespace

from common.training_tasks.service import can_manage_training_tasks


def test_training_manager_cannot_manage_training_tasks() -> None:
    leader = SimpleNamespace(role="training_manager")
    assert can_manage_training_tasks(leader) is False


def test_platform_admin_can_manage_training_tasks() -> None:
    admin = SimpleNamespace(role="admin")
    assert can_manage_training_tasks(admin) is True
