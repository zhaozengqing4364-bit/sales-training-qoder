---
id: S06
parent: M003
milestone: M003
provides:
  - A sales-only background finalization seam that promotes replay-ready same-session sessions from `status="scoring"` to `completed` without weakening the public replay/highlights gate.
  - Fresh backend regression coverage for the immediate-scoring → background-completed → replay/highlights-unlocked boundary.
  - One live localhost same-session proof showing current report/replay/highlights routes all load truthful same-session evidence after finalization.
requires:
  - slice: S05
    provides: The accepted objection-heavy same-session proof boundary and the documented scoring/replay blocker this slice had to retire.
affects:
  []
key_files:
  - backend/src/evaluation/services/report_generation_trigger.py
  - backend/tests/unit/test_report_generation_trigger.py
  - backend/tests/integration/test_session_lifecycle_api.py
  - backend/tests/integration/test_replay_api.py
  - backend/tests/contract/test_practice_evidence_contract.py
  - .gsd/milestones/M003/slices/S06/S06-SUMMARY.md
  - .gsd/milestones/M003/slices/S06/S06-UAT.md
key_decisions:
  - Kept the shipped sales lifecycle contract intact: immediate `/lifecycle end` responses still return `status="scoring"` instead of changing the terminal-status rule.
  - Used `SessionEvidenceService` as the sole authority for replay-ready same-session sales finalization, rather than broadening replay/highlights to admit generic scoring sessions.
  - Allowed `session.status="completed"` and `report_status="failed"` to coexist when canonical same-session evidence is readable but optional enhanced-report generation still fails.
patterns_established:
  - Separate canonical availability (`session.status`) from optional enhancement health (`report_status`).
  - Prove status-boundary fixes in order: immediate response, persisted row before finalization, persisted row after finalization, then live same-session routes.
  - Keep replay/highlights strict for unfinished sessions; unlock by promoting the session truthfully, not by relaxing the gate.
observability_surfaces:
  - Immediate lifecycle end response from `POST /api/v1/practice/sessions/{id}/lifecycle`, proving the shipped `status="scoring"` contract still holds at session end.
  - Persisted `PracticeSession.status` / `report_status` reads before and after background finalization on the same session.
  - `sales_session_finalized` backend log with projection completeness and message count once canonical evidence is readable.
  - Live `GET /api/v1/practice/sessions/{id}/report`, `GET /api/v1/sessions/{id}/replay`, and `GET /api/v1/sessions/{id}/highlights` on the same session.
  - Browser-visible `/practice/{sessionId}/report` and `/practice/{sessionId}/replay` routes on `http://localhost:3445`.
drill_down_paths:
  - .gsd/milestones/M003/slices/S06/tasks/T01-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-03-27T13:12:27.130Z
blocker_discovered: false
---

# S06: scoring 收口与 replay/highlights 解锁

**Unlocked same-session replay/highlights after sales background finalization without changing the immediate `status="scoring"` end-session contract.**

## What Happened

S06 closed the blocker that S05 had isolated. Focused regressions first locked the intended boundary: sales lifecycle end must still return `status="scoring"` immediately; true unfinished sessions must keep failing replay/highlights with `[SESSION_NOT_COMPLETED]`; and same-session replay/highlights should only unlock after a separate background finalization step can read canonical same-session evidence. The implementation stayed narrow inside `ReportGenerationTrigger`: after the background report/finalization path runs, sales sessions still in `scoring` are re-checked through `SessionEvidenceService`, and only replay-ready sessions with readable canonical evidence and session-level score evidence are promoted to `completed`. Replay/highlights themselves were not relaxed.

