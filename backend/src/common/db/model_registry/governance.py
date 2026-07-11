"""Grouped SQLAlchemy declarations extracted from the compatibility model registry."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import relationship

from common.db.model_registry.base import Base, _jsonb_compatible_type


class BusinessRuleConfig(Base):
    """Versioned business-rule configuration for governed runtime rules."""

    __tablename__ = "business_rule_configs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    domain = Column(String(80), nullable=False, index=True)
    key = Column(String(160), nullable=False, index=True)
    schema_version = Column(String(40), nullable=False)
    status = Column(String(20), nullable=False, default="draft", index=True)
    version = Column(Integer, nullable=False)
    value_json = Column("value", _jsonb_compatible_type(), nullable=False, default=dict)
    default_value_json = Column(
        "default_value",
        _jsonb_compatible_type(),
        nullable=False,
        default=dict,
    )
    type = Column(String(40), nullable=False, default="rule_json")
    range_or_allowlist_json = Column(
        "range_or_allowlist",
        _jsonb_compatible_type(),
        nullable=False,
        default=dict,
    )
    read_path = Column(String(255), nullable=False)
    admin_entry = Column(String(255), nullable=False)
    permission = Column(String(80), nullable=False, default="admin")
    audit_policy = Column(Text, nullable=False)
    fallback_policy = Column(Text, nullable=False)
    rollback_policy = Column(Text, nullable=False)
    enabled = Column(Boolean, nullable=False, default=True, index=True)
    validation_errors_json = Column(
        "validation_errors",
        _jsonb_compatible_type(),
        nullable=False,
        default=list,
    )
    created_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    updated_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'published', 'archived', 'disabled')",
            name="ck_business_rule_config_status",
        ),
        UniqueConstraint("key", "version", name="uq_business_rule_config_key_version"),
        Index(
            "idx_business_rule_configs_key_status_version",
            "key",
            "status",
            "version",
        ),
        Index("idx_business_rule_configs_domain_status", "domain", "status"),
    )

    creator = relationship("User", foreign_keys=[created_by])
    updater = relationship("User", foreign_keys=[updated_by])


class BusinessRuleConfigAuditLog(Base):
    """Audit trail for business-rule draft, publish, rollback, and disable actions."""

    __tablename__ = "business_rule_config_audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    config_id = Column(
        String(36),
        ForeignKey("business_rule_configs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    domain = Column(String(80), nullable=False, index=True)
    config_key = Column(String(160), nullable=False, index=True)
    action = Column(String(40), nullable=False, index=True)
    actor_id = Column(
        String(36), ForeignKey("users.user_id"), nullable=True, index=True
    )
    before_version = Column(Integer, nullable=True)
    after_version = Column(Integer, nullable=True)
    before_snapshot_json = Column(
        "before_snapshot",
        _jsonb_compatible_type(),
        nullable=True,
    )
    after_snapshot_json = Column(
        "after_snapshot",
        _jsonb_compatible_type(),
        nullable=True,
    )
    reason = Column(Text, nullable=False, default="not-provided")
    trace_id = Column(String(120), nullable=True, index=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        CheckConstraint(
            "action IN ('seed_default', 'create_draft', 'update_draft', 'validate', "
            "'preview', 'publish', 'rollback', 'disable', 'delete_draft')",
            name="ck_business_rule_audit_action",
        ),
        Index(
            "idx_business_rule_audit_key_created",
            "config_key",
            "created_at",
        ),
    )

    config = relationship("BusinessRuleConfig")
    actor = relationship("User", foreign_keys=[actor_id])


class ConfigBundle(Base):
    """Read-only registry row for a business-domain configuration bundle."""

    __tablename__ = "config_bundles"

    bundle_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    bundle_key = Column(String(160), nullable=False, unique=True, index=True)
    domain = Column(String(80), nullable=False, index=True)
    display_name = Column(String(160), nullable=False)
    adapter_key = Column(String(120), nullable=False, index=True)
    legacy_domain = Column(String(120), nullable=True)
    read_path = Column(String(255), nullable=False)
    admin_entry = Column(String(255), nullable=False)
    enabled = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "domain IN ('business_rules', 'scoring', 'model', 'knowledge', 'voice_runtime', 'ai_analysis')",
            name="ck_config_bundle_domain",
        ),
        Index("idx_config_bundles_domain_enabled", "domain", "enabled"),
    )

    versions = relationship(
        "ConfigVersion",
        back_populates="bundle",
        cascade="all, delete-orphan",
    )


class ConfigVersion(Base):
    """Read-only version snapshot row for a ConfigBundle."""

    __tablename__ = "config_versions"

    version_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    bundle_id = Column(
        String(36),
        ForeignKey("config_bundles.bundle_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_config_id = Column(String(36), nullable=True, index=True)
    version_number = Column(Integer, nullable=True)
    version_label = Column(String(120), nullable=False)
    status = Column(String(32), nullable=False, index=True)
    snapshot_json = Column(
        "snapshot", _jsonb_compatible_type(), nullable=False, default=dict
    )
    source_updated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'validated', 'published', 'rolled_back', 'archived', 'disabled', 'default')",
            name="ck_config_version_status",
        ),
        UniqueConstraint(
            "bundle_id",
            "source_config_id",
            name="uq_config_versions_bundle_source",
        ),
        Index("idx_config_versions_bundle_status", "bundle_id", "status"),
    )

    bundle = relationship("ConfigBundle", back_populates="versions")


class ConfigBundleAuditLog(Base):
    """Immutable audit trail for ConfigBundle lifecycle changes."""

    __tablename__ = "config_bundle_audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    bundle_key = Column(String(160), nullable=False, index=True)
    version_id = Column(
        String(36),
        ForeignKey("config_versions.version_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action = Column(String(40), nullable=False, index=True)
    actor_id = Column(
        String(36), ForeignKey("users.user_id"), nullable=True, index=True
    )
    before_version = Column(Integer, nullable=True)
    after_version = Column(Integer, nullable=True)
    before_snapshot_json = Column(
        "before_snapshot",
        _jsonb_compatible_type(),
        nullable=True,
    )
    after_snapshot_json = Column(
        "after_snapshot",
        _jsonb_compatible_type(),
        nullable=True,
    )
    reason = Column(Text, nullable=False, default="not-provided")
    trace_id = Column(String(120), nullable=True, index=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        CheckConstraint(
            "action IN ('create_draft', 'validate', 'preview', 'publish', 'rollback', 'disable')",
            name="ck_config_bundle_audit_action",
        ),
        Index("idx_config_bundle_audit_key_created", "bundle_key", "created_at"),
    )

    version = relationship("ConfigVersion")
    actor = relationship("User", foreign_keys=[actor_id])


class PromptTemplate(Base):
    """Prompt template for AI interactions."""

    __tablename__ = "prompt_templates"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    prompt_type = Column(String(50), nullable=False)
    business_purpose = Column(String(100), nullable=True)
    category = Column(String(100), nullable=False, default="common")
    template = Column(Text, nullable=False)
    variables = Column(JSON, nullable=True, default=list)
    is_active = Column(Boolean, nullable=False, default=True)
    is_default = Column(Boolean, nullable=False, default=False)
    is_system = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        Index("idx_prompt_templates_type", "prompt_type"),
        Index("idx_prompt_templates_business_purpose", "business_purpose"),
        Index("idx_prompt_templates_active", "is_active"),
        Index(
            "uq_prompt_templates_default_per_type",
            "prompt_type",
            unique=True,
            postgresql_where=text("is_default = true"),
            sqlite_where=text("is_default = 1"),
        ),
    )


class ScenarioPrompt(Base):
    """Link between scenarios and prompt templates."""

    __tablename__ = "scenario_prompts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scenario_type = Column(String(50), nullable=False)
    scenario_id = Column(String(255), nullable=True)
    prompt_type = Column(String(50), nullable=False)
    template_id = Column(String(36), ForeignKey("prompt_templates.id"), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    template = relationship("PromptTemplate")

    __table_args__ = (
        Index("idx_scenario_prompts_type", "scenario_type", "prompt_type"),
        Index(
            "uq_scenario_prompts_active_scope",
            "scenario_type",
            func.coalesce(scenario_id, ""),
            "prompt_type",
            unique=True,
            postgresql_where=text("is_active = true"),
            sqlite_where=text("is_active = 1"),
        ),
    )


class ScoringRuleset(Base):
    """Versioned scoring ruleset managed through the admin control plane."""

    __tablename__ = "scoring_rulesets"

    ruleset_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scenario_type = Column(String(20), nullable=False, index=True)
    version = Column(String(80), nullable=False)
    display_name = Column(String(160), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="draft", index=True)
    definition_json = Column(JSON, nullable=False, default=dict)
    is_active = Column(Boolean, nullable=False, default=False, index=True)
    created_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    updated_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    published_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "scenario_type IN ('sales', 'presentation')",
            name="ck_scoring_ruleset_scenario_type",
        ),
        CheckConstraint(
            "status IN ('draft', 'published', 'archived')",
            name="ck_scoring_ruleset_status",
        ),
        UniqueConstraint(
            "scenario_type",
            "version",
            name="uq_scoring_ruleset_scenario_version",
        ),
        Index("idx_scoring_rulesets_scenario_active", "scenario_type", "is_active"),
    )


__all__ = [
    "BusinessRuleConfig",
    "BusinessRuleConfigAuditLog",
    "ConfigBundle",
    "ConfigVersion",
    "ConfigBundleAuditLog",
    "PromptTemplate",
    "ScenarioPrompt",
    "ScoringRuleset",
]
