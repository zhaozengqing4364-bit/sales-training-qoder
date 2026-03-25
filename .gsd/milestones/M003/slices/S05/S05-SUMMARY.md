---
id: S05
parent: M003
milestone: M003
provides:
  - A focused regression net covering ROI, price, competitor, implementation-risk, and claim-truth evidence paths on the accepted M003 runtime/report routes.
  - One live same-session objection-heavy evidence pack with trace, timeline, report, and replay diagnostics on the current admin -> practice -> knowledge-check -> report chain.
  - The release boundary for M003: canonical report fallback may be shippable when truthful and explicit, but replay/highlights blocked behind `status="scoring"` is still milestone-blocking.
requires:
  - slice: S02
    provides: The frozen `customer_pressure` snapshot contract that let the live proof verify `customer_pressure_source: explicit` on the same session.
  - slice: S03
    provides: The unresolved objection ledger and reconnect-safe pressure behavior that kept the live proof gap visible across turns.
  - slice: S04
    provides: The shared claim-truth contract across realtime, knowledge-check, report, and replay that the regression suite and live proof compared on one same-session evidence line.
affects:
  []
key_files:
  - backend/tests/unit/test_stepfun_realtime_handler.py
  - backend/tests/unit/test_stepfun_knowledge_helpers.py
  - backend/tests/integration/test_knowledge_flow.py
  - backend/tests/contract/test_practice_evidence_contract.py
  - .gsd/milestones/M003/slices/S05/S05-UAT.md
  - .gsd/milestones/M003/slices/S05/tasks/T03-PLAN.md
  - .gsd/REQUIREMENTS.md
  - .gsd/PROJECT.md
key_decisions:
  - Kept the regression expansion on the existing StepFun/runtime/report routes instead of creating a helper-only proof surface.
  - Ran the live proof on the real `/practice/{sessionId}` recorder + websocket path with delayed synthetic `getUserMedia` playback rather than the websocket `type:"text"` shortcut.
  - Treated projection-backed canonical report fallback as shippable only when the learner still gets a truthful same-session evidence surface with explicit fallback copy.
  - Treated replay/highlights blocked behind `status="scoring"` after `report_generation_failed [NO_STAGE_RESULTS]` as the remaining M003 acceptance blocker even though the replay page surfaces that failure explicitly.
patterns_established:
  - Keep final-assembly proof on one real session and compare runtime, knowledge-check, canonical report, and replay on that exact session instead of stitching together green results from different sessions.
  - Expand regressions on the shipped StepFun/runtime/report routes rather than inventing helper-only acceptance surfaces; the accepted business chain stays the test seam.
  - Treat projection-backed canonical report fallback as the resilient evidence baseline, while optional enhanced-report/highlights failures stay secondary only when the learner still gets truthful same-session evidence.
  - When durable server-side latency metrics are absent, use browser trace/timeline artifacts plus explicit runtime/report/replay surfaces to define acceptance guardrails instead of guessing.
observability_surfaces:
  - `GET /api/v1/practice/sessions/{id}/knowledge-check` for live runtime status, hit metrics, and same-session KB inspection.
  - Canonical `/practice/{sessionId}/report` plus `effectiveness_snapshot.claim_truth`, knowledge-hit facts, snapshot reference, and explicit fallback copy (`综合洞察暂不可用` / `高光片段暂不可用`).
  - `/practice/{sessionId}/replay` and `/api/v1/sessions/{id}/replay` for the explicit `[SESSION_NOT_COMPLETED]` completed-session gate when replay remains blocked.
  - Backend logs for `timeout_proceeded_without_transcription_completion`, `report_generation_failed [NO_STAGE_RESULTS]`, and `no_scoring_context_available`.
  - Browser trace, timeline, and report/replay debug bundles under `.artifacts/browser/` for same-session latency and UI evidence.
drill_down_paths:
  - .gsd/milestones/M003/slices/S05/tasks/T01-SUMMARY.md
  - .gsd/milestones/M003/slices/S05/tasks/T02-SUMMARY.md
  - .gsd/milestones/M003/slices/S05/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-03-25T09:55:59.193Z
blocker_discovered: false
---

# S05: objection-heavy live proof 与稳定性护栏

**Proved the live objection-heavy admin→practice→knowledge-check→report chain on current routes, expanded the regression net around claim-truth and objection handling, and documented replay-blocked `status="scoring"` as the remaining M003 blocker.**

## What Happened

T01 expanded the objection-heavy regression net on the current runtime routes without touching production code. The backend suites now lock ROI, price, competitor, and implementation-risk retrieval tuning on `stepfun_knowledge_helpers`, prove StepFun runtime can open and close objection ledgers on competitor/risk evidence paths, verify implementation proof promotes claim truth to `evidence_verified`, and keep report/replay contract assertions aligned on the shared `effectiveness_snapshot.claim_truth` seam. That gave the slice a focused safety net for the exact business chain the milestone accepts.

T02 then captured one honest localhost same-session proof on the real admin Persona / knowledge -> practice -> knowledge-check -> report/replay path. The updated `石犀专家` persona froze an explicit objection-heavy `customer_pressure` contract into the session snapshot, the bound knowledge base was queryable on the current admin page, and the live `/practice/{sessionId}` runtime showed objection-heavy stage, score, and action-card updates that kept asking for ROI and evidence instead of drifting into generic chat. The same session also produced a genuine degraded runtime signal on the first synthetic-mic attempt (`timeout_proceeded_without_transcription_completion` and the KB-lock fallback copy), which later recovered on that same session. After end-of-session, the canonical report route still surfaced the same-session evidence line correctly: `overall_score=70.37`, `claim_truth.status=weak_evidence`, `knowledge-check.status=hit`, and `customer_pressure_source: explicit`. Optional enhanced layers degraded honestly with explicit fallback copy instead of hiding the usable report.

