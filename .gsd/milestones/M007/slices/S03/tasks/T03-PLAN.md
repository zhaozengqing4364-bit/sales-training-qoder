---
estimated_steps: 3
estimated_files: 6
skills_used:
  - safe-grow
  - verification-before-completion
---

# T03: Audit rendered state surfaces and capture any remaining generator drift

**Slice:** S03 — M002 remediation 归并与权威切换
**Milestone:** M007

## Description

Finish by proving whether the canonical authority switch actually reached the system-managed state surfaces. This task is read-heavy and proof-heavy: verify `.gsd/STATE.md` and `.gsd/state-manifest.json`, but do not hand-edit them as if they were primary sources. The output is an audit artifact that S04 can use directly during final validation.

## Steps

1. Re-run the M002 slice inventory and authority-line grep across `.gsd/milestones/M002`, `.gsd/milestones/M007`, `.gsd/PROJECT.md`, `.gsd/REQUIREMENTS.md`, `.gsd/DECISIONS.md`, `.gsd/STATE.md`, and `.gsd/state-manifest.json`.
2. Read back `.gsd/STATE.md` and `.gsd/state-manifest.json` after the canonical doc updates; if they still disagree with the active authority story, capture the exact mismatch and why it must remain an explicit blocker/follow-up rather than a hand-edited fix.
3. Write a compact audit artifact for S04 that records the inventory truth, the authority-line read-back, and the remaining generator-backed drift status.

## Must-Haves

- [ ] `.gsd/STATE.md` and `.gsd/state-manifest.json` are explicitly rechecked after canonical updates.
- [ ] `.artifacts/m007-s03-authority-audit.md` records the exact alignment or residual mismatch instead of glossing over it.
- [ ] The task leaves generated state surfaces untouched and documents any remaining drift as explicit evidence for S04.

## Verification

- `find .gsd/milestones/M002/slices -maxdepth 1 -mindepth 1 -type d | sort && printf '\n---\n' && rg -n "M002|M007|R009|needs-remediation|historical|authority|S07|S08" .gsd/milestones/M002 .gsd/milestones/M007 .gsd/PROJECT.md .gsd/REQUIREMENTS.md .gsd/DECISIONS.md .gsd/STATE.md .gsd/state-manifest.json && test -s .artifacts/m007-s03-authority-audit.md`

## Observability Impact

- Signals added/changed: one audit artifact that records whether generated state followed the canonical authority switch or still drifts.
- How a future agent inspects this: read `.artifacts/m007-s03-authority-audit.md` together with `.gsd/STATE.md` and `.gsd/state-manifest.json`.
- Failure state exposed: exact file-level mismatch between canonical docs and generated status surfaces.

## Inputs

- `.gsd/PROJECT.md` — current milestone narrative after T01
- `.gsd/REQUIREMENTS.md` — current R009 ownership wording after T01
- `.gsd/DECISIONS.md` — authority-switch decision after T01
- `.gsd/milestones/M002/M002-SUMMARY.md` — preserved historical record after T02
- `.gsd/milestones/M002/M002-VALIDATION.md` — preserved historical record after T02
- `.gsd/STATE.md` — system-managed rendered state surface to verify
- `.gsd/state-manifest.json` — system-managed structured state surface to verify

## Expected Output

- `.artifacts/m007-s03-authority-audit.md` — compact proof artifact for S04 close-out and validation
