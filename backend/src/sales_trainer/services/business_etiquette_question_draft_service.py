from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.ai.llm_service import create_llm_service, get_llm_service
from common.ai.models import ModelConfig, ModelType
from common.db.models import User
from common.db.typing import json_dict_or_empty
from prompt_templates.models import (
    PROMPT_BUSINESS_PURPOSE_BUSINESS_ETIQUETTE_QUESTION,
)
from prompt_templates.service import PromptTemplateService
from sales_trainer.models import (
    SalesTrainerAssetRevision,
    SalesTrainerBusinessEtiquetteQuestionDraft,
)
from sales_trainer.schemas import (
    BusinessEtiquetteCapabilityConfig,
    BusinessEtiquetteQuestionDraftApproveRequest,
    BusinessEtiquetteQuestionDraftGenerateRequest,
    BusinessEtiquetteQuestionDraftGenerateResponse,
    BusinessEtiquetteQuestionDraftListResponse,
    BusinessEtiquetteQuestionDraftOption,
    BusinessEtiquetteQuestionDraftRejectRequest,
    BusinessEtiquetteQuestionDraftResponse,
    BusinessEtiquetteQuestionDraftStatus,
    BusinessEtiquetteQuestionDraftType,
    BusinessEtiquetteQuestionDraftUpdateRequest,
    SalesTrainerQuestionCreate,
    SalesTrainerQuestionOption,
)
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionService,
)
from sales_trainer.services.business_etiquette_capability_service import (
    BusinessEtiquetteCapabilityService,
    BusinessEtiquetteCapabilityServiceError,
)
from sales_trainer.services.business_etiquette_import_service import (
    BUSINESS_ETIQUETTE_RESOURCE_TYPE,
    DEFAULT_BUSINESS_ETIQUETTE_TRAINING_PACK_KEY,
)
from sales_trainer.services.curriculum_practice_adapter import (
    LearningChapterSummary,
    get_learning_chapter_by_order,
)
from sales_trainer.services.operation_log_service import OperationLogService
from sales_trainer.services.question_bank.service import (
    SalesTrainerQuestionService,
    SalesTrainerQuestionServiceError,
)

QUESTION_DRAFT_TARGET_TYPE = "business_etiquette_question_draft"
QUESTION_DRAFT_RUNTIME_CONSUMER = "business_etiquette.question_draft_generation"
QUESTION_DRAFT_PROMPT_CATEGORIES = {
    "business_etiquette",
    "sales_trainer_ai_coach",
    "sales_trainer",
}
QUESTION_DRAFT_PROMPT_KEYWORDS = ("题目生成", "题目草稿", "试题生成", "question")
QUESTION_DRAFT_PROMPT_EXCLUDED_KEYWORDS = ("对话教练", "互动卡片", "chatbot")
QUESTION_DRAFT_REQUIRED_RUNTIME_VARIABLES = {
    "chapter_title",
    "chapter_content",
    "capabilities_json",
    "question_types_json",
    "draft_count",
    "output_schema",
}
AI_COACH_INTERACTION_PROMPT_MARKERS = (
    "ai_coach_interaction_v1",
    "answer_key",
    "scoring_rubric",
    "allowed_interaction_types",
)
AI_COACH_INTERACTION_VARIABLES = {
    "module_key",
    "turn_number",
    "article_title",
    "article_summary",
    "chapter_titles",
    "previous_turns",
    "allowed_interaction_types",
    "coach_mode",
}
QUESTION_DRAFT_SYSTEM_MESSAGE = (
    "你是商务礼仪新人训练题目生成器。必须只输出符合约定 JSON schema 的题目草稿，"
    "不得输出解释性正文。"
)
QUESTION_DRAFT_JSON_RESPONSE_FORMAT = {"type": "json_object"}
QUESTION_DRAFT_OUTPUT_SCHEMA = {
    "drafts": [
        {
            "question_type": "single_choice | multiple_choice | short_answer",
            "title": "题目标题，200 字以内",
            "stem": "题干，必须基于 source_excerpt 或 chapter_content",
            "options": [
                {"value": "A", "label": "选项文本"},
                {"value": "B", "label": "选项文本"},
            ],
            "correct_answer": "单选题正确选项 value",
            "correct_answers": ["多选题正确选项 value"],
            "reference_answer": "简答题参考答案",
            "explanation": "解析，说明答案依据",
            "difficulty": "easy | medium | hard",
            "capability_keys": ["能力点 key"],
            "source_excerpt": "题目依据的原文片段",
        }
    ]
}


class BusinessEtiquetteQuestionDraftServiceError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class _ChapterSource:
    chapter: LearningChapterSummary
    title: str
    content: str


class _GeneratedQuestionDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_type: BusinessEtiquetteQuestionDraftType
    title: str = Field(..., min_length=1, max_length=200)
    stem: str = Field(..., min_length=1)
    options: list[BusinessEtiquetteQuestionDraftOption] = Field(default_factory=list)
    correct_answer: str | None = Field(None, min_length=1, max_length=20)
    correct_answers: list[str] = Field(default_factory=list)
    reference_answer: str | None = Field(None, min_length=1, max_length=8000)
    explanation: str | None = Field(None, max_length=4000)
    difficulty: str = "medium"
    capability_keys: list[str] = Field(default_factory=list)
    source_excerpt: str | None = Field(None, max_length=4000)

    @model_validator(mode="after")
    def validate_question_shape(self) -> _GeneratedQuestionDraft:
        if self.difficulty not in {"easy", "medium", "hard"}:
            raise ValueError("difficulty must be easy, medium, or hard")
        option_values = {item.value for item in self.options}
        if self.question_type == "single_choice":
            if len(self.options) < 2:
                raise ValueError("single_choice requires at least 2 options")
            if not self.correct_answer or self.correct_answer not in option_values:
                raise ValueError("single_choice correct_answer must match options")
        if self.question_type == "multiple_choice":
            if len(self.options) < 2:
                raise ValueError("multiple_choice requires at least 2 options")
            if not self.correct_answers or any(
                value not in option_values for value in self.correct_answers
            ):
                raise ValueError("multiple_choice correct_answers must match options")
        if self.question_type == "short_answer" and not (
            self.reference_answer and self.reference_answer.strip()
        ):
            raise ValueError("short_answer requires reference_answer")
        return self


