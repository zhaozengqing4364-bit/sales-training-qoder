---
estimated_steps: 3
estimated_files: 4
skills_used:
  - safe-grow
  - verification-before-completion
---

# T02: Add dated M007 handoff notes to preserved M002 close-out artifacts

**Slice:** S03 — M002 remediation 归并与权威切换
**Milestone:** M007

## Description

Once the active authority is clear, reconcile the preserved M002 record without rewriting history. This task is about making the failed M002 close-out readable as preserved history with a forward pointer, not about repairing M002 into a completed milestone or inventing missing remediation slices.

## Steps

1. Update `.gsd/milestones/M002/M002-SUMMARY.md` and `.gsd/milestones/M002/M002-VALIDATION.md` with a short dated note that unresolved close-out/remediation work was later absorbed by M007.
2. Keep the original failed-audit verdict, slice inventory, and timeline intact; do not create fake `M002/S07` or `M002/S08` directories or language that implies M002 later completed.
3. Re-read the preserved M002 artifacts and confirm they now act as historical records with a forward pointer rather than a second live plan.

## Must-Haves

- [ ] The preserved M002 summary and validation still read as historical failed-closeout artifacts first.
- [ ] Each preserved M002 artifact includes a dated forward pointer to M007 as the current closure owner.
- [ ] No file invents executable `M002/S07` / `M002/S08` artifacts or retroactively marks M002 complete.

## Verification

- `rg -n "M007|S07|S08|2026-03-25|historical|failed|needs-remediation" .gsd/milestones/M002/M002-SUMMARY.md .gsd/milestones/M002/M002-VALIDATION.md`

## Inputs

- `.gsd/milestones/M002/M002-SUMMARY.md` — preserved failed close-out summary
- `.gsd/milestones/M002/M002-VALIDATION.md` — preserved failed validation record
- `.gsd/milestones/M002/M002-ROADMAP.md` — preserved historical slice inventory context
- `.gsd/milestones/M007/M007-ROADMAP.md` — current owner slices to point readers toward
- `.gsd/DECISIONS.md` — new authority-switch decision for consistent wording

## Expected Output

- `.gsd/milestones/M002/M002-SUMMARY.md` — historical summary with dated forward pointer
- `.gsd/milestones/M002/M002-VALIDATION.md` — historical validation with dated forward pointer
