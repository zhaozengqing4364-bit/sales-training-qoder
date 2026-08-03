"""Application-root adapters for foundation ReleasePlan orchestration."""

from __future__ import annotations

from typing import Any, Literal, cast

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_coach.contracts import CoachProfileSnapshot
from ai_coach.models import CoachProfileRevision
from ai_platform.models import AIModelRoutingProfileRecord, AIPromptRevisionRecord
from ai_platform.prompting import PublishedPromptRevisionSnapshot
from ai_platform.routing import (
    PublishedModelRoutingProfileSnapshot,
    compute_model_routing_profile_content_hash,
)
from audio_assessment.contracts import AudioScoringSchemeSnapshot
from audio_assessment.models import AudioActivityResourceRevision
from learning.application import LearningGovernanceService
from learning.contracts import LearningActor, LearningUnitRevisionDraft
from learning.errors import LearningGovernanceError
from learning.models import (
    LearningQuestion,
    LearningQuestionRevision,
    LearningQuiz,
    LearningQuizRevision,
    LearningSourceAnchor,
    LearningSourceDocument,
    LearningSourceDocumentRevision,
    LearningUnit,
    LearningUnitRevision,
)
from newcomer_training.errors import NewcomerTrainingError
from newcomer_training.ports import ReleaseDependency, ReleaseDependencyPort

_LEARNING_RELEASE_CAPABILITIES = frozenset(
    {
        "learning.source.manage",
        "learning.content.manage",
        "learning.question.manage",
        "learning.question.publish",
        "learning.quiz.manage",
    }
)


