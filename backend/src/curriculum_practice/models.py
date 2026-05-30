from __future__ import annotations

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
)

from common.db.models import Base


class PracticeTemplate(Base):
    __tablename__ = "practice_templates"

    template_id = Column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    scenario_type = Column(String(32), nullable=False, index=True)
    mode = Column(String(40), nullable=False)
    agent_id = Column(String(36), nullable=False, index=True)
    persona_id = Column(String(36), nullable=False, index=True)
    runtime_profile_id = Column(String(36), nullable=False, index=True)
    voice_mode = Column(String(32), nullable=False, default="stepfun_realtime")
    scoring_ruleset_id = Column(String(36), nullable=False, index=True)
    knowledge_base_refs = Column(JSON, nullable=False, default=list)
    case_item_id = Column(String(36), nullable=True, index=True)
    role_profile_id = Column(String(36), nullable=True, index=True)
    learning_content_id = Column(String(36), nullable=True, index=True)
    examiner_agent_id = Column(String(36), nullable=True, index=True)
    target_learner_level = Column(String(20), nullable=True, index=True)
    timeout_config = Column(JSON, nullable=True)
    curriculum_plan = Column(JSON, nullable=True)
    max_stage_duration_seconds = Column(Integer, nullable=True)
    situation_pack_code = Column(String(60), nullable=True)
    published_asset_refs = Column(JSON, nullable=False, default=dict)
    status = Column(String(20), nullable=False, default="draft", index=True)
    version = Column(Integer, nullable=False, default=1)
    content_hash = Column(String(80), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    published_by = Column(String(36), nullable=True)
    created_by = Column(String(36), nullable=True)
    updated_by = Column(String(36), nullable=True)
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
            name="ck_practice_template_scenario_type",
        ),
        CheckConstraint(
            "mode IN ('learning', 'expert_qa', 'examiner', 'customer_roleplay', 'mixed_path')",
            name="ck_practice_template_mode",
        ),
        CheckConstraint(
            "voice_mode IN ('legacy', 'stepfun_realtime')",
            name="ck_practice_template_voice_mode",
        ),
        CheckConstraint(
            "status IN ('draft', 'published', 'archived')",
            name="ck_practice_template_status",
        ),
        CheckConstraint(
            "(target_learner_level IS NULL OR target_learner_level IN ('conservative', 'beginner', 'intermediate', 'advanced'))",
            name="ck_practice_template_target_learner_level",
        ),
        Index("idx_practice_templates_status_updated", "status", "updated_at"),
    )


class ExaminerAgent(Base):
    __tablename__ = "examiner_agents"

    examiner_agent_id = Column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    question_source_ids = Column(JSON, nullable=False, default=list)
    learner_level_strategy = Column(JSON, nullable=False, default=dict)
    scoring_policy_id = Column(String(36), nullable=False, index=True)
    timeout_config = Column(JSON, nullable=False, default=dict)
    safety_config = Column(JSON, nullable=False, default=dict)
    prompt_config = Column(JSON, nullable=False, default=dict)
    simulation_config = Column(JSON, nullable=False, default=dict)
    status = Column(String(20), nullable=False, default="draft", index=True)
    version = Column(Integer, nullable=False, default=1)
    content_hash = Column(String(80), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    published_by = Column(String(36), nullable=True)
    created_by = Column(String(36), nullable=True)
    updated_by = Column(String(36), nullable=True)
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
            "status IN ('draft', 'published', 'archived')",
            name="ck_examiner_agent_status",
        ),
        Index("idx_examiner_agents_status_updated", "status", "updated_at"),
    )


class CaseItem(Base):
    __tablename__ = "case_items"

    case_item_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    industry = Column(String(120), nullable=False)
    company_profile = Column(Text, nullable=False)
    customer_role = Column(String(120), nullable=False)
    pain_points = Column(JSON, nullable=False, default=list)
    objections = Column(JSON, nullable=False, default=list)
    hidden_information = Column(Text, nullable=False)
    success_criteria = Column(JSON, nullable=False, default=list)
    allowed_disclosure_policy = Column(JSON, nullable=False, default=dict)
    version = Column(Integer, nullable=False, default=1)
    content_hash = Column(String(80), nullable=False)
    status = Column(String(20), nullable=False, default="draft", index=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    published_by = Column(String(36), nullable=True)
    created_by = Column(String(36), nullable=True)
    updated_by = Column(String(36), nullable=True)
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
            "status IN ('draft', 'published', 'archived')",
            name="ck_case_item_status",
        ),
        Index("idx_case_items_status_updated", "status", "updated_at"),
    )


