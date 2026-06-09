# Training Record Path Revision Lineage

Timestamp: 2026-06-03T23:50:20+08:00

## Scope

This slice extends newcomer training path revision lineage into unified training records.
It does not claim the full published-governance revision goal is complete.

## Behavior Proven

- Audio training record detail exposes top-level:
  - `path_key`
  - `path_revision_id`
  - `path_revision_no`
  - `module_key`
  - `legacy_snapshot_only`
- Quiz training records expose the same top-level lineage by reading frozen attempt answer context.
- The training record service reads lineage from the historical audio submission or quiz attempt payload.
- Legacy or unmatched records return nullable lineage fields with `legacy_snapshot_only=true` instead of fabricating revision ids from the latest path config.

## Files Changed In This Slice

- `backend/tests/unit/test_newcomer_training_path_record_lineage.py`
- `backend/src/sales_trainer/services/training_record_lineage.py`
- `backend/src/sales_trainer/services/training_record_service.py`
- `backend/src/sales_trainer/schemas.py`
- `web/src/lib/api/types.ts`
- `web/src/app/admin/sales-trainer/training-records/page.test.tsx`
- `docs/api-contract/sales-trainer.md`

## Verification

Red test:

```text
cd backend && venv/bin/python -m pytest tests/unit/test_newcomer_training_path_record_lineage.py -q --no-cov
FAILED with KeyError: 'path_revision_id'
```

Green:

```text
cd backend && venv/bin/python -m pytest tests/unit/test_newcomer_training_path_record_lineage.py -q --no-cov
2 passed
```

Regression:

```text
cd backend && venv/bin/python -m pytest tests/unit/test_newcomer_training_path_record_lineage.py tests/unit/test_newcomer_training_path_audio_lineage.py tests/unit/test_newcomer_training_path_attempt_lineage.py tests/unit/test_newcomer_training_path_papers.py tests/integration/test_newcomer_training_path_paper_api.py -q --no-cov
18 passed, 1 warning
```

Lint:

```text
cd backend && venv/bin/ruff check src/sales_trainer/services/training_record_lineage.py src/sales_trainer/services/training_record_service.py src/sales_trainer/schemas.py tests/unit/test_newcomer_training_path_record_lineage.py
All checks passed
```

Types:

```text
cd web && npx tsc --noEmit
passed
```

Focused frontend regression:

```text
cd web && npx vitest run src/app/admin/sales-trainer/training-records/page.test.tsx src/lib/sales-trainer/operational-diagnostics.test.ts
2 passed
```

## Notes

- `training_record_service.py` is 227 pure LOC after this slice.
- `test_newcomer_training_path_record_lineage.py` is 208 pure LOC after adding audio and quiz coverage.
- Editor LSP still reports missing `pytest`, `sqlalchemy`, and `pydantic` imports because the editor server is not using `backend/venv`; authoritative project commands above pass.