class BusinessEtiquetteQuestionDraftService:
    def __init__(self, db: AsyncSession, *, llm_service: Any | None = None) -> None:
        self._db = db
        self._asset_revisions = SalesTrainerAssetRevisionService(db)
        self._logs = OperationLogService(db)
        self._llm_service = llm_service

    async def generate_drafts(
        self,
        payload: BusinessEtiquetteQuestionDraftGenerateRequest,
        *,
        actor: User,
        trace_id: str | None = None,
    ) -> BusinessEtiquetteQuestionDraftGenerateResponse:
        logical_id = _normalize_training_pack_key(payload.training_pack_key)
        revision = await self._require_training_pack_revision(logical_id)
        capability_snapshot = await self._capability_snapshot(logical_id)
        capability_map = _active_capabilities_by_key(capability_snapshot.capabilities)
        capability_keys = _generation_capability_keys(
            requested_keys=payload.capability_keys,
            chapter_order=payload.chapter_order,
            chapter_bindings=capability_snapshot.chapter_bindings,
            capability_map=capability_map,
        )
        chapter_source = await self._require_chapter_source(
            revision,
            chapter_order=payload.chapter_order,
        )
        template = await self._require_prompt_template(payload.prompt_template_id)
        (
            runtime_model_config,
            selected_model_config,
        ) = await self._resolve_llm_model_config(payload.llm_model_config)
        variables = _generation_variables(
            payload=payload,
            logical_id=logical_id,
            revision=revision,
            chapter_source=chapter_source,
            capabilities=[capability_map[key] for key in capability_keys],
        )
        compile_result = PromptTemplateService(
            self._db
        ).compile_runtime_prompt_contract(
            template=template,
            variables=variables,
            runtime_consumer=QUESTION_DRAFT_RUNTIME_CONSUMER,
            system_message=QUESTION_DRAFT_SYSTEM_MESSAGE,
            model_config=runtime_model_config or None,
        )
        if not compile_result.is_success or compile_result.value is None:
            raise BusinessEtiquetteQuestionDraftServiceError(
                f"[BUSINESS_ETIQUETTE_QUESTION_PROMPT_COMPILE_FAILED:"
                f"{compile_result.fallback or 'unknown'}]",
                _prompt_compile_failure_message(compile_result.fallback),
                502,
            )
        contract = compile_result.value
        batch_id = str(uuid.uuid4())
        raw_text = await self._generate_llm_text(
            contract=contract,
            batch_id=batch_id,
            selected_model_config=selected_model_config,
        )
        raw_payload = _extract_json_payload(raw_text)
        if raw_payload is None:
            raise BusinessEtiquetteQuestionDraftServiceError(
                "[BUSINESS_ETIQUETTE_QUESTION_GENERATION_INVALID_JSON]",
                "AI 生成结果不是合法 JSON，本批次未写入草稿箱。",
                502,
            )
        generated_items = _parse_generated_items(
            raw_payload,
            allowed_question_types=set(payload.question_types),
            allowed_capability_keys=set(capability_map),
            fallback_capability_keys=capability_keys,
            fallback_source_excerpt=_excerpt(chapter_source.content),
        )
        if not generated_items:
            raise BusinessEtiquetteQuestionDraftServiceError(
                "[BUSINESS_ETIQUETTE_QUESTION_GENERATION_EMPTY]",
                "AI 生成结果未包含任何可审核题目草稿。",
                502,
            )
        if len(generated_items) > payload.draft_count:
            generated_items = generated_items[: payload.draft_count]

        drafts = [
            _draft_from_generated_item(
                item,
                raw_payload=raw_payload,
                batch_id=batch_id,
                logical_id=logical_id,
                revision=revision,
                chapter_source=chapter_source,
                prompt_template_id=str(template.id),
                prompt_template_name=template.name,
                prompt_contract_hash=contract.contract_hash,
                prompt_contract_version=contract.contract_version,
                prompt_rendered_hash=_sha256(contract.rendered_prompt),
                model_config=runtime_model_config,
                actor=actor,
            )
            for item in generated_items
        ]
        self._db.add_all(drafts)
        await self._logs.record(
            actor=actor,
            action="business_etiquette_question_drafts.generated",
            target_type=QUESTION_DRAFT_TARGET_TYPE,
            target_id=batch_id,
            request_id=trace_id,
            metadata={
                "batch_id": batch_id,
                "training_pack_key": logical_id,
                "chapter_order": payload.chapter_order,
                "draft_count": len(drafts),
                "question_types": list(payload.question_types),
                "capability_keys": capability_keys,
                "prompt_template_id": str(template.id),
                "prompt_contract_hash": contract.contract_hash,
            },
        )
        await self._db.commit()
        for draft in drafts:
            await self._db.refresh(draft)
        return BusinessEtiquetteQuestionDraftGenerateResponse(
            batch_id=batch_id,
            items=[
                _draft_response(draft, chapter_title=chapter_source.title)
                for draft in drafts
            ],
            total=len(drafts),
        )

    async def list_drafts(
        self,
        *,
        training_pack_key: str | None = None,
        chapter_order: int | None = None,
        question_type: str | None = None,
        status: str | None = None,
        capability_key: str | None = None,
        batch_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> BusinessEtiquetteQuestionDraftListResponse:
        logical_id = (
            _normalize_training_pack_key(training_pack_key)
            if training_pack_key is not None
            else None
        )
        stmt = select(SalesTrainerBusinessEtiquetteQuestionDraft)
        if logical_id is not None:
            stmt = stmt.where(
                SalesTrainerBusinessEtiquetteQuestionDraft.training_pack_key
                == logical_id
            )
        if chapter_order is not None:
            stmt = stmt.where(
                SalesTrainerBusinessEtiquetteQuestionDraft.chapter_order
                == chapter_order
            )
        if question_type is not None:
            stmt = stmt.where(
                SalesTrainerBusinessEtiquetteQuestionDraft.question_type
                == question_type
            )
        if status is not None:
            stmt = stmt.where(
                SalesTrainerBusinessEtiquetteQuestionDraft.status == status
            )
        if batch_id is not None:
            stmt = stmt.where(
                SalesTrainerBusinessEtiquetteQuestionDraft.batch_id == batch_id
            )
        result = await self._db.execute(
            stmt.order_by(
                SalesTrainerBusinessEtiquetteQuestionDraft.created_at.desc(),
                SalesTrainerBusinessEtiquetteQuestionDraft.draft_id.desc(),
            )
        )
        rows = list(result.scalars().all())
        if capability_key is not None:
            rows = [
                row for row in rows if capability_key in list(row.capability_keys or [])
            ]
        total = len(rows)
        page = rows[offset : offset + limit]
        return BusinessEtiquetteQuestionDraftListResponse(
            items=[_draft_response(row) for row in page],
            total=total,
        )

    async def update_draft(
        self,
        draft_id: str,
        payload: BusinessEtiquetteQuestionDraftUpdateRequest,
        *,
        actor: User,
        trace_id: str | None = None,
    ) -> BusinessEtiquetteQuestionDraftResponse:
        draft = await self._require_draft(draft_id)
        _require_pending_review(draft)
        updates = payload.model_dump(exclude_unset=True)
        for field, value in updates.items():
            setattr(draft, field, _dump_options(value) if field == "options" else value)
        _validate_draft_shape(draft)
        setattr(draft, "updated_by", str(actor.user_id))
        await self._logs.record(
            actor=actor,
            action="business_etiquette_question_draft.updated",
            target_type=QUESTION_DRAFT_TARGET_TYPE,
            target_id=draft_id,
            request_id=trace_id,
            metadata={
                "changed_fields": sorted(updates),
                "batch_id": draft.batch_id,
                "training_pack_key": draft.training_pack_key,
            },
        )
        await self._db.commit()
        await self._db.refresh(draft)
        return _draft_response(draft)

    async def reject_draft(
        self,
        draft_id: str,
        payload: BusinessEtiquetteQuestionDraftRejectRequest,
        *,
        actor: User,
        trace_id: str | None = None,
    ) -> BusinessEtiquetteQuestionDraftResponse:
        draft = await self._require_draft(draft_id)
        _require_pending_review(draft)
        setattr(draft, "status", "rejected")
        setattr(draft, "review_notes", payload.review_notes)
        setattr(draft, "reviewed_by", str(actor.user_id))
        setattr(draft, "reviewed_at", datetime.now(UTC))
        setattr(draft, "updated_by", str(actor.user_id))
        await self._logs.record(
            actor=actor,
            action="business_etiquette_question_draft.rejected",
            target_type=QUESTION_DRAFT_TARGET_TYPE,
            target_id=draft_id,
            request_id=trace_id,
            metadata={
                "batch_id": draft.batch_id,
                "training_pack_key": draft.training_pack_key,
                "review_notes": payload.review_notes,
            },
        )
        await self._db.commit()
        await self._db.refresh(draft)
        return _draft_response(draft)

    async def approve_draft(
        self,
        draft_id: str,
        payload: BusinessEtiquetteQuestionDraftApproveRequest,
        *,
        actor: User,
        trace_id: str | None = None,
    ) -> BusinessEtiquetteQuestionDraftResponse:
        draft = await self._require_draft(draft_id)
        _require_pending_review(draft)
        _validate_draft_shape(draft)
        question_payload = _question_payload_from_draft(
            draft,
            category_id=payload.category_id,
        )
        try:
            question = await SalesTrainerQuestionService(self._db).create_question(
                question_payload,
                actor_id=str(actor.user_id),
            )
        except SalesTrainerQuestionServiceError as exc:
            raise BusinessEtiquetteQuestionDraftServiceError(
                exc.code,
                exc.message,
                exc.status_code,
            ) from exc

        setattr(draft, "status", "converted")
        setattr(draft, "question_id", str(question.question_id))
        setattr(draft, "review_notes", payload.review_notes)
        setattr(draft, "reviewed_by", str(actor.user_id))
        setattr(draft, "reviewed_at", datetime.now(UTC))
        setattr(draft, "updated_by", str(actor.user_id))
        await self._logs.record(
            actor=actor,
            action="business_etiquette_question_draft.approved",
            target_type=QUESTION_DRAFT_TARGET_TYPE,
            target_id=draft_id,
            request_id=trace_id,
            metadata={
                "batch_id": draft.batch_id,
                "training_pack_key": draft.training_pack_key,
                "category_id": payload.category_id,
                "question_id": str(question.question_id),
                "question_status": str(question.status),
                "capability_keys": list(draft.capability_keys or []),
            },
        )
        await self._db.commit()
        await self._db.refresh(draft)
        return _draft_response(draft)

    async def _require_training_pack_revision(
        self,
        logical_id: str,
    ) -> SalesTrainerAssetRevision:
        working_revision = await self._asset_revisions.latest_working_revision(
            resource_type=BUSINESS_ETIQUETTE_RESOURCE_TYPE,
            logical_id=logical_id,
        )
        if working_revision is not None:
            return working_revision
        active_revision = await self._asset_revisions.active_revision(
            resource_type=BUSINESS_ETIQUETTE_RESOURCE_TYPE,
            logical_id=logical_id,
        )
        if active_revision is not None:
            return active_revision
        raise BusinessEtiquetteQuestionDraftServiceError(
            "[BUSINESS_ETIQUETTE_TRAINING_PACK_REVISION_MISSING]",
            "请先导入商务礼仪训练包资料，再生成题目草稿。",
            409,
        )

    async def _capability_snapshot(self, logical_id: str) -> Any:
        try:
            snapshot = await BusinessEtiquetteCapabilityService(self._db).get_snapshot(
                training_pack_key=logical_id
            )
        except BusinessEtiquetteCapabilityServiceError as exc:
            raise BusinessEtiquetteQuestionDraftServiceError(
                exc.code,
                exc.message,
                exc.status_code,
            ) from exc
        if snapshot.needs_save:
            raise BusinessEtiquetteQuestionDraftServiceError(
                "[BUSINESS_ETIQUETTE_CAPABILITY_SNAPSHOT_MISSING]",
                "请先保存商务礼仪能力点快照，再生成题目草稿。",
                409,
            )
        return snapshot

    async def _require_chapter_source(
        self,
        revision: SalesTrainerAssetRevision,
        *,
        chapter_order: int,
    ) -> _ChapterSource:
        payload: dict[str, Any] = json_dict_or_empty(revision.payload_json)
        learning_content_id = payload.get("learning_content_id")
        if not isinstance(learning_content_id, str) or not learning_content_id:
            raise BusinessEtiquetteQuestionDraftServiceError(
                "[BUSINESS_ETIQUETTE_TRAINING_PACK_CHAPTER_MISSING]",
                "商务礼仪训练包缺少文章内容绑定，无法生成题目草稿。",
                409,
            )
        chapter = await get_learning_chapter_by_order(
            self._db,
            learning_content_id,
            chapter_order,
        )
        if chapter is None:
            raise BusinessEtiquetteQuestionDraftServiceError(
                "[BUSINESS_ETIQUETTE_TRAINING_PACK_CHAPTER_MISSING]",
                f"商务礼仪训练包第 {chapter_order} 章不存在。",
                404,
            )
        content = str(chapter.content or "").strip()
        if not content:
            raise BusinessEtiquetteQuestionDraftServiceError(
                "[BUSINESS_ETIQUETTE_TRAINING_PACK_CHAPTER_EMPTY]",
                f"商务礼仪训练包第 {chapter_order} 章内容为空。",
                409,
            )
        return _ChapterSource(
            chapter=chapter,
            title=str(chapter.title),
            content=content,
        )

    async def _require_prompt_template(self, prompt_template_id: str) -> Any:
        try:
            template_uuid = UUID(prompt_template_id)
        except ValueError as exc:
            raise BusinessEtiquetteQuestionDraftServiceError(
                "[BUSINESS_ETIQUETTE_QUESTION_PROMPT_INVALID]",
                "商务礼仪题目生成 Prompt 模板 ID 非法。",
                422,
            ) from exc
        template = await PromptTemplateService(self._db).get_template(template_uuid)
        if template is None:
            raise BusinessEtiquetteQuestionDraftServiceError(
                "[BUSINESS_ETIQUETTE_QUESTION_PROMPT_NOT_FOUND]",
                "商务礼仪题目生成 Prompt 模板不存在。",
                404,
            )
        if not template.is_active:
            raise BusinessEtiquetteQuestionDraftServiceError(
                "[BUSINESS_ETIQUETTE_QUESTION_PROMPT_INACTIVE]",
                "商务礼仪题目生成 Prompt 模板已停用。",
                409,
            )
        if not _is_question_generation_prompt_template(template):
            raise BusinessEtiquetteQuestionDraftServiceError(
                "[BUSINESS_ETIQUETTE_QUESTION_PROMPT_PURPOSE_MISMATCH]",
                "请选择商务礼仪题目生成专用 Prompt 模板。",
                409,
            )
        if _is_ai_coach_interaction_prompt_template(template):
            raise BusinessEtiquetteQuestionDraftServiceError(
                "[BUSINESS_ETIQUETTE_QUESTION_PROMPT_SCHEMA_MISMATCH]",
                (
                    "当前模板是 AI 教练互动卡片模板，不是商务礼仪题目草稿生成模板。"
                    "请改选或新建「商务礼仪题目草稿生成 v1」。"
                ),
                409,
            )
        return template

    async def _resolve_llm_model_config(
        self,
        model_config_payload: dict[str, Any],
    ) -> tuple[dict[str, Any], ModelConfig | None]:
        runtime_config = dict(model_config_payload or {})
        model_config_id = str(runtime_config.get("model_config_id") or "").strip()
        if not model_config_id:
            return runtime_config, None
        try:
            UUID(model_config_id)
        except ValueError as exc:
            raise BusinessEtiquetteQuestionDraftServiceError(
                "[BUSINESS_ETIQUETTE_QUESTION_MODEL_CONFIG_INVALID]",
                "商务礼仪题目生成模型配置 ID 无效。",
                400,
            ) from exc

        selected = await self._db.get(ModelConfig, model_config_id)
        if selected is None:
            raise BusinessEtiquetteQuestionDraftServiceError(
                "[BUSINESS_ETIQUETTE_QUESTION_MODEL_CONFIG_NOT_FOUND]",
                "商务礼仪题目生成模型配置不存在。",
                404,
            )
        if selected.model_type != ModelType.LLM.value:
            raise BusinessEtiquetteQuestionDraftServiceError(
                "[BUSINESS_ETIQUETTE_QUESTION_MODEL_CONFIG_INVALID]",
                "商务礼仪题目生成只能选择 LLM 模型配置。",
                400,
            )
        if not selected.is_active:
            raise BusinessEtiquetteQuestionDraftServiceError(
                "[BUSINESS_ETIQUETTE_QUESTION_MODEL_CONFIG_INACTIVE]",
                "商务礼仪题目生成模型配置已停用。",
                409,
            )

        extra_config: dict[str, Any] = json_dict_or_empty(selected.extra_config)
        requested_extra_config = runtime_config.get("extra_config")
        if isinstance(requested_extra_config, dict):
            extra_config = {**extra_config, **requested_extra_config}

        selected_runtime_config: dict[str, Any] = {
            "model_config_id": selected.id,
            "provider": selected.provider,
            "base_url": selected.base_url,
            "model_name": selected.model_name,
            "extra_config": extra_config,
        }
        for key, value in runtime_config.items():
            if key not in selected_runtime_config and key != "api_key":
                selected_runtime_config[key] = value
        return selected_runtime_config, selected

    async def _generate_llm_text(
        self,
        *,
        contract: Any,
        batch_id: str,
        selected_model_config: ModelConfig | None = None,
    ) -> str:
        llm_service = self._llm_service
        if llm_service is None:
            llm_service = (
                create_llm_service(selected_model_config)
                if selected_model_config is not None
                else get_llm_service()
            )
        result = await llm_service.generate(
            prompt=contract.rendered_prompt,
            session_id=batch_id,
            system_message=contract.system_message,
            response_format=QUESTION_DRAFT_JSON_RESPONSE_FORMAT,
            allow_fallback_response=False,
        )
        if hasattr(result, "is_success"):
            if not result.is_success or not result.value:
                raise BusinessEtiquetteQuestionDraftServiceError(
                    "[BUSINESS_ETIQUETTE_QUESTION_GENERATION_FAILED]",
                    "AI 题目草稿生成失败。",
                    502,
                )
            return str(result.value)
        text = str(result or "").strip()
        if not text:
            raise BusinessEtiquetteQuestionDraftServiceError(
                "[BUSINESS_ETIQUETTE_QUESTION_GENERATION_FAILED]",
                "AI 题目草稿生成失败。",
                502,
            )
        return text

    async def _require_draft(
        self,
        draft_id: str,
    ) -> SalesTrainerBusinessEtiquetteQuestionDraft:
        draft = await self._db.get(SalesTrainerBusinessEtiquetteQuestionDraft, draft_id)
        if draft is None:
            raise BusinessEtiquetteQuestionDraftServiceError(
                "[BUSINESS_ETIQUETTE_QUESTION_DRAFT_NOT_FOUND]",
                "商务礼仪题目草稿不存在。",
                404,
            )
        return draft


def _normalize_training_pack_key(training_pack_key: str | None) -> str:
    logical_id = (
        training_pack_key or DEFAULT_BUSINESS_ETIQUETTE_TRAINING_PACK_KEY
    ).strip()
    if not logical_id:
        raise BusinessEtiquetteQuestionDraftServiceError(
            "[BUSINESS_ETIQUETTE_QUESTION_DRAFT_CONFIG_INVALID]",
            "商务礼仪训练包 key 不能为空。",
            400,
        )
    return logical_id


def _active_capabilities_by_key(
    capabilities: list[BusinessEtiquetteCapabilityConfig],
) -> dict[str, BusinessEtiquetteCapabilityConfig]:
    return {
        capability.capability_key: capability
        for capability in capabilities
        if capability.status != "archived"
    }


def _generation_capability_keys(
    *,
    requested_keys: list[str],
    chapter_order: int,
    chapter_bindings: list[Any],
    capability_map: dict[str, BusinessEtiquetteCapabilityConfig],
) -> list[str]:
    bound_keys: list[str] = []
    for binding in chapter_bindings:
        if binding.chapter_order == chapter_order:
            bound_keys = [
                key for key in binding.capability_keys if key in capability_map
            ]
            break
    selected = requested_keys or bound_keys
    unknown = sorted(set(selected) - set(capability_map))
    if unknown:
        raise BusinessEtiquetteQuestionDraftServiceError(
            "[BUSINESS_ETIQUETTE_QUESTION_CAPABILITY_INVALID]",
            f"题目草稿引用了不存在或已归档的能力点：{', '.join(unknown)}。",
            422,
        )
    if not selected:
        raise BusinessEtiquetteQuestionDraftServiceError(
            "[BUSINESS_ETIQUETTE_QUESTION_CAPABILITY_MISSING]",
            "请先为章节绑定至少一个有效能力点，再生成题目草稿。",
            409,
        )
    return _dedupe(selected)


def _generation_variables(
    *,
    payload: BusinessEtiquetteQuestionDraftGenerateRequest,
    logical_id: str,
    revision: SalesTrainerAssetRevision,
    chapter_source: _ChapterSource,
    capabilities: list[BusinessEtiquetteCapabilityConfig],
) -> dict[str, Any]:
    chapter_content = chapter_source.content
    capabilities_payload = [
        capability.model_dump(mode="json") for capability in capabilities
    ]
    revision_payload = json_dict_or_empty(revision.payload_json)
    return {
        "training_pack_key": logical_id,
        "training_pack_revision_id": str(revision.revision_id),
        "training_pack_revision_no": revision.revision_no,
        "book_title": str(revision_payload.get("book_title") or ""),
        "chapter_id": str(chapter_source.chapter.chapter_id),
        "chapter_order": payload.chapter_order,
        "chapter_title": chapter_source.title,
        "chapter_content": chapter_content,
        "source_excerpt": _excerpt(chapter_content),
        "capabilities_json": json.dumps(
            capabilities_payload,
            ensure_ascii=False,
        ),
        "capability_keys_json": json.dumps(
            [capability.capability_key for capability in capabilities],
            ensure_ascii=False,
        ),
        "question_types_json": json.dumps(
            list(payload.question_types),
            ensure_ascii=False,
        ),
        "draft_count": payload.draft_count,
        "output_schema": json.dumps(
            QUESTION_DRAFT_OUTPUT_SCHEMA,
            ensure_ascii=False,
            indent=2,
        ),
        "review_policy": "生成结果只能进入草稿箱；必须由管理员审核后才能转入正式题库。",
        "language": "zh-CN",
        "reason": payload.reason or "",
    }


def _extract_json_payload(raw_text: str) -> dict[str, Any] | list[Any] | None:
    text = raw_text.strip()
    if not text:
        return None
    try:
        payload = json.loads(text)
        if isinstance(payload, (dict, list)):
            return payload
    except json.JSONDecodeError:
        pass
    start_candidates = [
        index for index in (text.find("{"), text.find("[")) if index >= 0
    ]
    if not start_candidates:
        return None
    start = min(start_candidates)
    end = max(text.rfind("}"), text.rfind("]"))
    if end <= start:
        return None
    try:
        payload = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, (dict, list)) else None


