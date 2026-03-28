---
estimated_steps: 3
estimated_files: 5
skills_used:
  - safe-grow
  - verification-before-completion
---

# T01: Record the M002→M007 closure authority in current GSD sources

**Slice:** S03 — M002 remediation 归并与权威切换
**Milestone:** M007

## Description

Lock the active authority line before touching historical artifacts. This task establishes the durable current-state story: M002 remains the preserved failed close-out/foundation milestone, while unfinished R009 closure authority now belongs to M007. Do not rely on implied context or execution chatter; write the mapping explicitly where future agents will actually look.

## Steps

1. Save one explicit authority-switch decision that maps historical `M002/S07-S08` intent to `M007/S01-S04` and states that M007 now owns the remaining closure/proof work.
2. Tighten current-facing sources such as `.gsd/PROJECT.md`, `.gsd/REQUIREMENTS.md`, and the M007 milestone context/roadmap surfaces so they point unfinished work at M007 rather than a phantom M002 remediation branch.
3. Re-read the current-facing sources with focused grep/read-back checks and remove any wording that still implies future execution should happen under `M002/S07` or `M002/S08`.

## Must-Haves

- [ ] `.gsd/DECISIONS.md` contains a durable M002→M007 authority-switch entry.
- [ ] `.gsd/PROJECT.md`, `.gsd/REQUIREMENTS.md`, and M007-facing milestone docs name M007 as the only live owner of the remaining R009 closure work.
- [ ] Current-facing docs preserve M002 as historical foundation only and do not silently mark it completed later.

## Verification

- `rg -n "M002|M007|R009|S07|S08|authority|historical" .gsd/DECISIONS.md .gsd/PROJECT.md .gsd/REQUIREMENTS.md .gsd/milestones/M007/M007-CONTEXT.md .gsd/milestones/M007/M007-ROADMAP.md`

## Inputs

- `.gsd/DECISIONS.md` — current decision register and existing M007 authority decisions
- `.gsd/PROJECT.md` — current milestone state narrative
- `.gsd/REQUIREMENTS.md` — active requirement ownership for R009
- `.gsd/milestones/M007/M007-CONTEXT.md` — milestone scope and closure framing
- `.gsd/milestones/M007/M007-ROADMAP.md` — current slice ownership and demo wording
- `.gsd/milestones/M007/slices/S01/S01-SUMMARY.md` — completed authority work already absorbed by M007
- `.gsd/milestones/M007/slices/S02/S02-SUMMARY.md` — current remaining blocker framing

## Expected Output

- `.gsd/DECISIONS.md` — new authority-switch decision recorded
- `.gsd/PROJECT.md` — current-state milestone story clarified
- `.gsd/REQUIREMENTS.md` — R009 support/ownership wording tightened if needed
- `.gsd/milestones/M007/M007-CONTEXT.md` — milestone authority wording clarified
- `.gsd/milestones/M007/M007-ROADMAP.md` — active closure story aligned to M007
