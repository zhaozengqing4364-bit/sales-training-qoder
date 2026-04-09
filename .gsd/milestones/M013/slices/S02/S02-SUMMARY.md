---
id: S02
parent: M013
milestone: M013
provides:
  - A repo-root verification inventory for auth, dashboard, history, profile, practice, lifecycle, websocket, and admin surfaces.
  - An explicit repo-root + serial backend pytest contract that later auto-mode runs can copy safely.
  - A centralized M014-M018 verification baseline map with honest exceptions for M018/S02 dependency-governance and M018/S03 backup-recovery work.
requires:
  - slice: S01
    provides: Five-way audit disposition matrix, closeout appendix, and logical-to-real owner crosswalk for all 51 SYSTEM_AUDIT_REPORT findings.
affects:
  - M014/S01
  - M014/S02
  - M014/S03
  - M014/S04
  - M015/S01
  - M015/S02
  - M015/S03
  - M016/S01
  - M016/S02
  - M016/S03
  - M017/S01
  - M017/S02
  - M017/S03
  - M018/S01
  - M018/S02
  - M018/S03
key_files:
  - docs/plans/2026-04-08-system-audit-remediation-plan.md
  - .gsd/plans/GSD_PLAN_system-audit-repair.md
  - .gsd/milestones/M013/M013-ROADMAP.md
  - .gsd/DECISIONS.md
  - .gsd/KNOWLEDGE.md
  - .gsd/PROJECT.md
key_decisions:
  - Reuse the smallest existing focused web/backend suites per surface instead of inventing umbrella regression commands.
  - Keep backend-focused pytest proofs repo-root runnable and serial in both the execution handoff and the GSD authority plan.
  - Preserve M018/S02 dependency-governance and M018/S03 backup-recovery as explicit non-feature verification exceptions.
patterns_established:
  - Lock verification baselines by surface and reuse the smallest existing repo-root command instead of inventing umbrella suites.
  - Document auto-mode-sensitive backend proof rules in both the execution handoff and the GSD authority plan so later executors do not depend on chat memory or knowledge-only context.
  - Keep non-feature governance/runbook slices as explicit verification exceptions when forcing them into feature-surface tests would make the roadmap less truthful.
observability_surfaces:
  - none
drill_down_paths:
  - .gsd/milestones/M013/slices/S02/tasks/T01-SUMMARY.md
  - .gsd/milestones/M013/slices/S02/tasks/T02-SUMMARY.md
  - .gsd/milestones/M013/slices/S02/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-09T17:32:19.129Z
blocker_discovered: false
---

# S02: 审计相关验证基线补齐

**Locked a reusable repo-root verification baseline for every downstream audit-repair slice, including a serial backend-pytest contract and explicit governance/runbook exceptions for non-feature work.**

## What Happened

S02 turned M013 from audit normalization into an execution-ready verification handoff. T01 added a repo-root focused verification inventory to `docs/plans/2026-04-08-system-audit-remediation-plan.md`, mapping the real existing auth, dashboard, history, profile, practice, lifecycle, websocket, and admin surfaces to the smallest reusable web/backend commands instead of inventing new umbrella suites. T02 then made the backend execution contract explicit in both `docs/plans/2026-04-08-system-audit-remediation-plan.md` and `.gsd/plans/GSD_PLAN_system-audit-repair.md`: downstream slices must copy repo-root backend pytest commands verbatim and run them serially so auto-mode does not split `cd backend && pytest ...` into false failures and does not trip the shared top-level `.coverage` SQLite race. T03 finished the slice by centralizing the downstream verification baseline map for every slice in M014-M018, mirroring that contract into `.gsd/milestones/M013/M013-ROADMAP.md`, and preserving M018/S02 dependency-governance plus M018/S03 backup-recovery as explicit ops/runbook verification exceptions instead of forcing fake web/backend feature tests. During closeout I reviewed the task summaries, recorded the missing verification decisions in `.gsd/DECISIONS.md`, added one reusable knowledge note that dashboard/profile remain web-led surfaces until dedicated backend suites exist, and refreshed `.gsd/PROJECT.md` so the current state now reflects S02 as complete. The net result is that later repair/discovery executors can start from one authoritative verification map and spend time on real defects instead of re-researching or mis-running proof commands.

## Verification

Fresh slice-close verification reran all planned gates plus one coverage-completeness check from the repo root. 1) `rg -n "npm --prefix web test|backend/venv/bin/python -m pytest" docs/plans/2026-04-08-system-audit-remediation-plan.md` passed and confirmed the focused inventory plus downstream map still expose repo-root web/backend commands. 2) `rg -n "串行|coverage|backend/venv/bin/python -m pytest -c backend/pyproject.toml" docs/plans/2026-04-08-system-audit-remediation-plan.md .gsd/plans/GSD_PLAN_system-audit-repair.md` passed and confirmed both plan documents still carry the repo-root backend pytest form plus the serial/coverage contract. 3) The T03 plan grep was rerun successfully with a shell that actually expands `**`: `zsh -c 'setopt extended_glob; rg -n "npm --prefix web test|backend/venv/bin/python -m pytest" .gsd/milestones/M01{4,5,6,7,8}*/**/*.md docs/plans/2026-04-08-system-audit-remediation-plan.md'` passed and showed the downstream milestone plans plus the remediation handoff all expose the expected reusable baseline commands. 4) A structured scan over every M014-M018 roadmap/slice plan confirmed all 16 downstream slices are covered: 14 slices already carry a focused reusable baseline command and 2 slices (`M018/S02`, `M018/S03`) are explicitly documented as governance/runbook exceptions with honest non-feature proof commands. No missing downstream verification baselines remained.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

Minor closeout-only adaptation: the literal `**/*.md` T03 grep was rerun under `zsh` because the default shell harness here does not expand `**`. The verification target and path pattern stayed the same, and the structured scan was added only to prove slice-goal completeness beyond grep visibility.

## Known Limitations

This slice documents and locks reusable verification baselines; it does not add new product tests or retire downstream defects by itself. Dashboard and profile remain web-led surfaces today because the repository still has no dedicated backend-focused suites that map only to those pages.

## Follow-ups

Proceed into M014-M018 using the locked baseline map instead of re-researching proof commands. Keep backend pytest proofs repo-root runnable and serial, keep dashboard/profile slices web-led unless the change truly crosses a backend seam, and preserve the documented M018/S02-M018/S03 governance/runbook exceptions rather than forcing them into feature-surface test shapes.

## Files Created/Modified

- `docs/plans/2026-04-08-system-audit-remediation-plan.md` — Added the repo-root focused verification inventory, backend serial pytest contract, and downstream M014-M018 baseline map.
- `.gsd/plans/GSD_PLAN_system-audit-repair.md` — Mirrored the repo-root backend pytest/serial contract into the GSD authority plan for downstream repair slices.
- `.gsd/milestones/M013/M013-ROADMAP.md` — Recorded the centralized downstream verification baseline contract for later audit-repair slices.
- `.gsd/DECISIONS.md` — Appended the missing M013/S02 verification decisions covering reusable focused suites, backend serial pytest, and governance/runbook exceptions.
- `.gsd/KNOWLEDGE.md` — Added future-agent guidance that dashboard/profile are web-led verification surfaces and retained the shell-glob gotcha for milestone-plan greps.
- `.gsd/PROJECT.md` — Refreshed current-state tracking so M013/S02 now appears complete and downstream slices are told to consume the new verification crosswalk.
