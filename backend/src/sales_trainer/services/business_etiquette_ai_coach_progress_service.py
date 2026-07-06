from __future__ import annotations

from typing import Any, cast

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from sales_trainer.ai_coach_chat_models import SalesTrainerAiCoachUiEvent
from sales_trainer.models import SalesTrainerAiCoachSession
from sales_trainer.schemas import (
    AiCoachConfig,
    AiCoachInteractionPublicV1,
    AiCoachScoreResultV1,
    AiCoachTrainingCardTypeV1,
    BusinessEtiquetteAiCoachProgressResponse,
    BusinessEtiquetteAiCoachProgressStatus,
    BusinessEtiquetteCapabilityConfig,
    BusinessEtiquetteCapabilityScoreResponse,
    BusinessEtiquetteTrainingUnitConfig,
    NewcomerPathModuleConfig,
)
from sales_trainer.services.ai_coach_chat_coach_state import (
    coach_state_from_snapshot,
)
from sales_trainer.services.ai_coach_chat_store import (
    AiCoachChatStore,
    AiCoachChatStoreError,
)
from sales_trainer.services.business_etiquette_capability_service import (
    BusinessEtiquetteCapabilityService,
    BusinessEtiquetteCapabilityServiceError,
    default_business_etiquette_capability_snapshot,
)
from sales_trainer.services.business_etiquette_learning_service import (
    BUSINESS_SKILLS_MODULE_KEY,
)
from sales_trainer.services.operation_log_service import OperationLogService


