# Audio Submission Path Revision Lineage

Timestamp: 2026-06-03T23:33:20+08:00

## Scope

This slice extends newcomer training path revision lineage from paper attempts to audio submissions and audio score results.
It does not claim the full published-governance revision goal is complete.

## Behavior Proven

- Audio submissions tied to a published path module freeze the active path revision context at submit time.
- The frozen lineage is stored under `task_brief_snapshot.submission_context`.
- Serialized audio submissions expose top-level:
  - `path_key`
  - `path_revision_id`
  - `path_revision_no`
  - `module_key`
  - `legacy_snapshot_only`
- Serialization reads from the frozen snapshot rather than from the latest path config.
- Audio score results expose the same lineage by reading their submission's frozen `task_brief_snapshot.submission_context`.
- Legacy or unmatched submissions return `legacy_snapshot_only=true` with nullable revision fields instead of fabricated revision ids.

## Files Changed In This Slice

- `backend/tests/unit/test_newcomer_training_path_audio_lineage.py`
- `backend/src/sales_trainer/services/path_attempt_context_service.py`
- `backend/src/sales_trainer/services/audio_submission_lineage.py`
- `backend/src/sales_trainer/services/audio_submission_service.py`
- `backend/src/sales_trainer/schemas.py`
- `web/src/lib/api/types.ts`
- `web/src/lib/sales-trainer/operational-diagnostics.test.ts`
- `docs/api-contract/sales-trainer.md`

## Verification

Red test:

```text
cd backend && venv/bin/python -m pytest tests/unit/test_newcomer_training_path_audio_lineage.py -q --no-cov
FAILED with KeyError: 'submission_context'
```

Second red test:

```text
cd backend && venv/bin/python -m pytest tests/unit/test_newcomer_training_path_audio_lineage.py -q --no-cov
FAILED with TypeError: 'dict' object can't be awaited
```

Green/regression:

```text
cd backend && venv/bin/python -m pytest tests/unit/test_newcomer_training_path_audio_lineage.py tests/unit/test_newcomer_training_path_attempt_lineage.py tests/unit/test_newcomer_training_path_papers.py tests/integration/test_newcomer_training_path_paper_api.py -q --no-cov
16 passed, 1 warning
```

Lint:

```text
cd backend && venv/bin/ruff check src/sales_trainer/services/path_attempt_context_service.py src/sales_trainer/services/audio_submission_lineage.py src/sales_trainer/services/audio_submission_service.py src/sales_trainer/api.py src/sales_trainer/schemas.py tests/unit/test_newcomer_training_path_audio_lineage.py
All checks passed
```

Types:

```text
cd web && npx tsc --noEmit
passed
```

Focused frontend regression:

```text
cd web && npx vitest run src/lib/sales-trainer/operational-diagnostics.test.ts
1 passed
```

## Notes

- Editor LSP still reports missing `pytest`, `sqlalchemy`, `fastapi`, and `pydantic` imports because the editor server is not using `backend/venv`; authoritative project commands above pass.
- No database column migration was introduced in this slice. Existing immutable JSON snapshots carry the lineage, which is sufficient for freezing the historical submission context.
