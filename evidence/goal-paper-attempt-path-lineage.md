# Goal Evidence: Paper Attempt Path Revision Lineage

Timestamp: 2026-06-03T15:19:33Z

## Scope

This slice advances the unified published-governance revision goal by freezing the active newcomer path revision context into submitted paper attempt answer snapshots.

It does not complete the whole goal. Remaining work still includes audio submission lineage, full regrade governance, richer diagnostics, browser acceptance, and `curriculum_practice` alignment.

## Behavior

- `ExamPaperService.submit_paper_attempt()` resolves the current path active revision for the submitted paper at submission time.
- `PaperSnapshotAttemptService.submit_attempt()` writes `attempt_context` into each answer payload snapshot.
- `serialize_paper_attempt()` exposes top-level lineage:
  - `path_key`
  - `path_revision_id`
  - `path_revision_no`
  - `module_key`
  - `legacy_snapshot_only`
- Legacy/no-match attempts return nullable lineage and `legacy_snapshot_only=true` instead of fabricating revision ids.
- Operation log metadata for `quiz_submitted` now includes path revision lineage when available.
- `QuizService` attempt serialization was split into `quiz_attempt_payloads.py`; `quiz_service.py` is now 241 pure LOC.

## Verification

Red test before implementation:

```text
cd backend && venv/bin/python -m pytest tests/unit/test_newcomer_training_path_attempt_lineage.py -q --no-cov
FAILED KeyError: 'attempt_context'
```

Green focused test:

```text
cd backend && venv/bin/python -m pytest tests/unit/test_newcomer_training_path_attempt_lineage.py -q --no-cov
1 passed
```

Focused backend regression:

```text
cd backend && venv/bin/python -m pytest tests/unit/test_newcomer_training_path_attempt_lineage.py tests/unit/test_newcomer_training_path_papers.py tests/integration/test_newcomer_training_path_paper_api.py -q --no-cov
14 passed, 1 ChromaDB deprecation warning
```

Lint/type checks:

```text
cd backend && venv/bin/ruff check src/sales_trainer/services/path_attempt_context_service.py src/sales_trainer/services/paper_snapshot_attempt_service.py src/sales_trainer/services/paper_snapshot_scoring.py src/sales_trainer/services/exam_paper_service.py src/sales_trainer/services/exam_paper_serializers.py src/sales_trainer/services/quiz_service.py src/sales_trainer/services/quiz_attempt_payloads.py src/sales_trainer/schemas.py tests/unit/test_newcomer_training_path_attempt_lineage.py
All checks passed!

cd web && npx tsc --noEmit
passed
```

Pure LOC after split:

```text
backend/src/sales_trainer/services/quiz_service.py: 241
backend/src/sales_trainer/services/quiz_attempt_payloads.py: 141
backend/src/sales_trainer/services/paper_snapshot_attempt_service.py: 201
backend/src/sales_trainer/services/exam_paper_serializers.py: 145
```

## Adversarial Notes

- Stale state: the test failed first on missing `attempt_context` and passed after implementation.
- Legacy data: no active path projection returns `legacy_snapshot_only=true`; no fake revision id is produced.
- Dirty worktree: existing unrelated dirty files were preserved.
- Misleading success: narrow test was followed by paper unit/API regressions, ruff, and web typecheck.
