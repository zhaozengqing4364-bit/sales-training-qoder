from __future__ import annotations

import ast
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import PracticeSession, PromptTemplate, User
from curriculum_practice.models import LearningContent, QuestionCategory, QuestionItem
from prompt_templates.models import PROMPT_BUSINESS_PURPOSE_AI_COACH_CONVERSATION
from sales_trainer.models import (
    SalesTrainerExamPaper,
    SalesTrainerQuizAttempt,
    SalesTrainerUnit,
)
from sales_trainer.schemas import (
    NewcomerArticleBinding,
    NewcomerPathConfigSaveRequest,
    NewcomerPathModuleConfig,
    QuizAnswerSubmit,
    QuizAttemptCreate,
    SalesTrainerUnitCreate,
    UnitQuestionBinding,
)
from sales_trainer.services.article_binding_service import (
    ArticleBindingService,
    ArticleBindingServiceError,
)
from sales_trainer.services.exam_paper_service import (
    ExamPaperService,
    ExamPaperServiceError,
)
from sales_trainer.services.path_config_service import SalesTrainerPathConfigService
from sales_trainer.services.path_service import SalesTrainerPathService
from sales_trainer.services.quiz_service import QuizService, QuizServiceError
from sales_trainer.services.unit_service import SalesTrainerUnitError, UnitService


def _user() -> User:
    return User(
        user_id="newcomer-boundary-user",
        wechat_user_id="newcomer-boundary-user",
        name="Newcomer Boundary User",
        email="newcomer-boundary-user@example.com",
        role="admin",
    )


def _question() -> tuple[QuestionCategory, QuestionItem]:
    category = QuestionCategory(
        category_id="newcomer-boundary-category",
        name="新人路径边界题库",
        usage_scope="sales_trainer",
        order_index=1,
    )
    question = QuestionItem(
        question_id="newcomer-boundary-question",
        category_id=category.category_id,
        title="新人路径边界题",
        stem="见客户前第一步是什么？",
        reference_answer="A",
        scoring_criteria={
            "question_type": "single_choice",
            "options": [{"value": "A", "label": "确认目标"}],
            "correct_answer": "A",
        },
        scoring_dimensions=["business_skills"],
        usage_scope="sales_trainer",
        status="published",
    )
    return category, question


def _ai_coach_config() -> dict[str, object]:
    return {
        "enabled": True,
        "coach_mode": "mixed_drill",
        "allowed_interaction_types": ["single_choice", "multiple_choice"],
        "prompt_template_id": "11111111-1111-1111-1111-111111111111",
        "prompt_revision_id": None,
        "prompt_contract_hash": None,
        "scoring_prompt_template_id": None,
        "scoring_prompt_revision_id": None,
        "scoring_contract_hash": None,
        "min_turns": 3,
        "max_turns": 10,
        "mastery_threshold": 90,
        "output_schema_version": "ai_coach_interaction_v1",
        "generation_model": None,
        "scoring_model": None,
        "retry_policy": {"max_retries": 2, "retry_backoff": 1.0},
        "failure_behavior": "skip_turn",
    }


def test_sales_trainer_newcomer_path_does_not_import_realtime_runtime() -> None:
    source_root = Path(__file__).resolve().parents[2] / "src" / "sales_trainer"
    allowed_curriculum_adapter = Path("services/curriculum_practice_adapter.py")
    blocked_import_roots = {"sales_bot", "training_runtime"}
    adapter_only_roots = {"curriculum_practice"}
    offenders: list[str] = []

    def root_name(module: str | None) -> str:
        return str(module or "").split(".", 1)[0]

    for path in source_root.rglob("*.py"):
        relative_path = path.relative_to(source_root)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = root_name(alias.name)
                    if root in blocked_import_roots or (
                        root in adapter_only_roots
                        and relative_path != allowed_curriculum_adapter
                    ):
                        offenders.append(f"{relative_path}:{alias.name}")
            elif isinstance(node, ast.ImportFrom):
                root = root_name(node.module)
                if root in blocked_import_roots or (
                    root in adapter_only_roots
                    and relative_path != allowed_curriculum_adapter
                ):
                    offenders.append(f"{relative_path}:{node.module}")
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "import_module"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                root = root_name(node.args[0].value)
                if root in blocked_import_roots or (
                    root in adapter_only_roots
                    and relative_path != allowed_curriculum_adapter
                ):
                    offenders.append(f"{relative_path}:{node.args[0].value}")

    assert offenders == []