def _parse_generated_items(
    raw_payload: dict[str, Any] | list[Any],
    *,
    allowed_question_types: set[str],
    allowed_capability_keys: set[str],
    fallback_capability_keys: list[str],
    fallback_source_excerpt: str,
) -> list[_GeneratedQuestionDraft]:
    raw_items: Any
    if isinstance(raw_payload, list):
        raw_items = raw_payload
    else:
        raw_items = raw_payload.get("drafts") or raw_payload.get("questions")
    if not isinstance(raw_items, list):
        raise BusinessEtiquetteQuestionDraftServiceError(
            "[BUSINESS_ETIQUETTE_QUESTION_GENERATION_INVALID_SCHEMA]",
            "AI 生成结果缺少 drafts 数组。",
            502,
        )

    items: list[_GeneratedQuestionDraft] = []
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            raise BusinessEtiquetteQuestionDraftServiceError(
                "[BUSINESS_ETIQUETTE_QUESTION_GENERATION_INVALID_SCHEMA]",
                "AI 生成题目草稿必须是对象。",
                502,
            )
        normalized = _normalize_generated_item(
            raw_item,
            fallback_capability_keys=fallback_capability_keys,
            fallback_source_excerpt=fallback_source_excerpt,
        )
        try:
            item = _GeneratedQuestionDraft.model_validate(normalized)
        except ValidationError as exc:
            raise BusinessEtiquetteQuestionDraftServiceError(
                "[BUSINESS_ETIQUETTE_QUESTION_GENERATION_INVALID_SCHEMA]",
                f"AI 生成题目草稿结构非法：{exc.errors()[0]['msg']}。",
                502,
            ) from exc
        if item.question_type not in allowed_question_types:
            raise BusinessEtiquetteQuestionDraftServiceError(
                "[BUSINESS_ETIQUETTE_QUESTION_GENERATION_TYPE_NOT_ALLOWED]",
                f"AI 生成了未请求的题型：{item.question_type}。",
                502,
            )
        unknown_keys = sorted(set(item.capability_keys) - allowed_capability_keys)
        if unknown_keys:
            raise BusinessEtiquetteQuestionDraftServiceError(
                "[BUSINESS_ETIQUETTE_QUESTION_GENERATION_CAPABILITY_INVALID]",
                f"AI 生成题目引用了未知能力点：{', '.join(unknown_keys)}。",
                502,
            )
        items.append(item)
    return items


