from __future__ import annotations

import pytest
from sqlalchemy import func, select

from ai_coach.contracts import CoachProfileSnapshot
from ai_coach.models import CoachProfileRevision
from audio_assessment.contracts import (
    ASSIGNMENT_SEGMENTS,
    AUDIO_MAX_DURATION_SECONDS,
    AUDIO_MAX_SIZE_BYTES,
    AudioScenarioSnapshot,
    AudioScoringSchemeSnapshot,
)
from audio_assessment.models import AudioActivityResourceRevision
from foundation_standard_pack import (
    COMPETENCIES,
    install_or_verify_standard_pack,
)
from learning.models import (
    LearningQuestion,
    LearningQuiz,
    LearningSourceDocument,
    LearningUnit,
)
from newcomer_training.contracts import PathRevisionDraft
from newcomer_training.errors import NewcomerTrainingError
from newcomer_training.models import NewcomerPath, NewcomerPathRevision


@pytest.mark.asyncio
async def test_standard_pack_is_complete_repeatable_and_verify_only(test_db) -> None:
    first = await install_or_verify_standard_pack(
        test_db,
        organization_id="org-1",
    )
    second = await install_or_verify_standard_pack(
        test_db,
        organization_id="org-1",
    )
    verified = await install_or_verify_standard_pack(
        test_db,
        organization_id="org-1",
        verify_only=True,
    )

    expected_keys = tuple(item.key for item in COMPETENCIES)
    assert first.path_revision_id == second.path_revision_id
    assert first.path_revision_id == verified.path_revision_id
    assert first.competency_keys == expected_keys
    assert verified.verified_only is True
    assert set(first.learning_unit_revision_ids) == set(expected_keys)
    assert set(first.question_revision_ids) == set(expected_keys)
    assert set(first.quiz_revision_ids) == set(expected_keys)
    assert set(first.audio_resource_revision_ids) == {
        "explanation_material",
        "explanation_scoring",
        "assignment_scenario",
        "assignment_scoring",
    }
    assert first.audio_resource_revision_ids == second.audio_resource_revision_ids
    assert first.audio_resource_revision_ids == verified.audio_resource_revision_ids
    assert first.coach_profile_revision_id == second.coach_profile_revision_id
    assert first.coach_profile_revision_id == verified.coach_profile_revision_id
    assert int(await test_db.scalar(select(func.count(NewcomerPath.path_id))) or 0) == 1
    assert (
        int(
            await test_db.scalar(select(func.count(LearningSourceDocument.document_id)))
            or 0
        )
        == 1
    )
    assert int(await test_db.scalar(select(func.count(LearningUnit.unit_id))) or 0) == 7
    assert (
        int(await test_db.scalar(select(func.count(LearningQuestion.question_id))) or 0)
        == 7
    )
    assert int(await test_db.scalar(select(func.count(LearningQuiz.quiz_id))) or 0) == 7
    assert (
        int(
            await test_db.scalar(
                select(func.count(AudioActivityResourceRevision.revision_id))
            )
            or 0
        )
        == 4
    )
    assert (
        int(
            await test_db.scalar(select(func.count(CoachProfileRevision.revision_id)))
            or 0
        )
        == 1
    )

    path_revision = await test_db.get(NewcomerPathRevision, first.path_revision_id)
    assert path_revision is not None
    path = PathRevisionDraft.model_validate(path_revision.snapshot_json)
    activity_types = [
        activity.type.value for stage in path.stages for activity in stage.activities
    ]
    assert activity_types[-3:] == ["audio_assessment", "ai_coach", "assignment"]
    assert "realtime_roleplay" not in activity_types
    coach_activity = next(
        activity
        for stage in path.stages
        for activity in stage.activities
        if activity.type.value == "ai_coach"
    )
    assignment_activity = next(
        activity
        for stage in path.stages
        for activity in stage.activities
        if activity.type.value == "assignment"
    )
    assert coach_activity.prerequisite_activity_ids == ("audio-foundation-explanation",)
    assert assignment_activity.prerequisite_activity_ids == (
        "coach-foundation-remediation",
    )
    assert coach_activity.config.model_dump(mode="json")[
        "coach_profile_revision_id"
    ] == (
        first.coach_profile_revision_id
    )

    coach_profile_row = await test_db.get(
        CoachProfileRevision,
        first.coach_profile_revision_id,
    )
    assert coach_profile_row is not None
    coach_profile = CoachProfileSnapshot.model_validate(coach_profile_row.snapshot_json)
    assert len(coach_profile.checkpoints) == 3
    assert coach_profile.mastery_rule.threshold_percent == 80
    assert coach_profile.remediation_policy.maximum_automatic_cycles == 2

    scoring_rows = (
        (
            await test_db.execute(
                select(AudioActivityResourceRevision).where(
                    AudioActivityResourceRevision.resource_type == "scoring_scheme"
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(scoring_rows) == 2
    for row in scoring_rows:
        scoring = AudioScoringSchemeSnapshot.model_validate(row.snapshot_json)
        assert scoring.capture.max_duration_seconds == AUDIO_MAX_DURATION_SECONDS
        assert scoring.capture.max_size_bytes == AUDIO_MAX_SIZE_BYTES
        assert scoring.asr.prompt_template_id is None
        assert scoring.scoring.prompt_revision_id == "foundation-audio-scoring-v1"

    scenario_row = await test_db.get(
        AudioActivityResourceRevision,
        first.audio_resource_revision_ids["assignment_scenario"],
    )
    assert scenario_row is not None
    scenario = AudioScenarioSnapshot.model_validate(scenario_row.snapshot_json)
    assert tuple(segment.segment_id for segment in scenario.segments) == (
        ASSIGNMENT_SEGMENTS
    )


@pytest.mark.asyncio
async def test_standard_pack_verify_only_fails_without_writing(test_db) -> None:
    with pytest.raises(NewcomerTrainingError) as missing:
        await install_or_verify_standard_pack(
            test_db,
            organization_id="org-1",
            verify_only=True,
        )

    assert missing.value.code == "[STANDARD_PACK_MISSING]"
    assert int(await test_db.scalar(select(func.count(NewcomerPath.path_id))) or 0) == 0
