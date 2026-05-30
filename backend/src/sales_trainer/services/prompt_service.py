from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from sales_trainer.models import SalesTrainerAudioScorePrompt
from sales_trainer.schemas import AudioScorePromptCreate, AudioScorePromptUpdate
from sales_trainer.services.operation_log_service import OperationLogService


class PromptServiceError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class AudioScorePromptService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._logs = OperationLogService(db)

    async def list_prompts(
        self,
        *,
        include_archived: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[SalesTrainerAudioScorePrompt], int]:
        stmt = select(SalesTrainerAudioScorePrompt)
        count_stmt = select(func.count()).select_from(SalesTrainerAudioScorePrompt)
        if not include_archived:
            stmt = stmt.where(SalesTrainerAudioScorePrompt.status != "archived")
            count_stmt = count_stmt.where(SalesTrainerAudioScorePrompt.status != "archived")
        result = await self._db.execute(
            stmt.order_by(SalesTrainerAudioScorePrompt.updated_at.desc())
            .offset(offset)
            .limit(limit)
        )
        total = await self._db.scalar(count_stmt)
        return list(result.scalars().all()), int(total or 0)

    async def get_prompt(self, prompt_id: str) -> SalesTrainerAudioScorePrompt | None:
        return await self._db.get(SalesTrainerAudioScorePrompt, prompt_id)

    async def create_prompt(
        self, payload: AudioScorePromptCreate, *, actor: User
    ) -> SalesTrainerAudioScorePrompt:
        prompt = SalesTrainerAudioScorePrompt(
            name=payload.name,
            purpose=payload.purpose,
            system_prompt=payload.system_prompt,
            scoring_template=payload.scoring_template,
            output_schema=payload.output_schema,
            created_by=str(actor.user_id),
            updated_by=str(actor.user_id),
        )
        self._db.add(prompt)
        await self._db.flush()
        await self._logs.record(
            actor=actor,
            action="audio_score_prompt_created",
            target_type="sales_trainer_audio_score_prompt",
            target_id=prompt.prompt_id,
        )
        await self._db.commit()
        await self._db.refresh(prompt)
        return prompt

    async def update_prompt(
        self,
        prompt: SalesTrainerAudioScorePrompt,
        payload: AudioScorePromptUpdate,
        *,
        actor: User,
    ) -> SalesTrainerAudioScorePrompt:
        if prompt.status != "draft":
            raise PromptServiceError(
                "[SCORING_PROMPT_NOT_EDITABLE]",
                "只有 draft 状态的录音评分标准可以修改。",
                409,
            )
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(prompt, key, value)
        prompt.updated_by = str(actor.user_id)
        await self._logs.record(
            actor=actor,
            action="audio_score_prompt_updated",
            target_type="sales_trainer_audio_score_prompt",
            target_id=prompt.prompt_id,
        )
        await self._db.commit()
        await self._db.refresh(prompt)
        return prompt

    async def publish_prompt(
        self, prompt: SalesTrainerAudioScorePrompt, *, actor: User
    ) -> SalesTrainerAudioScorePrompt:
        if prompt.status == "archived":
            raise PromptServiceError(
                "[SCORING_PROMPT_ARCHIVED]",
                "已归档提示词不能发布。",
                409,
            )
        prompt.status = "published"
        prompt.updated_by = str(actor.user_id)
        await self._logs.record(
            actor=actor,
            action="audio_score_prompt_published",
            target_type="sales_trainer_audio_score_prompt",
            target_id=prompt.prompt_id,
        )
        await self._db.commit()
        await self._db.refresh(prompt)
        return prompt
