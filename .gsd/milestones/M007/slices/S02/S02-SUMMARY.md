---
id: S02
parent: M007
milestone: M007
provides:
  - A single same-session conclusion vocabulary across active runtime, `/knowledge-check`, learner practice UI, canonical report, and replay parity tests.
  - A localhost proof artifact that separates genuine backend completion drift from host/cookie or optional-enhancement noise during same-session close-out.
requires:
  - slice: S01
    provides: Fresh reconnect truth and learner-visible coach-health surfaces on the existing runtime authority line, so same-session conclusion work could build on a stable practice-page state contract and `/knowledge-check` diagnostics seam.
affects:
  - S03
  - S04
key_files:
  - backend/src/common/effectiveness/evaluator.py
  - backend/src/common/conversation/runtime_diagnostics.py
  - backend/src/sales_bot/websocket/stepfun_realtime_handler.py
  - backend/src/sales_bot/websocket/components/capability_processor.py
  - web/src/hooks/websocket/message-handlers.ts
  - web/src/lib/session-evidence.ts
  - web/src/components/practice/RightPanelContent.tsx
  - web/src/app/(user)/practice/[sessionId]/page.tsx
  - backend/tests/contract/test_practice_evidence_contract.py
  - backend/tests/integration/test_practice_evidence_flow.py
  - web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
  - web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx
  - .artifacts/m007-s02-same-session/session-proof.md
  - .gsd/PROJECT.md
key_decisions:
  - Use one evaluator-backed `live_session_summary` object as the active-session authority for main_issue/next_goal/claim_truth across StepFun, classic, and `/knowledge-check`.
  - Persist a normalized `liveSessionSummary` in learner websocket reducer state and render all same-session issue/goal/claim-truth copy through shared `session-evidence` helpers instead of deriving it from stage or action-card text.
  - Evaluate same-session report/replay parity on the canonical issue/goal/claim-truth family after stripping replay-only `replay_anchor` decoration, while separately asserting the anchor remains present and replay stays completion-gated.
  - Treat the localhost post-end `status="scoring"` + replay `[SESSION_NOT_COMPLETED]` split as backend completion drift once canonical `/practice/{id}/report` is already readable on that same session, not as a host/cookie bug.
patterns_established:
  - Treat evaluator-backed `live_session_summary` as the only active-session conclusion authority, then reuse it across runtime diagnostics, `/knowledge-check`, and learner websocket state rather than inventing route-local mappings.
  - Keep learner/report/replay wording on shared `session-evidence` helpers so frontend surfaces render one vocabulary contract instead of re-deriving family labels from stage, score, or action-card prose.
  - Verify report/replay parity on the canonical projection family while treating replay-only anchor metadata as additive decoration, not a divergent truth line.
observability_surfaces:
  - Websocket `score_update.data.live_session_summary` and learner reducer state on `/practice/{sessionId}`.
  - `/api/v1/practice/sessions/{id}/knowledge-check` live diagnostics, which now prefer active handler conclusions and fail soft on malformed partial summaries.
  - Backend logs around terminal flow: `practice_session_evidence_persisted`, `report_generation_triggered`, `no_scoring_context_available`, and `report_generation_failed [NO_STAGE_RESULTS]`.
  - Persistent proof artifact at `.artifacts/m007-s02-same-session/session-proof.md` documenting the localhost same-session wedge.
drill_down_paths:
  - .gsd/milestones/M007/slices/S02/tasks/T01-SUMMARY.md
  - .gsd/milestones/M007/slices/S02/tasks/T02-SUMMARY.md
  - .gsd/milestones/M007/slices/S02/tasks/T03-SUMMARY.md
  - .gsd/milestones/M007/slices/S02/tasks/T04-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-03-28T09:20:12.454Z
blocker_discovered: false
---

# S02: 同 session 结论同源收口

**Unified same-session issue/goal/claim-truth vocabulary now flows from live coaching to canonical report/replay on the current route family, and the remaining replay-unlock failure is isolated to a documented StepFun completion drift instead of frontend or host-alignment ambiguity.**

## What Happened

S02 closed the same-session truth gap on the existing learner/runtime/report/replay route family without inventing a second authority. On the backend, T01 established a single evaluator-backed `live_session_summary` shape for active sales sessions, then threaded it through StepFun, classic runtime diagnostics, and `/api/v1/practice/sessions/{id}/knowledge-check` so live main issue, next goal, and claim-truth semantics match while a handler is active and fail soft to null when the live payload is partial. On the frontend, T02 extended the websocket reducer and learner route so `/practice/{sessionId}` keeps a stable same-session cue sourced directly from `score_update.data.live_session_summary`; the page and right panel now render issue/goal/claim-truth copy via shared `session-evidence` helpers, while final-transcript cleanup continues clearing transient action cards and fuzzy detections without erasing the stable conclusion. T03 then tightened the completed-session proof line rather than changing business logic: backend contract/integration tests now assert the scoring-to-completed transition on one same session, report remains readable while replay is still gated, and replay parity compares the canonical issue/goal/claim-truth family while treating `replay_anchor` as replay-only decoration. Matching web tests prove the report page keeps canonical copy when replay is unavailable and that the replay page trusts canonical replay projection data instead of a conflicting report snapshot. T04 reran the localhost route-family proof on aligned `localhost` hosts, confirmed the learner cue on a real StepFun session, confirmed replay is blocked before completion, and re-confirmed the remaining blocker: after lifecycle end, a real StepFun session can persist evidence and keep the canonical report readable while still wedging in `status="scoring"`, with replay locked behind `[SESSION_NOT_COMPLETED]` and backend logs showing `report_generation_failed [NO_STAGE_RESULTS]`. The slice therefore delivered same-session vocabulary closure across live/runtime/report/replay plus a precise blocker artifact for the remaining unlock drift, rather than claiming a false full close-out.