def _normalize_generated_item(
    raw_item: dict[str, Any],
    *,
    fallback_capability_keys: list[str],
    fallback_source_excerpt: str,
) -> dict[str, Any]:
    question_type = str(raw_item.get("question_type") or raw_item.get("type") or "")
    options = _normalize_options(
        raw_item.get("options") or raw_item.get("choices") or []
    )
    correct_answers = raw_item.get("correct_answers") or raw_item.get("answers") or []
    if isinstance(correct_answers, str):
        correct_answers = [correct_answers]
    capability_keys = raw_item.get("capability_keys") or raw_item.get("capabilities")
    if not isinstance(capability_keys, list) or not capability_keys:
        capability_keys = fallback_capability_keys
    return {
        "question_type": question_type,
        "title": str(raw_item.get("title") or "").strip(),
        "stem": str(raw_item.get("stem") or raw_item.get("question") or "").strip(),
        "options": options,
        "correct_answer": _optional_string(raw_item.get("correct_answer")),
        "correct_answers": [
            str(value).strip() for value in correct_answers if str(value).strip()
        ],
        "reference_answer": _optional_string(raw_item.get("reference_answer")),
        "explanation": _optional_string(raw_item.get("explanation")),
        "difficulty": str(raw_item.get("difficulty") or "medium").strip(),
        "capability_keys": [
            str(value).strip() for value in capability_keys if str(value).strip()
        ],
        "source_excerpt": _optional_string(raw_item.get("source_excerpt"))
        or fallback_source_excerpt,
    }


