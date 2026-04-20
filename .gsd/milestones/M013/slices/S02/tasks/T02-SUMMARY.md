---
id: T02
parent: S02
milestone: M013
provides: []
requires: []
affects: []
key_files: ["docs/plans/2026-04-08-system-audit-remediation-plan.md", ".gsd/plans/GSD_PLAN_system-audit-repair.md", ".gsd/milestones/M013/slices/S02/tasks/T02-SUMMARY.md"]
key_decisions: ["Document backend-focused pytest as repo-root-only, serial commands in both the execution handoff and the GSD authority plan instead of relying on KNOWLEDGE-only context."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Ran the task-plan verification command exactly as written and confirmed both plan documents now contain the required repo-root backend pytest string plus the serial/coverage wording."
completed_at: 2026-04-09T17:03:35.561Z
blocker_discovered: false
---

# T02: Added an explicit repo-root serial backend pytest contract to both audit remediation plans so downstream slices can reuse focused commands without false auto-mode failures.

> Added an explicit repo-root serial backend pytest contract to both audit remediation plans so downstream slices can reuse focused commands without false auto-mode failures.

## What Happened
---
id: T02
parent: S02
milestone: M013
key_files:
  - docs/plans/2026-04-08-system-audit-remediation-plan.md
  - .gsd/plans/GSD_PLAN_system-audit-repair.md
  - .gsd/milestones/M013/slices/S02/tasks/T02-SUMMARY.md
key_decisions:
  - Document backend-focused pytest as repo-root-only, serial commands in both the execution handoff and the GSD authority plan instead of relying on KNOWLEDGE-only context.
duration: ""
verification_result: passed
completed_at: 2026-04-09T17:03:35.562Z
blocker_discovered: false
---

# T02: Added an explicit repo-root serial backend pytest contract to both audit remediation plans so downstream slices can reuse focused commands without false auto-mode failures.

**Added an explicit repo-root serial backend pytest contract to both audit remediation plans so downstream slices can reuse focused commands without false auto-mode failures.**

## What Happened

Reviewed the task contract, slice plan, T01 summary, and both remediation-plan documents to confirm the remaining gap. The plans already listed repo-root backend pytest commands, but the execution handoff did not make the auto-mode-safe contract explicit where downstream slices would copy the commands. Updated docs/plans/2026-04-08-system-audit-remediation-plan.md with a dedicated backend pytest contract that preserves the repo-root command form, forbids collapsing it back to `cd backend && pytest ...`, and states that multiple backend proofs must run serially because repo-root pytest-cov runs share the top-level `.coverage` SQLite file. Mirrored the same rule into .gsd/plans/GSD_PLAN_system-audit-repair.md under M013-S02 so the authority plan and the handoff plan now describe the same verification constraint.

## Verification

Ran the task-plan verification command exactly as written and confirmed both plan documents now contain the required repo-root backend pytest string plus the serial/coverage wording.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `rg -n "串行|coverage|backend/venv/bin/python -m pytest -c backend/pyproject.toml" docs/plans/2026-04-08-system-audit-remediation-plan.md .gsd/plans/GSD_PLAN_system-audit-repair.md` | 0 | ✅ pass | 39ms |


## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `docs/plans/2026-04-08-system-audit-remediation-plan.md`
- `.gsd/plans/GSD_PLAN_system-audit-repair.md`
- `.gsd/milestones/M013/slices/S02/tasks/T02-SUMMARY.md`


## Deviations
None.

## Known Issues
None.
