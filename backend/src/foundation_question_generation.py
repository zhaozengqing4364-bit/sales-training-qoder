"""Safe admin composition for governed newcomer question generation."""

from __future__ import annotations

from typing import Never

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.errors import AIPlatformError
from ai_platform.models import AIModelRoutingProfileRecord, AIPromptRevisionRecord
from ai_platform.prompting import PublishedPromptRevisionSnapshot, StrictPromptCompiler
from ai_platform.routing import (
    PublishedModelRoutingProfileSnapshot,
    compute_model_routing_profile_content_hash,
)
from learning.contracts import LearningActor, QuestionGenerationRequest
from learning.errors import LearningGovernanceError
from learning.models import (
    LearningSourceAnchor,
    LearningSourceDocumentRevision,
    LearningUnitRevision,
)
from learning.question_generation import build_question_generation_context

QUESTION_GENERATION_PURPOSE = "newcomer_question_generation"
QUESTION_GENERATION_INPUT_SCHEMA = "question-generation-input-v1"
QUESTION_GENERATION_OUTPUT_SCHEMA = "question-generation-output-v1"
QUESTION_GENERATION_RUNTIME_CONSUMER = "learning.question_generation.v1"


class FoundationQuestionGenerationSelection(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source_revision_id: str = Field(min_length=1, max_length=160)
    learning_unit_revision_id: str = Field(min_length=1, max_length=160)
    requested_count: int = Field(ge=1, le=100)
    prompt_template_id: str = Field(min_length=1, max_length=160)
    prompt_revision_id: str = Field(min_length=1, max_length=160)
    model_routing_profile_id: str = Field(min_length=1, max_length=160)
    model_routing_revision_id: str = Field(min_length=1, max_length=160)


class FoundationQuestionGenerationPolicyService:
    """Resolve exact published policy revisions without exposing governed payloads."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_options(self, *, actor: LearningActor) -> dict[str, object]:
        self._require(actor)
        prompt_rows = list(
            (
                await self._session.execute(
                    select(AIPromptRevisionRecord)
                    .where(AIPromptRevisionRecord.status == "published")
                    .where(
                        AIPromptRevisionRecord.business_purpose
                        == QUESTION_GENERATION_PURPOSE
                    )
                    .where(
                        AIPromptRevisionRecord.input_schema_version
                        == QUESTION_GENERATION_INPUT_SCHEMA
                    )
                    .where(
                        AIPromptRevisionRecord.output_schema_version
                        == QUESTION_GENERATION_OUTPUT_SCHEMA
                    )
                    .order_by(
                        AIPromptRevisionRecord.revision_no.desc(),
                        AIPromptRevisionRecord.revision_id.asc(),
                    )
                )
            ).scalars()
        )
        route_rows = list(
            (
                await self._session.execute(
                    select(AIModelRoutingProfileRecord)
                    .where(AIModelRoutingProfileRecord.status == "published")
                    .order_by(
                        AIModelRoutingProfileRecord.revision_no.desc(),
                        AIModelRoutingProfileRecord.revision_id.asc(),
                    )
                )
            ).scalars()
        )
        prompts = [
            {
                "template_id": row.template_id,
                "revision_id": row.revision_id,
                "revision_no": row.revision_no,
                "label": f"题目生成模板 · 第 {row.revision_no} 版",
            }
            for row in prompt_rows
            if self._valid_prompt(row)
        ]
        routes = [
            {
                "profile_id": row.profile_id,
                "revision_id": row.revision_id,
                "revision_no": row.revision_no,
                "label": f"题目生成模型策略 · 第 {row.revision_no} 版",
            }
            for row in route_rows
            if self._valid_route(row)
        ]
        return {
            "prompt_options": prompts,
            "model_routing_options": routes,
            "ready": bool(prompts and routes),
            "empty_message": (
                None
                if prompts and routes
                else "尚未发布可用的题目生成模板或模型策略，请先由系统管理员完成治理配置。"
            ),
        }

    async def build_request(
        self,
        *,
        actor: LearningActor,
        selection: FoundationQuestionGenerationSelection,
    ) -> QuestionGenerationRequest:
        self._require(actor)
        prompt = await self._session.scalar(
            select(AIPromptRevisionRecord)
            .where(AIPromptRevisionRecord.template_id == selection.prompt_template_id)
            .where(AIPromptRevisionRecord.revision_id == selection.prompt_revision_id)
            .where(AIPromptRevisionRecord.status == "published")
            .limit(1)
        )
        route = await self._session.scalar(
            select(AIModelRoutingProfileRecord)
            .where(
                AIModelRoutingProfileRecord.profile_id
                == selection.model_routing_profile_id
            )
            .where(
                AIModelRoutingProfileRecord.revision_id
                == selection.model_routing_revision_id
            )
            .where(AIModelRoutingProfileRecord.status == "published")
            .limit(1)
        )
        if prompt is None or route is None:
            self._policy_unavailable()
        try:
            prompt_snapshot = self._prompt_snapshot(prompt)
            route_snapshot = PublishedModelRoutingProfileSnapshot.model_validate(
                route.snapshot_json,
                strict=False,
            )
        except ValidationError:
            self._policy_unavailable()
        if (
            route_snapshot.business_purpose != QUESTION_GENERATION_PURPOSE
            or route_snapshot.profile_id != route.profile_id
            or route_snapshot.revision_id != route.revision_id
            or route.content_hash
            != compute_model_routing_profile_content_hash(route.snapshot_json)
        ):
            self._policy_unavailable()

        source = await self._session.get(
            LearningSourceDocumentRevision, selection.source_revision_id
        )
        unit = await self._session.get(
            LearningUnitRevision, selection.learning_unit_revision_id
        )
        if (
            source is None
            or unit is None
            or source.organization_id != actor.organization_id
            or unit.organization_id != actor.organization_id
            or source.status != "published"
            or source.parse_status != "ready"
            or unit.status != "published"
        ):
            raise LearningGovernanceError(
                "[QUESTION_GENERATION_SOURCE_UNAVAILABLE]",
                "请选择同一组织内已随发布计划生效的材料和学习单元。",
                422,
            )
        anchor_ids = tuple(unit.source_anchor_ids_json)
        anchors = list(
            (
                await self._session.execute(
                    select(LearningSourceAnchor)
                    .where(
                        LearningSourceAnchor.organization_id
                        == actor.organization_id
                    )
                    .where(
                        LearningSourceAnchor.source_revision_id
                        == source.revision_id
                    )
                    .where(LearningSourceAnchor.anchor_id.in_(anchor_ids))
                )
            ).scalars()
        )
        if {item.anchor_id for item in anchors} != set(anchor_ids):
            raise LearningGovernanceError(
                "[QUESTION_GENERATION_SOURCE_MISMATCH]",
                "所选学习单元与材料来源不匹配，请重新选择。",
                422,
            )
        _, variables = build_question_generation_context(
            source_revision_id=source.revision_id,
            learning_unit_revision_id=unit.revision_id,
            requested_count=selection.requested_count,
            learning_unit_snapshot=dict(unit.snapshot_json),
            anchors=anchors,
        )
        try:
            compiled = StrictPromptCompiler().compile(
                revision=prompt_snapshot,
                variables=variables,
                runtime_consumer=QUESTION_GENERATION_RUNTIME_CONSUMER,
                model_routing_revision_id=route.revision_id,
            )
        except AIPlatformError as exc:
            raise LearningGovernanceError(
                "[QUESTION_GENERATION_POLICY_INVALID]",
                "题目生成治理配置未通过完整性检查，请联系系统管理员。",
                422,
            ) from exc
        return QuestionGenerationRequest(
            source_revision_id=source.revision_id,
            learning_unit_revision_id=unit.revision_id,
            requested_count=selection.requested_count,
            prompt_template_id=prompt.template_id,
            prompt_revision_id=prompt.revision_id,
            prompt_contract_hash=compiled.contract_hash,
            model_routing_profile_id=route.profile_id,
            model_routing_revision_id=route.revision_id,
            input_schema_version=QUESTION_GENERATION_INPUT_SCHEMA,
            output_schema_version=QUESTION_GENERATION_OUTPUT_SCHEMA,
        )

    @staticmethod
    def _prompt_snapshot(row: AIPromptRevisionRecord) -> PublishedPromptRevisionSnapshot:
        return PublishedPromptRevisionSnapshot(
            template_id=row.template_id,
            business_purpose=row.business_purpose,
            revision_id=row.revision_id,
            revision_no=row.revision_no,
            status="published",
            template=row.template_text,
            variables=tuple(row.variables_json),
            input_schema_version=row.input_schema_version,
            output_schema_version=row.output_schema_version,
            content_hash=row.content_hash,
        )

    @classmethod
    def _valid_prompt(cls, row: AIPromptRevisionRecord) -> bool:
        try:
            cls._prompt_snapshot(row)
        except ValidationError:
            return False
        return True

    @staticmethod
    def _valid_route(row: AIModelRoutingProfileRecord) -> bool:
        try:
            snapshot = PublishedModelRoutingProfileSnapshot.model_validate(
                row.snapshot_json,
                strict=False,
            )
        except ValidationError:
            return False
        return (
            snapshot.business_purpose == QUESTION_GENERATION_PURPOSE
            and snapshot.profile_id == row.profile_id
            and snapshot.revision_id == row.revision_id
            and row.content_hash
            == compute_model_routing_profile_content_hash(row.snapshot_json)
        )

    @staticmethod
    def _require(actor: LearningActor) -> None:
        if "learning.question.generate" not in actor.capabilities:
            raise LearningGovernanceError(
                "[LEARNING_PERMISSION_DENIED]",
                "没有发起题目生成任务的权限。",
                403,
            )

    @staticmethod
    def _policy_unavailable() -> Never:
        raise LearningGovernanceError(
            "[QUESTION_GENERATION_POLICY_UNAVAILABLE]",
            "所选题目生成模板或模型策略不可用，请刷新后重试。",
            422,
        )


__all__ = [
    "FoundationQuestionGenerationPolicyService",
    "FoundationQuestionGenerationSelection",
]
