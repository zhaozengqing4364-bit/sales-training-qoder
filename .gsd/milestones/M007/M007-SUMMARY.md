---
id: M007
title: "实时教练闭环正式封板"
status: complete
completed_at: 2026-03-28T13:39:47.824Z
key_decisions:
  - Treat persisted same-session completion plus canonical report/replay/highlights unlock as the closure authority, not trigger-side optional-noise logs alone.
  - Keep replay completion-gated and make blocked replay explicit instead of relaxing the gate to hide backend truth.
  - Preserve M002 as historical failed-closeout foundation while moving all live closure ownership and validation authority to M007.
  - Use GSD DB/render flows as the only authority for requirement, slice, validation, and milestone close-out artifacts; verify generated state by read-back rather than patching system-managed files.
key_files:
  - backend/src/evaluation/services/report_generation_trigger.py
  - backend/tests/integration/test_report_generation_trigger_fire_and_forget.py
  - backend/tests/contract/test_practice_evidence_contract.py
  - backend/tests/integration/test_replay_api.py
  - web/src/lib/api/client.ts
  - .artifacts/m007-s03-authority-audit.md
  - .artifacts/m007-s04-final-closure-proof.md
  - .gsd/REQUIREMENTS.md
  - .gsd/milestones/M007/M007-VALIDATION.md
  - .gsd/milestones/M007/M007-SUMMARY.md
lessons_learned:
  - For this repo, milestone close-out needs both live product proof and generator-backed state reconciliation; either side alone can still lie about completion.
  - When optional enhancement or KB diagnostics remain noisy, classify them explicitly against the canonical persisted-completion authority line instead of suppressing them or treating them as the primary blocker by default.
  - Authority-switch work is only trustworthy when canonical docs and generated state are checked separately; aligning one without reading back the other just hides drift.
---

# M007: 实时教练闭环正式封板

**Closed M007 on one truthful realtime-coaching closure line by combining same-session localhost proof, R009 validation, M002 authority absorption, and GSD render-backed milestone completion.**

## What Happened

M007 existed to close realtime coaching honestly on the shipped learner/runtime/report/replay route family and to absorb the unfinished historical M002 remediation story into one live authority line. S01 made coach degraded/resumed truthful and learner-visible without breaking the training path. S02 aligned same-session issue/goal/claim-truth semantics across runtime, `/knowledge-check`, canonical report, and replay parity on the same route family. S03 moved the remaining authority from historical M002 intent into M007 and documented the stale generated-state story instead of patching it away. S04 then retired the last live close-out blocker: T01 fixed the own-session fire-and-forget finalization path, T02 locked same-session replay/report gating and parity, T03 produced a fresh localhost same-session artifact that showed one StepFun session move `in_progress -> scoring -> completed` and unlock replay on that same session, and T04 advanced R009 through the render-backed requirement flow before closing the slice and milestone through GSD tools only. The milestone now closes on one truthful line: realtime coaching stays usable during degraded/resumed runtime states, final report/replay conclusions stay coherent on the same session, historical authority drift is absorbed into M007, and the generated project state is expected to reflect that same closure after this completion render.

## Success Criteria Results

- **Current learner route shows explicit, non-disruptive coach degraded/resumed state.** Met by S01 runtime/reducer/UI proofs.
- **One real localhost sales session stays coherent from live coaching through report and replay on the same issue/goal family.** Met by S02 parity work plus the fresh S04 localhost artifact.
- **Remaining M002 remediation facts/artifacts are formally absorbed into M007.** Met by S03 canonical doc updates, preserved M002 historical handoff, and D106/D107.
- **Realtime coaching is marked complete only when live proof and artifact reconciliation pass together.** Met by T04’s requirement update, rendered S04 summary/UAT, milestone validation pass, and this milestone completion render.

## Definition of Done Results

- **Coach degraded/resumed is explicitly visible on the existing `/practice/{sessionId}` learner surface without breaking the training mainline.** Met by S01: reconnect/runtime truth now rebuilds from live handler state, learner shell/right panel render shared degraded/resumed copy, and healthy state stays quiet.
- **Reconnect, restore, runtime diagnostics, and learner UI all agree on coach health instead of drifting after recovery.** Met by S01 backend restore tests, `/knowledge-check` integration proof, and learner reducer/UI regression coverage.
- **At least one real localhost sales session proves realtime coaching, final report, and final replay stay on the same issue/goal family without cross-session stitching.** Met by S02/T03 proof line and the fresh S04 localhost artifact `.artifacts/m007-s04-final-closure-proof.md`, which records one StepFun session moving from `in_progress` to `scoring` to persisted `completed` and unlocking replay/highlights on the same session.
- **The remaining M002 remediation facts and artifacts are formally absorbed into M007, and closure authority is no longer split between an old M002 remediation narrative and the live product truth.** Met by S03 canonical doc updates, preserved M002 forward pointers, D106/D107, and the authority audit artifact.
- **`.gsd/REQUIREMENTS.md`, M007 roadmap/context, validation, summary, and state no longer contradict the delivered closure status.** Met by R009’s validated status transition plus the generator-backed M007 validation/summary/state render flow executed in this task.
- **R009 advances to validated only if both product truth and artifact reconciliation pass together.** Met by T04’s re-read of T01-T03 evidence, the requirement-update render, and this same-cycle milestone validation/completion pass.

## Requirement Outcomes

- **R009:** `active -> validated`
  - **Why:** S01-S04 together now prove the shipped realtime coaching loop truthfully from learner runtime through canonical report/replay. T01 fixed own-session background finalization persistence, T02 locked same-session replay/report contract coverage, T03 produced the fresh localhost same-session proof artifact, and T04 advanced the requirement through the GSD requirement-update flow only after re-reading that evidence chain.
  - **Evidence:** `.artifacts/m007-s04-final-closure-proof.md`, `.artifacts/m007-s03-authority-audit.md`, `backend/tests/unit/test_report_generation_trigger.py`, `backend/tests/integration/test_report_generation_trigger_fire_and_forget.py`, `backend/tests/contract/test_practice_evidence_contract.py`, `backend/tests/integration/test_replay_api.py`, learner report/replay page tests, rendered `M007-VALIDATION.md`.

No other requirement status changed in this milestone close-out.

## Deviations

None.

## Follow-ups

None.
