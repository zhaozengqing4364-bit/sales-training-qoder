from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from sales_trainer.ai_coach_chat_models import SalesTrainerAiCoachChatMessage
from sales_trainer.models import SalesTrainerAiCoachSession
from sales_trainer.services.ai_coach_chat_auto_advance import AiCoachChatAutoAdvance
from sales_trainer.services.ai_coach_chat_errors import service_error_from_exception
from sales_trainer.services.ai_coach_chat_event_writer import AiCoachChatEventWriter
from sales_trainer.services.ai_coach_chat_runtime import (
    AiCoachChatRuntime,
    AiCoachChatRuntimeError,
)
from sales_trainer.services.ai_coach_chat_store import AiCoachChatStore
from sales_trainer.services.learning_topic_config_service import (
    BUSINESS_SKILLS_SOURCE_MODULE_KEY,
    LearningTopicConfigError,
    NewcomerLearningTopicConfigService,
)
from sales_trainer.services.operation_log_service import OperationLogService
from sales_trainer.services.path_config_models import NEWCOMER_PATH_LOGICAL_ID
from sales_trainer.services.path_config_service import SalesTrainerPathConfigService


class AiCoachChatSessionCreator:
    def __init__(
        self,
        db: AsyncSession,
        runtime: AiCoachChatRuntime,
        logs: OperationLogService,
        store: AiCoachChatStore,
        events: AiCoachChatEventWriter,
    ) -> None:
        self._db = db
        self._runtime = runtime
        self._logs = logs
        self._auto_advance = AiCoachChatAutoAdvance(db, store, events, logs)

    async def create_session_id(
        self,
        *,
        user_id: str,
        module_key: str,
        actor: User | None,
        start_auto_advance: bool = True,
    ) -> str:
        try:
            if module_key == BUSINESS_SKILLS_SOURCE_MODULE_KEY:
                (
                    path_revision_id,
                    path_revision_no,
                    module,
                ) = await NewcomerLearningTopicConfigService(
                    self._db
                ).active_business_etiquette_module_config()
                config = module.ai_coach
                if config is None:
                    raise AiCoachChatRuntimeError(
                        "[AI_COACH_NOT_CONFIGURED]",
                        "商务礼仪规范学习专题未配置 AI 教练。",
                        409,
                    )
            else:
                path_response = await SalesTrainerPathConfigService(self._db).get_config()
                if (
                    path_response.get("path") is None
                    or not path_response.get("active_revision_id")
                    or path_response.get("active_revision_no") is None
                ):
                    raise AiCoachChatRuntimeError(
                        "[NEWCOMER_PATH_ACTIVE_REVISION_MISSING]",
                        "新人训练路径尚未发布 active revision，AI Coach 不能启动。",
                        409,
                    )
                module, config = self._runtime.module_ai_coach_config(
                    path_response.get("path"),
                    module_key,
                )
                path_revision_id = path_response.get("active_revision_id")
                path_revision_no = path_response.get("active_revision_no")
            self._runtime.validate_chat_config(config)
            article_snapshot = await self._runtime.article_snapshot(module)
        except LearningTopicConfigError as exc:
            raise service_error_from_exception(
                AiCoachChatRuntimeError(exc.code, exc.message, exc.status_code)
            ) from exc
        except AiCoachChatRuntimeError as exc:
            raise service_error_from_exception(exc) from exc
        session = SalesTrainerAiCoachSession(
            user_id=user_id,
            module_key=module_key,
            path_key=NEWCOMER_PATH_LOGICAL_ID,
            path_revision_id=path_revision_id,
            path_revision_no=path_revision_no,
            article_snapshot=article_snapshot,
            path_config_snapshot=module.model_dump(mode="json"),
            prompt_template_id=config.prompt_template_id,
            prompt_revision_id=config.prompt_revision_id,
            prompt_contract_hash=config.prompt_contract_hash,
            config_snapshot=config.model_dump(mode="json"),
            coach_state={},
            status="in_progress",
            trace_id=str(uuid.uuid4()),
        )
        self._db.add(session)
        await self._db.flush()
        self._db.add(
            SalesTrainerAiCoachChatMessage(
                session_id=session.session_id,
                role="assistant",
                content=self._runtime.welcome_message(config),
                order_index=1,
            )
        )
        await self._logs.record(
            actor=actor,
            action="ai_coach_chat_session_created_v1",
            target_type="sales_trainer_ai_coach_session",
            target_id=str(session.session_id),
            metadata={"module_key": module_key, "runtime": "chat"},
        )
        if start_auto_advance:
            await self._auto_advance.start_session_if_configured(
                session=session,
                config=config,
                actor=actor,
            )
        else:
            await self._db.commit()
        return str(session.session_id)
