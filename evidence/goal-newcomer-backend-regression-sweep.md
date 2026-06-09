# Newcomer Training Path Backend Regression Sweep

## Scope

This evidence records the current backend state for the newcomer training path
revision-governance slices. It does not claim the full goal is complete because
frontend, browser, diagnostics, rollback/regrade UX, and full quality gate
evidence remain open.

## Verification

- `cd backend && venv/bin/python -m pytest tests/unit/test_newcomer_training_path_papers.py tests/unit/test_newcomer_training_path_audit_logs.py tests/integration/test_newcomer_training_path_paper_api.py --no-cov -q`
  - Result: 16 passed, 1 warning.
- `cd backend && venv/bin/python -m pytest tests/unit/test_newcomer_training_path_config_revision.py tests/integration/test_newcomer_training_path_config_api.py --no-cov -q`
  - Result: 7 passed, 1 warning.
- `cd backend && venv/bin/python -m pytest tests/unit/test_newcomer_training_path_questions.py tests/integration/test_newcomer_training_path_question_api.py --no-cov -q`
  - Result: 2 passed, 1 warning.
- `cd backend && venv/bin/python -m pytest tests/unit/test_newcomer_training_path_articles.py tests/integration/test_newcomer_training_path_article_api.py tests/unit/test_newcomer_training_path_material_governance.py tests/integration/test_newcomer_training_path_material_api.py --no-cov -q`
  - Result: 13 passed, 1 warning.
- `cd backend && venv/bin/python -m pytest tests/unit/test_newcomer_training_path_score_prompts.py tests/integration/test_newcomer_training_path_score_prompt_api.py tests/unit/test_newcomer_training_path_unit_revisions.py tests/integration/test_newcomer_training_path_unit_revision_api.py --no-cov -q`
  - Result: 9 passed, 1 warning.
- `cd backend && venv/bin/python -m pytest tests/unit/test_newcomer_training_path_attempt_lineage.py tests/unit/test_newcomer_training_path_audio_lineage.py tests/unit/test_newcomer_training_path_record_lineage.py tests/unit/test_newcomer_training_path_permissions.py tests/integration/test_newcomer_training_path_rbac_api.py --no-cov -q`
  - Result: 13 passed, 1 warning.
- `cd backend && venv/bin/python -m pytest tests/unit/test_newcomer_training_path_*.py tests/integration/test_newcomer_training_path_*.py --no-cov -q`
  - Result: 67 passed, 1 warning.
- `cd backend && venv/bin/ruff check src/sales_trainer tests/unit/test_newcomer_training_path_*.py tests/integration/test_newcomer_training_path_*.py`
  - Initial result: failed on unused imports in
    `src/sales_trainer/services/question_service.py`.
  - Final result after removing unused imports: All checks passed.

## Notes

- `backend/src/sales_trainer/services/question_service.py` is 232 pure LOC after
  the ruff cleanup.
- Existing oversized sales trainer files remain and must be split before any
  further edits that add behavior to those files:
  - `backend/src/sales_trainer/api.py`
  - `backend/src/sales_trainer/services/audio_submission_service.py`
  - `backend/src/sales_trainer/schemas.py`
  - `backend/src/sales_trainer/services/material_service.py`
  - `backend/src/sales_trainer/services/unit_service.py`
  - `backend/src/sales_trainer/models.py`
  - `backend/src/sales_trainer/services/paraformer_file_asr.py`
  - `backend/src/sales_trainer/paper_api.py`
  - `backend/src/sales_trainer/services/asset_revision_service.py`
