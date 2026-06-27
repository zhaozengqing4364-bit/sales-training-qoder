# G008 Quality Gate Code Review

## Verdict

- status: APPROVE
- codeQualityStatus: WATCH
- recommendation: APPROVE
- codeReviewClean: true for blocker-level findings; residual LOW risks remain.
- blockers: []

## Scope Reviewed

- Repository: `/Users/zhaozengqing/github/销售训练qoder`
- Reviewed sources: `git status --short`, `git diff --name-status`, `git diff --stat`, grouped `git diff`, CodeGraph exploration, `.omo/ulw-loop/evidence/*`, untracked `backend/tests/unit/test_sales_trainer_asset_revision_service.py`, untracked `docs/architecture/governance-revision-inventory.md`.
- Focus areas: governance revision/snapshot/audit, path-config diagnostics and rollback preview, regrade append-only behavior, runtime snapshot `examiner_question_refs`, frontend path-config reason UI.

## Skill-Perspective Check

- `remove-ai-slops` skill: loaded and applied as a review pass over changed production code and tests.
  - No deletion-only tests found.
  - No tests that merely verify a requested removal found.
  - No skipped/xfail/only tests found.
  - Some frontend tests use `toHaveBeenCalled()` / `toBeTruthy()`, but they also assert payloads, UI labels, links, messages, and reason propagation, so they are not blocker-level tautologies.
- `programming` skill: loaded, including Python README, TypeScript README, and code-smells reference.
  - No `as any`, `@ts-ignore`, `@ts-expect-error`, or broad `except Exception` introduced in reviewed diff.
  - The 250 pure-LOC perspective is violated by existing/touched large modules; recorded as LOW residual maintainability risk below, not a blocker for this gate because the reviewed changes are behavior-covered and no needless abstraction was identified.

## Findings

### CRITICAL

None.

### HIGH

None.

### MEDIUM

None.

### LOW

1. `backend/src/curriculum_practice/services/publishing_gates.py:310` - Publish-gate validation still derives required refs from top-level template fields and does not explicitly expand `examiner_agent.question_source_ids` into `question_item` gate checks before publish. Runtime snapshot now validates frozen question refs and rejects stale/safety-flagged questions, so this is not a current blocker, but bad question refs can still be discovered later at runtime rather than earlier at publish time.

2. Touched modules remain over the programming skill's 250 pure-LOC ceiling: `backend/src/sales_trainer/services/path_config_service.py` (~738), `backend/src/curriculum_practice/services/snapshots.py` (~564), `backend/src/sales_trainer/services/asset_revision_service.py` (~315), `backend/src/curriculum_practice/services/published_asset_refs.py` (~275), `backend/src/sales_trainer/path_config_api.py` (~254). This is mostly pre-existing structure, but the diff adds governance behavior into already-large files. Not a blocker for G008; follow-up split should be planned before adding more responsibilities.

## Verification Run By Reviewer

- `git diff --check`: PASS.
- Backend focused gate:
  - Command: `cd backend && venv/bin/python -m pytest tests/unit/test_sales_trainer_asset_revision_service.py tests/unit/test_newcomer_training_path_config_revision.py tests/integration/test_newcomer_training_path_config_api.py tests/integration/test_newcomer_training_path_regrade_api.py tests/integration/test_newcomer_training_path_audio_regrade_api.py tests/unit/test_newcomer_training_path_papers.py tests/unit/test_newcomer_training_path_audio_lineage.py tests/unit/test_curriculum_runtime_snapshot_service.py tests/integration/test_curriculum_practice_session_snapshot.py tests/unit/test_practice_template_published_asset_refs.py tests/unit/common/test_alembic_migration_graph.py --no-cov`
  - Result: PASS, 59 passed, 2 warnings.
- Frontend typecheck:
  - Command: `cd web && npx tsc --noEmit`
  - Result: PASS.
- Frontend path-config tests:
  - Command: `cd web && npx vitest run src/app/admin/sales-trainer/paths/page.test.tsx src/app/admin/sales-trainer/paths/page-business-bindings.test.tsx src/app/admin/sales-trainer/paths/page-audio-bindings.test.tsx`
  - Result: first concurrent run timed out once in `page-business-bindings.test.tsx`; immediate standalone rerun PASS, 3 files / 9 tests passed. Treat as transient resource contention, not a stable regression.

## Evidence Inspected

- `.omo/ulw-loop/evidence/phase-6-path-config-governance-api.txt`
- `.omo/ulw-loop/evidence/phase-6-path-config-governance-unit.txt`
- `.omo/ulw-loop/evidence/phase-6-regrade-append-only-api.txt`
- `.omo/ulw-loop/evidence/phase-7-focused-backend.txt`
- `.omo/ulw-loop/evidence/phase-7-focused-frontend-tsc.txt`
- `.omo/ulw-loop/evidence/phase-7-focused-frontend-vitest.txt`
- `.omo/ulw-loop/evidence/phase-7-git-diff-check.txt`
- `.omo/ulw-loop/evidence/phase-4-path-config-browser-screenshot.txt`
- `.omo/ulw-loop/evidence/phase-4-path-config-admin-desktop.png`
- `.omo/ulw-loop/evidence/phase-4-path-config-admin-mobile.png`
- `.omo/ulw-loop/evidence/phase-4-path-config-admin-mobile-action.png`

## Residual Risk

- Full release gate was not rerun in this review; only the focused G008 gates were rerun.
- The frontend vitest timeout under concurrent load should be watched in CI. If it repeats, split the slow path-config test or raise timeout only with a clear reason.
- `examiner_question_refs` are now runtime-protected, but publish-time validation could still be moved earlier for better operator feedback.
- Several changed files are already large; future changes should split by responsibility rather than keep growing the same service/page modules.
