# Material Metadata Update Audit Slice

Plan: `.omo/plans/published-governance-revision-plan.md`

## Changed

- Added `backend/src/sales_trainer/services/material_metadata_update.py` to centralize material metadata snapshots, field diffing, and audit logging.
- Updated `SalesTrainerMaterialService.update_material` to write `material_metadata_updated` audit events with `before`, `after`, `changed_fields`, `trace_id`, `future_only`, and `impact_scope`.
- Added a backend unit test proving published material metadata edits keep the material published and record before/after audit metadata.
- Added a backend integration test proving `PUT /api/v1/admin/sales-trainer/materials/{material_id}` returns the updated published material and writes the same trace_id into the audit event.
- Updated `docs/api-contract/sales-trainer.md` so material metadata edits and audio scoring prompt edits match the future-only revision governance model.

## Verification

- `cd backend && venv/bin/python -m pytest tests/unit/test_newcomer_training_path_material_governance.py -q --no-cov` -> 2 passed.
- `cd backend && venv/bin/python -m pytest tests/integration/test_newcomer_training_path_material_api.py tests/unit/test_newcomer_training_path_material_governance.py -q --no-cov` -> 3 passed, 1 existing Chroma deprecation warning.
- `cd backend && venv/bin/python -m pytest tests/unit/test_newcomer_training_path_material_governance.py tests/unit/test_newcomer_training_path_audio_lineage.py -q --no-cov` -> 4 passed.
- `cd backend && venv/bin/ruff check src/sales_trainer/services/material_service.py src/sales_trainer/services/material_metadata_update.py tests/unit/test_newcomer_training_path_material_governance.py tests/integration/test_newcomer_training_path_material_api.py` -> passed.
- `rg -n '已发布或已归档提示词不可直接修改|更新 \`draft\` 提示词|修改非 \`draft\` 提示词' docs/api-contract/sales-trainer.md` -> no matches.

## Scope

This is a slice toward the full goal. It does not complete material file revision rollback, historical regrade, curriculum_practice parity, or final browser acceptance.
