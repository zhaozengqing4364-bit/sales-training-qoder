"""Versioned white-list snapshot and logical-key restore for runtime configuration."""

from __future__ import annotations

import enum
import hashlib
import json
import os
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import DateTime, select
from sqlalchemy.orm import Session, sessionmaker

from agent.models import VoiceRuntimeProfile
from common.ai.models import ModelConfig
from common.db.model_registry import BusinessRuleConfig, PromptTemplate, ScoringRuleset
from common.db.model_registry.registration import register_all_models
from common.knowledge.rag_profile_models import RagProfile
from launch_reset.errors import ResetExecutionError, ResetSafetyError
from launch_reset.guards import sync_database_url
from launch_reset.manifest import canonical_json, sha256_json, utc_now_iso

SNAPSHOT_FORMAT = "sales-training-config-snapshot"
SNAPSHOT_VERSION = 1

# Reset is another root composition surface: every relationship target must be
# registered before SQLAlchemy configures mappers for snapshot queries.
register_all_models()


@dataclass(frozen=True, slots=True)
class SnapshotHandler:
    type_name: str
    model: type[Any]
    primary_key: str
    logical_key_fields: tuple[str, ...]
    actor_fields: tuple[str, ...] = ()
    published_only: bool = False

    @property
    def table_name(self) -> str:
        return str(self.model.__table__.name)

    def statement(self) -> Any:
        statement = select(self.model)
        if self.published_only:
            statement = statement.where(self.model.status == "published")
        return statement


SNAPSHOT_HANDLERS: tuple[SnapshotHandler, ...] = (
    SnapshotHandler(
        "model_config",
        ModelConfig,
        "id",
        ("model_type", "provider", "model_name"),
    ),
    SnapshotHandler("rag_profile", RagProfile, "id", ("name",)),
    SnapshotHandler("voice_runtime_profile", VoiceRuntimeProfile, "id", ("name",)),
    SnapshotHandler(
        "prompt_template",
        PromptTemplate,
        "id",
        ("prompt_type", "name", "category"),
    ),
    SnapshotHandler(
        "business_rule",
        BusinessRuleConfig,
        "id",
        ("key", "version"),
        actor_fields=("created_by", "updated_by"),
        published_only=True,
    ),
    SnapshotHandler(
        "scoring_ruleset",
        ScoringRuleset,
        "ruleset_id",
        ("scenario_type", "version"),
        actor_fields=("created_by", "updated_by", "published_by"),
        published_only=True,
    ),
)


def encryption_key_fingerprint() -> str:
    value = os.getenv("MODEL_CONFIG_ENCRYPTION_KEY", "")
    if not value:
        return "unconfigured"
    return hashlib.sha256(value.encode()).hexdigest()


def _json_value(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, bytes):
        return {"encoding": "hex", "value": value.hex()}
    return value


def _row_payload(handler: SnapshotHandler, row: object) -> dict[str, Any]:
    excluded = {handler.primary_key, *handler.actor_fields}
    payload: dict[str, Any] = {}
    for column in handler.model.__table__.columns:
        attribute_key = handler.model.__mapper__.get_property_by_column(column).key
        if column.name in excluded or attribute_key in excluded:
            continue
        payload[column.name] = _json_value(getattr(row, attribute_key))
    return payload


def _logical_key(handler: SnapshotHandler, row: object) -> dict[str, Any]:
    return {
        field: _json_value(getattr(row, field)) for field in handler.logical_key_fields
    }


def _session_factory(raw_url: str) -> sessionmaker[Session]:
    from sqlalchemy import create_engine

    engine = create_engine(sync_database_url(raw_url), pool_pre_ping=True)
    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


def export_config_snapshot(raw_url: str) -> dict[str, Any]:
    session_factory = _session_factory(raw_url)
    sections: list[dict[str, Any]] = []
    try:
        with session_factory() as session:
            for handler in SNAPSHOT_HANDLERS:
                try:
                    rows = list(session.scalars(handler.statement()).all())
                except Exception as exc:
                    raise ResetExecutionError(
                        "[RESET_SNAPSHOT_TABLE_READ_FAILED]"
                    ) from exc
                for row in rows:
                    section = {
                        "type": handler.type_name,
                        "schema_version": 1,
                        "logical_key": _logical_key(handler, row),
                        "payload": _row_payload(handler, row),
                    }
                    section["checksum"] = sha256_json(section)
                    sections.append(section)
    finally:
        session_factory.kw["bind"].dispose()

    sections.sort(
        key=lambda item: (str(item["type"]), canonical_json(item["logical_key"]))
    )
    snapshot: dict[str, Any] = {
        "format": SNAPSHOT_FORMAT,
        "version": SNAPSHOT_VERSION,
        "created_at": utc_now_iso(),
        "encryption_key_fingerprint": encryption_key_fingerprint(),
        "sections": sections,
    }
    snapshot["sections_fingerprint"] = sha256_json(sections)
    snapshot["snapshot_checksum"] = sha256_json(snapshot)
    return snapshot


