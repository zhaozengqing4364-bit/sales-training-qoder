from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from curriculum_practice.models import QuestionItem
from sales_trainer.models import (
    SalesTrainerAssetRevision,
    SalesTrainerBusinessEtiquetteQuizAttempt,
)
from sales_trainer.schemas import (
    BusinessEtiquetteCapabilityConfig,
    BusinessEtiquetteCapabilityScoreResponse,
    BusinessEtiquetteChapterCapabilityBinding,
    BusinessEtiquetteQuizAnswerResultResponse,
    BusinessEtiquetteQuizQuestionResponse,
    BusinessEtiquetteTrainingUnitConfig,
    BusinessEtiquetteUnitQuizAttemptCreate,
    BusinessEtiquetteUnitQuizAttemptListResponse,
    BusinessEtiquetteUnitQuizAttemptResponse,
    BusinessEtiquetteUnitQuizResponse,
    NewcomerPathConfigPayload,
)
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionService,
)
from sales_trainer.services.business_etiquette_capability_service import (
    CAPABILITY_SNAPSHOT_KEY,
)
from sales_trainer.services.business_etiquette_import_service import (
    BUSINESS_ETIQUETTE_RESOURCE_TYPE,
    DEFAULT_BUSINESS_ETIQUETTE_TRAINING_PACK_KEY,
)
from sales_trainer.services.business_etiquette_learning_service import (
    BUSINESS_SKILLS_MODULE_KEY,
)
from sales_trainer.services.operation_log_service import OperationLogService
from sales_trainer.services.path_config_service import SalesTrainerPathConfigService
from sales_trainer.services.question_bank.adapter import QuestionBankAdapter
from sales_trainer.services.question_bank.contracts import SALES_TRAINER_QUESTION_SCOPE
from sales_trainer.services.short_answer_scoring_service import (
    ShortAnswerScoringService,
)


