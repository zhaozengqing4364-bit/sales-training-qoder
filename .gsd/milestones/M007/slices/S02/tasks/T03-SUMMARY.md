---
id: T03
parent: S02
milestone: M007
provides: []
requires: []
affects: []
key_files: ["backend/tests/contract/test_practice_evidence_contract.py", "backend/tests/integration/test_practice_evidence_flow.py", "web/src/app/(user)/practice/[sessionId]/report/page.test.tsx", "web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx"]
key_decisions: ["Assert completed report/replay parity by stripping replay-only `replay_anchor` decoration before comparison, while separately proving the anchor stays present on replay.", "Lock the scoring-to-completed transition as a same-session contract: report remains readable during scoring, replay stays blocked until completion, and frontend report UI must still render canonical issue/goal/claim-truth copy when replay is unavailable.", "Use conflicting report snapshot fixtures in replay-page tests to prove the page renders canonical replay projection data instead of inventing a second authority."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Ran the exact task-plan verification commands after updating the focused backend and frontend suites. The backend command passed with 15 targeted contract/integration tests, including the new same-session scoring-to-completed parity coverage. The frontend command passed with 21 targeted report/replay page tests, including the new replay-locked report-state and conflicting-report-snapshot replay cases."
completed_at: 2026-03-28T08:10:13.030Z
blocker_discovered: false
---

# T03: Locked same-session report/replay parity with scoring-gate, replay-anchor, and frontend authority tests on the canonical projection.

> Locked same-session report/replay parity with scoring-gate, replay-anchor, and frontend authority tests on the canonical projection.

## What Happened
---
id: T03
parent: S02
milestone: M007
key_files:
  - backend/tests/contract/test_practice_evidence_contract.py
  - backend/tests/integration/test_practice_evidence_flow.py
  - web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
  - web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx
key_decisions:
  - Assert completed report/replay parity by stripping replay-only `replay_anchor` decoration before comparison, while separately proving the anchor stays present on replay.
  - Lock the scoring-to-completed transition as a same-session contract: report remains readable during scoring, replay stays blocked until completion, and frontend report UI must still render canonical issue/goal/claim-truth copy when replay is unavailable.
  - Use conflicting report snapshot fixtures in replay-page tests to prove the page renders canonical replay projection data instead of inventing a second authority.
duration: ""
verification_result: passed
completed_at: 2026-03-28T08:10:13.030Z
blocker_discovered: false
---

# T03: Locked same-session report/replay parity with scoring-gate, replay-anchor, and frontend authority tests on the canonical projection.

**Locked same-session report/replay parity with scoring-gate, replay-anchor, and frontend authority tests on the canonical projection.**

## What Happened

Audited the current report/replay seam and found the shipped runtime behavior already matched the slice intent; the remaining gap was proof, not business logic. Extended backend contract and integration coverage so one same session is exercised across the scoring-to-completed transition: report stays available while replay is blocked, then completed report and replay are compared on the same canonical family after unlock, with replay-only `replay_anchor` treated as decoration rather than divergent truth. Tightened the report page tests so a replay `[SESSION_NOT_COMPLETED]` failure leaves canonical issue/goal/claim-truth copy intact and disables replay jumps instead of degrading the report itself. Tightened the replay page tests so conflicting report snapshot copy cannot override canonical replay projection data, which closes the risk of inventing a second authority in page code.

## Verification

Ran the exact task-plan verification commands after updating the focused backend and frontend suites. The backend command passed with 15 targeted contract/integration tests, including the new same-session scoring-to-completed parity coverage. The frontend command passed with 21 targeted report/replay page tests, including the new replay-locked report-state and conflicting-report-snapshot replay cases.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_practice_evidence_contract.py backend/tests/integration/test_practice_evidence_flow.py` | 0 | ✅ pass | 4331ms |
| 2 | `npm test -- --run 'web/src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx'` | 0 | ✅ pass | 2023ms |


## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `backend/tests/contract/test_practice_evidence_contract.py`
- `backend/tests/integration/test_practice_evidence_flow.py`
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`
- `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx`


## Deviations
None.

## Known Issues
None.
