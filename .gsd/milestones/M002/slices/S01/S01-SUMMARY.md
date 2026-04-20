---
id: S01
parent: M002
milestone: M002
provides:
  - One canonical five-dimension sales realtime contract across StepFun and classic voice modes, with the practice page preserving same-turn score/stage/suggestion refinements instead of falling back to generic coaching semantics.
requires: []
affects:
  - S02
  - S03
  - S04
  - S05
key_files:
  - backend/src/sales_bot/websocket/components/capability_processor.py
  - backend/tests/unit/test_capability_processor.py
  - backend/tests/unit/test_stepfun_realtime_handler.py
  - web/src/hooks/websocket/message-handlers.ts
  - web/src/hooks/websocket/message-handlers.test.ts
  - web/src/hooks/use-practice-websocket.test.ts
  - web/src/components/practice/ScorePanel.tsx
  - web/src/components/practice/ScorePanel.test.tsx
  - web/src/app/(dashboard)/agents/[agentId]/page.tsx
  - web/src/app/(dashboard)/agents/[agentId]/page.test.tsx
key_decisions:
  - D033
  - D034
patterns_established:
  - Classic sales realtime feedback must derive action-card pass flags from the shared sales effectiveness helper (`build_sales_effectiveness_metrics(...)` + `evaluate_pass_flags(...)`) instead of reviving generic communication/structure heuristics.
  - Frontend `score_update` idempotence must treat the full sales payload as the contract boundary; same-turn `stage_name`, `suggestions`, and `dimension_scores` refinements are product-significant even when `overall_score` and `turn_count` do not move.
  - Voice-mode selection can change transport/runtime behavior, but it must not imply a different scoring rubric on the training page.
observability_surfaces:
  - `backend/tests/unit/test_stepfun_realtime_handler.py::test_run_realtime_feedback_emits_canonical_sales_score_and_action_card`
  - `backend/tests/unit/test_capability_processor.py::test_realtime_scoring_action_card_uses_sales_effectiveness_semantics`
  - `backend/tests/unit/test_capability_processor.py::test_stage_update_emits_once_for_unchanged_stage`
  - `web/src/hooks/websocket/message-handlers.test.ts`
  - `web/src/hooks/use-practice-websocket.test.ts`
  - `web/src/components/practice/ScorePanel.test.tsx`
  - persisted handler snapshots `_latest_score_snapshot` / `_latest_action_card`
drill_down_paths:
  - .gsd/milestones/M002/slices/S01/tasks/T01-SUMMARY.md
  - .gsd/milestones/M002/slices/S01/tasks/T02-SUMMARY.md
duration: 55m
verification_result: passed
completed_at: 2026-03-24T19:25:11+08:00
---

# S01: 实时评分与训练页销售语义对齐

**Realtime sales coaching now uses one five-dimension rubric across StepFun and classic practice modes, and the practice page keeps same-turn sales refinements instead of silently dropping them or falling back to generic coaching semantics.**

## What Happened

S01 retired the first M002 drift path: training-time sales coaching no longer depends on which voice runtime the learner chose. On the backend, the StepFun handler’s canonical sales payload was locked with focused assertions around `score_update` and `action_card`, including five sales `dimension_scores`, `stage_name`, `suggestions`, `next_turn_rule`, and the persisted `_latest_score_snapshot` / `_latest_action_card` surfaces. The classic runtime path was then brought onto the same semantic line by changing `CapabilityProcessor` to prefer canonical `dimension_scores` and compute action-card pass flags through the shared sales effectiveness helper rather than the old communication/structure fallback math.

On the frontend, S01 removed the main consumer-side regression path. `score_update` dedupe no longer keys only on `overall_score + turn_count`; it now treats the full payload as meaningful so same-turn refinements to stage, suggestions, and dimension scores reach the practice page instead of being swallowed. `ScorePanel` stayed explicitly sales-first while preserving visible fallback rendering for unknown dimensions, and the launch-page voice-mode copy/tests were aligned so classic vs StepFun selection no longer implies a different scoring vocabulary.

The closer turn re-proved the slice from scratch instead of trusting task-level claims. All slice-plan verification commands passed fresh, and the extra websocket-hook diagnostic surface also passed. That leaves M002 with a stable transport/UI contract to build on: the training page now has one authoritative sales rubric, while the post-session report intentionally remains on the existing three-rollup evidence contract.

## Verification

Fresh slice-level verification passed:

- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_realtime_scoring.py tests/unit/test_effectiveness_sales_baseline.py tests/unit/test_stepfun_realtime_handler.py tests/unit/test_capability_processor.py`
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py tests/unit/test_capability_processor.py -k 'action_card or stage_update'`
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py`
- `cd web && npm test -- --run 'src/hooks/websocket/message-handlers.test.ts' 'src/components/practice/ScorePanel.test.tsx' 'src/app/(dashboard)/agents/[agentId]/page.test.tsx' 'src/app/(user)/practice/[sessionId]/runtime-lock.test.ts'`

Fresh observability / diagnostic confirmation also passed:

- `cd web && npm test -- --run 'src/hooks/use-practice-websocket.test.ts'`
- The focused backend diagnostic suite still locks `_latest_score_snapshot`, `_latest_action_card`, stage-update suppression, and classic-mode action-card semantics on one sales helper path.
- The focused frontend hook/panel suites still prove that same-turn score refreshes are preserved and fallback dimensions remain visible instead of being discarded.

## Requirements Advanced

- R009 — S01 advanced the requirement from “mapped” to a concrete shipped baseline: both realtime runtime paths and the training-page consumer now share one sales-first contract, so later slices can work on cadence, guidance prioritization, report alignment, and degraded-state visibility without first untangling vocabulary drift.

## Requirements Validated

- none

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none

## Deviations

T01 added a missing slice-level diagnostic verification command to `S01-PLAN.md` so the slice had an explicit inspectable failure-path check instead of only broad suite coverage. No scope change followed from that plan correction.

## Known Limitations

- S01 proves contract alignment only. It does not yet constrain prompt frequency, suppress competing coach channels, or enforce a single primary action direction per turn; that remains S02 work.
- The slice does not yet prove that training-time guidance and post-session `main_issue` / `next_goal` stay aligned for the same session; that remains S04 work.
- Coach degraded / reconnect visibility is still open. If the coaching chain partially fails, S01 only proves the canonical payload/UI line when it succeeds; S05 still needs to make degraded-state visibility explicit.
- This slice intentionally keeps the report-side three-rollup evidence contract unchanged. That preserves read-side stability, but it also means future slices must map realtime sales guidance to report conclusions without renaming canonical report keys.

## Follow-ups

- S02 should treat the S01 sales payload as the authoritative input to throttling, dedupe, and single-turn action selection. Do not invent parallel score/stage vocabularies.
- S03 should build next-turn coaching rules on top of the stabilized `stage_name` / `suggestions` / `next_turn_rule` contract instead of re-deriving guidance from ad hoc frontend heuristics.
- S04 should align realtime `suggestions` and action-card priorities to report `main_issue` / `next_goal` via mapping logic, not via websocket/report field renames.

## Files Created/Modified

- `backend/src/sales_bot/websocket/components/capability_processor.py` — moved classic sales realtime action-card semantics onto the shared sales effectiveness helper and canonical `dimension_scores` handling.
- `backend/tests/unit/test_capability_processor.py` — added focused regressions for stage-update suppression and classic-mode action-card alignment.
- `backend/tests/unit/test_stepfun_realtime_handler.py` — locked the canonical StepFun sales `score_update` / `action_card` payload plus `_latest_*` snapshot surfaces.
- `web/src/hooks/websocket/message-handlers.ts` — changed `score_update` idempotence to preserve same-turn sales refinements instead of deduping only on `overall_score + turn_count`.
- `web/src/hooks/websocket/message-handlers.test.ts` — covered same-turn score refresh semantics at the consumer boundary.
- `web/src/hooks/use-practice-websocket.test.ts` — re-confirmed the practice websocket hook still propagates the richer score-update contract end-to-end.
- `web/src/components/practice/ScorePanel.tsx` — kept five sales dimensions as the primary rendering order while preserving unknown-dimension fallback visibility.
- `web/src/components/practice/ScorePanel.test.tsx` — locked sales-first ordering and fallback rendering.
- `web/src/app/(dashboard)/agents/[agentId]/page.tsx` — aligned voice-mode affordances to one shared sales scoring rubric.
- `web/src/app/(dashboard)/agents/[agentId]/page.test.tsx` — covered the shared-rubric launch-page copy.
- `.gsd/REQUIREMENTS.md` — updated R009 to record the slice’s proved contract-alignment boundary and downstream supporting slices.
- `.gsd/PROJECT.md` — refreshed current-state documentation to include the shipped M002/S01 sales realtime alignment.
- `.gsd/milestones/M002/M002-ROADMAP.md` — marked S01 complete.
- `.gsd/milestones/M002/slices/S01/S01-SUMMARY.md` — recorded the slice outcome, verification, and downstream guidance.
- `.gsd/milestones/M002/slices/S01/S01-UAT.md` — captured the concrete artifact-driven UAT script for this slice.

## Forward Intelligence

### What the next slice should know
- The S01 contract is now stable: websocket/runtime surfaces speak in five sales dimensions plus `stage_name`, `suggestions`, and `next_turn_rule`, while the report remains on the existing three-rollup evidence line. Build mappings on top of that boundary; do not collapse the two contracts by renaming keys.

### What's fragile
- Reverting frontend dedupe to `overall_score + turn_count`, or reintroducing generic communication/structure heuristics on the classic backend path, will immediately recreate stale or contradictory coaching on the practice page even if broad suites still look green.

### Authoritative diagnostics
- Start with `backend/tests/unit/test_stepfun_realtime_handler.py::test_run_realtime_feedback_emits_canonical_sales_score_and_action_card`, `backend/tests/unit/test_capability_processor.py::test_realtime_scoring_action_card_uses_sales_effectiveness_semantics`, `web/src/hooks/websocket/message-handlers.test.ts`, and `web/src/hooks/use-practice-websocket.test.ts`. Those surfaces pin the exact contract that downstream M002 slices now depend on.

### What assumptions changed
- We started with the implicit assumption that same-turn score updates could be safely deduped on `overall_score + turn_count`, and that classic voice mode could tolerate older generic action-card heuristics. Both assumptions were false: sales coaching meaning changes within a turn, and classic mode is still a real user-facing path that must stay on the same sales semantics as StepFun.
