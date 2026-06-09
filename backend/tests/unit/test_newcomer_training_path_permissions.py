from __future__ import annotations

from common.db.models import User
from sales_trainer import api as sales_trainer_api
from sales_trainer.permissions import (
    can_manage_sales_trainer,
    can_retry_sales_trainer_jobs,
    can_view_sales_trainer_logs,
    can_view_sales_trainer_records,
    team_scope_department,
)


def _user(role: str, *, department: str | None = "销售一部") -> User:
    return User(
        user_id=f"user-{role}",
        wechat_user_id=f"wechat-{role}",
        name=role,
        email=f"{role}@example.com",
        role=role,
        department=department,
    )


def test_should_allow_super_admin_to_manage_view_retry_and_audit() -> None:
    user = _user("super_admin")

    assert can_manage_sales_trainer(user)
    assert can_view_sales_trainer_records(user)
    assert can_retry_sales_trainer_jobs(user)
    assert can_view_sales_trainer_logs(user)
    assert team_scope_department(user) is None


def test_should_scope_training_lead_to_department_records() -> None:
    user = _user("support", department="华东销售")

    assert not can_manage_sales_trainer(user)
    assert can_view_sales_trainer_records(user)
    assert not can_retry_sales_trainer_jobs(user)
    assert team_scope_department(user) == "华东销售"


def test_should_allow_content_admin_to_manage_content_but_not_records() -> None:
    user = _user("content_admin")

    assert can_manage_sales_trainer(user)
    assert not can_view_sales_trainer_records(user)
    assert not can_retry_sales_trainer_jobs(user)


def test_should_allow_ops_to_diagnose_and_retry_without_content_management() -> None:
    user = _user("operations")

    assert not can_manage_sales_trainer(user)
    assert can_view_sales_trainer_records(user)
    assert can_retry_sales_trainer_jobs(user)
    assert can_view_sales_trainer_logs(user)


def test_should_keep_support_as_training_lead_compatibility_alias() -> None:
    user = _user("support", department="北区")

    assert not can_manage_sales_trainer(user)
    assert can_view_sales_trainer_records(user)
    assert team_scope_department(user) == "北区"


def test_should_accept_ops_as_operations_compatibility_alias() -> None:
    user = _user("ops")

    assert can_view_sales_trainer_logs(user)
    assert can_retry_sales_trainer_jobs(user)


def test_should_use_granular_route_guards_for_admin_surfaces() -> None:
    content_admin = _user("content_admin")
    training_lead = _user("support")
    ops = _user("operations")
    training_error = sales_trainer_api._require_manager(training_lead)
    retry_error = sales_trainer_api._require_job_retry(content_admin)

    assert sales_trainer_api._require_manager(content_admin) is None
    assert training_error is not None
    assert training_error.status_code == 403
    assert sales_trainer_api._require_records_viewer(training_lead) is None
    assert retry_error is not None
    assert retry_error.status_code == 403
    assert sales_trainer_api._require_job_retry(ops) is None