class RoleProfile(Base):
    __tablename__ = "role_profiles"

    role_profile_id = Column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    role_type = Column(String(40), nullable=False)
    role_name = Column(String(160), nullable=False)
    persona_ref = Column(String(36), nullable=True, index=True)
    communication_style = Column(Text, nullable=False)
    pressure_level = Column(String(20), nullable=False)
    knowledge_boundary = Column(JSON, nullable=False, default=list)
    behavior_rules = Column(JSON, nullable=False, default=list)
    voice_style_hint = Column(String(300), nullable=False)
    voice_id = Column(String(64), nullable=True)
    voice_sample_url = Column(String(512), nullable=True)
    version = Column(Integer, nullable=False, default=1)
    content_hash = Column(String(80), nullable=False)
    status = Column(String(20), nullable=False, default="draft", index=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    published_by = Column(String(36), nullable=True)
    created_by = Column(String(36), nullable=True)
    updated_by = Column(String(36), nullable=True)
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
            "role_type IN ('customer')",
            name="ck_role_profile_role_type",
        ),
        CheckConstraint(
            "pressure_level IN ('low', 'medium', 'high')",
            name="ck_role_profile_pressure_level",
        ),
        CheckConstraint(
            "status IN ('draft', 'published', 'archived')",
            name="ck_role_profile_status",
        ),
        Index("idx_role_profiles_status_updated", "status", "updated_at"),
    )


class LearningContent(Base):
    __tablename__ = "learning_contents"

    learning_content_id = Column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    title = Column(String(200), nullable=False)
    summary = Column(Text, nullable=True)
    owner = Column(String(120), nullable=True)
    source = Column(String(300), nullable=True)
    status = Column(String(20), nullable=False, default="draft", index=True)
    safety_flagged = Column(Boolean, nullable=False, default=False)
    version = Column(Integer, nullable=False, default=1)
    content_hash = Column(String(80), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    published_by = Column(String(36), nullable=True)
    created_by = Column(String(36), nullable=True)
    updated_by = Column(String(36), nullable=True)
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
            "status IN ('draft', 'published', 'archived')",
            name="ck_learning_content_status",
        ),
        Index("idx_learning_contents_status_updated", "status", "updated_at"),
    )


class LearningChapter(Base):
    __tablename__ = "learning_chapters"

    chapter_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    learning_content_id = Column(
        String(36),
        ForeignKey("learning_contents.learning_content_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    order_index = Column(Integer, nullable=False)
    created_by = Column(String(36), nullable=True)
    updated_by = Column(String(36), nullable=True)
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
        CheckConstraint("order_index >= 1", name="ck_learning_chapter_order_index"),
        UniqueConstraint(
            "learning_content_id",
            "order_index",
            name="uq_learning_chapters_content_order",
        ),
        Index("idx_learning_chapters_content_order", "learning_content_id", "order_index"),
    )


class QuestionCategory(Base):
    __tablename__ = "question_categories"

    category_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    parent_id = Column(
        String(36),
        ForeignKey("question_categories.category_id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    name = Column(String(160), nullable=False)
    description = Column(Text, nullable=True)
    usage_scope = Column(String(50), nullable=False, default="general", index=True)
    order_index = Column(Integer, nullable=False, default=1)
    created_by = Column(String(36), nullable=True)
    updated_by = Column(String(36), nullable=True)
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
        CheckConstraint("order_index >= 1", name="ck_question_category_order_index"),
        Index("idx_question_categories_parent_order", "parent_id", "order_index"),
        Index(
            "idx_question_categories_scope_parent",
            "usage_scope",
            "parent_id",
            "order_index",
        ),
    )


class QuestionItem(Base):
    __tablename__ = "question_items"

    question_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    category_id = Column(
        String(36),
        ForeignKey("question_categories.category_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    title = Column(String(200), nullable=False)
    stem = Column(Text, nullable=False)
    reference_answer = Column(Text, nullable=True)
    scoring_criteria = Column(JSON, nullable=False, default=dict)
    scoring_dimensions = Column(JSON, nullable=False, default=list)
    tags = Column(JSON, nullable=False, default=list)
    usage_scope = Column(String(50), nullable=False, default="general", index=True)
    difficulty = Column(String(20), nullable=False, default="medium", index=True)
    status = Column(String(20), nullable=False, default="draft", index=True)
    safety_flagged = Column(Boolean, nullable=False, default=False)
    department = Column(String(120), nullable=True, index=True)
    version = Column(Integer, nullable=False, default=1)
    content_hash = Column(String(80), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    published_by = Column(String(36), nullable=True)
    created_by = Column(String(36), nullable=True)
    updated_by = Column(String(36), nullable=True)
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
            "difficulty IN ('easy', 'medium', 'hard')",
            name="ck_question_item_difficulty",
        ),
        CheckConstraint(
            "status IN ('draft', 'published', 'archived')",
            name="ck_question_item_status",
        ),
        Index("idx_question_items_status_updated", "status", "updated_at"),
        Index("idx_question_items_category_status", "category_id", "status"),
        Index("idx_question_items_scope_status", "usage_scope", "status"),
        Index("idx_question_items_scope_category", "usage_scope", "category_id"),
    )


class TestBankImportJob(Base):
    __tablename__ = "test_bank_import_jobs"

    task_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String(255), nullable=False)
    status = Column(String(20), nullable=False, default="pending", index=True)
    imported = Column(Integer, nullable=False, default=0)
    failed = Column(Integer, nullable=False, default=0)
    errors = Column(JSON, nullable=False, default=list)
    created_by = Column(String(36), nullable=True, index=True)
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
            "status IN ('pending', 'processing', 'completed', 'failed')",
            name="ck_test_bank_import_job_status",
        ),
        Index("idx_test_bank_import_jobs_created", "created_by", "created_at"),
    )