Fresh verification then re-proved the full boundary on one localhost same session. Session `6a9e45d7-c15a-43c6-95cf-59583918780a` was created on the live API and opened on `/practice/{sessionId}`. Canonical same-session objection/evidence facts were seeded on that exact session, and the real lifecycle API still returned `status="scoring"` at end-of-session. A separate background finalization run with intentionally failing optional enhanced-report generation then changed the persisted row to `status="completed"` while `report_status` remained `failed`. After that transition, canonical report, replay, and highlights all loaded for that same session on both the live APIs and the learner report/replay pages. This retired the blocker that had kept same-session replay/highlights trapped behind persisted `status="scoring"` and moved the milestone from “report-readable but replay-blocked” to “same-session read surfaces all unlock truthfully.”

## Verification

Fresh focused verification passed on `tests/unit/test_report_generation_trigger.py`, `tests/integration/test_session_lifecycle_api.py`, `tests/integration/test_replay_api.py`, and `tests/contract/test_practice_evidence_contract.py` (`44 passed`). The accepted same-chain backend pack also reran green on `tests/unit/test_stepfun_realtime_handler.py`, `tests/unit/test_stepfun_knowledge_helpers.py`, `tests/integration/test_knowledge_flow.py`, `tests/integration/test_replay_api.py`, and `tests/contract/test_practice_evidence_contract.py` (`114 passed`).

Live localhost proof also passed on the exact same session: the immediate lifecycle end response returned `status="scoring"`, the persisted row later moved to `status="completed"` while `report_status="failed"`, `GET /api/v1/practice/sessions/{id}/report`, `GET /api/v1/sessions/{id}/replay`, and `GET /api/v1/sessions/{id}/highlights` all returned 200 on that same session, `/practice/{sessionId}/report` rendered the canonical same-session report body, and `/practice/{sessionId}/replay` rendered unlocked replay evidence with no `统一训练证据不可用` or `SESSION_NOT_COMPLETED` text. True unfinished sessions still remained behind `[SESSION_NOT_COMPLETED]`.

## Requirements Advanced

- R010 — Retired the remaining S05 blocker by proving the accepted same-session sales chain now crosses from immediate `status="scoring"` to background-finalized `status="completed"`, after which canonical report/replay/highlights all load on current routes.

## Requirements Validated

- R010 — Combined with S05’s live admin Persona/knowledge mutation proof, S06 now proves the full accepted M003 chain reaches same-session report/replay/highlights on truthful evidence instead of stopping at `[SESSION_NOT_COMPLETED]`.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

Used a fresh localhost same-session proof that seeded canonical evidence via the live database seam before lifecycle end/finalization, rather than re-running the full microphone-driven objection conversation. This kept the acceptance route family real while isolating the S06 scoring/finalization blocker.

## Known Limitations

Optional enhanced-report generation is still unhealthy on this localhost proof path (`[REPORT_NOT_FOUND]` / `[REPORT_GENERATION_FAILED]`), so learner report pages continue to show explicit fallback copy for that optional layer. This slice intentionally did not change that path because canonical report/replay/highlights are now unlocked independently.

## Follow-ups

Run milestone-level validation for M003 now that all roadmap slices are complete and DB/filesystem state is aligned, then decide whether milestone close-out can proceed directly.

## Files Created/Modified

- `backend/src/evaluation/services/report_generation_trigger.py` — Added a sales-only background finalization seam that promotes `status=scoring` to `completed` once `SessionEvidenceService` can read canonical same-session evidence, without coupling completion to optional enhanced-report success.
- `backend/tests/unit/test_report_generation_trigger.py` — Locked the new scoring-to-completed background finalization behavior in a focused unit regression.
- `backend/tests/integration/test_session_lifecycle_api.py` — Locked the two-stage contract: lifecycle end still returns `scoring` immediately, then background finalization can persist `completed` on the same session.
- `backend/tests/integration/test_replay_api.py` — Added same-session replay/highlights unlock coverage after background finalization while preserving the true in-progress completion gate.
- `backend/tests/contract/test_practice_evidence_contract.py` — Extended the practice evidence contract to prove the accepted same-session replay/highlights unlock and preserve the unchanged `[SESSION_NOT_COMPLETED]` gate for unfinished sessions.
