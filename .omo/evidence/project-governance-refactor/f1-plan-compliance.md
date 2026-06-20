# F1 Plan Compliance Audit

Date: 2026-06-20

## Commands

- `git diff --name-only`
- `git log --name-only --pretty=format:'commit %h %s' d4f233e6^..HEAD`
- `git status --short`

## Result

Task 1 through Task 24 were implemented as separate commits:

- Task 1: `d4f233e6` - alembic migration graph invariant.
- Task 2: `d9827ebe` - configurable surface and gate inventory.
- Task 3: `581515be` - newcomer completion rule contract alignment.
- Task 4: `9e07d1ed` - checkpoint evidence flow.
- Task 5: `0de93c71` - domain contributor bootstrap split.
- Task 6: `28c4689e` - runtime repair boundary split.
- Task 7: `f0518872` - backend runtime boundary ADR.
- Task 8: `e71d94d8` - sales trainer route registry.
- Task 9: `a0c624a5` - newcomer training API facade split.
- Task 10: `0aa9a440` - sales trainer API type partition.
- Task 11: `bf650e9e` - admin path config workflow extraction.
- Task 12: `040ee481` - business skills workflow extraction.
- Task 13: `0fda8cb2` - configurable surface inventory facade.
- Task 14: `d1f618c4` - prompt governance permission boundary.
- Task 15: `6a9a02ae` - AI coach model and scoring contract alignment.
- Task 16: `ccc1cf32` - runtime descriptor neutral boundary.
- Task 17: `cfb0ebd6` - roleplay shared contract primitives.
- Task 18: `2d984f54` - training task template lookup port.
- Task 19: `ea75e37b` - controlled cross-domain adapter policy.
- Task 20: `5e0a4cc6` - data-changing script safety inventory.
- Task 20b: `7371a12a` - newcomer seed explicit apply guard.
- Task 21: `7cd7dab4` - release truth gate integration branch alignment.
- Task 22: `524bebde` - release verification evidence bridge.
- Task 23: `4c2c4362` - learner public projection centralization.
- Task 24: `9e8dcc1a` - presentation realtime handler separated from sales runtime inheritance.

## Current Working Tree Diff Mapping

`git diff --name-only` reports the following uncommitted working-tree files. They are not part of the Task 1-24 committed slice and were not staged by this verification wave.

| File | Mapping |
| --- | --- |
| `CONTEXT.md` | External/uncommitted working-tree change outside this plan execution slice. |
| `backend/src/curriculum_practice/services/asset_resolution.py` | External/uncommitted working-tree change outside this plan execution slice. |
| `backend/src/curriculum_practice/services/frozen_asset_refs.py` | External/uncommitted working-tree change outside this plan execution slice. |
| `backend/src/curriculum_practice/services/published_asset_refs.py` | External/uncommitted working-tree change outside this plan execution slice. |
| `backend/src/curriculum_practice/services/publishing_gates.py` | External/uncommitted working-tree change outside this plan execution slice. |
| `backend/src/curriculum_practice/services/snapshots.py` | External/uncommitted working-tree change outside this plan execution slice. |
| `backend/src/sales_trainer/path_config_api.py` | External/uncommitted working-tree change outside this plan execution slice. |
| `backend/src/sales_trainer/schemas.py` | External/uncommitted working-tree change outside this plan execution slice. |
| `backend/src/sales_trainer/services/asset_revision_service.py` | External/uncommitted working-tree change outside this plan execution slice. |
| `backend/src/sales_trainer/services/exam_paper_revision_payloads.py` | External/uncommitted working-tree change outside this plan execution slice. |
| `backend/src/sales_trainer/services/path_config_service.py` | External/uncommitted working-tree change outside this plan execution slice. |
| `backend/src/sales_trainer/services/quiz_attempt_payloads.py` | External/uncommitted working-tree change outside this plan execution slice. |
| `backend/tests/integration/test_curriculum_practice_session_snapshot.py` | External/uncommitted working-tree change outside this plan execution slice. |
| `backend/tests/integration/test_newcomer_training_path_config_api.py` | External/uncommitted working-tree change outside this plan execution slice. |
| `backend/tests/unit/test_curriculum_runtime_snapshot_service.py` | External/uncommitted working-tree change outside this plan execution slice. |
| `backend/tests/unit/test_newcomer_training_path_audio_lineage.py` | External/uncommitted working-tree change outside this plan execution slice. |
| `backend/tests/unit/test_newcomer_training_path_config_revision.py` | External/uncommitted working-tree change outside this plan execution slice. |
| `backend/tests/unit/test_newcomer_training_path_papers.py` | External/uncommitted working-tree change outside this plan execution slice. |
| `backend/tests/unit/test_practice_template_published_asset_refs.py` | External/uncommitted working-tree change outside this plan execution slice. |
| `docs/adr/2026-05-11-curriculum-practice-boundary-contract.md` | External/uncommitted working-tree change outside this plan execution slice. |
| `docs/api-contract/sales-trainer.md` | External/uncommitted working-tree change outside this plan execution slice. |
| `docs/architecture/config-asset-center.md` | External/uncommitted working-tree change outside this plan execution slice. |
| `web/tests/e2e/smoke.spec.ts` | External/uncommitted working-tree change outside this plan execution slice. |

## Compliance Notes

- Each executed task has a corresponding evidence record under `.omo/evidence/project-governance-refactor/`.
- The final verification evidence files are the only new files intended for the final verification commit.
- Existing untracked planning, team, and Trellis artifacts remain uncommitted unless explicitly selected by a later task.
