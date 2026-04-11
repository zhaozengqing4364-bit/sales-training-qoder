---
id: T02
parent: S03
milestone: M017
key_files:
  - backend/src/presentation_coach/api/presentations.py
  - backend/tests/contract/test_presentations.py
  - backend/tests/integration/test_presentation_flow.py
  - .gsd/KNOWLEDGE.md
key_decisions:
  - Use a per-request `get_db` override on a shared file-backed SQLite engine for truthful concurrent presentation-replace proofs; the shared `backend/tests/conftest.py::async_client` fixture is not valid for race reproduction because it reuses one `AsyncSession` across requests.
duration: 
verification_result: passed
completed_at: 2026-04-11T22:04:45.170Z
blocker_discovered: false
---

# T02: Added a focused concurrent-replace proof that confirms in-place presentation replace has a real writer race and updated the code-adjacent discovery inventory with the observed failure mode and next mitigation.

**Added a focused concurrent-replace proof that confirms in-place presentation replace has a real writer race and updated the code-adjacent discovery inventory with the observed failure mode and next mitigation.**

## What Happened

I started from the T01 inventory and wrote two new task-level proofs: a tighter contract assertion in `backend/tests/contract/test_presentations.py` and a focused concurrent replace integration proof in `backend/tests/integration/test_presentation_flow.py`. The first red run exposed a misleading harness behavior: the shared `backend/tests/conftest.py::async_client` fixture injects one `AsyncSession` into both requests, so concurrent API calls there can fail for shared-session reasons before they say anything truthful about route-level races. I preserved that finding in `.gsd/KNOWLEDGE.md`, then rebuilt the integration proof with a per-request `get_db` override backed by a shared file-based SQLite database so each replace request had its own real session.

With that corrected harness, the focused proof showed the actual replace race: two concurrent `/api/v1/presentations/{id}/replace` writers can both pass the active-session preflight and enter the version-2 path; the faster writer commits `version_number=2`, while the delayed writer falls into the global 500 fallback during page rebuild because `pages(presentation_id, page_number)` collides. I wrote that observed failure mode back into `backend/src/presentation_coach/api/presentations.py` by upgrading `PRESENTATION_RESOURCE_RACE_INVENTORY` from `needs_focused_proof` to `confirmed_concurrent_writer_race`, and by adding the concrete recommendation to serialize in-place replace with a compare-and-swap or lock before any broader multi-writer rollout. The upload surface remains inventory-only, and the delete surface remains a separately confirmed route-guard gap rather than an imagined lock issue.

This task did not implement locking or retry logic. It only converted the highest-priority suspicion into a code-adjacent, test-backed discovery conclusion that future agents can cite directly.

## Verification

Fresh task-plan verification passed with `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_presentations.py backend/tests/integration/test_presentation_flow.py backend/tests/integration/test_presentation_delete_permissions.py -x -q`, which finished 11/11 green. That run covers the new contract conclusion, the focused concurrent replace proof, the existing replace/delete presentation flow coverage, and the delete-permission boundary proof. I also ran fresh LSP diagnostics on `backend/src/presentation_coach/api/presentations.py`, `backend/tests/contract/test_presentations.py`, and `backend/tests/integration/test_presentation_flow.py`; all three reported no diagnostics.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_presentations.py backend/tests/integration/test_presentation_flow.py backend/tests/integration/test_presentation_delete_permissions.py -x -q` | 0 | ✅ pass | 4220ms |

## Deviations

I slightly widened the planner’s test-file scope into a small writeback in `backend/src/presentation_coach/api/presentations.py` because T01 had already established the code-adjacent inventory as the canonical discovery artifact, and the focused proof result needed to be recorded there to actually distinguish confirmed races from audit guesses. I also replaced the default shared-session `async_client` harness with a per-request session override inside the focused integration proof after the first red run showed that the default fixture was only reproducing shared-session commit contention, not the route’s real concurrent conflict surface.

## Known Issues

Concurrent in-place replace is still unmitigated in production: the loser of the reproduced race still falls into the generic 500 fallback instead of a structured conflict response, and the focused proof emits an `SAWarning` because the stale writer tries to delete a page row the winner already removed. The delete route still has no live-session blocker and still does not remove stored PPT/thumbnail artifacts.

## Files Created/Modified

- `backend/src/presentation_coach/api/presentations.py`
- `backend/tests/contract/test_presentations.py`
- `backend/tests/integration/test_presentation_flow.py`
- `.gsd/KNOWLEDGE.md`
