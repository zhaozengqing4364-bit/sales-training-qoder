from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from common.api.response import error_response, success_response
from common.auth.service import get_current_user
from common.db.models import User
from common.db.session import get_db
from sales_trainer.schemas import (
    CustomerFaqLearningTopicResponse,
    CustomerFaqShortAnswerAttemptResponse,
    CustomerFaqShortAnswerSubmitRequest,
)
from sales_trainer.services.customer_faq_short_answer_service import (
    CustomerFaqShortAnswerService,
    CustomerFaqShortAnswerServiceError,
)
from sales_trainer.services.learner_unit_access import (
    LearnerUnitAccessError,
    require_learner_learning_topic_access,
)
from sales_trainer.services.learning_topic_config_service import (
    CUSTOMER_FAQ_TOPIC_KEY,
    LearningTopicConfigError,
    NewcomerLearningTopicConfigService,
)

customer_faq_router = APIRouter(
    prefix="/newcomer-training/customer-faq",
    tags=["newcomer-training-customer-faq"],
)


def _api_error(
    code: str,
    *,
    status_code: int = 400,
    message: str | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=error_response(code, message=message or code),
    )


@customer_faq_router.get("/topic", response_model=None)
async def get_customer_faq_learning_topic(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object] | JSONResponse:
    try:
        await require_learner_learning_topic_access(
            db,
            actor=current_user,
            topic_key=CUSTOMER_FAQ_TOPIC_KEY,
        )
        topic, revision = await NewcomerLearningTopicConfigService(
            db
        ).active_customer_faq_topic()
    except LearnerUnitAccessError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    except LearningTopicConfigError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)

    response = CustomerFaqLearningTopicResponse(
        title=topic.title,
        description=topic.description,
        revision_id=str(revision.revision_id),
        revision_no=int(revision.revision_no),
        units=[unit for unit in topic.learning_units if unit.enabled],
        cards=[card for card in topic.faq_cards if card.status == "published"],
        duplicate_groups=topic.duplicate_groups,
        evidence_cases=topic.evidence_cases,
        audio_scenario_key=topic.audio_scenario_key,
        quiz_paper_id=topic.quiz_paper_id,
        ai_coach=topic.ai_coach,
    )
    return success_response(response.model_dump(mode="json"))


@customer_faq_router.post(
    "/learning-units/{unit_key}/short-answer-attempts",
    response_model=None,
)
async def submit_customer_faq_unit_short_answer_attempt(
    unit_key: str,
    payload: CustomerFaqShortAnswerSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object] | JSONResponse:
    try:
        await require_learner_learning_topic_access(
            db,
            actor=current_user,
            topic_key=CUSTOMER_FAQ_TOPIC_KEY,
        )
        result = await CustomerFaqShortAnswerService(
            db
        ).submit_unit_short_answer_attempt(unit_key, payload)
    except LearnerUnitAccessError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    except CustomerFaqShortAnswerServiceError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    return success_response(
        CustomerFaqShortAnswerAttemptResponse.model_validate(result).model_dump(
            mode="json"
        )
    )