def _normalize_options(raw_options: Any) -> list[dict[str, str]]:
    if not isinstance(raw_options, list):
        return []
    normalized: list[dict[str, str]] = []
    default_values = ("A", "B", "C", "D", "E", "F")
    for index, raw in enumerate(raw_options):
        if isinstance(raw, dict):
            value = str(
                raw.get("value") or raw.get("id") or raw.get("key") or ""
            ).strip()
            label = str(raw.get("label") or raw.get("text") or "").strip()
        else:
            value = ""
            label = str(raw or "").strip()
        if not value and index < len(default_values):
            value = default_values[index]
        if value and label:
            normalized.append({"value": value, "label": label})
    return normalized


def _draft_from_generated_item(
    item: _GeneratedQuestionDraft,
    *,
    raw_payload: dict[str, Any] | list[Any],
    batch_id: str,
    logical_id: str,
    revision: SalesTrainerAssetRevision,
    chapter_source: _ChapterSource,
    prompt_template_id: str,
    prompt_template_name: str,
    prompt_contract_hash: str,
    prompt_contract_version: str,
    prompt_rendered_hash: str,
    model_config: dict[str, Any],
    actor: User,
) -> SalesTrainerBusinessEtiquetteQuestionDraft:
    payload: dict[str, Any] = json_dict_or_empty(revision.payload_json)
    return SalesTrainerBusinessEtiquetteQuestionDraft(
        batch_id=batch_id,
        training_pack_key=logical_id,
        training_pack_revision_id=str(revision.revision_id),
        training_pack_revision_no=revision.revision_no,
        learning_content_id=payload.get("learning_content_id"),
        chapter_id=str(chapter_source.chapter.chapter_id),
        chapter_order=chapter_source.chapter.order_index,
        source_excerpt=item.source_excerpt,
        question_type=item.question_type,
        title=item.title,
        stem=item.stem,
        options=[option.model_dump() for option in item.options],
        correct_answer=item.correct_answer,
        correct_answers=item.correct_answers,
        reference_answer=item.reference_answer,
        explanation=item.explanation,
        difficulty=item.difficulty,
        capability_keys=item.capability_keys,
        status="pending_review",
        prompt_template_id=prompt_template_id,
        prompt_template_name=prompt_template_name,
        prompt_contract_hash=prompt_contract_hash,
        prompt_contract_version=prompt_contract_version,
        prompt_rendered_hash=prompt_rendered_hash,
        model_config=model_config,
        raw_generation=_json_object(raw_payload),
        created_by=str(actor.user_id),
        updated_by=str(actor.user_id),
    )


