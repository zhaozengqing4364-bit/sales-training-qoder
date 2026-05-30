from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from sales_trainer.models import (
    SalesTrainerAudioScorePrompt,
    SalesTrainerUnit,
    SalesTrainerUnitQuestion,
)
from sales_trainer.schemas import (
    SalesTrainerPathConfig,
    SalesTrainerUnitCreate,
    SalesTrainerUnitUpdate,
    UnitQuestionBinding,
)
from sales_trainer.services.operation_log_service import OperationLogService
from sales_trainer.services.question_bank_adapter import QuestionBankAdapter


class SalesTrainerUnitError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.metadata = metadata or {}
        super().__init__(message)


class UnitService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._question_adapter = QuestionBankAdapter(db)
        self._logs = OperationLogService(db)

    async def list_units(
        self,
        *,
        include_archived: bool = False,
        published_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[SalesTrainerUnit], int]:
        stmt = select(SalesTrainerUnit)
        count_stmt = select(func.count()).select_from(SalesTrainerUnit)
        if published_only:
            stmt = stmt.where(SalesTrainerUnit.status == "published")
            count_stmt = count_stmt.where(SalesTrainerUnit.status == "published")
        elif not include_archived:
            stmt = stmt.where(SalesTrainerUnit.status != "archived")
            count_stmt = count_stmt.where(SalesTrainerUnit.status != "archived")
        result = await self._db.execute(
            stmt.order_by(SalesTrainerUnit.updated_at.desc()).offset(offset).limit(limit)
        )
        total = await self._db.scalar(count_stmt)
        return list(result.scalars().all()), int(total or 0)

    async def get_unit(self, unit_id: str) -> SalesTrainerUnit | None:
        return await self._db.get(SalesTrainerUnit, unit_id)

    async def create_unit(
        self, payload: SalesTrainerUnitCreate, *, actor: User
    ) -> SalesTrainerUnit:
        await self._validate_payload(
            payload.unit_type,
            payload.config,
            payload.questions,
            actor=actor,
            target_unit_id=None,
        )
        unit = SalesTrainerUnit(
            name=payload.name,
            description=payload.description,
            unit_type=payload.unit_type,
            config=payload.config,
            created_by=str(actor.user_id),
            updated_by=str(actor.user_id),
        )
        self._db.add(unit)
        await self._db.flush()
        await self._replace_questions(unit.unit_id, payload.questions)
        await self._logs.record(
            actor=actor,
            action="unit_created",
            target_type="sales_trainer_unit",
            target_id=unit.unit_id,
            metadata={"unit_type": unit.unit_type},
        )
        await self._db.commit()
        await self._db.refresh(unit)
        return unit

    async def update_unit(
        self,
        unit: SalesTrainerUnit,
        payload: SalesTrainerUnitUpdate,
        *,
        actor: User,
    ) -> SalesTrainerUnit:
        if unit.status != "draft":
            raise SalesTrainerUnitError(
                "[SALES_TRAINER_UNIT_NOT_EDITABLE]",
                "只有 draft 状态的训练单元可以修改。",
                status_code=409,
            )
        data = payload.model_dump(exclude_unset=True)
        next_config = data.get("config", unit.config)
        next_questions = data.get("questions")
        await self._validate_payload(
            str(unit.unit_type),
            next_config,
            next_questions if next_questions is not None else None,
            actor=actor,
            target_unit_id=str(unit.unit_id),
        )
        for field in ("name", "description", "config"):
            if field in data:
                setattr(unit, field, data[field])
        unit.updated_by = str(actor.user_id)
        if next_questions is not None:
            await self._replace_questions(unit.unit_id, next_questions)
        await self._logs.record(
            actor=actor,
            action="unit_updated",
            target_type="sales_trainer_unit",
            target_id=unit.unit_id,
        )
        await self._db.commit()
        await self._db.refresh(unit)
        return unit

    async def publish_unit(
        self, unit: SalesTrainerUnit, *, actor: User
    ) -> SalesTrainerUnit:
        await self._validate_publishable(unit, actor=actor)
        unit.status = "published"
        unit.updated_by = str(actor.user_id)
        await self._logs.record(
            actor=actor,
            action="unit_published",
            target_type="sales_trainer_unit",
            target_id=unit.unit_id,
        )
        await self._db.commit()
        await self._db.refresh(unit)
        return unit

    async def archive_unit(
        self, unit: SalesTrainerUnit, *, actor: User
    ) -> SalesTrainerUnit:
        unit.status = "archived"
        unit.updated_by = str(actor.user_id)
        await self._logs.record(
            actor=actor,
            action="unit_archived",
            target_type="sales_trainer_unit",
            target_id=unit.unit_id,
        )
        await self._db.commit()
        await self._db.refresh(unit)
        return unit

    async def get_unit_questions(self, unit_id: str) -> list[SalesTrainerUnitQuestion]:
        result = await self._db.execute(
            select(SalesTrainerUnitQuestion)
            .where(SalesTrainerUnitQuestion.unit_id == unit_id)
            .order_by(SalesTrainerUnitQuestion.order_index.asc())
        )
        return list(result.scalars().all())

    async def serialize_unit(self, unit: SalesTrainerUnit) -> dict[str, Any]:
        questions = await self.get_unit_questions(unit.unit_id)
        question_map = await self._question_adapter.get_questions(
            [str(item.question_id) for item in questions]
        )
        return {
            "unit_id": unit.unit_id,
            "name": unit.name,
            "description": unit.description,
            "unit_type": unit.unit_type,
            "config": unit.config or {},
            "status": unit.status,
            "created_by": unit.created_by,
            "updated_by": unit.updated_by,
            "created_at": unit.created_at,
            "updated_at": unit.updated_at,
            "questions": [
                self._question_adapter.serialize_for_learner(
                    question_map[item.question_id],
                    points=int(item.points),
                    order_index=int(item.order_index),
                )
                for item in questions
                if item.question_id in question_map
            ],
        }

    async def _replace_questions(
        self, unit_id: str, questions: list[UnitQuestionBinding]
    ) -> None:
        await self._db.execute(
            delete(SalesTrainerUnitQuestion).where(
                SalesTrainerUnitQuestion.unit_id == unit_id
            )
        )
        for item in questions:
            self._db.add(
                SalesTrainerUnitQuestion(
                    unit_id=unit_id,
                    question_id=item.question_id,
                    order_index=item.order_index,
                    points=item.points,
                )
            )
        await self._db.flush()

    async def _validate_payload(
        self,
        unit_type: str,
        config: dict[str, Any] | None,
        questions: Sequence[Any] | None,
        *,
        actor: User | None,
        target_unit_id: str | None,
    ) -> None:
        if unit_type == "quiz":
            if questions is not None:
                if not questions:
                    raise SalesTrainerUnitError(
                        "[SALES_TRAINER_QUIZ_REQUIRES_QUESTIONS]",
                        "做题训练单元至少需要绑定一道题。",
                    )
                question_map = await self._question_adapter.get_published_questions(
                    [item.question_id for item in questions]
                )
                missing = [
                    item.question_id
                    for item in questions
                    if item.question_id not in question_map
                ]
                if missing:
                    raise SalesTrainerUnitError(
                        "[QUESTION_ITEM_NOT_FOUND_OR_UNPUBLISHED]",
                        "绑定题目不存在或未发布。",
                        status_code=404,
                    )
                unsupported = [
                    reason
                    for question in question_map.values()
                    if (reason := self._question_adapter.unsupported_reason(question))
                    is not None
                ]
                if unsupported:
                    unsupported_metadata = {
                        "questions": [
                            {
                                "question_id": item.question_id,
                                "declared_type": item.declared_type,
                                "reason": item.reason,
                            }
                            for item in unsupported
                        ]
                    }
                    await self._logs.record(
                        actor=actor,
                        action="question_type_unsupported",
                        target_type="sales_trainer_unit",
                        target_id=target_unit_id,
                        metadata=unsupported_metadata,
                    )
                    await self._db.commit()
                    raise SalesTrainerUnitError(
                        "[QUESTION_TYPE_UNSUPPORTED]",
                        "绑定题目缺少销售训练做题模块需要的题型结构。",
                        status_code=422,
                        metadata=unsupported_metadata,
                    )
            quiz_config = (config or {}).get("quiz") or {}
            pass_threshold = quiz_config.get("pass_threshold")
            if pass_threshold is not None:
                try:
                    threshold = float(pass_threshold)
                except (TypeError, ValueError) as exc:
                    raise SalesTrainerUnitError(
                        "[QUIZ_PASS_THRESHOLD_INVALID]",
                        "做题通过线必须是非负数字。",
                    ) from exc
                if threshold < 0:
                    raise SalesTrainerUnitError(
                        "[QUIZ_PASS_THRESHOLD_INVALID]",
                        "做题通过线必须是非负数字。",
                    )
        if unit_type == "audio_scoring":
            audio_config = (config or {}).get("audio") or {}
            scoring_prompt_id = audio_config.get("scoring_prompt_id")
            if not scoring_prompt_id:
                raise SalesTrainerUnitError(
                    "[SCORING_PROMPT_REQUIRED]",
                    "音频评分训练单元必须绑定录音评分标准。",
                )
            prompt = await self._db.get(
                SalesTrainerAudioScorePrompt, str(scoring_prompt_id)
            )
            if prompt is None or prompt.status != "published":
                raise SalesTrainerUnitError(
                    "[SCORING_PROMPT_NOT_PUBLISHED]",
                    "录音评分标准不存在或未发布。",
                    status_code=404,
                )
            pass_threshold = audio_config.get("pass_threshold")
            if pass_threshold is not None:
                try:
                    threshold = float(pass_threshold)
                except (TypeError, ValueError) as exc:
                    raise SalesTrainerUnitError(
                        "[AUDIO_PASS_THRESHOLD_INVALID]",
                        "音频评分通过线必须是 0-100 的数字。",
                    ) from exc
                if threshold < 0 or threshold > 100:
                    raise SalesTrainerUnitError(
                        "[AUDIO_PASS_THRESHOLD_INVALID]",
                        "音频评分通过线必须是 0-100 的数字。",
                    )
        self._validate_path_config(config or {})

    def _validate_path_config(self, config: dict[str, Any]) -> None:
        raw_path_config = config.get("path")
        if raw_path_config is None:
            return
        if not isinstance(raw_path_config, dict):
            raise SalesTrainerUnitError(
                "[SALES_TRAINER_PATH_CONFIG_INVALID]",
                "训练路径配置必须是对象。",
                status_code=422,
            )
        try:
            SalesTrainerPathConfig.model_validate(raw_path_config)
        except ValueError as exc:
            raise SalesTrainerUnitError(
                "[SALES_TRAINER_PATH_CONFIG_INVALID]",
                "训练路径配置不合法。",
                status_code=422,
            ) from exc

    async def _validate_publishable(
        self,
        unit: SalesTrainerUnit,
        *,
        actor: User | None,
    ) -> None:
        if unit.status == "archived":
            raise SalesTrainerUnitError(
                "[SALES_TRAINER_UNIT_ARCHIVED]",
                "已归档训练单元不能发布。",
                status_code=409,
            )
        await self._validate_payload(
            str(unit.unit_type),
            unit.config or {},
            await self.get_unit_questions(unit.unit_id)
            if unit.unit_type == "quiz"
            else None,
            actor=actor,
            target_unit_id=str(unit.unit_id),
        )
