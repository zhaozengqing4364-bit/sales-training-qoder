---
id: S04
parent: M003
milestone: M003
provides:
  - One shared claim-truth vocabulary (`unsupported_claim`, `weak_evidence`, `evidence_pending`, `evidence_verified`) across realtime diagnostics, report, and replay on current routes.
  - A hard boundary between evidence-quality states and kb-lock chain-failure diagnostics so runtime degradation does not overwrite learner-facing truth conclusions.
  - A shared frontend formatter and learner-facing report/replay card for canonical claim-truth explanations.
requires:
  - slice: S02
    provides: Frozen persona pressure behavior inside `voice_policy_snapshot.customer_pressure` / `source.customer_pressure_source`, which keeps objection direction stable while claim truth is evaluated.
  - slice: S03
    provides: Persisted unresolved objection ledgers and closure states on transcript metadata/runtime snapshots, which feed evidence-pending, unsupported, weak, and verified claim-truth classification and issue-goal carry-forward.
affects:
  - S05
key_files:
  - backend/src/common/effectiveness/evaluator.py
  - backend/src/common/conversation/session_evidence.py
  - backend/src/sales_bot/websocket/stepfun_realtime_handler.py
  - backend/src/common/conversation/runtime_diagnostics.py
  - backend/src/common/api/practice.py
  - web/src/lib/session-evidence.ts
  - web/src/app/(user)/practice/[sessionId]/report/page.tsx
  - web/src/app/(user)/practice/[sessionId]/replay/page.tsx
key_decisions:
  - Store the new truth state on `effectiveness_snapshot.claim_truth` and keep `main_issue` / `next_goal` stable for current report/replay consumers.
  - Expose live claim truth through the existing StepFun `score_update` payload plus reconnect-safe handler state and a live-first `/knowledge-check` fallback, rather than mutating the stable persisted `score_snapshot` shape.
  - Source learner report/replay truth from the completed-session `SessionEvidenceService` projection via one shared frontend formatter instead of using `/knowledge-check` as the primary read-side truth line.
patterns_established:
  - When the product needs richer semantics, preserve stable public contracts and add the richer state on the existing authority line instead of renaming top-level report/websocket keys.
  - Use live-runtime state first and projection fallback second for diagnostics that must work both during a session and after completion.
  - Keep operational chain failures (`blocked_*`, kb-lock/search failures) separate from evidence-quality truth states so degraded runtime conditions do not masquerade as coaching conclusions.
observability_surfaces:
  - `/api/v1/practice/sessions/{id}/knowledge-check` now exposes `claim_truth`, `claim_truth_status`, `claim_truth_source`, and `kb_lock_chain_failure` on the current diagnostics surface.
  - StepFun live `score_update.claim_truth` plus reconnect-safe `_latest_claim_truth` handler state make the realtime truth line inspectable without changing the public score snapshot shape.
  - `SessionEvidenceService` projection logs now carry claim-truth status/source so downstream report/replay/admin debugging can see which fact line won.
drill_down_paths:
  - .gsd/milestones/M003/slices/S04/tasks/T01-SUMMARY.md
  - .gsd/milestones/M003/slices/S04/tasks/T02-SUMMARY.md
  - .gsd/milestones/M003/slices/S04/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-03-25T07:14:07.926Z
blocker_discovered: false
---

# S04: unsupported claim / weak evidence truth contract

**Canonical claim-truth states now flow from evaluator/session evidence through runtime diagnostics and learner report/replay, so one sales session can distinguish unsupported, weak, pending, and verified claims without mixing them with kb-lock failures.**

## What Happened

S04 closed the evidence-truth gap on the current sales authority line instead of inventing a second evaluator. T01 added a canonical `effectiveness_snapshot.claim_truth` payload to the existing sales evaluator and `SessionEvidenceService` projection, covering `unsupported_claim`, `weak_evidence`, `evidence_pending`, and `evidence_verified` while leaving `main_issue` / `next_goal` on the stable read-side keys. T02 carried that same truth contract onto the current runtime diagnostics path by classifying kb-lock chain failures separately, emitting live `claim_truth` on the existing StepFun `score_update` path, persisting reconnect-safe `_latest_claim_truth`, and teaching `/api/v1/practice/sessions/{id}/knowledge-check` to prefer live runtime state with completed-session projection fallback. T03 finished the learner-facing closure by adding a shared frontend formatter in `web/src/lib/session-evidence.ts` and rendering a `主张证据状态` card on the current report and replay routes for sales sessions only, so completed-session surfaces now explain whether the learner's claim was unsupported, weakly supported, pending proof, or verified without borrowing runtime chain-failure copy. Across the slice, the work kept the stable public contract shape intact, reused the S03 objection ledger and existing report/replay projection line, and recorded the important boundary: kb-lock `blocked_*` / chain-failure diagnostics stay operational, while claim truth stays on the session-evidence line.

## Verification

