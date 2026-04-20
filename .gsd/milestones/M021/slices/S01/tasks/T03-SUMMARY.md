---
id: T03
parent: S01
milestone: M021
key_files:
  - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
  - .gsd/plans/GSD_PLAN_post-M018-next-wave.md
  - .gsd/DECISIONS.md
key_decisions:
  - Treat the M021/S01 must-keep / compat / retire-candidate matrix as the execution authority for S02-S04 instead of re-deriving AI seam status in each later slice.
  - Do not retire legacy evaluation/report or classic scoring paths until their shipped report-status, operator, classic-runtime, and debug consumers are migrated to canonical live evidence surfaces.
duration: 
verification_result: passed
completed_at: 2026-04-14T01:50:36.777Z
blocker_discovered: false
---

# T03: Added the M021 live/compat/retire input matrix and legacy-consumer guardrails to the architecture scan and next-wave plan.

**Added the M021 live/compat/retire input matrix and legacy-consumer guardrails to the architecture scan and next-wave plan.**

## What Happened

I turned the existing M021/S01 live AI authority inventory into an execution-ready downstream matrix instead of leaving it as descriptive labels only. In `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`, I added a T03 matrix that classifies the real AI/runtime/prompt/score/report seams into **must keep**, **compat**, and **retire candidate**, and pairs each seam with its current consumer/blocker plus the intended S02-S04 handling. That write-back now makes the downstream contract explicit: the live StepFun runtime, compiled voice snapshot, and knowledge compat rollout seams remain the authority; PromptTemplateService and classic scoring stay compat-owned; staged/comprehensive evaluation plus `common/ai/llm_service.py::evaluate/generate_report` are retire candidates only after their shipped consumers migrate. In `.gsd/plans/GSD_PLAN_post-M018-next-wave.md`, I added the matching M021 S02-S04 input matrix so later slices can execute against the same keep/compat/retire model without rediscovering it. I also made the no-brute-delete rule explicit for the legacy consumers that still matter in this milestone: classic `voice_mode == "legacy"` runtime, `report_status` / comprehensive-report readers, manual `/evaluation/*` operator flows, PromptTemplateService admin/runtime helper usage, and knowledge compat debug/audit consumers. Because that consumer-migration rule is now a real downstream authority decision rather than a transient note, I recorded it as GSD decision D230.

## Verification

Ran the exact task-plan verification command `rg -n "must keep|compat|retire candidate|consumer" .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md .gsd/plans/GSD_PLAN_post-M018-next-wave.md` and confirmed both target documents now expose the keep/compat/retire matrix language plus explicit consumer guardrails for downstream slices. Read back the edited sections to confirm the matrix content landed under the M021/S01 analysis section and the M021 slice block in the next-wave plan.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `rg -n "must keep|compat|retire candidate|consumer" .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md .gsd/plans/GSD_PLAN_post-M018-next-wave.md` | 0 | ✅ pass | 43ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`
- `.gsd/plans/GSD_PLAN_post-M018-next-wave.md`
- `.gsd/DECISIONS.md`
