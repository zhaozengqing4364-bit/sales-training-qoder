"""Independent post-reset verification with no schema or data repair behavior."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import RowMapping

from launch_reset.errors import ResetExecutionError
from launch_reset.guards import sync_database_url
from launch_reset.scopes import BACKEND_ROOT
from launch_reset.snapshot import SNAPSHOT_HANDLERS, current_config_fingerprint


def _is_valid_managed_admin(
    admin: Mapping[str, Any] | RowMapping,
    *,
    admin_email: str | None,
) -> bool:
    credential_status = str(admin["credential_status"])
    valid_credential_lifecycle = credential_status == "temporary" or (
        credential_status == "active" and admin["password_changed_at"] is not None
    )
    return (
        str(admin["role"]) == "admin"
        and bool(admin["is_active"])
        and bool(admin["has_password"])
        and valid_credential_lifecycle
        and (
            not admin_email
            or str(admin["email"]).lower() == admin_email.lower()
        )
    )


class IndependentVerifier:
    def __init__(self, raw_url: str) -> None:
        self.raw_url = raw_url

    @staticmethod
    def expected_head() -> str:
        config = Config(str(BACKEND_ROOT / "alembic.ini"))
        config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
        heads = tuple(ScriptDirectory.from_config(config).get_heads())
        if len(heads) != 1:
            raise ResetExecutionError("[RESET_ALEMBIC_HEAD_COUNT_INVALID]")
        return heads[0]

    def verify(
        self,
        *,
        admin_email: str | None = None,
        expected_config_fingerprint: str | None = None,
    ) -> dict[str, Any]:
        engine = create_engine(sync_database_url(self.raw_url))
        try:
            with engine.connect() as connection:
                version_rows = (
                    connection.execute(text("SELECT version_num FROM alembic_version"))
                    .scalars()
                    .all()
                )
                expected_head = self.expected_head()
                if version_rows != [expected_head]:
                    raise ResetExecutionError("[RESET_SCHEMA_HEAD_MISMATCH]")

                admin_rows = (
                    connection.execute(
                        text(
                            "SELECT user_id, email, role, is_active, credential_status, "
                            "password_changed_at, "
                            "hashed_password IS NOT NULL AS has_password FROM users"
                        )
                    )
                    .mappings()
                    .all()
                )
                if len(admin_rows) != 1:
                    raise ResetExecutionError("[RESET_ADMIN_COUNT_INVALID]")
                admin = admin_rows[0]
                if not _is_valid_managed_admin(admin, admin_email=admin_email):
                    raise ResetExecutionError("[RESET_ADMIN_STATE_INVALID]")

                allowed_non_empty = {
                    "users",
                    "admin_role_permissions",
                    *(handler.table_name for handler in SNAPSHOT_HANDLERS),
                }
                inspector = inspect(connection)
                non_empty_business_tables: dict[str, int] = {}
                for table_name in inspector.get_table_names(schema="public"):
                    if (
                        table_name in allowed_non_empty
                        or table_name == "alembic_version"
                    ):
                        continue
                    count = int(
                        connection.execute(
                            text(f'SELECT count(*) FROM "{table_name}"')
                        ).scalar_one()
                    )
                    if count:
                        non_empty_business_tables[table_name] = count
                if non_empty_business_tables:
                    raise ResetExecutionError("[RESET_BUSINESS_TABLES_NOT_EMPTY]")
        finally:
            engine.dispose()

        config_fingerprint = current_config_fingerprint(self.raw_url)
        if (
            expected_config_fingerprint is not None
            and config_fingerprint != expected_config_fingerprint
        ):
            raise ResetExecutionError("[RESET_CONFIG_FINGERPRINT_MISMATCH]")
        return {
            "schema_head": self.expected_head(),
            "admin_count": 1,
            "business_tables_empty": True,
            "config_fingerprint": config_fingerprint,
        }


__all__ = ["IndependentVerifier"]
