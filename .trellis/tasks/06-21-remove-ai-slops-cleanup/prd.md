# remove-ai-slops-cleanup

## Goal

Clean AI-generated slop from the current uncommitted working-tree changes while preserving behavior. The default `merge-base main..HEAD` scope is empty because the work is currently on `main`; the practical scope is the dirty working tree.

## Requirements

* Use the `omo:remove-ai-slops` process.
* Lock behavior with existing regression tests before cleanup.
* Filter out generated, vendored, binary, lockfile, `.omo/`, and Trellis task files.
* Preserve public APIs, type hints, error handling at boundaries, security checks, and audit/contract behavior.
* Do not rewrite unrelated files.
* Do not introduce new dependencies or abstractions.

## Acceptance Criteria

* [ ] Final source scope is listed.
* [ ] Baseline relevant tests are green before cleanup.
* [ ] Cleanup plan lists file, categories, order, and risk.
* [ ] Any oversized source file over 250 pure LOC has a split plan before execution.
* [ ] Cleanup diffs are behavior-preserving and minimal.
* [ ] Relevant tests, lint, type/security checks pass after cleanup.

## Definition of Done

* Regression tests pass before and after cleanup.
* Ruff / typecheck / security scan status is reported.
* Final report lists per-file cleanup and skipped items.
* Remaining oversized-module work is either completed or explicitly deferred by user decision.

## Technical Approach

1. Determine scope from dirty working-tree source files because branch diff is empty.
2. Run baseline tests that already covered the changed areas.
3. Identify slop categories per file.
4. For oversized modules, present split plan before code edits.
5. Execute only the approved, behavior-preserving cleanup.

## Current Scope

Dirty source/document files after filtering:

* `CONTEXT.md`
* `backend/pyproject.toml`
* `backend/requirements.txt`
* `backend/src/admin/api/release_verification.py`
* `backend/src/common/analytics/release_verification_service.py`
* `backend/src/common/analytics/verification_runner.py`
* `backend/src/curriculum_practice/services/asset_resolution.py`
* `backend/src/curriculum_practice/services/frozen_asset_refs.py`
* `backend/src/curriculum_practice/services/published_asset_refs.py`
* `backend/src/curriculum_practice/services/publishing_gates.py`
* `backend/src/curriculum_practice/services/snapshots.py`
* `backend/src/presentation_coach/websocket/presentation_stepfun_realtime_handler.py`
* `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
* `backend/src/sales_trainer/path_config_api.py`
* `backend/src/sales_trainer/schemas.py`
* `backend/src/sales_trainer/services/asset_revision_service.py`
* `backend/src/sales_trainer/services/exam_paper_revision_payloads.py`
* `backend/src/sales_trainer/services/path_config_service.py`
* `backend/src/sales_trainer/services/quiz_attempt_payloads.py`
* `backend/tests/contract/test_release_verification_contract.py`
* `backend/tests/integration/test_curriculum_practice_session_snapshot.py`
* `backend/tests/integration/test_newcomer_training_path_config_api.py`
* `backend/tests/integration/test_release_gate.py`
* `backend/tests/unit/test_curriculum_runtime_snapshot_service.py`
* `backend/tests/unit/test_newcomer_training_path_audio_lineage.py`
* `backend/tests/unit/test_newcomer_training_path_config_revision.py`
* `backend/tests/unit/test_newcomer_training_path_papers.py`
* `backend/tests/unit/test_practice_template_published_asset_refs.py`
* `backend/tests/unit/test_presentation_stepfun_realtime_handler.py`
* `backend/tests/unit/test_sales_trainer_asset_revision_service.py`
* `backend/tests/unit/test_verification_runner.py`
* `docs/adr/2026-05-11-curriculum-practice-boundary-contract.md`
* `docs/api-contract/release-verification.md`
* `docs/api-contract/sales-trainer.md`
* `docs/architecture/config-asset-center.md`
* `web/tests/e2e/smoke.spec.ts`

## Oversized Source Split Candidates

These source/test files exceed 250 pure LOC and require user approval before modular refactoring:

* `backend/src/sales_trainer/schemas.py` — split DTO groups by domain: path config, assets/materials, quiz/exam/audio, admin projections.
* `backend/src/common/analytics/verification_runner.py` — split runners by concern: test execution, security scans, quality gate parsing, result persistence.
* `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` — split authentication/session lifecycle, message handling, transcript persistence, StepFun event routing.
* `backend/tests/unit/test_newcomer_training_path_papers.py` — split by payload lineage, paper revision, learner/admin projection.
* `backend/src/common/analytics/release_verification_service.py` — split default check definitions, summary/recommendation building, quality gate decision logic.
* `backend/src/sales_trainer/services/path_config_service.py` — split revision lifecycle, validation, public projection, admin commands.
* `backend/tests/unit/test_newcomer_training_path_audio_lineage.py` — split by audio lineage and asset revision scenario.
* `backend/src/presentation_coach/websocket/presentation_stepfun_realtime_handler.py` — split persistence helpers, event emitters, policy/page requirement loading.
* `backend/src/curriculum_practice/services/snapshots.py` — split snapshot building, linked asset resolution, evidence serialization.
* `backend/tests/unit/test_curriculum_runtime_snapshot_service.py` — split runtime snapshot, linked asset, fallback scenarios.
* `backend/tests/integration/test_newcomer_training_path_config_api.py` — split CRUD, publish/revision, learner projection.
* `backend/tests/integration/test_curriculum_practice_session_snapshot.py` — split session snapshot and publishing lineage flows.
* `backend/tests/unit/test_verification_runner.py` — split runner execution, security scans, quality gate tests.
* `backend/tests/unit/test_presentation_stepfun_realtime_handler.py` — split auth, text routing, persistence seams.
* `backend/tests/contract/test_release_verification_contract.py` — split default checks, API schema, decision contract.
* `backend/src/admin/api/release_verification.py` — split request/response schemas, release candidate endpoints, decision endpoints.
* `backend/tests/integration/test_release_gate.py` — split gate defaults, blocking decisions, warning decisions.
* `web/tests/e2e/smoke.spec.ts` — split auth/navigation smoke, practice/report/replay smoke, admin/support smoke.
* `backend/src/curriculum_practice/services/publishing_gates.py` — split gate evaluation helpers from public service surface if approved.
* `backend/tests/unit/test_newcomer_training_path_config_revision.py` — split config revision and publish behavior.
* `backend/src/sales_trainer/services/asset_revision_service.py` — split revision fetch/selection from mutation workflows.
* `backend/tests/unit/test_practice_template_published_asset_refs.py` — split template refs and published asset scenarios.
* `backend/src/curriculum_practice/services/published_asset_refs.py` — split reference collection from serialization.
* `backend/src/sales_trainer/path_config_api.py` — split schemas/routes or route groups if approved.

## Out of Scope Unless Confirmed

* Large module/test splitting for the files above.
* Algorithmic rewrites that need proof beyond existing tests.
* Cleaning unrelated existing slop outside the dirty working tree.

## Technical Notes

* `check-no-excuse-rules.py` was not found in this repository; pure LOC was measured with the `awk` rule from the skill.
* Baseline from the previous review run: `bash scripts/critical-quality-gate.sh` passed before this cleanup task.
