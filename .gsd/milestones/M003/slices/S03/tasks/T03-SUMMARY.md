---
id: T03
parent: S03
milestone: M003
provides: []
requires: []
affects: []
key_files: ["backend/src/common/conversation/session_evidence.py", "backend/tests/unit/test_session_evidence_service.py", "web/src/hooks/use-practice-websocket.ts", "web/src/hooks/use-practice-websocket.test.ts", "web/src/components/practice/RightPanelContent.tsx", "web/src/components/practice/RightPanelContent.test.tsx", ".gsd/DECISIONS.md"]
key_decisions: ["Prefer the latest open transcript-metadata objection ledger over generic sales score-stage alignment when projecting `main_issue` and `next_goal`.", "Treat `actionCard` and `fuzzyDetections` as reconnect-unsafe turn hints, but preserve `scores.suggestions` as the durable learner-side proof prompt that can survive reconnect."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Ran a focused backend projection regression to prove the latest open objection ledger now overrides generic sales alignment on the shared session-evidence path, then ran the slice-plan web gate to prove the practice websocket reducer and right-panel component keep the proof prompt visible while reconnect cleanup drops stale action-card/fuzzy state. Commands: `cd backend && /usr/bin/time -p venv/bin/python -m pytest -c pyproject.toml tests/unit/test_session_evidence_service.py -k 'latest_open_objection_ledger or preserves_insufficient_sales_evidence_fallback'`; `cd web && /usr/bin/time -p npm test -- --run 'src/hooks/use-practice-websocket.test.ts' 'src/components/practice/RightPanelContent.test.tsx'`."
completed_at: 2026-03-25T04:16:44.584Z
blocker_discovered: false
---

# T03: Surfaced unresolved objection proof gaps in report projection and the practice panel without replaying stale reconnect hints.

> Surfaced unresolved objection proof gaps in report projection and the practice panel without replaying stale reconnect hints.

## What Happened
---
id: T03
parent: S03
milestone: M003
key_files:
  - backend/src/common/conversation/session_evidence.py
  - backend/tests/unit/test_session_evidence_service.py
  - web/src/hooks/use-practice-websocket.ts
  - web/src/hooks/use-practice-websocket.test.ts
  - web/src/components/practice/RightPanelContent.tsx
  - web/src/components/practice/RightPanelContent.test.tsx
  - .gsd/DECISIONS.md
key_decisions:
  - Prefer the latest open transcript-metadata objection ledger over generic sales score-stage alignment when projecting `main_issue` and `next_goal`.
  - Treat `actionCard` and `fuzzyDetections` as reconnect-unsafe turn hints, but preserve `scores.suggestions` as the durable learner-side proof prompt that can survive reconnect.
duration: ""
verification_result: passed
completed_at: 2026-03-25T04:16:44.585Z
blocker_discovered: false
---

# T03: Surfaced unresolved objection proof gaps in report projection and the practice panel without replaying stale reconnect hints.

**Surfaced unresolved objection proof gaps in report projection and the practice panel without replaying stale reconnect hints.**

## What Happened

I kept the change on the existing surfaces instead of inventing a new objection UI or report schema. On the read-side, `SessionEvidenceService` now scans the normalized message transcript metadata for the latest persisted `objection_ledger`; when the latest ledger is still open, it overrides the usual sales score/stage alignment and rewrites the existing `main_issue` / `next_goal` fields with objection-family-specific proof-gap text. That keeps replay/report/history-style consumers on the same contract while making the final blocker visible when score alignment would otherwise drift back to a generic closing gap.

On the learner runtime side, I tightened `usePracticeWebSocket` reconnect cleanup so abnormal disconnects clear only transient turn hints (`actionCard` and `fuzzyDetections`) while preserving the durable score payload and its objection-proof suggestion. Then I updated `RightPanelContent` to surface that proof prompt inside the existing action-card surface as a fourth sub-block, so the user can still see the concrete evidence request that is blocking progress without opening a separate objection panel or re-enabling the full suggestions section.

I followed a red-green loop around the three seams that were actually missing: a backend unit regression proving open objection ledgers beat generic closing alignment, a websocket reconnect test proving stale turn hints are dropped while the proof prompt survives, and a panel test proving the prompt is visible even when the one-action-card rule is active. After the implementation, the backend projection test and the slice’s planned web gate both passed cleanly.

## Verification

Ran a focused backend projection regression to prove the latest open objection ledger now overrides generic sales alignment on the shared session-evidence path, then ran the slice-plan web gate to prove the practice websocket reducer and right-panel component keep the proof prompt visible while reconnect cleanup drops stale action-card/fuzzy state. Commands: `cd backend && /usr/bin/time -p venv/bin/python -m pytest -c pyproject.toml tests/unit/test_session_evidence_service.py -k 'latest_open_objection_ledger or preserves_insufficient_sales_evidence_fallback'`; `cd web && /usr/bin/time -p npm test -- --run 'src/hooks/use-practice-websocket.test.ts' 'src/components/practice/RightPanelContent.test.tsx'`.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend && /usr/bin/time -p venv/bin/python -m pytest -c pyproject.toml tests/unit/test_session_evidence_service.py -k 'latest_open_objection_ledger or preserves_insufficient_sales_evidence_fallback'` | 0 | ✅ pass | 5720ms |
| 2 | `cd web && /usr/bin/time -p npm test -- --run 'src/hooks/use-practice-websocket.test.ts' 'src/components/practice/RightPanelContent.test.tsx'` | 0 | ✅ pass | 1150ms |


## Deviations

Added focused backend regression coverage in `backend/tests/unit/test_session_evidence_service.py` beyond the task-plan file list, because the read-side carry-forward change needed an explicit shared-projection proof even though the planner’s verification line only listed the web gate.

## Known Issues

None.

## Files Created/Modified

- `backend/src/common/conversation/session_evidence.py`
- `backend/tests/unit/test_session_evidence_service.py`
- `web/src/hooks/use-practice-websocket.ts`
- `web/src/hooks/use-practice-websocket.test.ts`
- `web/src/components/practice/RightPanelContent.tsx`
- `web/src/components/practice/RightPanelContent.test.tsx`
- `.gsd/DECISIONS.md`


## Deviations
Added focused backend regression coverage in `backend/tests/unit/test_session_evidence_service.py` beyond the task-plan file list, because the read-side carry-forward change needed an explicit shared-projection proof even though the planner’s verification line only listed the web gate.

## Known Issues
None.