class FoundationReleaseDependencyAdapter(ReleaseDependencyPort):
    """Inspect/publish cross-domain dependencies without leaking them downstream."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def inspect(
        self,
        *,
        organization_id: str,
        activity_type: str,
        revision_id: str,
    ) -> ReleaseDependency:
        if activity_type == "lesson":
            return await self._inspect_learning_unit(
                organization_id=organization_id,
                revision_id=revision_id,
            )
        if activity_type == "quiz":
            return await self._inspect_quiz(
                organization_id=organization_id,
                revision_id=revision_id,
            )
        if activity_type == "ai_coach":
            return await self._inspect_coach_profile(
                organization_id=organization_id,
                revision_id=revision_id,
            )
        return await self._inspect_audio(
            organization_id=organization_id,
            activity_type=activity_type,
            revision_id=revision_id,
        )

    async def inspect_resource(
        self,
        *,
        organization_id: str,
        resource_type: str,
        revision_id: str,
    ) -> ReleaseDependency:
        if resource_type == "source_document":
            return await self._inspect_source(
                organization_id=organization_id, revision_id=revision_id
            )
        if resource_type == "question":
            return await self._inspect_question(
                organization_id=organization_id, revision_id=revision_id
            )
        if resource_type == "learning_unit":
            return await self._inspect_learning_unit(
                organization_id=organization_id, revision_id=revision_id
            )
        if resource_type == "quiz":
            return await self._inspect_quiz(
                organization_id=organization_id, revision_id=revision_id
            )
        if resource_type == "prompt":
            return await self._inspect_prompt(revision_id=revision_id)
        if resource_type == "model_routing":
            return await self._inspect_model_route(revision_id=revision_id)
        return self._missing(resource_type, revision_id, "发布依赖")

    async def publish(
        self,
        *,
        organization_id: str,
        actor_id: str,
        capability_set: frozenset[str],
        dependency: ReleaseDependency,
        idempotency_key: str,
        reason: str,
        trace_id: str | None,
    ) -> ReleaseDependency:
        if "newcomer.path.publish" not in capability_set:
            raise NewcomerTrainingError(
                "[NEWCOMER_PERMISSION_DENIED]", "没有执行发布的权限。", 403
            )
        resource_type = dependency.resource_type
        if resource_type not in {
            "source_document",
            "learning_unit",
            "question",
            "quiz",
        }:
            if dependency.publish_required:
                raise NewcomerTrainingError(
                    "[NEWCOMER_RELEASE_DEPENDENCY_UNPUBLISHABLE]",
                    "该引用必须先由其业务工作区完成审核发布。",
                    422,
                )
            return dependency
        if dependency.expected_resource_version is None:
            raise NewcomerTrainingError(
                "[NEWCOMER_RELEASE_TARGET_CHANGED]",
                "引用资源版本不完整，请重新预览。",
                409,
            )
        actor = LearningActor(
            organization_id=organization_id,
            actor_id=actor_id,
            capabilities=_LEARNING_RELEASE_CAPABILITIES,
            trace_id=trace_id,
        )
        try:
            result = await LearningGovernanceService(
                self._session
            ).publish_resource_working_revision(
                actor=actor,
                resource_type=cast(
                    Literal[
                        "source_document", "learning_unit", "question", "quiz"
                    ],
                    resource_type,
                ),
                resource_id=dependency.resource_id,
                expected_resource_version=dependency.expected_resource_version,
                idempotency_key=idempotency_key,
                reason=reason,
            )
        except LearningGovernanceError as exc:
            raise NewcomerTrainingError(
                exc.code, exc.message, exc.status_code, details=exc.details
            ) from exc
        if result.revision_id != dependency.revision_id:
            raise NewcomerTrainingError(
                "[NEWCOMER_RELEASE_TARGET_CHANGED]",
                "引用资源的工作修订已经变化，请重新预览。",
                409,
            )
        return ReleaseDependency(
            **{
                **dependency.model_dump(),
                "status": "published",
                "publish_required": False,
            }
        )

    async def _inspect_source(
        self, *, organization_id: str, revision_id: str
    ) -> ReleaseDependency:
        revision = await self._session.get(
            LearningSourceDocumentRevision, revision_id
        )
        if revision is None or revision.organization_id != organization_id:
            return self._missing("source_document", revision_id, "原始材料")
        document = await self._session.get(
            LearningSourceDocument, revision.document_id
        )
        issues: list[dict[str, str]] = []
        expected_version = None
        publish_required = revision.status == "working"
        if document is None or document.organization_id != organization_id:
            issues.append(self._issue("resource_not_found", "原始材料主体不存在。"))
        elif publish_required:
            expected_version = document.version
            if document.working_revision_id != revision.revision_id:
                issues.append(
                    self._issue("revision_not_current", "该修订已不是当前工作版本。")
                )
            else:
                issues.extend(
                    await self._learning_validation_issues(
                        organization_id=organization_id,
                        resource_type="source_document",
                        resource_id=document.document_id,
                    )
                )
        elif revision.status not in {"published", "archived"}:
            issues.append(self._issue("revision_unpublished", "原始材料修订未发布。"))
        return ReleaseDependency(
            resource_type="source_document",
            resource_id=revision.document_id,
            revision_id=revision.revision_id,
            label=(document.title if document is not None else "原始材料"),
            status=revision.status,
            content_hash=revision.content_hash,
            publish_required=publish_required,
            expected_resource_version=expected_version,
            issues=tuple(issues),
        )

    async def _inspect_question(
        self, *, organization_id: str, revision_id: str
    ) -> ReleaseDependency:
        revision = await self._session.get(LearningQuestionRevision, revision_id)
        if revision is None or revision.organization_id != organization_id:
            return self._missing("question", revision_id, "题目")
        question = await self._session.get(LearningQuestion, revision.question_id)
        issues: list[dict[str, str]] = []
        expected_version = None
        publish_required = revision.status in {"approved", "in_review", "draft"}
        if question is None or question.organization_id != organization_id:
            issues.append(self._issue("resource_not_found", "题目主体不存在。"))
        elif publish_required:
            expected_version = question.version
            if question.working_revision_id != revision.revision_id:
                issues.append(
                    self._issue("revision_not_current", "该修订已不是当前工作版本。")
                )
            else:
                issues.extend(
                    item
                    for item in await self._learning_validation_issues(
                        organization_id=organization_id,
                        resource_type="question",
                        resource_id=question.question_id,
                    )
                    if item.get("code") != "source_revision_unpublished"
                )
        elif revision.status not in {"published", "archived"}:
            issues.append(self._issue("revision_unpublished", "题目修订尚未批准。"))
        dependencies: list[dict[str, str]] = []
        anchors = list(
            (
                await self._session.execute(
                    select(LearningSourceAnchor).where(
                        LearningSourceAnchor.anchor_id.in_(
                            revision.source_anchor_ids_json
                        )
                    )
                )
            ).scalars()
        )
        by_id = {anchor.anchor_id: anchor for anchor in anchors}
        for anchor_id in revision.source_anchor_ids_json:
            anchor = by_id.get(anchor_id)
            if anchor is None or anchor.organization_id != organization_id:
                issues.append(self._issue("source_anchor_missing", "题目来源定位已失效。"))
                continue
            dependencies.append(
                {
                    "resource_type": "source_document",
                    "revision_id": anchor.source_revision_id,
                    "status": "referenced",
                }
            )
        return ReleaseDependency(
            resource_type="question",
            resource_id=revision.question_id,
            revision_id=revision.revision_id,
            label="正式题目",
            status=revision.status,
            content_hash=revision.content_hash,
            publish_required=publish_required,
            expected_resource_version=expected_version,
            dependencies=tuple(dependencies),
            issues=tuple(issues),
        )

    async def _inspect_prompt(self, *, revision_id: str) -> ReleaseDependency:
        row = await self._session.scalar(
            select(AIPromptRevisionRecord)
            .where(AIPromptRevisionRecord.revision_id == revision_id)
            .limit(1)
        )
        issues: list[dict[str, str]] = []
        if row is None:
            return self._missing("prompt", revision_id, "提示模板")
        if row.status != "published":
            issues.append(self._issue("prompt_revision_unpublished", "提示模板修订未发布。"))
        return ReleaseDependency(
            resource_type="prompt",
            resource_id=row.template_id,
            revision_id=row.revision_id,
            label=row.business_purpose,
            status=row.status,
            content_hash=row.content_hash,
            issues=tuple(issues),
        )

    async def _inspect_model_route(self, *, revision_id: str) -> ReleaseDependency:
        row = await self._session.scalar(
            select(AIModelRoutingProfileRecord)
            .where(AIModelRoutingProfileRecord.revision_id == revision_id)
            .limit(1)
        )
        issues: list[dict[str, str]] = []
        if row is None:
            return self._missing("model_routing", revision_id, "模型策略")
        if row.status != "published":
            issues.append(self._issue("model_route_unpublished", "模型策略修订未发布。"))
        elif row.content_hash != compute_model_routing_profile_content_hash(
            row.snapshot_json
        ):
            issues.append(
                self._issue("model_route_integrity_invalid", "模型策略完整性校验失败。")
            )
        return ReleaseDependency(
            resource_type="model_routing",
            resource_id=row.profile_id,
            revision_id=row.revision_id,
            label=str(row.snapshot_json.get("business_purpose") or "模型策略"),
            status=row.status,
            content_hash=row.content_hash,
            issues=tuple(issues),
        )

    async def _inspect_learning_unit(
        self, *, organization_id: str, revision_id: str
    ) -> ReleaseDependency:
        revision = await self._session.get(LearningUnitRevision, revision_id)
        if revision is None or revision.organization_id != organization_id:
            return self._missing("learning_unit", revision_id, "学习内容")
        unit = await self._session.get(LearningUnit, revision.unit_id)
        issues: list[dict[str, str]] = []
        publish_required = revision.status == "working"
        expected_version = None
        if unit is None or unit.organization_id != organization_id:
            issues.append(self._issue("resource_not_found", "学习内容主体不存在。"))
        elif revision.status == "working":
            expected_version = unit.version
            if unit.working_revision_id != revision.revision_id:
                issues.append(
                    self._issue("revision_not_current", "该修订已不是当前工作版本。")
                )
            else:
                issues.extend(
                    item
                    for item in await self._learning_validation_issues(
                        organization_id=organization_id,
                        resource_type="learning_unit",
                        resource_id=unit.unit_id,
                    )
                    if item.get("code") != "source_revision_unpublished"
                )
        elif revision.status != "published":
            issues.append(self._issue("revision_unpublished", "学习内容修订未发布。"))
        dependencies: list[dict[str, str]] = []
        try:
            unit_contract = LearningUnitRevisionDraft.model_validate(
                revision.snapshot_json
            )
        except ValidationError:
            unit_contract = None
            issues.append(
                self._issue("learning_unit_schema_invalid", "学习内容结构不完整。")
            )
        anchors = list(
            (
                await self._session.execute(
                    select(LearningSourceAnchor).where(
                        LearningSourceAnchor.anchor_id.in_(
                            revision.source_anchor_ids_json
                        )
                    )
                )
            ).scalars()
        )
        anchors_by_id = {item.anchor_id: item for item in anchors}
        seen_source_revision_ids: set[str] = set()
        for anchor_id in revision.source_anchor_ids_json:
            anchor = anchors_by_id.get(anchor_id)
            if anchor is None or anchor.organization_id != organization_id:
                issues.append(self._issue("source_anchor_missing", "来源定位已失效。"))
                continue
            source = await self._session.get(
                LearningSourceDocumentRevision, anchor.source_revision_id
            )
            dependencies.append(
                {
                    "resource_type": "source_document",
                    "revision_id": anchor.source_revision_id,
                    "status": source.status if source is not None else "missing",
                }
            )
            seen_source_revision_ids.add(anchor.source_revision_id)
            if source is None or source.organization_id != organization_id:
                issues.append(
                    self._issue("source_revision_missing", "来源修订不存在或越权。")
                )
        if unit_contract is not None:
            for source_revision_id, anchor_id in unit_contract.exact_source_references():
                anchor = anchors_by_id.get(anchor_id)
                if anchor is None or anchor.source_revision_id != source_revision_id:
                    issues.append(
                        self._issue(
                            "exact_source_reference_invalid",
                            "内容块的来源修订与来源定位不一致。",
                        )
                    )
                if source_revision_id in seen_source_revision_ids:
                    continue
                source = await self._session.get(
                    LearningSourceDocumentRevision, source_revision_id
                )
                dependencies.append(
                    {
                        "resource_type": "source_document",
                        "revision_id": source_revision_id,
                        "status": source.status if source is not None else "missing",
                    }
                )
                seen_source_revision_ids.add(source_revision_id)
                if source is None or source.organization_id != organization_id:
                    issues.append(
                        self._issue(
                            "source_revision_missing", "来源修订不存在或越权。"
                        )
                    )
        return ReleaseDependency(
            resource_type="learning_unit",
            resource_id=revision.unit_id,
            revision_id=revision.revision_id,
            label=(unit.title if unit is not None else "学习内容"),
            status=revision.status,
            content_hash=revision.content_hash,
            publish_required=publish_required,
            expected_resource_version=expected_version,
            dependencies=tuple(dependencies),
            issues=tuple(issues),
        )

    async def _inspect_quiz(
        self, *, organization_id: str, revision_id: str
    ) -> ReleaseDependency:
        revision = await self._session.get(LearningQuizRevision, revision_id)
        if revision is None or revision.organization_id != organization_id:
            return self._missing("quiz", revision_id, "测验")
        quiz = await self._session.get(LearningQuiz, revision.quiz_id)
        issues: list[dict[str, str]] = []
        publish_required = revision.status == "working"
        expected_version = None
        if quiz is None or quiz.organization_id != organization_id:
            issues.append(self._issue("resource_not_found", "测验主体不存在。"))
        elif revision.status == "working":
            expected_version = quiz.version
            if quiz.working_revision_id != revision.revision_id:
                issues.append(
                    self._issue("revision_not_current", "该修订已不是当前工作版本。")
                )
            else:
                issues.extend(
                    item
                    for item in await self._learning_validation_issues(
                        organization_id=organization_id,
                        resource_type="quiz",
                        resource_id=quiz.quiz_id,
                    )
                    if item.get("code") != "quiz_question_revision_unpublished"
                )
        elif revision.status != "published":
            issues.append(self._issue("revision_unpublished", "测验修订未发布。"))
        dependencies: list[dict[str, str]] = []
        if revision.question_revision_ids_json:
            questions = list(
                (
                    await self._session.execute(
                        select(LearningQuestionRevision).where(
                            LearningQuestionRevision.revision_id.in_(
                                revision.question_revision_ids_json
                            )
                        )
                    )
                ).scalars()
            )
            by_id = {item.revision_id: item for item in questions}
            for question_revision_id in revision.question_revision_ids_json:
                question = by_id.get(question_revision_id)
                status = question.status if question is not None else "missing"
                dependencies.append(
                    {
                        "resource_type": "question",
                        "revision_id": question_revision_id,
                        "status": status,
                    }
                )
                if question is None or question.organization_id != organization_id:
                    issues.append(
                        self._issue(
                            "question_revision_missing",
                            "测验引用的题目不存在或越权。",
                        )
                    )
        return ReleaseDependency(
            resource_type="quiz",
            resource_id=revision.quiz_id,
            revision_id=revision.revision_id,
            label=(quiz.title if quiz is not None else "测验"),
            status=revision.status,
            content_hash=revision.content_hash,
            publish_required=publish_required,
            expected_resource_version=expected_version,
            dependencies=tuple(dependencies),
            issues=tuple(self._dedupe_issues(issues)),
        )

    async def _inspect_audio(
        self,
        *,
        organization_id: str,
        activity_type: str,
        revision_id: str,
    ) -> ReleaseDependency:
        row = await self._session.get(AudioActivityResourceRevision, revision_id)
        if row is None or row.organization_id != organization_id:
            return self._missing("audio_resource", revision_id, "录音评测资源")
        expected = {
            "audio_assessment": {"audio_material", "scoring_scheme"},
            "assignment": {"scenario", "scoring_scheme"},
        }.get(activity_type, set())
        issues: list[dict[str, str]] = []
        if row.resource_type not in expected:
            issues.append(self._issue("resource_type_mismatch", "录音资源类型不匹配。"))
        if row.status != "published":
            issues.append(self._issue("revision_unpublished", "录音资源修订尚未发布。"))
        dependencies: list[dict[str, str]] = []
        if row.resource_type == "scoring_scheme":
            try:
                snapshot = AudioScoringSchemeSnapshot.model_validate(row.snapshot_json)
            except ValidationError:
                issues.append(
                    self._issue("scorecard_contract_invalid", "评分规则结构不完整。")
                )
            else:
                for ai_contract in (snapshot.asr, snapshot.scoring):
                    dependencies.extend(self._ai_dependency_refs(ai_contract))
                    issues.extend(await self._validate_ai_contract(ai_contract))
                for knowledge_revision_id in snapshot.allowed_knowledge:
                    dependencies.append(
                        {
                            "resource_type": "learning_unit",
                            "revision_id": knowledge_revision_id,
                            "status": "referenced",
                        }
                    )
                    knowledge = await self._session.get(
                        LearningUnitRevision, knowledge_revision_id
                    )
                    if (
                        knowledge is None
                        or knowledge.organization_id != organization_id
                        or knowledge.status not in {"published", "archived"}
                    ):
                        issues.append(
                            self._issue(
                                "knowledge_revision_unpublished",
                                "评分规则引用的知识修订不可用。",
                            )
                        )
        type_name = {
            "audio_material": "audio_material",
            "scoring_scheme": "audio_scoring_scheme",
            "scenario": "audio_scenario",
        }[row.resource_type]
        return ReleaseDependency(
            resource_type=type_name,
            resource_id=f"{row.resource_type}:{row.stable_key}",
            revision_id=row.revision_id,
            label=row.title,
            status=row.status,
            content_hash=row.content_hash,
            dependencies=tuple(dependencies),
            issues=tuple(self._dedupe_issues(issues)),
        )

    async def _inspect_coach_profile(
        self, *, organization_id: str, revision_id: str
    ) -> ReleaseDependency:
        row = await self._session.get(CoachProfileRevision, revision_id)
        if row is None or row.organization_id != organization_id:
            return self._missing("coach_profile", revision_id, "教练配置")
        issues: list[dict[str, str]] = []
        dependencies: list[dict[str, str]] = []
        if row.status != "published":
            issues.append(self._issue("revision_unpublished", "教练配置尚未发布。"))
        try:
            profile = CoachProfileSnapshot.model_validate(row.snapshot_json)
        except ValidationError:
            issues.append(
                self._issue("coach_profile_contract_invalid", "教练配置结构不完整。")
            )
        else:
            for contract in (
                profile.ai.card_generation,
                profile.ai.answer_evaluation,
                profile.ai.feedback_explanation,
            ):
                dependencies.extend(self._ai_dependency_refs(contract))
                issues.extend(await self._validate_ai_contract(contract))
            for knowledge_revision_id in profile.allowed_knowledge_scope:
                dependencies.append(
                    {
                        "resource_type": "learning_unit",
                        "revision_id": knowledge_revision_id,
                        "status": "referenced",
                    }
                )
                knowledge = await self._session.get(
                    LearningUnitRevision, knowledge_revision_id
                )
                if (
                    knowledge is None
                    or knowledge.organization_id != organization_id
                    or knowledge.status not in {"published", "archived"}
                ):
                    issues.append(
                        self._issue(
                            "knowledge_revision_unpublished",
                            "教练配置引用的学习内容不可用。",
                        )
                    )
        return ReleaseDependency(
            resource_type="coach_profile",
            resource_id=f"coach_profile:{row.stable_key}",
            revision_id=row.revision_id,
            label=str(row.snapshot_json.get("title") or "教练配置"),
            status=row.status,
            content_hash=row.content_hash,
            dependencies=tuple(dependencies),
            issues=tuple(self._dedupe_issues(issues)),
        )

    async def _learning_validation_issues(
        self,
        *,
        organization_id: str,
        resource_type: str,
        resource_id: str,
    ) -> list[dict[str, str]]:
        actor = LearningActor(
            organization_id=organization_id,
            actor_id="foundation-release-validator",
            capabilities=_LEARNING_RELEASE_CAPABILITIES,
        )
        try:
            result = await LearningGovernanceService(
                self._session
            ).validate_resource_working_revision(
                actor=actor,
                resource_type=cast(
                    Literal[
                        "source_document", "learning_unit", "question", "quiz"
                    ],
                    resource_type,
                ),
                resource_id=resource_id,
            )
        except LearningGovernanceError as exc:
            return [self._issue(exc.code.strip("[]").lower(), exc.message)]
        return [
            self._issue(item.code, item.message)
            for item in result.issues
        ]

    async def _validate_ai_contract(self, contract: Any) -> list[dict[str, str]]:
        issues: list[dict[str, str]] = []
        prompt_revision_id = getattr(contract, "prompt_revision_id", None)
        prompt_template_id = getattr(contract, "prompt_template_id", None)
        if prompt_revision_id:
            prompt = await self._session.scalar(
                select(AIPromptRevisionRecord)
                .where(AIPromptRevisionRecord.revision_id == prompt_revision_id)
                .where(AIPromptRevisionRecord.template_id == prompt_template_id)
                .limit(1)
            )
            if prompt is None or prompt.status != "published":
                issues.append(
                    self._issue("prompt_revision_unpublished", "引用的提示模板修订未发布。")
                )
            else:
                try:
                    PublishedPromptRevisionSnapshot(
                        template_id=prompt.template_id,
                        business_purpose=prompt.business_purpose,
                        revision_id=prompt.revision_id,
                        revision_no=prompt.revision_no,
                        status="published",
                        template=prompt.template_text,
                        variables=tuple(prompt.variables_json),
                        input_schema_version=prompt.input_schema_version,
                        output_schema_version=prompt.output_schema_version,
                        content_hash=prompt.content_hash,
                    )
                except ValidationError:
                    issues.append(
                        self._issue("prompt_integrity_invalid", "提示模板完整性校验失败。")
                    )
        route = await self._session.scalar(
            select(AIModelRoutingProfileRecord)
            .where(
                AIModelRoutingProfileRecord.revision_id
                == contract.model_routing_revision_id
            )
            .where(
                AIModelRoutingProfileRecord.profile_id
                == contract.model_routing_profile_id
            )
            .limit(1)
        )
        if route is None or route.status != "published":
            issues.append(
                self._issue("model_route_unpublished", "引用的模型策略修订未发布。")
            )
        else:
            try:
                snapshot = PublishedModelRoutingProfileSnapshot.model_validate(
                    route.snapshot_json, strict=False
                )
                if (
                    snapshot.revision_id != route.revision_id
                    or snapshot.profile_id != route.profile_id
                    or route.content_hash
                    != compute_model_routing_profile_content_hash(route.snapshot_json)
                ):
                    raise ValueError("routing integrity mismatch")
            except (ValidationError, ValueError):
                issues.append(
                    self._issue("model_route_integrity_invalid", "模型策略完整性校验失败。")
                )
        return issues

    @staticmethod
    def _ai_dependency_refs(contract: Any) -> list[dict[str, str]]:
        refs = [
            {
                "resource_type": "model_routing",
                "revision_id": str(contract.model_routing_revision_id),
                "status": "referenced",
            }
        ]
        if getattr(contract, "prompt_revision_id", None):
            refs.append(
                {
                    "resource_type": "prompt",
                    "revision_id": str(contract.prompt_revision_id),
                    "status": "referenced",
                }
            )
        return refs

    @staticmethod
    def _missing(
        resource_type: str, revision_id: str, label: str
    ) -> ReleaseDependency:
        return ReleaseDependency(
            resource_type=resource_type,
            resource_id=f"missing:{revision_id}",
            revision_id=revision_id,
            label=label,
            status="missing",
            content_hash="missing",
            issues=(
                {
                    "code": "resource_not_found",
                    "message": f"{label}不存在或不在当前组织范围内。",
                },
            ),
        )

    @staticmethod
    def _issue(code: str, message: str) -> dict[str, str]:
        return {"code": code, "message": message}

    @staticmethod
    def _dedupe_issues(items: list[dict[str, str]]) -> list[dict[str, str]]:
        return list(
            {
                (item.get("code", ""), item.get("message", "")): item
                for item in items
            }.values()
        )


__all__ = ["FoundationReleaseDependencyAdapter"]