@pytest.mark.asyncio
async def test_realtime_placeholder_is_disabled_and_does_not_create_practice_session(
    test_db: AsyncSession,
) -> None:
    user = _user()
    unit = SalesTrainerUnit(
        unit_id="newcomer-realtime-placeholder",
        name="实时对练占位",
        unit_type="quiz",
        status="published",
        config={
            "path": {
                "enabled": False,
                "path_key": "newcomer_training_path_v1",
                "module_key": "realtime_placeholder",
                "module_type": "realtime_placeholder",
                "order_index": 4,
                "completion_rule": "submitted",
                "disabled_reason": "暂不开放",
            }
        },
        created_by=user.user_id,
        updated_by=user.user_id,
    )
    test_db.add_all([user, unit])
    await test_db.commit()

    paths = await SalesTrainerPathService(test_db).list_paths_for_user(user.user_id)
    practice_session_count = await test_db.scalar(
        select(func.count()).select_from(PracticeSession)
    )

    assert paths == []
    assert practice_session_count == 0


@pytest.mark.asyncio
async def test_active_realtime_placeholder_revision_is_visible_without_runtime_session(
    test_db: AsyncSession,
) -> None:
    user = _user()
    unit = SalesTrainerUnit(
        unit_id="newcomer-active-realtime-placeholder",
        name="实时对练占位",
        unit_type="quiz",
        status="published",
        config={},
        created_by=user.user_id,
        updated_by=user.user_id,
    )
    test_db.add_all([user, unit])
    await test_db.commit()

    path_service = SalesTrainerPathConfigService(test_db)
    await path_service.save_config(
        NewcomerPathConfigSaveRequest(
            title="新人训练路径",
            reason="发布实时对练占位",
            modules=[
                NewcomerPathModuleConfig(
                    module_key="realtime_roleplay_placeholder",
                    module_type="realtime_placeholder",
                    enabled=False,
                    order_index=4,
                    title="实时对练占位",
                    target_unit_id=unit.unit_id,
                    disabled_reason="模块 4 仅为占位，不支持实时对练。",
                    completion_rule="submitted",
                )
            ],
        ),
        actor=user,
    )
    await path_service.publish_config(actor=user, reason="占位生效")

    paths = await SalesTrainerPathService(test_db).list_paths_for_user(user.user_id)
    practice_session_count = await test_db.scalar(
        select(func.count()).select_from(PracticeSession)
    )

    assert paths[0]["levels"][0]["module_type"] == "realtime_placeholder"
    assert paths[0]["levels"][0]["locked"] is True
    assert paths[0]["levels"][0]["status"] == "locked"
    assert paths[0]["current_level_id"] is None
    assert practice_session_count == 0


@pytest.mark.asyncio
async def test_article_exam_module_targets_business_skills_flow(
    test_db: AsyncSession,
) -> None:
    user = _user()
    content = LearningContent(
        learning_content_id="newcomer-boundary-business-content",
        title="商务技巧文章",
        summary="商务技巧学习内容。",
        owner="新人训练路径",
        source="unit_test",
        status="published",
        created_by=str(user.user_id),
        updated_by=str(user.user_id),
    )
    unit = SalesTrainerUnit(
        unit_id="newcomer-business-skills-target",
        name="商务技巧",
        unit_type="quiz",
        status="published",
        config={
            "path": {
                "enabled": True,
                "path_key": "newcomer_training_path_v1",
                "module_key": "business_skills",
                "module_type": "article_exam",
                "order_index": 2,
                "completion_rule": "submitted",
            }
        },
        created_by=user.user_id,
        updated_by=user.user_id,
    )
    paper = SalesTrainerExamPaper(
        paper_id="newcomer-boundary-business-paper",
        paper_key="newcomer-boundary-business-paper",
        title="商务技巧考卷",
        module_key="business_skills",
        unit_id=unit.unit_id,
        status="published",
        created_by=str(user.user_id),
        updated_by=str(user.user_id),
    )
    prompt = PromptTemplate(
        id="11111111-1111-1111-1111-111111111111",
        name="商务技巧 AI 教练对话生成",
        prompt_type="stage",
        business_purpose=PROMPT_BUSINESS_PURPOSE_AI_COACH_CONVERSATION,
        category="sales_trainer_ai_coach",
        template="请根据 {{ module_key }} 和 {{ coach_mode }} 生成教练回复。",
        variables=["module_key", "coach_mode"],
        is_active=True,
        is_default=False,
        is_system=False,
    )
    test_db.add_all([user, content, unit, paper, prompt])
    await test_db.commit()

    assert await SalesTrainerPathService(test_db).list_paths_for_user(user.user_id) == []

    path_service = SalesTrainerPathConfigService(test_db)
    await path_service.save_config(
        NewcomerPathConfigSaveRequest(
            title="新人训练路径",
            reason="发布商务技巧模块",
            modules=[
                NewcomerPathModuleConfig(
                    module_key="business_skills",
                    module_type="article_exam",
                    enabled=True,
                    order_index=2,
                    title="商务技巧",
                    target_unit_id=unit.unit_id,
                    learning_content_id=content.learning_content_id,
                    exam_paper_id=paper.paper_id,
                    ai_coach=_ai_coach_config(),
                    completion_rule="submitted",
                )
            ],
        ),
        actor=user,
    )
    await path_service.publish_config(actor=user, reason="商务技巧路径生效")

    paths = await SalesTrainerPathService(test_db).list_paths_for_user(user.user_id)

    assert paths[0]["levels"][0]["target_path"] == "/sales-trainer/business-skills"
    assert paths[0]["levels"][0]["learning_content_id"] == content.learning_content_id
    assert paths[0]["levels"][0]["exam_paper_id"] == paper.paper_id


