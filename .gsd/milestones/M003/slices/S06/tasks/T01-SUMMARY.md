---
id: T01
parent: S06
milestone: M003
provides: []
requires: []
affects: []
key_files: ["backend/src/evaluation/services/report_generation_trigger.py", "backend/tests/unit/test_report_generation_trigger.py", "backend/tests/integration/test_session_lifecycle_api.py", "backend/tests/integration/test_replay_api.py", "backend/tests/contract/test_practice_evidence_contract.py", ".gsd/milestones/M003/slices/S06/S06-SUMMARY.md", ".gsd/milestones/M003/slices/S06/S06-UAT.md"]
key_decisions: ["Preserved the shipped sales lifecycle contract: immediate `/lifecycle end` responses still return `status="scoring"`.", "Used `SessionEvidenceService` as the authority for replay-ready finalization instead of broadening replay/highlights to admit generic scoring sessions.", "Allowed `session.status="completed"` and `report_status="failed"` to coexist when canonical same-session evidence is readable but optional enhanced-report generation still fails."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Fresh focused verification passed on `tests/unit/test_report_generation_trigger.py`, `tests/integration/test_session_lifecycle_api.py`, `tests/integration/test_replay_api.py`, and `tests/contract/test_practice_evidence_contract.py` (`44 passed`). The accepted same-chain backend pack also reran green on `tests/unit/test_stepfun_realtime_handler.py`, `tests/unit/test_stepfun_knowledge_helpers.py`, `tests/integration/test_knowledge_flow.py`, `tests/integration/test_replay_api.py`, and `tests/contract/test_practice_evidence_contract.py` (`114 passed`).

Live localhost proof also passed on the exact same session: the immediate lifecycle end response returned `status="scoring"`, the persisted row later moved to `status="completed"` while `report_status="failed"`, `GET /api/v1/practice/sessions/{id}/report`, `GET /api/v1/sessions/{id}/replay`, and `GET /api/v1/sessions/{id}/highlights` all returned 200 on that same session, `/practice/{sessionId}/report` rendered the canonical same-session report body, and `/practice/{sessionId}/replay` rendered unlocked replay evidence with no `统一训练证据不可用` or `SESSION_NOT_COMPLETED` text. True unfinished sessions still remained behind `[SESSION_NOT_COMPLETED]`."
completed_at: 2026-03-27T13:11:15.399Z
blocker_discovered: false
---

# T01: Unlocked same-session replay/highlights after sales background finalization without changing the immediate `status="scoring"` end-session contract.

> Unlocked same-session replay/highlights after sales background finalization without changing the immediate `status="scoring"` end-session contract.

## What Happened
---
id: T01
parent: S06
milestone: M003
key_files:
  - backend/src/evaluation/services/report_generation_trigger.py
  - backend/tests/unit/test_report_generation_trigger.py
  - backend/tests/integration/test_session_lifecycle_api.py
  - backend/tests/integration/test_replay_api.py
  - backend/tests/contract/test_practice_evidence_contract.py
  - .gsd/milestones/M003/slices/S06/S06-SUMMARY.md
  - .gsd/milestones/M003/slices/S06/S06-UAT.md
key_decisions:
  - Preserved the shipped sales lifecycle contract: immediate `/lifecycle end` responses still return `status="scoring"`.
  - Used `SessionEvidenceService` as the authority for replay-ready finalization instead of broadening replay/highlights to admit generic scoring sessions.
  - Allowed `session.status="completed"` and `report_status="failed"` to coexist when canonical same-session evidence is readable but optional enhanced-report generation still fails.
duration: ""
verification_result: passed
completed_at: 2026-03-27T13:11:15.400Z
blocker_discovered: false
---

# T01: Unlocked same-session replay/highlights after sales background finalization without changing the immediate `status="scoring"` end-session contract.

**Unlocked same-session replay/highlights after sales background finalization without changing the immediate `status="scoring"` end-session contract.**

## What Happened

T01 closed the last blocker from S05. The task first locked the intended boundary with focused regressions: sales lifecycle end must still return `status="scoring"` immediately; true unfinished sessions must keep failing replay/highlights with `[SESSION_NOT_COMPLETED]`; and same-session replay/highlights should only unlock after a separate background finalization step can read canonical same-session evidence. The implementation then stayed inside `ReportGenerationTrigger`: after the background report/finalization path runs, sales sessions still in `scoring` are re-checked through `SessionEvidenceService`, and only replay-ready sessions with readable canonical evidence and session-level scores are promoted to `completed`. Replay/highlights themselves were not relaxed.

Fresh verification then re-proved the boundary on one localhost same session. Session `6a9e45d7-c15a-43c6-95cf-59583918780a` was created on the live API and opened on `/practice/{sessionId}`. Canonical same-session objection/evidence facts were seeded on that exact session, and the real lifecycle API still returned `status="scoring"` at end-of-session. A separate background finalization run with intentionally failing optional enhanced-report generation then changed the persisted row to `status="completed"` while `report_status` remained `failed`. After that transition, canonical report, replay, and highlights all loaded for that same session on both the live APIs and the learner report/replay pages. This retired the blocker that had kept same-session replay/highlights trapped behind persisted `status="scoring"`.

## Verification

Fresh focused verification passed on `tests/unit/test_report_generation_trigger.py`, `tests/integration/test_session_lifecycle_api.py`, `tests/integration/test_replay_api.py`, and `tests/contract/test_practice_evidence_contract.py` (`44 passed`). The accepted same-chain backend pack also reran green on `tests/unit/test_stepfun_realtime_handler.py`, `tests/unit/test_stepfun_knowledge_helpers.py`, `tests/integration/test_knowledge_flow.py`, `tests/integration/test_replay_api.py`, and `tests/contract/test_practice_evidence_contract.py` (`114 passed`).

Live localhost proof also passed on the exact same session: the immediate lifecycle end response returned `status="scoring"`, the persisted row later moved to `status="completed"` while `report_status="failed"`, `GET /api/v1/practice/sessions/{id}/report`, `GET /api/v1/sessions/{id}/replay`, and `GET /api/v1/sessions/{id}/highlights` all returned 200 on that same session, `/practice/{sessionId}/report` rendered the canonical same-session report body, and `/practice/{sessionId}/replay` rendered unlocked replay evidence with no `统一训练证据不可用` or `SESSION_NOT_COMPLETED` text. True unfinished sessions still remained behind `[SESSION_NOT_COMPLETED]`.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_report_generation_trigger.py tests/integration/test_session_lifecycle_api.py tests/integration/test_replay_api.py tests/contract/test_practice_evidence_contract.py -v` | 0 | ✅ pass | 9250ms |
| 2 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py tests/unit/test_stepfun_knowledge_helpers.py tests/integration/test_knowledge_flow.py tests/integration/test_replay_api.py tests/contract/test_practice_evidence_contract.py` | 0 | ✅ pass | 14840ms |
| 3 | `live localhost proof on session 6a9e45d7-c15a-43c6-95cf-59583918780a: /practice/{sessionId} -> lifecycle end (status=scoring) -> background finalization -> GET /api/v1/practice/sessions/{id}/report,/knowledge-check and GET /api/v1/sessions/{id}/replay,/highlights plus learner /report,/replay routes` | 0 | ✅ pass | 42000ms |


## Deviations

Used a fresh localhost same-session proof that seeded canonical evidence via the live database seam before lifecycle end/finalization, rather than replaying the full microphone-driven objection conversation again. This kept the accepted route family real while isolating the S06 finalization boundary.

## Known Issues

Optional enhanced-report generation is still unhealthy on the localhost proof path (`[REPORT_NOT_FOUND]` / `[REPORT_GENERATION_FAILED]`) and continues to produce explicit degraded copy on the learner report page. This slice intentionally did not change that optional path.

## Files Created/Modified

- `backend/src/evaluation/services/report_generation_trigger.py`
- `backend/tests/unit/test_report_generation_trigger.py`
- `backend/tests/integration/test_session_lifecycle_api.py`
- `backend/tests/integration/test_replay_api.py`
- `backend/tests/contract/test_practice_evidence_contract.py`
- `.gsd/milestones/M003/slices/S06/S06-SUMMARY.md`
- `.gsd/milestones/M003/slices/S06/S06-UAT.md`


## Deviations
Used a fresh localhost same-session proof that seeded canonical evidence via the live database seam before lifecycle end/finalization, rather than replaying the full microphone-driven objection conversation again. This kept the accepted route family real while isolating the S06 finalization boundary.

## Known Issues
Optional enhanced-report generation is still unhealthy on the localhost proof path (`[REPORT_NOT_FOUND]` / `[REPORT_GENERATION_FAILED]`) and continues to produce explicit degraded copy on the learner report page. This slice intentionally did not change that optional path.
