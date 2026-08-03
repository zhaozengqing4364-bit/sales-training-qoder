from datetime import UTC, datetime

import pytest

from launch_reset.verifier import _is_valid_managed_admin


def _admin_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "email": "admin@qoder.ai",
        "role": "admin",
        "is_active": True,
        "credential_status": "temporary",
        "has_password": True,
        "password_changed_at": None,
    }
    row.update(overrides)
    return row


@pytest.mark.parametrize(
    ("credential_status", "password_changed_at"),
    [
        ("temporary", None),
        ("active", datetime.now(UTC)),
    ],
)
def test_should_accept_managed_admin_before_and_after_first_password_change(
    credential_status: str,
    password_changed_at: datetime | None,
) -> None:
    assert _is_valid_managed_admin(
        _admin_row(
            credential_status=credential_status,
            password_changed_at=password_changed_at,
        ),
        admin_email="admin@qoder.ai",
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {"credential_status": "reset_required"},
        {"credential_status": "active", "password_changed_at": None},
        {"role": "user"},
        {"is_active": False},
        {"has_password": False},
        {"email": "other@example.com"},
    ],
)
def test_should_reject_invalid_managed_admin_state(
    overrides: dict[str, object],
) -> None:
    assert not _is_valid_managed_admin(
        _admin_row(**overrides),
        admin_email="admin@qoder.ai",
    )
