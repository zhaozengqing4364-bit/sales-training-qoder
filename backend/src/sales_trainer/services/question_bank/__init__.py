"""Question-bank service facade for the sales trainer bounded context."""

from sales_trainer.services.question_bank.adapter import QuestionBankAdapter
from sales_trainer.services.question_bank.contracts import (
    SALES_TRAINER_QUESTION_SCOPE,
    to_question_item_create,
    to_question_item_update,
)
from sales_trainer.services.question_bank.errors import SalesTrainerQuestionServiceError
from sales_trainer.services.question_bank.payloads import (
    QUESTION_RESOURCE_TYPE,
    apply_question_revision_payload,
    question_change_class,
    question_lifecycle_metadata,
    question_lifecycle_snapshot,
    question_revision_payload_from_update,
    serialize_sales_trainer_category,
    serialize_sales_trainer_question,
)
from sales_trainer.services.question_bank.revision_service import (
    SalesTrainerQuestionRevisionService,
)
from sales_trainer.services.question_bank.service import SalesTrainerQuestionService

__all__ = [
    "QUESTION_RESOURCE_TYPE",
    "SALES_TRAINER_QUESTION_SCOPE",
    "QuestionBankAdapter",
    "SalesTrainerQuestionRevisionService",
    "SalesTrainerQuestionService",
    "SalesTrainerQuestionServiceError",
    "apply_question_revision_payload",
    "question_change_class",
    "question_lifecycle_metadata",
    "question_lifecycle_snapshot",
    "question_revision_payload_from_update",
    "serialize_sales_trainer_category",
    "serialize_sales_trainer_question",
    "to_question_item_create",
    "to_question_item_update",
]