def _draft_response(
    draft: SalesTrainerBusinessEtiquetteQuestionDraft,
    *,
    chapter_title: str | None = None,
) -> BusinessEtiquetteQuestionDraftResponse:
    return BusinessEtiquetteQuestionDraftResponse(
        draft_id=str(draft.draft_id),
        batch_id=str(draft.batch_id),
        training_pack_key=str(draft.training_pack_key),
        training_pack_revision_id=_optional_string(draft.training_pack_revision_id),
        training_pack_revision_no=draft.training_pack_revision_no,
        learning_content_id=_optional_string(draft.learning_content_id),
        chapter_id=_optional_string(draft.chapter_id),
        chapter_order=int(draft.chapter_order),
        chapter_title=chapter_title,
        source_excerpt=_optional_string(draft.source_excerpt),
        question_type=_literal_question_type(draft.question_type),
        title=str(draft.title),
        stem=str(draft.stem),
        options=[
            BusinessEtiquetteQuestionDraftOption.model_validate(item)
            for item in list(draft.options or [])
            if isinstance(item, dict)
        ],
        correct_answer=_optional_string(draft.correct_answer),
        correct_answers=[str(value) for value in list(draft.correct_answers or [])],
        reference_answer=_optional_string(draft.reference_answer),
        explanation=_optional_string(draft.explanation),
        difficulty=str(draft.difficulty),
        capability_keys=[str(value) for value in list(draft.capability_keys or [])],
        status=_literal_status(draft.status),
        prompt_template_id=str(draft.prompt_template_id),
        prompt_template_name=_optional_string(draft.prompt_template_name),
        prompt_contract_hash=str(draft.prompt_contract_hash),
        prompt_contract_version=str(draft.prompt_contract_version),
        prompt_rendered_hash=str(draft.prompt_rendered_hash),
        llm_model_config=dict(draft.model_config or {}),
        raw_generation=dict(draft.raw_generation or {}),
        review_notes=_optional_string(draft.review_notes),
        reviewed_by=_optional_string(draft.reviewed_by),
        reviewed_at=draft.reviewed_at,
        question_id=_optional_string(draft.question_id),
        created_by=_optional_string(draft.created_by),
        updated_by=_optional_string(draft.updated_by),
        created_at=draft.created_at,
        updated_at=draft.updated_at,
    )


