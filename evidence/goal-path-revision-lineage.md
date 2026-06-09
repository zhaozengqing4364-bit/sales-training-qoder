# Goal Evidence: Path Active Revision Lineage

Timestamp: 2026-06-03T15:01:53Z

Scope:

- Learner path payload now exposes `path_revision_id` and `path_revision_no` from the active newcomer path revision.
- Legacy Unit/backfill path payload keeps the same keys with `null` values.
- Frontend API types and `docs/api-contract/sales-trainer.md` now document the lineage fields.

Verification:

- `cd backend && venv/bin/python -m pytest tests/unit/test_newcomer_training_path_config_revision.py tests/integration/test_newcomer_training_path_config_api.py -q --no-cov`
  - Result: 5 passed, 1 unrelated ChromaDB deprecation warning.
- `cd backend && venv/bin/python -m ruff check src/sales_trainer/services/path_service.py src/sales_trainer/services/path_config_service.py src/sales_trainer/services/path_config_models.py src/sales_trainer/services/path_projection_payloads.py src/sales_trainer/schemas.py tests/unit/test_newcomer_training_path_config_revision.py tests/integration/test_newcomer_training_path_config_api.py`
  - Result: all checks passed.
- `cd web && npx tsc --noEmit`
  - Result: passed.
- Pure LOC check:
  - `path_service.py`: 111
  - `path_config_service.py`: 250
  - `path_config_models.py`: 136
  - `path_projection_payloads.py`: 152

Completion status:

- This only completes the path active revision lineage slice.
- The full goal remains active; quiz/audio/curriculum history snapshots, natural edit UI, high-risk regrade, diagnostics, and browser acceptance are not yet proven complete.
