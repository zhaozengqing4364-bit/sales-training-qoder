from __future__ import annotations

from common.db.models import User
from sales_trainer import api as sales_trainer_api
from sales_trainer.permissions import (
    can_enter_sales_trainer_learning_path,
    can_manage_sales_trainer,
    can_manage_sales_trainer_prompts,
    can_regrade_sales_trainer_history,
    can_retry_sales_trainer_jobs,
    can_view_sales_trainer_logs,
    can_view_sales_trainer_records,
    can_view_sales_trainer_settings,
    is_sales_trainer_manager,
    sales_trainer_admin_capability_projection,
    sales_trainer_manager_roles,
)


def _user(role: str) -> User:
    return User(
        user_id=f"user-{role}",
        wechat_user_id=f"wechat-{role}",
        name=role,
        email=f"{role}@example.com",
        role=role,
    )


def test_should_allow_super_admin_to_manage_view_retry_and_audit() -> None:
    user = _user("super_admin")

    assert can_manage_sales_trainer(user)
    assert can_view_sales_trainer_records(user)
    assert can_retry_sales_trainer_jobs(user)
    assert can_view_sales_trainer_logs(user)


def test_should_grant_training_lead_record_capability_before_object_scope() -> None:
    user = _user("support")

    assert not can_manage_sales_trainer(user)
    assert can_view_sales_trainer_records(user)
    assert not can_view_sales_trainer_logs(user)
    assert not can_view_sales_trainer_settings(user)
    assert not can_retry_sales_trainer_jobs(user)
    assert not can_regrade_sales_trainer_history(user)


def test_should_allow_content_admin_to_manage_content_but_not_records() -> None:
    user = _user("content_admin")

    assert can_manage_sales_trainer(user)
    assert not can_manage_sales_trainer_prompts(user)
    assert not can_view_sales_trainer_records(user)
    assert not can_retry_sales_trainer_jobs(user)
    assert not can_regrade_sales_trainer_history(user)


def test_should_allow_ops_to_retry_without_content_or_learner_record_access() -> None:
    user = _user("operations")

    assert not can_manage_sales_trainer(user)
    assert not can_view_sales_trainer_records(user)
    assert can_retry_sales_trainer_jobs(user)
    assert not can_regrade_sales_trainer_history(user)
    assert can_view_sales_trainer_logs(user)


def test_should_keep_support_as_training_lead_compatibility_alias() -> None:
    user = _user("support")

    assert not can_manage_sales_trainer(user)
    assert can_view_sales_trainer_records(user)
    assert not can_view_sales_trainer_logs(user)


def test_should_accept_ops_as_operations_compatibility_alias() -> None:
    user = _user("ops")

    assert can_view_sales_trainer_logs(user)
    assert can_retry_sales_trainer_jobs(user)
    assert not can_regrade_sales_trainer_history(user)


def test_should_filter_invalid_manager_roles_without_expanding_capabilities(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "SALES_TRAINER_MANAGER_ROLES",
        "training_manager,evil,user,content_admin,admin,ops",
    )

    assert sales_trainer_manager_roles() == {"training_manager"}
    assert is_sales_trainer_manager(_user("training_manager"))
    assert not is_sales_trainer_manager(_user("user"))
    assert not is_sales_trainer_manager(_user("content_admin"))
    assert not is_sales_trainer_manager(_user("admin"))
    assert not is_sales_trainer_manager(_user("ops"))


def test_should_fail_closed_when_manager_roles_env_has_no_allowlisted_role(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "SALES_TRAINER_MANAGER_ROLES",
        "evil,user,content_admin,admin,ops",
    )

    assert sales_trainer_manager_roles() == set()
    assert not is_sales_trainer_manager(_user("support"))
    assert not is_sales_trainer_manager(_user("training_lead"))
    assert not is_sales_trainer_manager(_user("training_manager"))
    assert not is_sales_trainer_manager(_user("user"))


def test_should_use_granular_route_guards_for_admin_surfaces() -> None:
    content_admin = _user("content_admin")
    training_lead = _user("support")
    training_error = sales_trainer_api._require_manager(training_lead)

    assert sales_trainer_api._require_manager(content_admin) is None
    assert training_error is not None
    assert training_error.status_code == 403
    assert sales_trainer_api._require_records_viewer(training_lead) is None
    assert not hasattr(sales_trainer_api, "_require_job_retry")


def test_admin_capability_projection_uses_permission_authority() -> None:
    admin = sales_trainer_admin_capability_projection(_user("admin"))
    content_admin = sales_trainer_admin_capability_projection(_user("content_admin"))
    training_lead = sales_trainer_admin_capability_projection(_user("support"))
    ops = sales_trainer_admin_capability_projection(_user("operations"))

    assert admin["capabilities"]["manage_prompts"] is True

    assert content_admin["role_label"] == "内容管理员"
    assert content_admin["capabilities"]["manage_content"] is True
    assert content_admin["capabilities"]["manage_prompts"] is False
    assert content_admin["capabilities"]["view_records"] is False

    assert training_lead["role_label"] == "培训负责人"
    assert training_lead["capabilities"]["view_records"] is True
    assert training_lead["capabilities"]["view_logs"] is False
    assert training_lead["capabilities"]["view_settings"] is False
    assert training_lead["capabilities"]["manage_content"] is False
    assert training_lead["capabilities"]["regrade_history"] is False

    assert ops["role_label"] == "运维人员"
    assert ops["capabilities"]["retry_jobs"] is True
    assert ops["capabilities"]["view_records"] is False
    assert ops["capabilities"]["regrade_history"] is False
    assert ops["capabilities"]["view_logs"] is True
    assert ops["capabilities"]["view_settings"] is True
    assert ops["capabilities"]["manage_content"] is False
    assert ops["capabilities"]["manage_prompts"] is False


def test_should_limit_prompt_governance_to_platform_admin_roles() -> None:
    assert can_manage_sales_trainer_prompts(_user("admin"))
    assert can_manage_sales_trainer_prompts(_user("super_admin"))
    assert not can_manage_sales_trainer_prompts(_user("content_admin"))
    assert not can_manage_sales_trainer_prompts(_user("support"))
    assert not can_manage_sales_trainer_prompts(_user("operations"))


def test_admin_can_enter_learner_path_for_dev_and_acceptance() -> None:
    """Platform admins may enter the learner path without a separate learner account."""
    admin = _user("admin")
    super_admin = _user("super_admin")
    assert can_enter_sales_trainer_learning_path(admin) is True
    assert can_enter_sales_trainer_learning_path(super_admin) is True


def test_learner_and_user_can_enter_learner_path() -> None:
    assert can_enter_sales_trainer_learning_path(_user("user")) is True
    assert can_enter_sales_trainer_learning_path(_user("learner")) is True


def test_inactive_admin_cannot_enter_learner_path() -> None:
    admin = _user("admin")
    admin.is_active = False
    assert can_enter_sales_trainer_learning_path(admin) is False


def test_content_admin_and_ops_still_cannot_enter_learner_path() -> None:
    """Only platform admins are admitted; other admin roles stay gated."""
    assert can_enter_sales_trainer_learning_path(_user("content_admin")) is False
    assert can_enter_sales_trainer_learning_path(_user("operations")) is False
