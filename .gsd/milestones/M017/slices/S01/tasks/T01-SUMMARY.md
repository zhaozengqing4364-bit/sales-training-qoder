---
id: T01
parent: S01
milestone: M017
key_files:
  - backend/src/common/db/session_lifecycle.py
  - backend/tests/unit/test_session_lifecycle_service.py
  - backend/tests/integration/test_session_lifecycle_api.py
  - .gsd/KNOWLEDGE.md
key_decisions:
  - T01 only catalogs and proves terminal-regression races (`end` losing to stale `pause`/`resume`), leaving the actual convergence strategy choice to T02.
  - The race proof is kept as strict xfail after a verified red run so the suite stays usable while still carrying executable failing evidence.
duration: 
verification_result: passed
completed_at: 2026-04-11T20:57:17.643Z
blocker_discovered: false
---

# T01: Added lifecycle race catalog and strict xfail proofs for stale pause/resume reopening terminal sessions

**Added lifecycle race catalog and strict xfail proofs for stale pause/resume reopening terminal sessions**

## What Happened

I read `SessionLifecycleService` plus the existing unit/integration lifecycle tests, then narrowed the concurrency focus to the two highest-risk regressions: (1) a stale `resume` reopening a sales session after `end` already converged it to `scoring`, and (2) a stale `pause` reopening a presentation session after `end` already converged it to `completed`. To make that target explicit for downstream work, I added `SESSION_LIFECYCLE_RACE_SCENARIOS` to `backend/src/common/db/session_lifecycle.py` as the shared proof catalog. I added a unit-level catalog assertion in `backend/tests/unit/test_session_lifecycle_service.py` so future agents can see which transitions are intentionally prioritized. I then added a parameterized strict-`xfail` integration proof in `backend/tests/integration/test_session_lifecycle_api.py` that binds two independent `AsyncSession` instances to the same engine, loads the same `PracticeSession` row twice, commits `end` in one session, and then commits `pause`/`resume` from the stale session. Running that proof with `--runxfail` showed the current regressions exactly as expected: `scoring -> in_progress` for sales and `completed -> paused` for presentation. After preserving the proof as strict `xfail`, the focused lifecycle suite stays green while still carrying the concrete red evidence T02 needs to turn passing. I also appended the stale-writer reproduction pattern to `.gsd/KNOWLEDGE.md` so the next task can reuse the same harness directly.

## Verification

Verified the new proof in two modes. First, I ran the stale-writer proof with `--runxfail` to force the xfail test to fail normally and confirm the real race: the sales scenario reopened `scoring` back to `in_progress`, and the presentation scenario reopened `completed` back to `paused`. Second, I ran the focused lifecycle backend suite normally and confirmed it remains stable at `18 passed, 2 xfailed`, which preserves the failing proof without breaking the slice baseline. I also ran the task-plan `rg` verification and confirmed the new pause/resume/end/scoring/completed race catalog and proof references are present in the intended service and test files. LSP diagnostics for the touched Python files returned no issues.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_session_lifecycle_api.py -k 'lifecycle_race_proof_preserves_terminal_status_against_stale_writer' --runxfail -q` | 1 | ✅ pass (expected red proof exposed stale-writer regressions) | 2900ms |
| 2 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_session_lifecycle_service.py backend/tests/integration/test_session_lifecycle_api.py -q` | 0 | ✅ pass | 4130ms |
| 3 | `rg -n "pause|resume|end|scoring|completed" backend/src/common/db/session_lifecycle.py backend/tests/unit/test_session_lifecycle_service.py backend/tests/integration/test_session_lifecycle_api.py` | 0 | ✅ pass | 18ms |

## Deviations

Instead of leaving the repository in a permanently red state after proving the race, I converted the verified red proofs into `strict=True` xfail tests. This keeps T01 executable and preserves the evidence for T02 without blocking focused lifecycle verification.

## Known Issues

The focused pytest commands still emit existing repo-level warnings unrelated to this task: pytest-cov reports `Module src was never imported` / `No data was collected` on these focused runs, and the pre-existing `test_lifecycle_api_refreshes_live_session_activity_after_rest_transition` path emits a `RuntimeWarning: coroutine 'Connection._cancel' was never awaited` while the suite still exits 0. No new product blocker was introduced.

## Files Created/Modified

- `backend/src/common/db/session_lifecycle.py`
- `backend/tests/unit/test_session_lifecycle_service.py`
- `backend/tests/integration/test_session_lifecycle_api.py`
- `.gsd/KNOWLEDGE.md`