def validate_snapshot(snapshot: dict[str, Any]) -> None:
    if snapshot.get("format") != SNAPSHOT_FORMAT or snapshot.get("version") != 1:
        raise ResetSafetyError("[RESET_SNAPSHOT_FORMAT_INVALID]")
    supplied_checksum = str(snapshot.get("snapshot_checksum") or "")
    without_checksum = {
        key: value for key, value in snapshot.items() if key != "snapshot_checksum"
    }
    if supplied_checksum != sha256_json(without_checksum):
        raise ResetSafetyError("[RESET_SNAPSHOT_CHECKSUM_MISMATCH]")
    sections = snapshot.get("sections")
    if not isinstance(sections, list):
        raise ResetSafetyError("[RESET_SNAPSHOT_SECTIONS_INVALID]")
    if snapshot.get("sections_fingerprint") != sha256_json(sections):
        raise ResetSafetyError("[RESET_SNAPSHOT_FINGERPRINT_MISMATCH]")
    for section in sections:
        if not isinstance(section, dict):
            raise ResetSafetyError("[RESET_SNAPSHOT_SECTION_INVALID]")
        checksum = str(section.get("checksum") or "")
        without_section_checksum = {
            key: value for key, value in section.items() if key != "checksum"
        }
        if checksum != sha256_json(without_section_checksum):
            raise ResetSafetyError("[RESET_SNAPSHOT_SECTION_CHECKSUM_MISMATCH]")
    if snapshot.get("encryption_key_fingerprint") != encryption_key_fingerprint():
        raise ResetSafetyError("[RESET_ENCRYPTION_KEY_FINGERPRINT_MISMATCH]")


def write_snapshot(path: Path, snapshot: dict[str, Any]) -> None:
    validate_snapshot(snapshot)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent, text=True
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(snapshot, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_name, 0o600)
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def load_snapshot(path: Path) -> dict[str, Any]:
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ResetSafetyError("[RESET_SNAPSHOT_READ_FAILED]") from exc
    if not isinstance(snapshot, dict):
        raise ResetSafetyError("[RESET_SNAPSHOT_ROOT_INVALID]")
    validate_snapshot(snapshot)
    return snapshot


def _handler_by_type() -> dict[str, SnapshotHandler]:
    return {handler.type_name: handler for handler in SNAPSHOT_HANDLERS}


def _restore_value(handler: SnapshotHandler, field_name: str, value: object) -> object:
    column = handler.model.__table__.columns[field_name]
    if isinstance(column.type, DateTime) and isinstance(value, str):
        return datetime.fromisoformat(value)
    if isinstance(value, dict) and value.get("encoding") == "hex":
        return bytes.fromhex(str(value.get("value") or ""))
    return value


def _attribute_key(handler: SnapshotHandler, column_name: str) -> str:
    column = handler.model.__table__.columns[column_name]
    return str(handler.model.__mapper__.get_property_by_column(column).key)


def restore_config_snapshot(
    raw_url: str,
    snapshot: dict[str, Any],
    *,
    admin_user_id: str,
) -> dict[str, int]:
    validate_snapshot(snapshot)
    handlers = _handler_by_type()
    restored: dict[str, int] = {handler.type_name: 0 for handler in SNAPSHOT_HANDLERS}
    session_factory = _session_factory(raw_url)
    try:
        with session_factory.begin() as session:
            for section in snapshot["sections"]:
                handler = handlers.get(str(section["type"]))
                if handler is None:
                    raise ResetSafetyError("[RESET_SNAPSHOT_HANDLER_MISSING]")
                logical_key = dict(section["logical_key"])
                conditions = [
                    getattr(handler.model, field) == logical_key[field]
                    for field in handler.logical_key_fields
                ]
                row = session.scalar(select(handler.model).where(*conditions))
                payload = {
                    _attribute_key(handler, field): _restore_value(
                        handler, field, value
                    )
                    for field, value in dict(section["payload"]).items()
                }
                if row is None:
                    payload[handler.primary_key] = str(uuid.uuid4())
                    for actor_field in handler.actor_fields:
                        payload[actor_field] = admin_user_id
                    row = handler.model(**payload)
                    session.add(row)
                else:
                    for field, value in payload.items():
                        setattr(row, field, value)
                    for actor_field in handler.actor_fields:
                        setattr(row, actor_field, admin_user_id)
                restored[handler.type_name] += 1
    finally:
        session_factory.kw["bind"].dispose()
    return restored


def current_config_fingerprint(raw_url: str) -> str:
    return str(export_config_snapshot(raw_url)["sections_fingerprint"])


__all__ = [
    "SNAPSHOT_HANDLERS",
    "SNAPSHOT_FORMAT",
    "SNAPSHOT_VERSION",
    "current_config_fingerprint",
    "encryption_key_fingerprint",
    "export_config_snapshot",
    "load_snapshot",
    "restore_config_snapshot",
    "validate_snapshot",
    "write_snapshot",
]