Ran all three slice-plan verification gates fresh and all passed. 1) `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_report_alignment.py tests/unit/test_session_evidence_service.py` passed with 11/11 tests green, proving unsupported/weak/pending/verified mapping plus open/closed objection-ledger handling on the shared evaluator/session-evidence seam. 2) `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py tests/contract/test_practice_evidence_contract.py` passed with 62/62 tests green, confirming live StepFun claim-truth emission, reconnect-safe handler state, and the `/knowledge-check` contract that keeps claim truth distinct from kb-lock chain failures. 3) `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx'` passed with 2/2 test files and 7/7 tests green, proving learner report/replay render the canonical truth card on sales sessions while presentation routes stay free of the sales-only surface. The observability/diagnostic surface was confirmed through the runtime contract coverage around `claim_truth_status`, `claim_truth_source`, `kb_lock_chain_failure`, and live `score_update.claim_truth`.

## Requirements Advanced

- R010 — Added one canonical `effectiveness_snapshot.claim_truth` contract across evaluator/session evidence, StepFun runtime diagnostics, `/api/v1/practice/sessions/{id}/knowledge-check`, `/api/v1/practice/sessions/{id}/report`, and `/api/v1/sessions/{id}/replay`, so unsupported/weak/pending/verified evidence states now travel on the current realism chain without being confused with kb-lock failures.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

None.

## Known Limitations

This slice proves the contract through focused backend/web integration tests, not a fresh live objection-heavy browser/runtime run; S05 still owns that same-session live proof. Repo-wide `cd web && npx tsc --noEmit` also still fails on the pre-existing unrelated admin knowledge client typing gap in `src/app/admin/knowledge/[id]/page.tsx` (`api.reprocessKnowledgeDocument`), so repo-wide web typecheck is not yet a usable hard gate for this slice.

## Follow-ups

S05 should run one real admin -> practice -> report/replay objection-heavy session that exercises the claim-truth contract on the current routes and confirms degraded kb-lock states remain inspectable without replacing the learner-facing truth line. Separately, the unrelated admin knowledge client typing gap should be cleared so repo-wide web typecheck can return as a hard verification gate.

## Files Created/Modified

- `backend/src/common/effectiveness/evaluator.py` — Derives canonical sales `claim_truth` states from score evidence, evaluability fallback, and objection-ledger closure semantics.
- `backend/src/common/conversation/session_evidence.py` — Projects `effectiveness_snapshot.claim_truth`, keeps open-ledger override narrow, and logs claim-truth status/source for downstream diagnostics.
- `backend/tests/unit/test_effectiveness_sales_report_alignment.py` — Covers unsupported, weak, pending, and verified claim-truth mappings on the shared sales alignment seam.
- `backend/tests/unit/test_session_evidence_service.py` — Covers projection overlay behavior plus open/closed objection-ledger effects on claim-truth classification.
- `backend/src/common/knowledge/kb_lock_guard.py` — Adds shared kb-lock chain-failure classification so infrastructure/setup failures stay separate from evidence-quality states.
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` — Emits live `claim_truth` on the existing `score_update` websocket payload and persists reconnect-safe `_latest_claim_truth` handler state.
- `backend/src/common/conversation/runtime_diagnostics.py` — Surfaces `claim_truth`, `claim_truth_status`, `claim_truth_source`, and `kb_lock_chain_failure` on the current diagnostics path.
- `backend/src/common/api/practice.py` — Makes `/api/v1/practice/sessions/{id}/knowledge-check` prefer live runtime claim-truth and fall back to completed-session projection.
- `backend/tests/unit/test_stepfun_realtime_handler.py` — Adds runtime coverage for live claim-truth payloads, stable score-update shape, and reconnect restoration.
- `backend/tests/contract/test_practice_evidence_contract.py` — Guards the knowledge-check/report/replay contract boundary so claim truth does not collapse into kb-lock chain-failure states.
- `web/src/lib/session-evidence.ts` — Introduces the shared frontend parser/formatter for canonical claim-truth states and learner-facing explanations.
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx` — Renders a sales-only `主张证据状态` card from completed-session evidence on the learner report page.
- `web/src/app/(user)/practice/[sessionId]/replay/page.tsx` — Renders the same canonical claim-truth card on the learner replay page.
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx` — Verifies report rendering for weak/unsupported/pending/verified truth states and keeps presentation routes free of the sales-only card.
- `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx` — Verifies replay rendering for the canonical claim-truth contract.
- `.gsd/DECISIONS.md` — Recorded the S04 truth-contract decisions on evaluator storage, runtime exposure, and learner read-side sourcing.
- `.gsd/KNOWLEDGE.md` — Recorded the S04 closure-state/runtime/typecheck gotchas future slices need when extending the claim-truth path.
- `.gsd/REQUIREMENTS.md` — Updated R010 to capture that S04 advanced the current realism chain with one shared claim-truth contract.
- `.gsd/PROJECT.md` — Refreshed current-state project context to reflect that M003/S04 is now complete.