class LearningProgress(Base):
    __tablename__ = "learning_progress"

    progress_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=False, index=True)
    learning_content_id = Column(
        String(36),
        ForeignKey("learning_contents.learning_content_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chapter_id = Column(
        String(36),
        ForeignKey("learning_chapters.chapter_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    completed_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
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
        UniqueConstraint(
            "user_id",
            "learning_content_id",
            "chapter_id",
            name="uq_learning_progress_user_content_chapter",
        ),
        Index("idx_learning_progress_user_content", "user_id", "learning_content_id"),
    )


class SituationPack(Base):
    __tablename__ = "situation_packs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code = Column(String(60), nullable=False, unique=True)
    label = Column(String(120), nullable=False)
    description = Column(Text, nullable=True)
    version = Column(String(20), nullable=False, default="v1")
    content_hash = Column(String(80), nullable=True)
    status = Column(String(20), nullable=False, default="draft")
    relationship_context = Column(JSON, nullable=False, default=dict)
    visible_information_scope = Column(JSON, nullable=False, default=dict)
    forbidden_claim_patterns = Column(JSON, nullable=False, default=list)
    forbidden_topic_codes = Column(JSON, nullable=False, default=list)
    forbidden_stage_codes = Column(JSON, nullable=False, default=list)
    conflict_response_strategy = Column(
        String(40), nullable=True, default="neutral_clarification"
    )
    behavior_rules_for_prompt_only = Column(JSON, nullable=False, default=list)
    disclosure_policy = Column(JSON, nullable=False, default=dict)
    runtime_violation_policy = Column(JSON, nullable=False, default=dict)
    compatible_practice_modes = Column(
        JSON, nullable=False, default=lambda: ["customer_roleplay"]
    )
    compatible_scenario_types = Column(JSON, nullable=False, default=lambda: ["sales"])
    created_by = Column(String(36), nullable=True)
    updated_by = Column(String(36), nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
    published_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'published', 'archived')",
            name="ck_situation_pack_status",
        ),
        Index("idx_situation_packs_status", "status"),
        Index("idx_situation_packs_code", "code"),
    )


class LearnerProfile(Base):
    __tablename__ = "learner_profiles"

    user_id = Column(
        String(36),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        primary_key=True,
    )
    self_assessed_level = Column(String(20), nullable=True)
    admin_overridden_level = Column(String(20), nullable=True)
    effective_level = Column(String(20), nullable=False, default="conservative", index=True)
    self_assessed_at = Column(DateTime(timezone=True), nullable=True)
    overridden_by = Column(String(36), nullable=True)
    overridden_at = Column(DateTime(timezone=True), nullable=True)
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
            "(self_assessed_level IS NULL OR self_assessed_level IN ('conservative', 'beginner', 'intermediate', 'advanced'))",
            name="ck_learner_profile_self_assessed_level",
        ),
        CheckConstraint(
            "(admin_overridden_level IS NULL OR admin_overridden_level IN ('conservative', 'beginner', 'intermediate', 'advanced'))",
            name="ck_learner_profile_admin_overridden_level",
        ),
        CheckConstraint(
            "effective_level IN ('conservative', 'beginner', 'intermediate', 'advanced')",
            name="ck_learner_profile_effective_level",
        ),
        Index("idx_learner_profiles_effective_level", "effective_level"),
    )