class BusinessEtiquetteAiCoachProgressServiceError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class BusinessEtiquetteAiCoachProgressService:
    def __init__(
        self,
        db: AsyncSession,
        *,
        store: AiCoachChatStore | None = None,
        logs: OperationLogService | None = None,
    ) -> None:
        self._db = db
        self._store = store or AiCoachChatStore(db)
        self._logs = logs or OperationLogService(db)

    async def get_progress(
        self,
        *,
        session_id: str,
        user_id: str,
        unit_key: str | None = None,
    ) -> BusinessEtiquetteAiCoachProgressResponse:
        try:
            session = await self._store.require_owned_session(session_id, user_id)
            events = await self._store.events(session_id)
        except AiCoachChatStoreError as exc:
            raise BusinessEtiquetteAiCoachProgressServiceError(
                exc.code,
                exc.message,
                exc.status_code,
            ) from exc
        return await self._build_progress(
            session=session,
            events=events,
            unit_key=unit_key,
        )

    async def update_session_progress_snapshot(
        self,
        session: SalesTrainerAiCoachSession,
        *,
        actor: User | None,
        unit_key: str | None = None,
    ) -> BusinessEtiquetteAiCoachProgressResponse:
        events = await self._store.events(str(session.session_id))
        progress = await self._build_progress(
            session=session,
            events=events,
            unit_key=unit_key,
        )
        state = coach_state_from_snapshot(session.coach_state)
        setattr(
            session,
            "coach_state",
            state.model_copy(update={"business_etiquette_progress": progress}).model_dump(
                mode="json"
            ),
        )
        setattr(
            session,
            "mastery_state",
            "mastered" if progress.passed else "not_mastered",
        )
        normalized_scores = [
            item.normalized_score
            for item in progress.capability_scores
            if item.normalized_score is not None
        ]
        if normalized_scores:
            average_score = round(sum(normalized_scores) / len(normalized_scores), 2)
            setattr(session, "total_score", average_score)
            setattr(session, "max_score", 100.0)
        await self._logs.record(
            actor=actor,
            action="business_etiquette_ai_coach_progress.updated",
            target_type="sales_trainer_ai_coach_session",
            target_id=str(session.session_id),
            metadata={
                "module_key": progress.module_key,
                "learning_unit_key": progress.learning_unit_key,
                "status": progress.status,
                "passed": progress.passed,
                "ready_for_field": progress.ready_for_field,
                "manual_review_required": progress.manual_review_required,
                "weak_capability_keys": progress.weak_capability_keys,
            },
        )
        await self._db.flush()
        return progress

    async def _build_progress(
        self,
        *,
        session: SalesTrainerAiCoachSession,
        events: list[SalesTrainerAiCoachUiEvent],
        unit_key: str | None,
    ) -> BusinessEtiquetteAiCoachProgressResponse:
        module = self._module_from_session(session)
        unit = self._resolve_unit(module, events, unit_key)
        required_keys = list(
            unit.ai_coach_required_capability_keys or unit.capability_keys
        )
        if not required_keys:
            raise BusinessEtiquetteAiCoachProgressServiceError(
                "[BUSINESS_ETIQUETTE_AI_COACH_CONFIG_INVALID]",
                "商务礼仪 AI 教练达标能力点配置缺失。",
                409,
            )
        capabilities_by_key = await self._capabilities_by_key(required_keys)
        scored_events = [
            event
            for event in events
            if event.event_type == "quiz_card"
            and event.status == "scored"
            and event.score_result
            and self._event_matches_unit(event, unit)
        ]
        pending_events = [
            event
            for event in events
            if event.event_type == "quiz_card"
            and event.status == "pending"
            and self._event_matches_unit(event, unit)
        ]
        capability_points = self._capability_points(
            events=scored_events,
            unit=unit,
            required_keys=required_keys,
        )
        capability_scores = self._capability_scores(
            required_keys=required_keys,
            capabilities_by_key=capabilities_by_key,
            capability_points=capability_points,
            pass_level_key=unit.ai_coach_pass_mastery_level_key,
            ready_level_key=unit.ai_coach_ready_mastery_level_key,
        )
        weak_keys = [
            item.capability_key for item in capability_scores if item.mastered is not True
        ]
        passed = not weak_keys and bool(scored_events)
        ready = passed and all(
            self._is_at_or_above_level(
                capabilities_by_key[item.capability_key],
                item.normalized_score,
                unit.ai_coach_ready_mastery_level_key,
            )
            for item in capability_scores
        )
        remediation_attempt_count = self._remediation_attempt_count(
            scored_events,
            unit=unit,
            capabilities_by_key=capabilities_by_key,
            required_keys=required_keys,
        )
        manual_review_required = (
            not passed
            and bool(scored_events)
            and unit.ai_coach_manual_review_after_max_attempts
            and remediation_attempt_count >= unit.ai_coach_max_remediation_attempts
        )
        status = self._status(
            scored_card_count=len(scored_events),
            has_pending_card=bool(pending_events),
            passed=passed,
            ready=ready,
            manual_review_required=manual_review_required,
        )
        next_step_code, next_step = self._next_step(module, status)
        return BusinessEtiquetteAiCoachProgressResponse(
            session_id=str(session.session_id),
            module_key=str(session.module_key),
            learning_unit_key=unit.unit_key,
            learning_unit_title=unit.title,
            status=status,
            passed=passed,
            ready_for_field=ready,
            manual_review_required=manual_review_required,
            block_next=unit.ai_coach_block_next_until_passed and not passed,
            answered_card_count=len(scored_events),
            scored_card_count=len(scored_events),
            remediation_attempt_count=remediation_attempt_count,
            max_remediation_attempts=unit.ai_coach_max_remediation_attempts,
            pass_mastery_level_key=unit.ai_coach_pass_mastery_level_key,
            ready_mastery_level_key=unit.ai_coach_ready_mastery_level_key,
            weak_capability_keys=weak_keys,
            recommended_chapter_orders=list(
                unit.ai_coach_remediation_chapter_orders
                or unit.source_chapter_orders
            ),
            recommended_training_card_types=self._recommended_training_card_types(
                session
            ),
            next_step_code=next_step_code,
            next_step=next_step,
            capability_scores=capability_scores,
        )

    @staticmethod
    def _module_from_session(
        session: SalesTrainerAiCoachSession,
    ) -> NewcomerPathModuleConfig:
        if str(session.module_key) != BUSINESS_SKILLS_MODULE_KEY:
            raise BusinessEtiquetteAiCoachProgressServiceError(
                "[BUSINESS_ETIQUETTE_AI_COACH_SESSION_INVALID]",
                "该 AI 教练会话不属于商务礼仪训练模块。",
                409,
            )
        try:
            module = NewcomerPathModuleConfig.model_validate(
                session.path_config_snapshot or {}
            )
        except ValidationError as exc:
            raise BusinessEtiquetteAiCoachProgressServiceError(
                "[BUSINESS_ETIQUETTE_AI_COACH_CONFIG_INVALID]",
                "商务礼仪 AI 教练会话配置快照非法。",
                409,
            ) from exc
        if not module.learning_units:
            raise BusinessEtiquetteAiCoachProgressServiceError(
                "[BUSINESS_ETIQUETTE_AI_COACH_UNIT_NOT_FOUND]",
                "商务礼仪 AI 教练会话缺少训练小单元快照。",
                409,
            )
        return module

    def _resolve_unit(
        self,
        module: NewcomerPathModuleConfig,
        events: list[SalesTrainerAiCoachUiEvent],
        unit_key: str | None,
    ) -> BusinessEtiquetteTrainingUnitConfig:
        units = sorted(module.learning_units, key=lambda item: item.order_index)
        if unit_key:
            for unit in units:
                if unit.unit_key == unit_key:
                    return unit
            raise BusinessEtiquetteAiCoachProgressServiceError(
                "[BUSINESS_ETIQUETTE_AI_COACH_UNIT_NOT_FOUND]",
                "指定的商务礼仪小单元不存在。",
                404,
            )
        for event in reversed(events):
            if event.event_type != "quiz_card":
                continue
            for unit in units:
                if self._event_matches_unit(event, unit):
                    return unit
        for unit in units:
            if unit.enabled:
                return unit
        return units[0]

    async def _capabilities_by_key(
        self,
        required_keys: list[str],
    ) -> dict[str, BusinessEtiquetteCapabilityConfig]:
        try:
            capabilities = await BusinessEtiquetteCapabilityService(
                self._db
            ).published_capabilities_by_key()
        except BusinessEtiquetteCapabilityServiceError as exc:
            raise BusinessEtiquetteAiCoachProgressServiceError(
                exc.code,
                exc.message,
                exc.status_code,
            ) from exc
        if not capabilities:
            seed = default_business_etiquette_capability_snapshot()
            capabilities = {
                item.capability_key: item
                for item in (
                    BusinessEtiquetteCapabilityConfig.model_validate(raw)
                    for raw in seed["capabilities"]
                )
            }
        missing = sorted(set(required_keys) - set(capabilities))
        if missing:
            raise BusinessEtiquetteAiCoachProgressServiceError(
                "[BUSINESS_ETIQUETTE_AI_COACH_CAPABILITY_CONFIG_MISSING]",
                f"商务礼仪能力点配置缺失：{', '.join(missing)}。",
                409,
            )
        return capabilities

    def _capability_points(
        self,
        *,
        events: list[SalesTrainerAiCoachUiEvent],
        unit: BusinessEtiquetteTrainingUnitConfig,
        required_keys: list[str],
    ) -> dict[str, list[tuple[float, float]]]:
        points: dict[str, list[tuple[float, float]]] = {}
        required_key_set = set(required_keys)
        for event in events:
            interaction = self._interaction_for_event(event)
            if interaction is None:
                continue
            score_result = self._score_result_for_event(event)
            capability_keys = [
                key
                for key in interaction.capability_keys
                if key in required_key_set
            ]
            if not capability_keys:
                capability_keys = required_keys if self._event_matches_unit(event, unit) else []
            for key in capability_keys:
                points.setdefault(key, []).append(
                    (float(score_result.score), float(score_result.max_score))
                )
        return points

    def _capability_scores(
        self,
        *,
        required_keys: list[str],
        capabilities_by_key: dict[str, BusinessEtiquetteCapabilityConfig],
        capability_points: dict[str, list[tuple[float, float]]],
        pass_level_key: str,
        ready_level_key: str,
    ) -> list[BusinessEtiquetteCapabilityScoreResponse]:
        scores: list[BusinessEtiquetteCapabilityScoreResponse] = []
        for key in required_keys:
            capability = capabilities_by_key[key]
            pass_threshold = self._level_min_score(capability, pass_level_key)
            ready_threshold = self._level_min_score(capability, ready_level_key)
            if ready_threshold < pass_threshold:
                raise BusinessEtiquetteAiCoachProgressServiceError(
                    "[BUSINESS_ETIQUETTE_AI_COACH_CONFIG_INVALID]",
                    "商务礼仪 AI 教练可上场等级不能低于达标等级。",
                    409,
                )
            points = capability_points.get(key, [])
            score = sum(item[0] for item in points)
            max_score = sum(item[1] for item in points)
            normalized = (score / max_score * 100) if max_score > 0 else None
            mastery_level = self._mastery_level(capability, normalized)
            scores.append(
                BusinessEtiquetteCapabilityScoreResponse(
                    capability_key=capability.capability_key,
                    display_name=capability.display_name,
                    score=score if max_score > 0 else None,
                    max_score=max_score,
                    normalized_score=normalized,
                    threshold=pass_threshold,
                    mastered=(
                        normalized >= pass_threshold
                        if normalized is not None
                        else None
                    ),
                    mastery_level_key=(
                        mastery_level.get("level_key") if mastery_level else None
                    ),
                    mastery_level_name=(
                        mastery_level.get("display_name") if mastery_level else None
                    ),
                )
            )
        return scores

    def _remediation_attempt_count(
        self,
        events: list[SalesTrainerAiCoachUiEvent],
        *,
        unit: BusinessEtiquetteTrainingUnitConfig,
        capabilities_by_key: dict[str, BusinessEtiquetteCapabilityConfig],
        required_keys: list[str],
    ) -> int:
        attempts = 0
        for event in events:
            score_result = self._score_result_for_event(event)
            interaction = self._interaction_for_event(event)
            if interaction is None:
                continue
            event_keys = [
                key for key in interaction.capability_keys if key in required_keys
            ] or required_keys
            thresholds = [
                self._level_min_score(
                    capabilities_by_key[key],
                    unit.ai_coach_pass_mastery_level_key,
                )
                for key in event_keys
            ]
            threshold = min(thresholds) if thresholds else 100.0
            normalized = (
                float(score_result.score) / float(score_result.max_score) * 100
                if float(score_result.max_score) > 0
                else 0
            )
            mastered = (
                score_result.mastered
                if score_result.mastered is not None
                else normalized >= threshold
            )
            if not mastered:
                attempts += 1
        return attempts

    @staticmethod
    def _status(
        *,
        scored_card_count: int,
        has_pending_card: bool,
        passed: bool,
        ready: bool,
        manual_review_required: bool,
    ) -> BusinessEtiquetteAiCoachProgressStatus:
        if manual_review_required:
            return "manual_review"
        if ready:
            return "ready"
        if passed:
            return "mastered"
        if scored_card_count > 0:
            return "not_mastered"
        if has_pending_card:
            return "in_progress"
        return "not_started"

    @staticmethod
    def _next_step(
        module: NewcomerPathModuleConfig,
        status: BusinessEtiquetteAiCoachProgressStatus,
    ) -> tuple[str, str]:
        templates = module.guidance_templates or {}
        if status == "manual_review":
            return (
                "manual_review",
                templates.get(
                    "ai_coach_manual_review",
                    "已达到补救次数上限，建议提交给带教人复盘后再继续。",
                ),
            )
        if status == "ready":
            return (
                "ready",
                templates.get(
                    "ai_coach_ready",
                    "已达到可上场标准，可以进入真实客户场景前复盘。",
                ),
            )
        if status == "mastered":
            return (
                "mastered",
                templates.get(
                    "ai_coach_mastered",
                    "已达到本单元 AI 教练达标线，可以继续巩固或进入下一单元。",
                ),
            )
        if status in {"not_mastered", "in_progress"}:
            return (
                "continue_remediation",
                templates.get(
                    "ai_coach_continue_remediation",
                    "优先回看推荐章节，并围绕薄弱能力重练一张训练卡。",
                ),
            )
        return (
            "start_training",
            templates.get(
                "ai_coach_start_training",
                "先完成一张 AI 教练训练卡，系统会按能力点记录掌握证据。",
            ),
        )

    @staticmethod
    def _recommended_training_card_types(
        session: SalesTrainerAiCoachSession,
    ) -> list[AiCoachTrainingCardTypeV1]:
        try:
            config = AiCoachConfig.model_validate(session.config_snapshot or {})
        except ValidationError:
            return ["scenario_judgment"]
        return list(config.allowed_training_card_types or ["scenario_judgment"])

    def _event_matches_unit(
        self,
        event: SalesTrainerAiCoachUiEvent,
        unit: BusinessEtiquetteTrainingUnitConfig,
    ) -> bool:
        interaction = self._interaction_for_event(event, allow_missing=True)
        if interaction is None:
            return False
        event_keys = set(interaction.capability_keys)
        event_chapters = set(interaction.source_chapter_orders)
        if event_keys & set(unit.capability_keys):
            return True
        if event_chapters & set(unit.source_chapter_orders):
            return True
        return not event_keys and not event_chapters and len(unit.capability_keys) == 1

    @staticmethod
    def _interaction_for_event(
        event: SalesTrainerAiCoachUiEvent,
        *,
        allow_missing: bool = False,
    ) -> AiCoachInteractionPublicV1 | None:
        raw_payload: dict[str, Any] = cast(dict[str, Any], event.payload_json or {})
        raw_interaction = raw_payload.get("public_interaction")
        if raw_interaction is None:
            if allow_missing:
                return None
            raise BusinessEtiquetteAiCoachProgressServiceError(
                "[BUSINESS_ETIQUETTE_AI_COACH_EVENT_INVALID]",
                "商务礼仪 AI 教练训练卡缺少公开互动快照。",
                409,
            )
        try:
            return AiCoachInteractionPublicV1.model_validate(raw_interaction)
        except ValidationError as exc:
            raise BusinessEtiquetteAiCoachProgressServiceError(
                "[BUSINESS_ETIQUETTE_AI_COACH_EVENT_INVALID]",
                "商务礼仪 AI 教练训练卡公开互动快照非法。",
                409,
            ) from exc

    @staticmethod
    def _score_result_for_event(
        event: SalesTrainerAiCoachUiEvent,
    ) -> AiCoachScoreResultV1:
        try:
            return AiCoachScoreResultV1.model_validate(event.score_result)
        except ValidationError as exc:
            raise BusinessEtiquetteAiCoachProgressServiceError(
                "[BUSINESS_ETIQUETTE_AI_COACH_SCORE_INVALID]",
                "商务礼仪 AI 教练训练卡评分结果非法。",
                409,
            ) from exc

    def _is_at_or_above_level(
        self,
        capability: BusinessEtiquetteCapabilityConfig,
        normalized_score: float | None,
        level_key: str,
    ) -> bool:
        if normalized_score is None:
            return False
        return normalized_score >= self._level_min_score(capability, level_key)

    @staticmethod
    def _level_min_score(
        capability: BusinessEtiquetteCapabilityConfig,
        level_key: str,
    ) -> float:
        for level in capability.mastery_levels:
            if level.level_key == level_key:
                return float(level.min_score)
        raise BusinessEtiquetteAiCoachProgressServiceError(
            "[BUSINESS_ETIQUETTE_AI_COACH_CONFIG_INVALID]",
            f"能力点 {capability.capability_key} 缺少掌握等级 {level_key}。",
            409,
        )

    @staticmethod
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
