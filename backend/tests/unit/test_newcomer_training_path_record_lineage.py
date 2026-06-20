from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from curriculum_practice.models import (
    LearningChapter,
    LearningContent,
    QuestionCategory,
    QuestionItem,
)
from curriculum_practice.services.learning_progress_service import (
    LearningProgressService,
)
from sales_trainer.models import (
    SalesTrainerAudioScorePrompt,
    SalesTrainerMaterial,
    SalesTrainerMaterialVersion,
    SalesTrainerUnit,
)
from sales_trainer.schemas import (
    AudioSubmissionCreate,
    ExamPaperCreate,
    ExamPaperQuestionBinding,
    NewcomerPathConfigSaveRequest,
    NewcomerPathModuleConfig,
    PaperAttemptCreate,
    QuizAnswerSubmit,
)
from sales_trainer.services.audio_submission_service import AudioSubmissionService
from sales_trainer.services.exam_paper_service import ExamPaperService
from sales_trainer.services.path_config_service import SalesTrainerPathConfigService
from sales_trainer.services.training_record_service import TrainingRecordService


def _user(role: str) -> User:
    return User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"record-lineage-{role}-{uuid.uuid4().hex[:8]}",
        name=f"Record Lineage {role}",
        email=f"record-lineage-{role}-{uuid.uuid4().hex[:8]}@example.com",
        role=role,
    )


def _question(question_id: str, *, category_id: str) -> QuestionItem:
    return QuestionItem(
        question_id=question_id,
        category_id=category_id,
        title="客户拜访礼仪",
        stem="见客户前应该先确认什么？",
        reference_answer="A",
        scoring_criteria={
            "question_type": "single_choice",
            "options": [
                {"value": "A", "label": "确认客户背景与拜访目标"},
                {"value": "B", "label": "临场发挥"},
            ],
            "correct_answer": "A",
        },
        scoring_dimensions=["content_accuracy"],
        status="published",
        usage_scope="sales_trainer",
    )


def _published_material(
    admin: User,
) -> tuple[SalesTrainerMaterial, SalesTrainerMaterialVersion]:
    material = SalesTrainerMaterial(
        material_id=str(uuid.uuid4()),
        material_key=f"record-lineage-ppt-{uuid.uuid4().hex[:8]}",
        name="PPT 讲解材料",
        material_type="ppt_deck",
        purpose="ppt_pitch",
        status="published",
        created_by=admin.user_id,
        updated_by=admin.user_id,
    )
    version = SalesTrainerMaterialVersion(
        version_id=str(uuid.uuid4()),
        material_id=material.material_id,
        version_label="v1",
        title="PPT 讲解材料 v1",
        file_name="record-lineage.pptx",
        content_type="application/vnd.ms-powerpoint",
        file_size_bytes=1024,
        storage_key="/tmp/record-lineage.pptx",
        status="published",
        created_by=admin.user_id,
        published_by=admin.user_id,
    )
    material.current_version_id = version.version_id
    return material, version


async def _completed_article(
    test_db: AsyncSession,
    *,
    content_id: str,
    admin: User,
    learner: User,
) -> LearningContent:
    content = LearningContent(
        learning_content_id=content_id,
        title="见客户前商务礼仪",
        summary="阅读后提交商务技巧考卷。",
        owner="新人训练路径",
        source="unit_test",
        status="published",
        created_by=str(admin.user_id),
        updated_by=str(admin.user_id),
    )
    chapter = LearningChapter(
        chapter_id=f"{content_id}-chapter-1",
        learning_content_id=content.learning_content_id,
        title="拜访前准备",
        content="先确认客户背景、到访时间和接待安排。",
        order_index=1,
        created_by=str(admin.user_id),
        updated_by=str(admin.user_id),
    )
    test_db.add_all([content, chapter])
    await test_db.commit()
    result = await LearningProgressService(test_db).complete_chapter(
        user_id=str(learner.user_id),
        content_id=content.learning_content_id,
        chapter_id=chapter.chapter_id,
    )
    assert result.is_success
    return content


