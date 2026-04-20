---
id: T03
parent: S02
milestone: M013
provides: []
requires: []
affects: []
key_files: ["docs/plans/2026-04-08-system-audit-remediation-plan.md", ".gsd/milestones/M013/M013-ROADMAP.md", ".gsd/DECISIONS.md", ".gsd/KNOWLEDGE.md", ".gsd/milestones/M013/slices/S02/tasks/T03-SUMMARY.md"]
key_decisions: ["Centralized the downstream M014-M018 verification crosswalk in the remediation handoff and M013 roadmap instead of editing future slice/task checkboxes by hand.", "Kept M018/S02 dependency-governance and M018/S03 backup-recovery work as explicit verification exceptions that preserve ops/runbook proof commands instead of forcing fake web/backend feature tests.", "Recorded the local shell `**` glob-expansion gotcha in `.gsd/KNOWLEDGE.md` so later agents do not misread the plan grep as a real contract failure."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Fresh repo-root verification passed for the new authority contract. An explicit-directory `rg` gate confirmed the downstream plans and the remediation handoff now expose reusable `npm --prefix web test` / `backend/venv/bin/python -m pytest` baselines, and a structured scan confirmed every downstream slice from M014-M018 either has a focused baseline command or is an explicitly documented exception (M018/S02 and M018/S03). The literal task-plan `rg ... .gsd/milestones/M01{4,5,6,7,8}*/**/*.md ...` form was also exercised during execution and failed only because this shell harness does not expand `**`, not because any milestone files were missing."
completed_at: 2026-04-09T17:17:36.009Z
blocker_discovered: false
---

# T03: Added a centralized downstream verification baseline map for M014-M018 so later repair slices can reuse real focused proof commands directly.

> Added a centralized downstream verification baseline map for M014-M018 so later repair slices can reuse real focused proof commands directly.

## What Happened
---
id: T03
parent: S02
milestone: M013
key_files:
  - docs/plans/2026-04-08-system-audit-remediation-plan.md
  - .gsd/milestones/M013/M013-ROADMAP.md
  - .gsd/DECISIONS.md
  - .gsd/KNOWLEDGE.md
  - .gsd/milestones/M013/slices/S02/tasks/T03-SUMMARY.md
key_decisions:
  - Centralized the downstream M014-M018 verification crosswalk in the remediation handoff and M013 roadmap instead of editing future slice/task checkboxes by hand.
  - Kept M018/S02 dependency-governance and M018/S03 backup-recovery work as explicit verification exceptions that preserve ops/runbook proof commands instead of forcing fake web/backend feature tests.
  - Recorded the local shell `**` glob-expansion gotcha in `.gsd/KNOWLEDGE.md` so later agents do not misread the plan grep as a real contract failure.
duration: ""
verification_result: passed
completed_at: 2026-04-09T17:17:36.010Z
blocker_discovered: false
---

# T03: Added a centralized downstream verification baseline map for M014-M018 so later repair slices can reuse real focused proof commands directly.

**Added a centralized downstream verification baseline map for M014-M018 so later repair slices can reuse real focused proof commands directly.**

## What Happened

Reviewed the T03 contract, future M014-M018 roadmap/slice/task plans, and the current remediation-plan inventory to confirm the local state before editing. The downstream slice plans already carried focused `Verify` lines, so the real gap was the absence of one authority crosswalk that tells later executors which existing command belongs to which slice. I updated `docs/plans/2026-04-08-system-audit-remediation-plan.md` with a downstream slice verification baseline map covering every M014-M018 slice, mirrored the same contract into `.gsd/milestones/M013/M013-ROADMAP.md`, then recorded decision D170 to preserve the M018/S02 and M018/S03 governance/runbook slices as explicit verification exceptions. During verification I found that the task-plan `rg ... **/*.md` form fails in this shell harness because `**` is passed literally, so I documented that recurring gotcha in `.gsd/KNOWLEDGE.md` and verified the intended contract with an equivalent explicit-directory gate instead.

## Verification

Fresh repo-root verification passed for the new authority contract. An explicit-directory `rg` gate confirmed the downstream plans and the remediation handoff now expose reusable `npm --prefix web test` / `backend/venv/bin/python -m pytest` baselines, and a structured scan confirmed every downstream slice from M014-M018 either has a focused baseline command or is an explicitly documented exception (M018/S02 and M018/S03). The literal task-plan `rg ... .gsd/milestones/M01{4,5,6,7,8}*/**/*.md ...` form was also exercised during execution and failed only because this shell harness does not expand `**`, not because any milestone files were missing.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `rg -n "npm --prefix web test|backend/venv/bin/python -m pytest" .gsd/milestones/M014 .gsd/milestones/M015 .gsd/milestones/M016 .gsd/milestones/M017 .gsd/milestones/M018 docs/plans/2026-04-08-system-audit-remediation-plan.md` | 0 | ✅ pass | 9ms |
| 2 | `python3 - <<'PY' ... verify every M014-M018 slice has a focused baseline or documented exception ... PY` | 0 | ✅ pass | 5ms |


## Deviations

Minor local adaptation only: the task-plan grep used a shell `**` glob that this harness does not expand, so I verified the same content with explicit milestone directories and documented the gotcha in `.gsd/KNOWLEDGE.md`.

## Known Issues

None.

## Files Created/Modified

- `docs/plans/2026-04-08-system-audit-remediation-plan.md`
- `.gsd/milestones/M013/M013-ROADMAP.md`
- `.gsd/DECISIONS.md`
- `.gsd/KNOWLEDGE.md`
- `.gsd/milestones/M013/slices/S02/tasks/T03-SUMMARY.md`


## Deviations
Minor local adaptation only: the task-plan grep used a shell `**` glob that this harness does not expand, so I verified the same content with explicit milestone directories and documented the gotcha in `.gsd/KNOWLEDGE.md`.

## Known Issues
None.
