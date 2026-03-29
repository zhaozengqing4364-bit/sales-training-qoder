---
id: S04
parent: M007
milestone: M007
provides:
  - A final same-session closure evidence line tying realtime coaching, canonical report, replay unlock, and generated-state reconciliation together under M007.
  - Validated R009 proof notes that downstream milestone validation can quote directly without reopening M002 authority drift.
requires:
  - slice: S01
    provides: Canonical coach degraded/resumed truth on the learner/runtime surfaces, so S04 could close the milestone on an already-honest runtime authority line.
  - slice: S02
    provides: Same-session practice/report/replay parity expectations and the localhost route-family proof contract that S04 had to retire fully.
  - slice: S03
    provides: Canonical M002→M007 authority alignment plus the generated-state drift audit that S04 had to reconcile through GSD renders.
affects:
  []
key_files:
  - backend/src/evaluation/services/report_generation_trigger.py
  - backend/tests/unit/test_report_generation_trigger.py
  - backend/tests/integration/test_report_generation_trigger_fire_and_forget.py
  - backend/tests/contract/test_practice_evidence_contract.py
  - backend/tests/integration/test_replay_api.py
  - web/src/lib/api/client.ts
  - .artifacts/m007-s04-final-closure-proof.md
  - .artifacts/m007-s03-authority-audit.md
  - .gsd/REQUIREMENTS.md
key_decisions:
  - Treat persisted same-session completion plus canonical report/replay/highlights unlock as the closure authority; concurrent `kb_not_ready`, `no_scoring_context_available`, and `report_generation_failed [NO_STAGE_RESULTS]` signals stay observable but do not override that authority when the same session still completes and unlocks.
  - Advance R009 only after re-reading the focused T01-T03 regression/proof chain and the fresh localhost artifact, not from prior milestone intent or manually edited generated state.
  - Use GSD DB/render flows as the sole authority for S04 and M007 close-out artifacts; generated `STATE.md` and `state-manifest.json` must be read back after those renders instead of patched by hand.
patterns_established:
  - Prove close-out on one real same-session route family and only then let requirements or milestone artifacts advance.
  - When generated state lags canonical proof, use the GSD DB/render path and verify the read-back; do not patch system-managed files by hand.
  - Keep replay completion-gated and make the blocked state explicit instead of relaxing the gate or masking backend truth with frontend fallbacks.
observability_surfaces:
  - .artifacts/m007-s04-final-closure-proof.md
  - .artifacts/m007-s03-authority-audit.md
  - .gsd/REQUIREMENTS.md (R009 validated row)
  - Rendered S04 summary/UAT artifacts
  - .gsd/STATE.md and .gsd/state-manifest.json read-back surfaces after the milestone render flow
drill_down_paths:
  - .gsd/milestones/M007/slices/S04/tasks/T01-SUMMARY.md
  - .gsd/milestones/M007/slices/S04/tasks/T02-SUMMARY.md
  - .gsd/milestones/M007/slices/S04/tasks/T03-SUMMARY.md
  - .gsd/milestones/M007/slices/S04/tasks/T04-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-03-28T13:38:35.000Z
blocker_discovered: false
---

# S04: 最终集成验证与封板

**Retired the last R009 closure blocker, validated it from T01-T03 evidence, and closed S04 on the same DB-backed route and artifact truth line.**

## What Happened

S04 retired the last honest-closeout blocker for R009 in four steps. T01 fixed the real fire-and-forget report trigger path so own-session execution durably persists terminal report/session state instead of leaving replay truth dependent on caller-owned commits. T02 then locked the same-session contract on the existing APIs and learner pages: report stays readable during scoring, replay/highlights stay completion-gated until persisted completion, and replay copy stays explicit instead of masking backend truth. T03 added the final localhost product proof on one StepFun sales session: the same session moved `in_progress -> scoring -> completed`, report remained readable on `/practice/{sessionId}/report`, replay/highlights were blocked before completion and unlocked after persisted completion on that same session, and concurrent `kb_not_ready` / trigger-side `report_generation_failed [NO_STAGE_RESULTS]` noise was preserved as optional diagnostics rather than misclassified as the canonical blocker. T04 re-read that full evidence chain, advanced R009 to validated through the requirement-update render flow, and used the DB-backed close-out tools instead of hand-editing generated state. The slice therefore completes with one truthful authority line for realtime coaching closure: explicit regression proof, fresh localhost product proof, and generator-backed artifact reconciliation now all point at the same delivered behavior.

## Verification

S04 closed on the combined task evidence chain. T01 verified the own-session fire-and-forget persistence path with focused unit/integration pytest. T02 verified same-session report readability during scoring, replay/highlights gating before completion, post-finalization parity, and learner replay blocked-state copy. T03 verified the fresh localhost same-session proof on one StepFun session through `/practice/{sessionId}` -> `/report` -> `/replay` plus supporting APIs, with replay/highlights unlocking only after persisted completion on that same session. T04 then re-read the proof artifact and authority audit, advanced R009 through the requirement-update flow, and handed off to the GSD slice/milestone render path for final state reconciliation.

## Requirements Advanced

- R009 — Used T01-T03 regression and localhost proof to retire the remaining close-out blocker, then moved the requirement from active to validated through the GSD requirement-update flow.

## Requirements Validated

- R009 — Validated by the combined S04 evidence chain: T01 own-session fire-and-forget persistence regressions, T02 same-session report/replay/highlights gating and parity suites, and T03’s fresh localhost artifact `.artifacts/m007-s04-final-closure-proof.md` showing one StepFun session move `in_progress -> scoring -> completed` with same-session replay unlock.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

None.

## Known Limitations

Optional knowledge-check / enhanced-report noise still exists and remains visible in diagnostics, but S04 proved these signals are non-blocking when the same session persists `completed` and unlocks report/replay/highlights on the shipped route family.

## Follow-ups

None.

## Files Created/Modified

- `backend/src/evaluation/services/report_generation_trigger.py` — T01 fixed the fire-and-forget own-session finalization path so background report generation durably persists terminal report/session state.
- `backend/tests/unit/test_report_generation_trigger.py` — T01 locked caller-owned vs own-session persistence behavior and negative finalization paths.
- `backend/tests/integration/test_report_generation_trigger_fire_and_forget.py` — T01 added real own-session persistence proof for success and failure branches.
- `backend/tests/contract/test_practice_evidence_contract.py` — T02 locked same-session report readability during scoring plus replay/highlights gating and parity after completion.
- `backend/tests/integration/test_replay_api.py` — T02 proved replay remains blocked before completion and unlocks truthfully after persisted completion.
- `web/src/lib/api/client.ts` — T02 mapped `[SESSION_NOT_COMPLETED]` into explicit learner replay-blocked copy instead of leaking raw backend text.
- `.artifacts/m007-s04-final-closure-proof.md` — T03 recorded the fresh localhost same-session closure proof showing `in_progress -> scoring -> completed` plus replay unlock on the same StepFun session.
- `.artifacts/m007-s03-authority-audit.md` — S03/T03 carried forward the generated-state drift audit that S04 had to retire through normal render flows.
- `.gsd/REQUIREMENTS.md` — T04 advanced R009 to validated using explicit T01-T03 proof references through the requirement-update render path.
