from __future__ import annotations

import inspect
from pathlib import Path

from sales_trainer.services.audio_submission_service import AudioSubmissionService

REPO_ROOT = Path(__file__).resolve().parents[4]


def test_legacy_audio_service_is_read_only_and_background_writers_are_removed() -> None:
    forbidden_methods = {
        "generate_upload_url",
        "save_uploaded_file",
        "create_submission",
        "process_submission",
        "retry_transcription",
        "transcribe_submission",
        "retry_scoring",
        "score_submission",
    }
    assert forbidden_methods.isdisjoint(
        name
        for name, _ in inspect.getmembers(AudioSubmissionService, inspect.isfunction)
    )
    for filename in ("process_audio.py", "score_audio.py", "transcribe_audio.py"):
        assert not (REPO_ROOT / "backend/src/sales_trainer/tasks" / filename).exists()


def test_legacy_delivery_exposes_no_audio_or_assignment_write_routes() -> None:
    sales_api = (REPO_ROOT / "backend/src/sales_trainer/api.py").read_text()
    learner_api_path = (
        REPO_ROOT / "backend/src/sales_trainer/orchestration/learner_api.py"
    )

    for retired_path in (
        '"/audio-submissions/upload-url"',
        '"/audio-submissions/upload"',
        '"/audio-submissions/{submission_id}/retry-transcription"',
        '"/audio-submissions/{submission_id}/retry-scoring"',
    ):
        assert retired_path not in sales_api
    assert "BackgroundTasks" not in sales_api
    assert not learner_api_path.exists()
    for retired_module in (
        "regrade_api.py",
        "regrade_schemas.py",
        "services/regrade_service.py",
        "services/audio_regrade_service.py",
    ):
        assert not (REPO_ROOT / "backend/src/sales_trainer" / retired_module).exists()


def test_new_audio_delivery_is_the_only_write_surface() -> None:
    source = (REPO_ROOT / "backend/src/foundation_learner_api.py").read_text()
    application = (
        REPO_ROOT / "backend/src/newcomer_training/activity_application.py"
    ).read_text()
    assert '"/activities/{activity_id}/commands"' in source
    assert (
        '"/audio-upload-sessions/{upload_session_id}/parts/{part_number}/content"'
        in source
    )
    for command in (
        "create_upload_session",
        "confirm_upload_part",
        "finalize_upload",
        "retry_stage",
        "cancel",
    ):
        assert command in application
