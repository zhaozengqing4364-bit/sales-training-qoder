---
id: T01
parent: S03
milestone: M017
key_files:
  - backend/src/presentation_coach/api/presentations.py
  - backend/tests/contract/test_presentations.py
  - backend/tests/integration/test_presentation_flow.py
  - .gsd/DECISIONS.md
  - .gsd/KNOWLEDGE.md
key_decisions:
  - D201 — keep presentation upload/resource-race discovery code-adjacent in `backend/src/presentation_coach/api/presentations.py` and prioritize reproducing concurrent in-place replace before adding broad lock/distributed-lock work.
duration: 
verification_result: passed
completed_at: 2026-04-11T21:54:03.814Z
blocker_discovered: false
---

# T01: Added a code-adjacent presentation race inventory and focused proofs that lock concurrent in-place replace as the next target while proving delete currently lacks a route-level live-session blocker.

**Added a code-adjacent presentation race inventory and focused proofs that lock concurrent in-place replace as the next target while proving delete currently lacks a route-level live-session blocker.**

## What Happened

I traced the live presentation mutation authority in `backend/src/presentation_coach/api/presentations.py` and wrote the discovery result back next to the runtime code as `PRESENTATION_RESOURCE_RACE_INVENTORY` plus `PRESENTATION_RESOURCE_RACE_FOCUS`. That inventory now separates three surfaces: new uploads are mostly isolated by fresh storage keys and atomic writes, in-place replace is the first concurrent-writer proof target because it mutates the stable `presentation_id` after only a read-then-write active-session preflight, and delete is an already-confirmed guard gap because the route only checks ownership/admin permission.

I locked that discovery seam with one focused contract assertion and one focused integration proof. The contract test now keeps the inventory categories and recommended next proof stable for later agents. The new integration test proves the current delete behavior directly: after creating a live presentation session, deleting the presentation still returns 204 and the session row remains persisted with its `presentation_id` detached to `None` in the shared test harness. I also recorded the pattern/priority choice in D201 and saved the non-obvious delete-path gotcha in `.gsd/KNOWLEDGE.md` so downstream work can start T02 from the real race surface instead of re-auditing the same routes.

## Verification

Fresh backend verification passed on the touched presentation authority and proof files. `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_presentations.py backend/tests/integration/test_presentation_flow.py -q` finished 9/9 green, covering the existing replace contract/integration behavior plus the new discovery-focused inventory and delete guard-gap proof. The exact task-plan grep gate, `rg -n "replace|upload|delete|active-session|lock" backend/src/presentation_coach/api/presentations.py backend/tests/contract/test_presentations.py backend/tests/integration/test_presentation_flow.py`, returned the expected inventory/proof lines. Fresh LSP diagnostics on `backend/src/presentation_coach/api/presentations.py`, `backend/tests/contract/test_presentations.py`, and `backend/tests/integration/test_presentation_flow.py` reported no issues.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_presentations.py backend/tests/integration/test_presentation_flow.py -q` | 0 | ✅ pass | 3665ms |
| 2 | `rg -n "replace|upload|delete|active-session|lock" backend/src/presentation_coach/api/presentations.py backend/tests/contract/test_presentations.py backend/tests/integration/test_presentation_flow.py` | 0 | ✅ pass | 23ms |

## Deviations

I slightly widened the planned inventory-only writeback into one focused delete-path proof in `backend/tests/integration/test_presentation_flow.py` because the live route code showed no session-state preflight on delete, and the slice goal required separating covered surfaces from already-observable guard gaps.

## Known Issues

Concurrent in-place replace without active sessions is still unproved and remains the highest-priority T02 target. The delete handler still has no route-level live-session blocker and still does not remove stored PPT/thumbnail artifacts; the new focused proof shows that, in the shared integration harness, delete can detach a live session from its presentation authority.

## Files Created/Modified

- `backend/src/presentation_coach/api/presentations.py`
- `backend/tests/contract/test_presentations.py`
- `backend/tests/integration/test_presentation_flow.py`
- `.gsd/DECISIONS.md`
- `.gsd/KNOWLEDGE.md`
