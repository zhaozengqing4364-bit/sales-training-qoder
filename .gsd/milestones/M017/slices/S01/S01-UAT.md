# S01: Session lifecycle 并发安全 proof — UAT

**Milestone:** M017
**Written:** 2026-04-11T21:19:54.405Z

# S01 UAT — Session lifecycle concurrency contract

## Preconditions
- Repository state includes the S01 lifecycle concurrency changes.
- Python dependencies are installed in `backend/venv`.
- Run commands from repo root: `/Users/zhaozengqing/github/销售训练qoder`.

## Test Case 1 — Sales `end` beats a stale `resume` without reopening the session
1. Run:
   ```bash
   backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_session_lifecycle_api.py -k "lifecycle_race_proof_preserves_terminal_status_against_stale_writer" -q
   ```
2. Wait for the focused integration proof to finish.
3. Inspect the selected test output.

**Expected outcome**
- Pytest exits `0`.
- The sales stale-writer proof passes and shows that once `end` has already persisted the sales terminal handoff (`scoring`), a stale `resume` writer converges to a no-op instead of reopening the session to `in_progress`.
- The stale writer should observe terminal state semantics rather than claiming a real state change.

## Test Case 2 — Presentation `end` still settles directly to `completed`, and a stale `pause` cannot reopen it
1. Run:
   ```bash
   backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_session_lifecycle_service.py backend/tests/integration/test_session_lifecycle_api.py -k "presentation_completes_without_scoring_handoff or lifecycle_race_proof_preserves_terminal_status_against_stale_writer or contract_documents" -q
   ```
2. Wait for completion.
3. Review the selected test names in the output.

**Expected outcome**
- Pytest exits `0`.
- The presentation API proof confirms `end` still settles directly to `completed` instead of borrowing the sales `scoring` handoff.
- The same focused bundle proves a stale `pause` writer cannot reopen a presentation session after `end` has already won.
- The contract-document tests keep the intentional terminal split visible in executable assertions, not just prose.

## Test Case 3 — Service-layer conflict handling distinguishes stale-writer convergence from fresh invalid transitions
1. Run:
   ```bash
   backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_session_lifecycle_service.py -k "stale_terminal_writer_converges_to_persisted_terminal_noop or fresh_terminal_resume_still_raises_invalid_transition" -q
   ```
2. Wait for completion.
3. Inspect the selected test names.

**Expected outcome**
- Pytest exits `0`.
- The stale-writer test proves the compare-and-swap path collapses the loser into `changed=False` once the durable row is already terminal.
- The fresh-transition test proves this slice did **not** soften real lifecycle validation: a normal resume against a terminal session still fails as an invalid transition.

## Test Case 4 — Full focused lifecycle gate stays green
1. Run the exact slice-plan verification command:
   ```bash
   backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_session_lifecycle_service.py backend/tests/integration/test_session_lifecycle_api.py -x -q
   ```
2. Wait for completion.

**Expected outcome**
- Pytest exits `0`.
- All focused lifecycle tests pass (`27 passed` on the current branch).
- The only acceptable noise is the known focused-run warning set: `pytest-cov` no-data warnings, the `passlib` `crypt` deprecation warning, and the pre-existing `Connection._cancel` runtime warning. No assertion failures or collection errors are allowed.

## Edge Cases To Confirm
- Sales and presentation intentionally keep different immediate terminal states: sales ends into `scoring`, presentation ends into `completed`.
- Only stale non-terminal writers that lost to an already-persisted terminal state are collapsed into no-ops; fresh invalid transitions are still rejected.
- If a presentation terminal-state proof fails because of timezone-aware vs naive timestamp math inside `PresentationCoachService.end_session()`, treat that as a separate coach-service duration bug, not immediate evidence that lifecycle terminal routing regressed.
- Lifecycle concurrency fixes must stay on the backend authority seam (`SessionLifecycleService` compare-and-swap / conflict resolution path), not drift into route-local debounce or websocket-only guards.
