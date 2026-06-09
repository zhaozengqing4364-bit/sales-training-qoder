# Goal Evidence: Support Runtime Quality Gate Recovery

Timestamp: 2026-06-04T10:46:19+08:00

Scope:

- Fixed the quality-gate blocker in `tests/integration/test_support_runtime_api.py::test_support_role_can_read_release_health_overview_and_faults`.
- Kept legacy/missing Roleplay Contract sessions visible in the roleplay summary without counting every legacy-compatible session as a release-blocking fault.
- Fixed the smoke `training entry` watcher so navigation away from the dashboard does not count already-aborted dashboard background requests as `/training` failures.

Red evidence:

- `cd backend && venv/bin/python -m pytest tests/unit/test_support_runtime_roleplay_faults.py -q --no-cov`
- Failed before production change with `AssertionError: assert 'roleplay_contract_missing' not in {'roleplay_contract_missing'}`.
- `bash scripts/critical-quality-gate.sh` failed before the fix with `overview["release_health"]["blocking_count"] == 6`, expected `3`.
- The next quality-gate run failed in Playwright `training entry smoke` because dashboard background requests were aborted during navigation.

Green evidence:

- `cd backend && venv/bin/python -m pytest tests/unit/test_support_runtime_roleplay_faults.py tests/integration/test_support_runtime_api.py::test_support_role_can_read_release_health_overview_and_faults -q --no-cov`
- Result: `2 passed, 1 warning`.
- `cd backend && venv/bin/python -m pytest tests/unit/test_support_runtime_service.py tests/unit/test_support_runtime_roleplay_faults.py tests/integration/test_support_runtime_api.py -q --no-cov`
- Result: `19 passed, 1 warning`.
- `cd backend && venv/bin/ruff check src/support/services/runtime_status_service.py src/support/services/runtime_roleplay_faults.py tests/unit/test_support_runtime_roleplay_faults.py`
- Result: `All checks passed!`
- `cd web && npx tsc --noEmit`
- Result: passed.
- `bash scripts/critical-quality-gate.sh`
- Result: `Critical quality gate passed`.

Quality-gate details:

- Web typecheck passed.
- Vitest smoke coverage suite passed: `16 files / 160 tests`.
- Playwright smoke passed: `9 passed`, including `training entry smoke`.
- Presentation Phase 4 E2E passed: `2 passed`.
- Sales Phase 4 E2E passed: `1 passed`.
- Backend gate passed: `113 passed, 1 warning`.
- Backend smoke regression passed: `58 passed, 1 warning`.

Remaining:

- This evidence does not complete the full published-governance revision objective.
- Browser old/new revision isolation, AI prompt isolation, path rollback future-only semantics, audit/regrade browser proof, and full completion audit remain active.