@pytest.mark.asyncio
async def test_should_expose_audio_training_record_path_revision_lineage(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    prompt = SalesTrainerAudioScorePrompt(
        prompt_id=str(uuid.uuid4()),
        name="PPT 讲解评分",
        purpose="general_audio_scoring",
        system_prompt="你是销售训练评分员。",
        scoring_template="请评分：{transcript}",
        output_schema={},
        status="published",
        created_by=admin.user_id,
        updated_by=admin.user_id,
    )
    unit = SalesTrainerUnit(
        unit_id=str(uuid.uuid4()),
        name="PPT 讲解录音",
        unit_type="audio_scoring",
        config={
            "audio": {
                "scoring_prompt_id": prompt.prompt_id,
                "pass_threshold": 80,
                "purpose": "general_audio_scoring",
            }
        },
        status="published",
        created_by=admin.user_id,
        updated_by=admin.user_id,
    )
    material, version = _published_material(admin)
    test_db.add_all([admin, learner, prompt, material, version, unit])
    await test_db.commit()

    path_service = SalesTrainerPathConfigService(test_db)
    await path_service.save_config(
        NewcomerPathConfigSaveRequest(
            title="新人训练路径",
            reason="绑定 PPT 讲解录音",
            modules=[
                NewcomerPathModuleConfig(
                    module_key="ppt_explanation",
                    module_type="audio_scoring",
                    enabled=True,
                    order_index=1,
                    title="PPT 讲解录音",
                    target_unit_id=unit.unit_id,
                    material_id=material.material_id,
                    material_version_id=version.version_id,
                    completion_rule="scored",
                )
            ],
        ),
        actor=admin,
    )
    publish_result = await path_service.publish_config(
        actor=admin,
        reason="PPT 讲解路径生效",
    )

    submission = await AudioSubmissionService(test_db).create_submission(
        AudioSubmissionCreate(
            unit_id=unit.unit_id,
            purpose="general_audio_scoring",
            original_filename="ppt-explanation.wav",
            content_type="audio/wav",
            size_bytes=1024,
            storage_key="/tmp/ppt-explanation.wav",
            source_page="sales_trainer_unit_detail",
            confirmed_material_version_id=version.version_id,
            auto_process=False,
        ),
        actor=learner,
    )

    record = await TrainingRecordService(test_db).get_audio_record(
        submission.submission_id
    )

    assert record is not None
    assert record["path_revision_id"] == str(publish_result.revision.revision_id)
    assert record["path_revision_no"] == 1
    assert record["path_key"] == "newcomer_training_path_v1"
    assert record["module_key"] == "ppt_explanation"
    assert record["legacy_snapshot_only"] is False


@pytest.mark.asyncio
async def test_should_expose_quiz_training_record_path_revision_lineage(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    category = QuestionCategory(
        category_id="record-lineage-quiz-category",
        name="商务技巧记录版本",
        order_index=1,
        usage_scope="sales_trainer",
    )
    question = _question(
        "record-lineage-quiz-question",
        category_id=category.category_id,
    )
    test_db.add_all([admin, learner, category, question])
    await test_db.commit()
    content = await _completed_article(
        test_db,
        content_id="record-lineage-quiz-content",
        admin=admin,
        learner=learner,
    )

    paper_service = ExamPaperService(test_db)
    paper = await paper_service.create_paper(
        ExamPaperCreate(
            paper_key="record-lineage-quiz-paper",
            title="商务技巧路径版本考卷",
            module_key="business_skills",
            pass_threshold=10,
            questions=[
                ExamPaperQuestionBinding(
                    question_id=question.question_id,
                    order_index=1,
                    points=10,
                )
            ],
        ),
        actor=admin,
    )
    published = await paper_service.publish_paper(paper.paper_id, actor=admin)

    path_service = SalesTrainerPathConfigService(test_db)
    await path_service.save_config(
        NewcomerPathConfigSaveRequest(
            title="新人训练路径",
            reason="绑定商务技巧考卷",
            modules=[
                NewcomerPathModuleConfig(
                    module_key="business_skills",
                    module_type="article_exam",
                    enabled=True,
                    order_index=1,
                    title="商务技巧",
                    target_unit_id=published.unit_id,
                    learning_content_id=content.learning_content_id,
                    exam_paper_id=published.paper_id,
                    completion_rule="passed",
                )
            ],
        ),
        actor=admin,
    )
    publish_result = await path_service.publish_config(
        actor=admin,
        reason="商务技巧路径生效",
    )

    attempt = await paper_service.submit_paper_attempt(
        PaperAttemptCreate(
            paper_id=published.paper_id,
            answers=[
                QuizAnswerSubmit(
                    question_id=question.question_id,
                    answer_payload="A",
                )
            ],
        ),
        actor=learner,
    )

    records, total = await TrainingRecordService(test_db).list_records(
        user_id=learner.user_id,
    )

    assert total == 1
    assert records[0]["record_id"] == attempt.attempt_id
    assert records[0]["path_revision_id"] == str(publish_result.revision.revision_id)
    assert records[0]["path_revision_no"] == 1
    assert records[0]["path_key"] == "newcomer_training_path_v1"
    assert records[0]["module_key"] == "business_skills"
    assert records[0]["legacy_snapshot_only"] is False