def _require_pending_review(draft: SalesTrainerBusinessEtiquetteQuestionDraft) -> None:
    if draft.status != "pending_review":
        raise BusinessEtiquetteQuestionDraftServiceError(
            "[BUSINESS_ETIQUETTE_QUESTION_DRAFT_NOT_EDITABLE]",
            "只有待审核的商务礼仪题目草稿可以编辑、审批或拒绝。",
            409,
        )


def _validate_draft_shape(draft: SalesTrainerBusinessEtiquetteQuestionDraft) -> None:
    try:
        _GeneratedQuestionDraft.model_validate(
            {
                "question_type": draft.question_type,
                "title": draft.title,
                "stem": draft.stem,
                "options": list(draft.options or []),
                "correct_answer": draft.correct_answer,
                "correct_answers": list(draft.correct_answers or []),
                "reference_answer": draft.reference_answer,
                "explanation": draft.explanation,
                "difficulty": draft.difficulty,
                "capability_keys": list(draft.capability_keys or []),
                "source_excerpt": draft.source_excerpt,
            }
        )
    except ValidationError as exc:
        raise BusinessEtiquetteQuestionDraftServiceError(
            "[BUSINESS_ETIQUETTE_QUESTION_DRAFT_INVALID]",
            f"商务礼仪题目草稿结构非法：{exc.errors()[0]['msg']}。",
            422,
        ) from exc