The live proof also exposed the remaining acceptance boundary. Replay and highlights did not go green for that same session: the session stayed `status="scoring"`, replay/highlights returned `[SESSION_NOT_COMPLETED]`, the replay page surfaced `统一训练证据不可用`, and backend logs tied the failure to `report_generation_failed [NO_STAGE_RESULTS]` plus `no_scoring_context_available`. T03 turned that evidence into the final M003 guardrail document: measured latency bands from the browser timeline, shippable degraded states when the canonical evidence line survives, and a hard rule that replay/highlights blocked behind scoring is release-blocking even if the error is explicit. This slice therefore delivered the final-assembly proof and the acceptance boundary, but not milestone close-out.

## Verification

Ran the slice-plan verification fresh instead of trusting prior task output. The exact backend gate `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py tests/unit/test_stepfun_knowledge_helpers.py tests/integration/test_knowledge_flow.py tests/contract/test_practice_evidence_contract.py` passed with 90/90 tests green. Then rechecked the live-proof artifacts and slice-level diagnostics from repo root: `test -s .gsd/milestones/M003/slices/S05/S05-UAT.md`, verified the referenced browser trace/timeline/report/replay bundles still exist, reran `rg -n "latency|degraded|fallback|block" .gsd/milestones/M003/slices/S05/tasks/T03-PLAN.md`, and confirmed the UAT still contains the key inspectable signals for `claim_truth.status == "weak_evidence"`, `knowledge-check.status == "hit"`, `综合洞察暂不可用`, `高光片段暂不可用`, and `[SESSION_NOT_COMPLETED]`. Together those checks prove the regression net, the live UAT artifact, and the slice’s observability/guardrail surfaces are all present and current.

## Requirements Advanced

- R010 — Added the first live same-session objection-heavy proof on the accepted admin Persona/knowledge -> practice -> knowledge-check -> canonical report chain, showed frozen explicit pressure + KB-hit evidence on current routes, and locked the remaining replay-blocked scoring acceptance boundary instead of leaving it implicit.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

Live UAT used delayed synthetic `getUserMedia` audio on the shipped recorder/websocket path because browser automation cannot speak into a physical microphone. The slice also recorded the real same-session replay-blocked `status="scoring"` outcome instead of forcing an artificial completed replay path.

## Known Limitations

The current live proof still ends at a real blocker: after end-of-session, an objection-heavy session can remain `status="scoring"`, the canonical `/practice/{sessionId}/report` still builds from persisted evidence, but `/api/v1/sessions/{id}/replay` and `/api/v1/sessions/{id}/highlights` stay blocked with `[SESSION_NOT_COMPLETED]` after `report_generation_failed [NO_STAGE_RESULTS]` / `no_scoring_context_available`. Also, the slice’s latency guardrails are based on browser timeline evidence because this proof chain does not yet expose a durable server-side latency metric.

## Follow-ups

1. Fix the post-end scoring/report finalization path so the same objection-heavy proof session leaves `status="scoring"` and unlocks `/api/v1/sessions/{id}/replay` plus `/api/v1/sessions/{id}/highlights` on the accepted proof chain. 2. Add a durable server-side latency signal for the M003 proof path if milestone close-out or later slices need automated latency enforcement beyond browser timeline artifacts.

## Files Created/Modified

- `backend/tests/unit/test_stepfun_realtime_handler.py` — Expanded StepFun realtime regression coverage for competitor objections, implementation-risk proof, objection ledger closure, and verified claim-truth transitions on the live runtime path.
- `backend/tests/unit/test_stepfun_knowledge_helpers.py` — Broadened objection-style retrieval assertions so ROI, price, competitor, and implementation-risk queries keep the widened entity-query retrieval window on current helpers.
- `backend/tests/integration/test_knowledge_flow.py` — Added integration assertions that new sales sessions freeze distinct competitor and implementation pressure contracts from the current session-create entry chain.
- `backend/tests/contract/test_practice_evidence_contract.py` — Tightened report/replay evidence-contract coverage for weak-evidence versus verified-evidence states while preserving the replay completion gate contract.
- `.gsd/milestones/M003/slices/S05/S05-UAT.md` — Captured the live same-session objection-heavy proof, artifact paths, runtime/report behavior, and replay degradation findings on current product routes.
- `.gsd/milestones/M003/slices/S05/tasks/T03-PLAN.md` — Rewrote the task artifact into the release-facing latency, degradation, and blocking guardrail document for the M003 proof chain.
- `.gsd/DECISIONS.md` — Recorded the acceptance decision that truthful canonical report degradation is shippable but replay/highlights blocked behind `status="scoring"` is still release-blocking.
- `.gsd/KNOWLEDGE.md` — Added reusable S05 live-proof gotchas for delayed synthetic mic playback and the current report-readable / replay-blocked scoring failure mode.
- `.codex/loop/state.json` — Updated safe-grow continuity state to point at T03 completion and the replay blocker carry-forward.
- `.codex/loop/log.md` — Logged the live proof and guardrail execution trail for safe-grow continuity.
- `.gsd/REQUIREMENTS.md` — Updated R010 to include the S05 live proof and the remaining replay-blocked scoring acceptance blocker.
- `.gsd/PROJECT.md` — Refreshed current project state with S05 completion and the remaining M003 milestone blocker.