class BusinessEtiquetteQuizServiceError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class BusinessEtiquetteQuizService:
    def __init__(
        self,
        db: AsyncSession,
        *,
        short_answer_scoring_service: ShortAnswerScoringService | None = None,
    ) -> None:
        self._db = db
        self._asset_revisions = SalesTrainerAssetRevisionService(db)
        self._question_adapter = QuestionBankAdapter(db)
        self._logs = OperationLogService(db)
        self._short_answer_scoring = (
            short_answer_scoring_service or ShortAnswerScoringService()
        )

    async def get_unit_quiz(
        self,
        unit_key: str,
        *,
        user_id: str,
    ) -> BusinessEtiquetteUnitQuizResponse:
        context = await self._quiz_context(unit_key)
        await self._enforce_attempt_limits(context.unit_config, unit_key, user_id)
        questions = await self._select_questions(context)
        return _quiz_response(context, questions)

    async def preview_unit_quiz(
        self,
        unit_key: str,
    ) -> BusinessEtiquetteUnitQuizResponse:
        context = await self._quiz_context(unit_key)
        questions = await self._select_questions(context)
        return _quiz_response(context, questions)

    async def submit_attempt(
        self,
        unit_key: str,
        payload: BusinessEtiquetteUnitQuizAttemptCreate,
        *,
        actor: User,
    ) -> BusinessEtiquetteUnitQuizAttemptResponse:
        context = await self._quiz_context(unit_key)
        await self._enforce_attempt_limits(
            context.unit_config,
            unit_key,
            str(actor.user_id),
        )
        questions = await self._select_questions(context)
        question_by_id = {str(question.question_id): question for question in questions}
        answer_map = {
            answer.question_id: answer.answer_payload for answer in payload.answers
        }
        unknown_ids = sorted(set(answer_map) - set(question_by_id))
        if unknown_ids:
            raise BusinessEtiquetteQuizServiceError(
                "[BUSINESS_ETIQUETTE_QUIZ_QUESTION_NOT_IN_UNIT]",
                "提交答案包含未出现在当前小单元测验中的题目。",
                422,
            )

        answers_snapshot: list[dict[str, Any]] = []
        capability_points: dict[str, list[tuple[float, float]]] = defaultdict(list)
        total_score = 0.0
        max_score = 0.0
        has_unscored = False
        for order_index, question in enumerate(questions, start=1):
            answer_payload = answer_map.get(str(question.question_id))
            points = 10
            is_correct, score = self._question_adapter.grade(
                question,
                answer_payload=answer_payload,
                points=points,
            )
            question_type = self._question_adapter.resolve_type(question)
            scoring_source: str | None = (
                "rule_answer_key"
                if question_type != "short_answer"
                else "ai_llm_pending"
            )
            scoring_provider: str | None = None
            scoring_model: str | None = None
            scoring_latency_ms: int | None = None
            answer_analysis = _question_analysis(
                question,
                is_correct=is_correct,
            )
            if score is None and question_type == "short_answer":
                scoring_result = await self._short_answer_scoring.score(
                    question,
                    answer_text=str(answer_payload or ""),
                )
                if scoring_result.is_success and scoring_result.value is not None:
                    outcome = scoring_result.value
                    score = points * float(outcome.score) / 100
                    is_correct = outcome.passed
                    answer_analysis = outcome.feedback
                    scoring_source = outcome.scoring_source
                    scoring_provider = outcome.scoring_provider
                    scoring_model = outcome.scoring_model
                    scoring_latency_ms = outcome.scoring_latency_ms
                else:
                    scoring_source = "ai_llm_failed"
            if score is None:
                has_unscored = True
            else:
                total_score += float(score)
                max_score += float(points)
            capability_keys = _question_capability_keys(
                question, context.capability_map
            )
            for capability_key in capability_keys:
                capability_points[capability_key].append(
                    (float(score or 0), float(points))
                )
            answers_snapshot.append(
                _answer_result_payload(
                    question,
                    answer_payload=answer_payload,
                    order_index=order_index,
                    points=points,
                    score=score,
                    is_correct=is_correct,
                    capability_keys=capability_keys,
                    analysis=answer_analysis,
                    scoring_source=scoring_source,
                    scoring_provider=scoring_provider,
                    scoring_model=scoring_model,
                    scoring_latency_ms=scoring_latency_ms,
                )
            )

        capability_scores = _capability_scores(
            context=context,
            capability_points=capability_points,
        )
        weak_capability_keys = [
            item.capability_key for item in capability_scores if item.mastered is False
        ]
        pass_threshold = context.unit_config.quiz_pass_threshold
        passed = None
        if not has_unscored:
            if pass_threshold is not None and max_score > 0:
                passed = (total_score / max_score) * 100 >= pass_threshold
            else:
                passed = not weak_capability_keys

        attempt = SalesTrainerBusinessEtiquetteQuizAttempt(
            training_pack_key=context.training_pack_key,
            learning_unit_key=context.unit_config.unit_key,
            learning_unit_title=context.unit_config.title,
            user_id=str(actor.user_id),
            path_revision_id=context.path_revision_id,
            path_revision_no=context.path_revision_no,
            training_pack_revision_id=str(context.training_pack_revision.revision_id),
            training_pack_revision_no=context.training_pack_revision.revision_no,
            capability_snapshot={
                "capabilities": [
                    capability.model_dump(mode="json")
                    for capability in context.capabilities
                ],
                "chapter_bindings": [
                    binding.model_dump(mode="json")
                    for binding in context.chapter_bindings
                ],
            },
            question_snapshots=[
                _question_snapshot(question, order_index=index)
                for index, question in enumerate(questions, start=1)
            ],
            answers_snapshot=answers_snapshot,
            capability_scores=[
                item.model_dump(mode="json") for item in capability_scores
            ],
            weak_capability_keys=weak_capability_keys,
            recommended_chapter_orders=context.unit_config.source_chapter_orders,
            total_score=Decimal(str(total_score)) if not has_unscored else None,
            max_score=Decimal(str(max_score)) if not has_unscored else None,
            passed=passed,
            status="submitted" if has_unscored else "scored",
        )
        self._db.add(attempt)
        await self._logs.record(
            actor=actor,
            action="business_etiquette_unit_quiz.submitted",
            target_type="business_etiquette_unit_quiz_attempt",
            target_id=attempt.attempt_id,
            metadata={
                "learning_unit_key": context.unit_config.unit_key,
                "training_pack_key": context.training_pack_key,
                "question_count": len(questions),
                "weak_capability_keys": weak_capability_keys,
                "passed": passed,
            },
        )
        await self._db.commit()
        await self._db.refresh(attempt)
        return await self._attempt_response(attempt)

    async def list_attempts(
        self,
        *,
        user_id: str | None = None,
        learning_unit_key: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> BusinessEtiquetteUnitQuizAttemptListResponse:
        stmt = select(SalesTrainerBusinessEtiquetteQuizAttempt)
        count_stmt = select(func.count()).select_from(
            SalesTrainerBusinessEtiquetteQuizAttempt
        )
        if user_id:
            stmt = stmt.where(
                SalesTrainerBusinessEtiquetteQuizAttempt.user_id == user_id
            )
            count_stmt = count_stmt.where(
                SalesTrainerBusinessEtiquetteQuizAttempt.user_id == user_id
            )
        if learning_unit_key:
            stmt = stmt.where(
                SalesTrainerBusinessEtiquetteQuizAttempt.learning_unit_key
                == learning_unit_key
            )
            count_stmt = count_stmt.where(
                SalesTrainerBusinessEtiquetteQuizAttempt.learning_unit_key
                == learning_unit_key
            )
        result = await self._db.execute(
            stmt.order_by(SalesTrainerBusinessEtiquetteQuizAttempt.submitted_at.desc())
            .offset(offset)
            .limit(limit)
        )
        total = await self._db.scalar(count_stmt)
        attempts = list(result.scalars().all())
        return BusinessEtiquetteUnitQuizAttemptListResponse(
            items=[await self._attempt_response(attempt) for attempt in attempts],
            total=int(total or 0),
        )

    async def _quiz_context(self, unit_key: str) -> _QuizContext:
        path_response = await SalesTrainerPathConfigService(self._db).get_config()
        path_payload = NewcomerPathConfigPayload.model_validate(path_response["path"])
        module = next(
            (
                item
                for item in path_payload.modules
                if item.module_key == BUSINESS_SKILLS_MODULE_KEY
            ),
            None,
        )
        if module is None or not module.enabled:
            raise BusinessEtiquetteQuizServiceError(
                "[BUSINESS_ETIQUETTE_MODULE_CONFIG_MISSING]",
                "商务礼仪学习模块配置不存在或未启用。",
                404,
            )
        unit_config = next(
            (item for item in module.learning_units if item.unit_key == unit_key),
            None,
        )
        if unit_config is None or not unit_config.enabled:
            raise BusinessEtiquetteQuizServiceError(
                "[BUSINESS_ETIQUETTE_UNIT_CONFIG_MISSING]",
                "商务礼仪小单元配置不存在或未启用。",
                404,
            )
        if not unit_config.require_quiz:
            raise BusinessEtiquetteQuizServiceError(
                "[BUSINESS_ETIQUETTE_UNIT_QUIZ_DISABLED]",
                "该商务礼仪小单元未要求小测。",
                409,
            )
        training_pack_revision = await self._asset_revisions.active_revision(
            resource_type=BUSINESS_ETIQUETTE_RESOURCE_TYPE,
            logical_id=DEFAULT_BUSINESS_ETIQUETTE_TRAINING_PACK_KEY,
        )
        if training_pack_revision is None:
            raise BusinessEtiquetteQuizServiceError(
                "[BUSINESS_ETIQUETTE_TRAINING_PACK_NOT_PUBLISHED]",
                "商务礼仪训练包尚未发布，无法开始小测。",
                409,
            )
        capabilities, chapter_bindings = _capability_snapshot_from_revision(
            training_pack_revision
        )
        capability_map = {
            capability.capability_key: capability
            for capability in capabilities
            if capability.status != "archived"
        }
        missing_keys = sorted(set(unit_config.capability_keys) - set(capability_map))
        if missing_keys:
            raise BusinessEtiquetteQuizServiceError(
                "[BUSINESS_ETIQUETTE_UNIT_CAPABILITY_INVALID]",
                f"小单元绑定了不存在或已归档的能力点：{', '.join(missing_keys)}。",
                409,
            )
        return _QuizContext(
            training_pack_key=DEFAULT_BUSINESS_ETIQUETTE_TRAINING_PACK_KEY,
            unit_config=unit_config,
            path_revision_id=path_response["active_revision_id"],
            path_revision_no=path_response["active_revision_no"],
            training_pack_revision=training_pack_revision,
            capabilities=[capability_map[key] for key in unit_config.capability_keys],
            capability_map=capability_map,
            chapter_bindings=chapter_bindings,
        )

    async def _select_questions(self, context: _QuizContext) -> list[QuestionItem]:
        result = await self._db.execute(
            select(QuestionItem)
            .where(
                QuestionItem.status == "published",
                QuestionItem.usage_scope == SALES_TRAINER_QUESTION_SCOPE,
                QuestionItem.safety_flagged.is_(False),
            )
            .order_by(QuestionItem.updated_at.desc())
        )
        unit_capability_keys = set(context.unit_config.capability_keys)
        candidates = [
            question
            for question in result.scalars().all()
            if unit_capability_keys
            & set(_question_capability_keys(question, context.capability_map))
        ]
        if not candidates:
            raise BusinessEtiquetteQuizServiceError(
                "[BUSINESS_ETIQUETTE_UNIT_QUIZ_QUESTIONS_MISSING]",
                "该小单元没有已发布且绑定能力点的商务礼仪题目。",
                409,
            )
        return _select_weighted_questions(
            candidates,
            question_count=context.unit_config.quiz_question_count,
            question_type_weights=context.unit_config.quiz_question_type_weights,
        )

    async def _enforce_attempt_limits(
        self,
        unit_config: BusinessEtiquetteTrainingUnitConfig,
        unit_key: str,
        user_id: str,
    ) -> None:
        total = await self._db.scalar(
            select(func.count())
            .select_from(SalesTrainerBusinessEtiquetteQuizAttempt)
            .where(
                SalesTrainerBusinessEtiquetteQuizAttempt.learning_unit_key == unit_key,
                SalesTrainerBusinessEtiquetteQuizAttempt.user_id == user_id,
            )
        )
        attempt_count = int(total or 0)
        if not unit_config.quiz_allow_retake and attempt_count > 0:
            raise BusinessEtiquetteQuizServiceError(
                "[BUSINESS_ETIQUETTE_UNIT_QUIZ_RETAKE_NOT_ALLOWED]",
                "该商务礼仪小单元不允许重复小测。",
                409,
            )
        if (
            unit_config.quiz_max_attempts is not None
            and attempt_count >= unit_config.quiz_max_attempts
        ):
            raise BusinessEtiquetteQuizServiceError(
                "[BUSINESS_ETIQUETTE_UNIT_QUIZ_ATTEMPT_LIMIT_REACHED]",
                "该商务礼仪小单元已达到最大重测次数。",
                409,
            )

    async def _attempt_response(
        self,
        attempt: SalesTrainerBusinessEtiquetteQuizAttempt,
    ) -> BusinessEtiquetteUnitQuizAttemptResponse:
        user = await self._db.get(User, attempt.user_id)
        return BusinessEtiquetteUnitQuizAttemptResponse(
            attempt_id=str(attempt.attempt_id),
            training_pack_key=str(attempt.training_pack_key),
            learning_unit_key=str(attempt.learning_unit_key),
            learning_unit_title=str(attempt.learning_unit_title),
            user_id=str(attempt.user_id),
            user_name=user.name if user is not None else None,
            user_department=user.department if user is not None else None,
            path_revision_id=attempt.path_revision_id,
            path_revision_no=attempt.path_revision_no,
            training_pack_revision_id=attempt.training_pack_revision_id,
            training_pack_revision_no=attempt.training_pack_revision_no,
            status=str(attempt.status),  # type: ignore[arg-type]
            total_score=float(attempt.total_score)
            if attempt.total_score is not None
            else None,
            max_score=float(attempt.max_score)
            if attempt.max_score is not None
            else None,
            passed=attempt.passed,
            capability_scores=[
                BusinessEtiquetteCapabilityScoreResponse.model_validate(item)
                for item in list(attempt.capability_scores or [])
                if isinstance(item, dict)
            ],
            weak_capability_keys=[
                str(item) for item in list(attempt.weak_capability_keys or [])
            ],
            recommended_chapter_orders=[
                int(item) for item in list(attempt.recommended_chapter_orders or [])
            ],
            answers=[
                BusinessEtiquetteQuizAnswerResultResponse.model_validate(item)
                for item in list(attempt.answers_snapshot or [])
                if isinstance(item, dict)
            ],
            submitted_at=attempt.submitted_at,
        )


class _QuizContext:
    def __init__(
        self,
        *,
        training_pack_key: str,
        unit_config: BusinessEtiquetteTrainingUnitConfig,
        path_revision_id: str | None,
        path_revision_no: int | None,
        training_pack_revision: SalesTrainerAssetRevision,
        capabilities: list[BusinessEtiquetteCapabilityConfig],
        capability_map: dict[str, BusinessEtiquetteCapabilityConfig],
        chapter_bindings: list[BusinessEtiquetteChapterCapabilityBinding],
    ) -> None:
        self.training_pack_key = training_pack_key
        self.unit_config = unit_config
        self.path_revision_id = path_revision_id
        self.path_revision_no = path_revision_no
        self.training_pack_revision = training_pack_revision
        self.capabilities = capabilities
        self.capability_map = capability_map
        self.chapter_bindings = chapter_bindings


def _capability_snapshot_from_revision(
    revision: SalesTrainerAssetRevision,
) -> tuple[
    list[BusinessEtiquetteCapabilityConfig],
    list[BusinessEtiquetteChapterCapabilityBinding],
]:
    raw_snapshot = (revision.payload_json or {}).get(CAPABILITY_SNAPSHOT_KEY)
    if not isinstance(raw_snapshot, dict):
        raise BusinessEtiquetteQuizServiceError(
            "[BUSINESS_ETIQUETTE_CAPABILITY_SNAPSHOT_MISSING]",
            "已发布商务礼仪训练包缺少能力点快照。",
            409,
        )
    raw_capabilities = raw_snapshot.get("capabilities")
    raw_bindings = raw_snapshot.get("chapter_bindings")
    if not isinstance(raw_capabilities, list) or not isinstance(raw_bindings, list):
        raise BusinessEtiquetteQuizServiceError(
            "[BUSINESS_ETIQUETTE_CAPABILITY_CONFIG_INVALID]",
            "已发布商务礼仪能力点快照结构非法。",
            409,
        )
    return (
        [
            BusinessEtiquetteCapabilityConfig.model_validate(item)
            for item in raw_capabilities
        ],
        [
            BusinessEtiquetteChapterCapabilityBinding.model_validate(item)
            for item in raw_bindings
        ],
    )


def _quiz_response(
    context: _QuizContext,
    questions: list[QuestionItem],
) -> BusinessEtiquetteUnitQuizResponse:
    return BusinessEtiquetteUnitQuizResponse(
        training_pack_key=context.training_pack_key,
        learning_unit_key=context.unit_config.unit_key,
        learning_unit_title=context.unit_config.title,
        path_revision_id=context.path_revision_id,
        path_revision_no=context.path_revision_no,
        training_pack_revision_id=str(context.training_pack_revision.revision_id),
        training_pack_revision_no=context.training_pack_revision.revision_no,
        question_count=len(questions),
        pass_threshold=context.unit_config.quiz_pass_threshold,
        allow_retake=context.unit_config.quiz_allow_retake,
        max_attempts=context.unit_config.quiz_max_attempts,
        capabilities=context.capabilities,
        questions=[
            _question_response(
                question,
                order_index=index,
                context=context,
            )
            for index, question in enumerate(questions, start=1)
        ],
    )


def _question_response(
    question: QuestionItem,
    *,
    order_index: int,
    context: _QuizContext,
) -> BusinessEtiquetteQuizQuestionResponse:
    criteria = question.scoring_criteria or {}
    question_type = _question_type(criteria)
    return BusinessEtiquetteQuizQuestionResponse(
        question_id=str(question.question_id),
        title=str(question.title),
        stem=str(question.stem),
        question_type=question_type,
        points=10,
        order_index=order_index,
        options=criteria.get("options") or [],
        capability_keys=_question_capability_keys(question, context.capability_map),
        chapter_orders=_question_chapter_orders(question),
    )


def _question_snapshot(question: QuestionItem, *, order_index: int) -> dict[str, Any]:
    criteria = question.scoring_criteria or {}
    return {
        "question_id": str(question.question_id),
        "title": question.title,
        "stem": question.stem,
        "question_type": _question_type(criteria),
        "options": criteria.get("options") or [],
        "reference_answer": question.reference_answer,
        "explanation": criteria.get("explanation"),
        "scoring_dimensions": list(question.scoring_dimensions or []),
        "tags": list(question.tags or []),
        "points": 10,
        "order_index": order_index,
        "version": question.version,
        "content_hash": question.content_hash,
    }


def _answer_result_payload(
    question: QuestionItem,
    *,
    answer_payload: Any,
    order_index: int,
    points: int,
    score: float | None,
    is_correct: bool | None,
    capability_keys: list[str],
    analysis: str | None,
    scoring_source: str | None,
    scoring_provider: str | None,
    scoring_model: str | None,
    scoring_latency_ms: int | None,
) -> dict[str, Any]:
    snapshot = _question_snapshot(question, order_index=order_index)
    return {
        "question_id": str(question.question_id),
        "question_type": snapshot["question_type"],
        "answer_payload": answer_payload,
        "is_correct": is_correct,
        "score": score,
        "max_score": float(points),
        "capability_keys": capability_keys,
        "question_snapshot": snapshot,
        "analysis": analysis,
        "scoring_source": scoring_source,
        "scoring_provider": scoring_provider,
        "scoring_model": scoring_model,
        "scoring_latency_ms": scoring_latency_ms,
    }


def _question_analysis(
    question: QuestionItem,
    *,
    is_correct: bool | None,
) -> str | None:
    criteria = question.scoring_criteria or {}
    explanation = criteria.get("explanation")
    if isinstance(explanation, str) and explanation.strip():
        return explanation.strip()
    reference_answer = (question.reference_answer or "").strip()
    if is_correct is True:
        return "本题答对了，继续保留这个做法。"
    if is_correct is False:
        if reference_answer:
            return f"本题需要回到参考答案复盘：{reference_answer}"
        return "本题需要结合题干场景复盘，重点看商务礼仪中的尊重、分寸和顺序要求。"
    return "本题正在等待评分，评分完成后会显示解析。"


def _capability_scores(
    *,
    context: _QuizContext,
    capability_points: dict[str, list[tuple[float, float]]],
) -> list[BusinessEtiquetteCapabilityScoreResponse]:
    items: list[BusinessEtiquetteCapabilityScoreResponse] = []
    for capability in context.capabilities:
        points = capability_points.get(capability.capability_key, [])
        score = sum(item[0] for item in points)
        max_score = sum(item[1] for item in points)
        normalized = (score / max_score * 100) if max_score > 0 else None
        mastery_level = _mastery_level(capability, normalized)
        threshold = capability.default_threshold
        items.append(
            BusinessEtiquetteCapabilityScoreResponse(
                capability_key=capability.capability_key,
                display_name=capability.display_name,
                score=score if max_score > 0 else None,
                max_score=max_score,
                normalized_score=normalized,
                threshold=threshold,
                mastered=(normalized >= threshold) if normalized is not None else None,
                mastery_level_key=mastery_level.get("level_key")
                if mastery_level
                else None,
                mastery_level_name=mastery_level.get("display_name")
                if mastery_level
                else None,
            )
        )
    return items


def _mastery_level(
    capability: BusinessEtiquetteCapabilityConfig,
    normalized_score: float | None,
) -> dict[str, Any] | None:
    if normalized_score is None:
        return None
    matched = None
    for level in capability.mastery_levels:
        if normalized_score >= level.min_score:
            matched = level.model_dump(mode="json")
    return matched


def _question_capability_keys(
    question: QuestionItem,
    capability_map: dict[str, BusinessEtiquetteCapabilityConfig],
) -> list[str]:
    keys: list[str] = []
    for value in list(question.scoring_dimensions or []):
        text = str(value)
        if text in capability_map:
            keys.append(text)
    for tag in list(question.tags or []):
        text = str(tag)
        if text.startswith("capability:"):
            key = text.removeprefix("capability:")
            if key in capability_map:
                keys.append(key)
    return _dedupe(keys)


def _question_chapter_orders(question: QuestionItem) -> list[int]:
    orders: list[int] = []
    for tag in list(question.tags or []):
        text = str(tag)
        if not text.startswith("chapter:"):
            continue
        try:
            orders.append(int(text.removeprefix("chapter:")))
        except ValueError:
            continue
    return sorted(set(orders))


def _select_weighted_questions(
    candidates: list[QuestionItem],
    *,
    question_count: int,
    question_type_weights: dict[str, float],
) -> list[QuestionItem]:
    if not question_type_weights:
        return candidates[:question_count]

    positive_weights = {
        question_type: weight
        for question_type, weight in question_type_weights.items()
        if weight > 0
    }
    if not positive_weights:
        return candidates[:question_count]

    groups: dict[str, list[QuestionItem]] = {
        "single_choice": [],
        "multiple_choice": [],
        "short_answer": [],
    }
    for question in candidates:
        groups[_question_type(question.scoring_criteria or {})].append(question)

    available_weights = {
        question_type: weight
        for question_type, weight in positive_weights.items()
        if groups.get(question_type)
    }
    if not available_weights:
        return candidates[:question_count]

    total_weight = sum(available_weights.values())
    quotas: dict[str, int] = {}
    remainders: dict[str, float] = {}
    for question_type, weight in available_weights.items():
        raw_quota = question_count * weight / total_weight
        quota = min(len(groups[question_type]), int(raw_quota))
        quotas[question_type] = quota
        remainders[question_type] = raw_quota - int(raw_quota)

    while sum(quotas.values()) < question_count:
        eligible_types = [
            question_type
            for question_type in available_weights
            if quotas[question_type] < len(groups[question_type])
        ]
        if not eligible_types:
            break
        next_type = max(
            eligible_types,
            key=lambda question_type: (
                remainders[question_type],
                available_weights[question_type],
            ),
        )
        quotas[next_type] += 1
        remainders[next_type] = 0

    selected: list[QuestionItem] = []
    selected_ids: set[str] = set()
    for question in candidates:
        question_type = _question_type(question.scoring_criteria or {})
        if quotas.get(question_type, 0) <= 0:
            continue
        selected.append(question)
        selected_ids.add(str(question.question_id))
        quotas[question_type] -= 1
        if len(selected) >= question_count:
            return selected

    for question in candidates:
        if len(selected) >= question_count:
            break
        question_id = str(question.question_id)
        if question_id in selected_ids:
            continue
        selected.append(question)
        selected_ids.add(question_id)
    return selected


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result


def _question_type(criteria: dict[str, Any]) -> str:
    raw_type = str(criteria.get("question_type") or "short_answer")
    if raw_type in {"single_choice", "multiple_choice", "short_answer"}:
        return raw_type
    return "short_answer"