## Verification

Fresh slice-close verification passed for the planned focused suites and the live localhost proof. Commands rerun from repo root in this close-out session: `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_stepfun_realtime_handler.py` (63 passed), `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_enhanced_handler_coach_health.py` (6 passed), `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_practice_evidence_contract.py -k 'knowledge_check or replay or report'` (10 passed), `npm test -- --run 'web/src/hooks/websocket/message-handlers.test.ts' 'web/src/components/practice/RightPanelContent.test.tsx' 'web/src/app/(user)/practice/[sessionId]/page.test.tsx'` (44 passed), `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_practice_evidence_contract.py backend/tests/integration/test_practice_evidence_flow.py` (15 passed), `npm test -- --run 'web/src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx'` (21 passed), and `npm test -- --run 'web/src/hooks/websocket/message-handlers.test.ts' 'web/src/app/(user)/practice/[sessionId]/page.test.tsx' 'web/src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx'` (57 passed). On live localhost with backend `:3444` and web `:3445`, dev-login restored auth, `/practice/3830822a-505d-4db0-a9fd-167e02e20d45/report` rendered the canonical report headings (`训练评估报告`, `主张证据状态`, `销售推进结果`, `下一轮销售目标`), and `/practice/3830822a-505d-4db0-a9fd-167e02e20d45/replay` still truthfully showed `[SESSION_NOT_COMPLETED] ... Current status: scoring`, matching the documented StepFun completion blocker.

## Requirements Advanced

- R009 — S02 pushed R009 from coach-health truth into same-session conclusion truth: live coaching, knowledge-check, learner practice UI, canonical report, and replay parity tests now share one issue/goal/claim-truth vocabulary on the current route family. The remaining active blocker is no longer semantic drift; it is the StepFun completion wedge that keeps replay locked in `status="scoring"` after end.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

Used the learner page’s own websocket `type:"text"` path for the localhost proof after the machine’s legacy streaming ASR dependency failed (`torch._C`), so the live proof stayed on the shipped `/practice/{sessionId}` route family instead of proving an environment-specific microphone failure. Otherwise the slice stayed within plan.

## Known Limitations

A real localhost `stepfun_realtime` sales session can still wedge after lifecycle end: canonical `/practice/{id}/report` remains readable from the persisted projection, but the session can stay in `status="scoring"` and `/practice/{id}/replay` continues to fail with `[SESSION_NOT_COMPLETED]` because terminal report generation logs `report_generation_failed [NO_STAGE_RESULTS]`. This slice intentionally documented that blocker instead of papering over it. The machine used for proof also has a broken legacy streaming ASR dependency (`torch._C`), so raw microphone-path proof on legacy mode is not a trustworthy signal here.

## Follow-ups

1. In S03/S04, fix the StepFun terminal path that accepts lifecycle end, persists evidence, then logs `report_generation_failed [NO_STAGE_RESULTS]` and leaves the session stuck in `status="scoring"`; that is the blocker preventing same-session replay unlock on localhost. 2. After that fix, rerun one fresh localhost StepFun proof across `/practice/{id}` → `/practice/{id}/report` → `/practice/{id}/replay` and promote the result into milestone validation evidence. 3. Keep same-host frontend/backend alignment (`localhost` ↔ `localhost`) during future live proofs so host-only auth cookies do not create false 401 regressions.

## Files Created/Modified

- `backend/src/common/effectiveness/evaluator.py` — Added the evaluator-backed `live_session_summary` authority used by active runtime, knowledge-check, and learner UI vocabulary.
- `backend/src/common/conversation/runtime_diagnostics.py` — Threaded live-session conclusion data through runtime diagnostics so `/knowledge-check` can prefer active handler truth without reviving stale persisted conclusions.
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` — Made StepFun emit, persist, and restore the richer same-session conclusion summary alongside existing claim-truth/runtime diagnostics.
- `backend/src/sales_bot/websocket/components/capability_processor.py` — Reordered classic score-update emission behind objection-ledger alignment so classic and StepFun expose the same active-session issue/goal/claim-truth semantics.
- `web/src/hooks/websocket/message-handlers.ts` — Stored normalized `liveSessionSummary` in reducer state and cleared it safely when backend authority disappears or becomes partial.
- `web/src/lib/session-evidence.ts` — Centralized learner/report/replay issue/goal/claim-truth wording so frontend surfaces stop inferring family labels from stage or action-card text.
- `web/src/components/practice/RightPanelContent.tsx` — Rendered the stable same-session cue from backend authority while preserving action-card/fuzzy cleanup behavior.
- `web/src/app/(user)/practice/[sessionId]/page.tsx` — Wired the new stable same-session cue through the learner page shell and panels on the current practice route.
- `backend/tests/contract/test_practice_evidence_contract.py` — Locked knowledge-check live-summary precedence and same-session report/replay parity expectations on the canonical projection.
- `backend/tests/integration/test_practice_evidence_flow.py` — Covered the scoring-to-completed family behavior and replay unlock parity on the projection-backed backend flow.
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx` — Proved report keeps canonical issue/goal/claim-truth copy even when replay remains unavailable.
- `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx` — Proved replay consumes canonical projection data and treats `replay_anchor` as decoration rather than a second conclusion authority.
- `.artifacts/m007-s02-same-session/session-proof.md` — Captured the localhost same-session proof and the remaining StepFun completion drift that leaves report readable while replay stays locked.
- `.gsd/PROJECT.md` — Refreshed current-state documentation so M007 now records S02 as delivered and names the remaining StepFun scoring wedge explicitly.
