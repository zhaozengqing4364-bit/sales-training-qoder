---
id: T03
parent: S01
milestone: M017
key_files:
  - backend/tests/unit/test_session_lifecycle_service.py
  - backend/tests/integration/test_session_lifecycle_api.py
  - .gsd/KNOWLEDGE.md
key_decisions:
  - Kept the lifecycle concurrency contract adjacent to the focused unit/integration proofs so the repo-root pytest command remains the durable regression entrypoint for future slices.
  - Stubbed `PresentationCoachService.end_session()` in the new presentation terminal-split API proof so the test isolates lifecycle terminal semantics from the pre-existing timezone-mismatch bug in the presentation coach service.
duration: 
verification_result: passed
completed_at: 2026-04-11T21:15:30.810Z
blocker_discovered: false
---

# T03: Documented the lifecycle concurrency contract in focused tests and added a presentation terminal-split proof.

**Documented the lifecycle concurrency contract in focused tests and added a presentation terminal-split proof.**

## What Happened

I turned the stale-writer lifecycle behavior from implicit knowledge into explicit focused-test contract text in both lifecycle proof files. `backend/tests/unit/test_session_lifecycle_service.py` now carries a `LIFECYCLE_CONCURRENCY_CONTRACT` block that states why this slice stays on optimistic compare-and-swap instead of row locks, which race scenarios are intentionally converged (`sales_end_beats_stale_resume`, `presentation_end_beats_stale_pause`), which terminal statuses are intentionally different by scenario (`sales -> scoring`, `presentation -> completed`), and what repo-root pytest command remains the long-term regression entrypoint. I added unit assertions that bind those statements back to the real race catalog and `SessionLifecycleService.terminal_status_for_scenario(...)` so the contract is executable instead of comment-only.

On the API side, `backend/tests/integration/test_session_lifecycle_api.py` now carries a matching `LIFECYCLE_API_CONCURRENCY_CONTRACT` block plus a dedicated proof that presentation `end` settles directly to `completed` while sales keeps the `scoring` handoff semantics documented elsewhere. During TDD I first added contract assertions without the constants and verified the red `NameError` failure, then added the contract constants and the new proof until the targeted subset and full focused lifecycle suite both passed. I also appended the presentation timestamp gotcha to `.gsd/KNOWLEDGE.md` so future agents do not mistake the existing aware/naive `PresentationCoachService.end_session()` issue for a lifecycle concurrency regression.

## Verification

I followed a red-green flow for the new contract checks: the first targeted run failed with `NameError` because the contract constants were not defined yet, which confirmed the new assertions were live. After adding the contract text and the presentation terminal-split proof, I reran the focused contract subset and it passed. I then reran the full task-plan verification command (`backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_session_lifecycle_service.py backend/tests/integration/test_session_lifecycle_api.py -x -q`) and it passed at `27 passed`. LSP diagnostics on both touched Python test files returned `No diagnostics`. The focused pytest commands still emit the pre-existing pytest-cov no-data warnings, the passlib `crypt` deprecation warning, and the existing `Connection._cancel` runtime warning in the idempotent-end integration test, but no new failures were introduced.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_session_lifecycle_service.py backend/tests/integration/test_session_lifecycle_api.py -k 'contract_documents or terminal_split or presentation_completes_without_scoring_handoff' -q` | 0 | ✅ pass | 3105ms |
| 2 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_session_lifecycle_service.py backend/tests/integration/test_session_lifecycle_api.py -x -q` | 0 | ✅ pass | 3846ms |
| 3 | `rg -n "LIFECYCLE_CONCURRENCY_CONTRACT|LIFECYCLE_API_CONCURRENCY_CONTRACT|presentation_completes_without_scoring_handoff" backend/tests/unit/test_session_lifecycle_service.py backend/tests/integration/test_session_lifecycle_api.py .gsd/KNOWLEDGE.md` | 0 | ✅ pass | 35ms |

## Deviations

I initially tried to prove the presentation `end -> completed` contract through the real `PresentationCoachService.end_session()` path, but that surfaced a pre-existing aware/naive timestamp mismatch unrelated to lifecycle concurrency. To keep this task focused on lifecycle semantics rather than duration math in another module, I narrowed the new presentation API proof by stubbing the coach-service collaborator to a stable terminal result.

## Known Issues

The underlying `PresentationCoachService.end_session()` timezone-mismatch behavior in the SQLite-backed test environment remains unfixed and is now documented in `.gsd/KNOWLEDGE.md`. Existing focused-suite warnings also remain: pytest-cov reports `Module src was never imported` / `No data was collected`, passlib emits a `crypt` deprecation warning, and `test_lifecycle_api_end_is_idempotent_and_logs_unified_terminal_context` still triggers the pre-existing `RuntimeWarning: coroutine 'Connection._cancel' was never awaited` while the suite exits 0.

## Files Created/Modified

- `backend/tests/unit/test_session_lifecycle_service.py`
- `backend/tests/integration/test_session_lifecycle_api.py`
- `.gsd/KNOWLEDGE.md`