def _question_payload_from_draft(
    draft: SalesTrainerBusinessEtiquetteQuestionDraft,
    *,
    category_id: str,
) -> SalesTrainerQuestionCreate:
    capability_keys = [str(value) for value in list(draft.capability_keys or [])]
    return SalesTrainerQuestionCreate(
        title=str(draft.title),
        stem=str(draft.stem),
        category_id=category_id,
        question_type=_literal_question_type(draft.question_type),
        difficulty=str(draft.difficulty),
        tags=_question_tags(draft, capability_keys),
        options=[
            SalesTrainerQuestionOption.model_validate(item)
            for item in list(draft.options or [])
            if isinstance(item, dict)
        ],
        correct_answer=_optional_string(draft.correct_answer),
        correct_answers=[str(value) for value in list(draft.correct_answers or [])],
        reference_answer=_optional_string(draft.reference_answer),
        explanation=_optional_string(draft.explanation),
        scoring_dimensions=capability_keys or ["business_etiquette"],
    )


def _question_tags(
    draft: SalesTrainerBusinessEtiquetteQuestionDraft,
    capability_keys: list[str],
) -> list[str]:
    tags = [
        "business_etiquette",
        f"chapter:{draft.chapter_order}",
        f"draft:{draft.draft_id}",
        f"batch:{draft.batch_id}",
    ]
    tags.extend(f"capability:{key}" for key in capability_keys)
    return tags


def _dump_options(value: Any) -> Any:
    if isinstance(value, list):
        return [
            item.model_dump() if hasattr(item, "model_dump") else item for item in value
        ]
    return value


def _is_question_generation_prompt_template(template: Any) -> bool:
    raw_business_purpose = getattr(template, "business_purpose", None)
    raw_business_purpose_value = getattr(raw_business_purpose, "value", None)
    if raw_business_purpose_value is not None:
        raw_business_purpose = raw_business_purpose_value
    business_purpose = str(raw_business_purpose or "").strip()
    if business_purpose:
        return business_purpose == PROMPT_BUSINESS_PURPOSE_BUSINESS_ETIQUETTE_QUESTION

    category = str(getattr(template, "category", "") or "").strip()
    if category not in QUESTION_DRAFT_PROMPT_CATEGORIES:
        return False
    searchable_text = " ".join(
        str(getattr(template, field, "") or "")
        for field in ("name", "prompt_type", "category", "template")
    ).lower()
    has_question_intent = any(
        keyword.lower() in searchable_text for keyword in QUESTION_DRAFT_PROMPT_KEYWORDS
    )
    has_excluded_intent = any(
        keyword.lower() in searchable_text
        for keyword in QUESTION_DRAFT_PROMPT_EXCLUDED_KEYWORDS
    )
    return has_question_intent and not has_excluded_intent


def _is_ai_coach_interaction_prompt_template(template: Any) -> bool:
    text = " ".join(
        str(getattr(template, field, "") or "")
        for field in ("name", "prompt_type", "category", "template")
    ).lower()
    if any(marker.lower() in text for marker in AI_COACH_INTERACTION_PROMPT_MARKERS):
        return True
    variables = {
        str(value).strip()
        for value in list(getattr(template, "variables", None) or [])
        if str(value).strip()
    }
    ai_coach_overlap = variables.intersection(AI_COACH_INTERACTION_VARIABLES)
    question_overlap = variables.intersection(QUESTION_DRAFT_REQUIRED_RUNTIME_VARIABLES)
    return len(ai_coach_overlap) >= 3 and not question_overlap


def _prompt_compile_failure_message(fallback: str | None) -> str:
    raw = str(fallback or "").strip()
    missing_prefix = "[PROMPT_CONTRACT_MISSING_VARIABLES:"
    if raw.startswith(missing_prefix) and raw.endswith("]"):
        missing = raw.removeprefix(missing_prefix).removesuffix("]")
        return (
            "商务礼仪题目生成 Prompt 编译失败：模板引用了当前题目生成服务不提供的变量"
            f"（{missing}）。请使用「商务礼仪题目草稿生成 v1」模板，或在提示词管理中按"
            "章节内容、能力点、题型和输出 schema 变量重建模板。"
        )
    if raw == "[PROMPT_CONTRACT_EMPTY_RENDERED_PROMPT]":
        return "商务礼仪题目生成 Prompt 编译失败：模板渲染后为空，请检查模板正文。"
    if raw == "[PROMPT_CONTRACT_BASE_URL_REQUIRED]":
        return "商务礼仪题目生成 Prompt 编译失败：当前 LLM 模型配置缺少 base_url，请先检查模型配置。"
    return "商务礼仪题目生成 Prompt 编译失败，请检查模板变量和模型配置。"


def _optional_string(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if text and text not in seen:
            result.append(text)
            seen.add(text)
    return result


def _excerpt(content: str, *, max_chars: int = 1200) -> str:
    text = " ".join(str(content or "").split())
    return text[:max_chars]


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _json_object(value: dict[str, Any] | list[Any]) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {"items": value}


def _literal_question_type(value: Any) -> BusinessEtiquetteQuestionDraftType:
    text = str(value)
    if text not in {"single_choice", "multiple_choice", "short_answer"}:
        raise BusinessEtiquetteQuestionDraftServiceError(
            "[BUSINESS_ETIQUETTE_QUESTION_DRAFT_INVALID]",
            "商务礼仪题目草稿题型非法。",
            422,
        )
    return text  # type: ignore[return-value]


def _literal_status(value: Any) -> BusinessEtiquetteQuestionDraftStatus:
    text = str(value)
    if text not in {"pending_review", "approved", "rejected", "converted"}:
        raise BusinessEtiquetteQuestionDraftServiceError(
            "[BUSINESS_ETIQUETTE_QUESTION_DRAFT_INVALID]",
            "商务礼仪题目草稿状态非法。",
            422,
        )
    return text  # type: ignore[return-value]