@pytest.mark.asyncio
async def test_should_reject_quiz_submission_when_active_path_level_is_locked(
    test_db: AsyncSession,
) -> None:
    admin = _user()
    learner = User(
        user_id="newcomer-boundary-learner",
        wechat_user_id="newcomer-boundary-learner",
        name="Newcomer Boundary Learner",
        email="newcomer-boundary-learner@example.com",
        role="user",
    )
    content = LearningContent(
        learning_content_id="newcomer-locked-business-content",
        title="商务技巧文章",
        summary="商务技巧学习内容。",
        owner="新人训练路径",
        source="unit_test",
        status="published",
        created_by=str(admin.user_id),
        updated_by=str(admin.user_id),
    )
    unit = SalesTrainerUnit(
        unit_id="newcomer-locked-business-unit",
        name="商务技巧停用关卡",
        unit_type="quiz",
        status="published",
        config={},
        created_by=admin.user_id,
        updated_by=admin.user_id,
    )
    paper = SalesTrainerExamPaper(
        paper_id="newcomer-locked-business-paper",
        paper_key="newcomer-locked-business-paper",
        title="商务技巧停用考卷",
        module_key="business_skills",
        unit_id=unit.unit_id,
        status="published",
        created_by=str(admin.user_id),
        updated_by=str(admin.user_id),
    )
    test_db.add_all([admin, learner, content, unit, paper])
    await test_db.commit()

    path_service = SalesTrainerPathConfigService(test_db)
    await path_service.save_config(
        NewcomerPathConfigSaveRequest(
            title="新人训练路径",
            reason="发布停用商务技巧模块",
            modules=[
                NewcomerPathModuleConfig(
                    module_key="business_skills",
                    module_type="article_exam",
                    enabled=False,
                    order_index=2,
                    title="商务技巧",
                    target_unit_id=unit.unit_id,
                    learning_content_id=content.learning_content_id,
                    exam_paper_id=paper.paper_id,
                    disabled_reason="暂不开放",
                    completion_rule="submitted",
                )
            ],
        ),
        actor=admin,
    )
    await path_service.publish_config(actor=admin, reason="停用模块生效")

    with pytest.raises(QuizServiceError) as exc_info:
        await QuizService(test_db).submit_attempt(
            QuizAttemptCreate(
                unit_id=unit.unit_id,
                answers=[
                    QuizAnswerSubmit(
                        question_id="newcomer-boundary-question",
                        answer_payload="A",
                    )
                ],
            ),
            actor=learner,
        )

    assert exc_info.value.code == "[SALES_TRAINER_UNIT_NOT_FOUND]"
    assert exc_info.value.status_code == 404
    attempt_count = await test_db.scalar(
        select(func.count()).select_from(SalesTrainerQuizAttempt)
    )
    assert attempt_count == 0


@pytest.mark.asyncio
async def test_newcomer_module_invalid_config_reports_typed_error(
    test_db: AsyncSession,
) -> None:
    user = _user()
    category, question = _question()
    test_db.add_all([user, category, question])
    await test_db.commit()

    with pytest.raises(SalesTrainerUnitError) as exc:
        await UnitService(test_db).create_unit(
            SalesTrainerUnitCreate(
                name="非法新人模块",
                unit_type="quiz",
                config={
                    "quiz": {"pass_threshold": 10},
                    "path": {
                        "enabled": True,
                        "path_key": "newcomer_training_path_v1",
                        "module_key": "business_skills",
                        "module_type": "sales_queue",
                        "order_index": 1,
                    },
                },
                questions=[
                    UnitQuestionBinding(
                        question_id=question.question_id,
                        order_index=1,
                        points=10,
                    )
                ],
            ),
            actor=user,
        )

    assert exc.value.code == "[NEWCOMER_MODULE_CONFIG_INVALID]"
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_missing_article_and_paper_keep_typed_failures(
    test_db: AsyncSession,
) -> None:
    with pytest.raises(ArticleBindingServiceError) as article_error:
        await ArticleBindingService(test_db).resolve_module_article(
            binding=NewcomerArticleBinding(module_key="business_skills")
        )
    with pytest.raises(ExamPaperServiceError) as paper_error:
        await ExamPaperService(test_db).get_published_paper("missing-paper")

    assert article_error.value.code == "[LEARNING_CONTENT_NOT_PUBLISHED]"
    assert paper_error.value.code == "[PAPER_NOT_FOUND]"
