---
estimated_steps: 3
estimated_files: 7
skills_used:
  - safe-grow
  - verification-before-completion
---

# T04: Validate and close M007 through GSD render flows, then read back generated state truthfully

**Slice:** S04 — 最终集成验证与封板
**Milestone:** M007

## Description

The slice is only done if the proof and the generated project state agree. The executor should load `safe-grow` and `verification-before-completion`. This task consumes the focused regression evidence and the fresh localhost proof, advances R009 only if that evidence is real, and then uses GSD DB/render flows to complete the slice and milestone without hand-editing generated state.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| focused regression evidence from T01-T03 | stop and surface a blocker instead of forcing close-out | do not proceed until the missing verification is rerun or explicitly failed | reject proof that does not clearly show same-session persisted completion and replay unlock |
| GSD completion / validation tool flow | stop on the first non-pass verdict and capture the rendered blocker instead of editing generated files manually | rerun only with the same evidence set if the tool itself requires it; do not mutate the story to make it pass | treat missing or contradictory rendered outputs as a blocker to investigate, not a prompt to hand-edit files |
| rendered state read-back (`.gsd/STATE.md`, `.gsd/state-manifest.json`) | keep the mismatch explicit and unclosed until the generator-backed truth is fixed | stop before declaring success if read-back cannot be verified | do not infer milestone truth from partial or stale generated surfaces |

## Load Profile

- **Shared resources**: one DB-backed render pass plus read-back checks on generated state files.
- **Per-operation cost**: requirement update, slice completion, milestone validation, milestone completion, and two small rendered-state reads.
- **10x breakpoint**: duplicate completion calls with changing payloads or repeated re-renders that drift from the proof set; keep one coherent close-out pass.

## Negative Tests

- **Malformed inputs**: missing proof artifact, incomplete task evidence, or weak proof notes for R009 validation.
- **Error paths**: milestone validation returning anything but `pass`, or GSD render flows producing incomplete/missing files.
- **Boundary conditions**: generated state that still shows M007 queued or M002 active after the render path completes.

## Steps

1. Re-read the focused regression evidence plus `.artifacts/m007-s04-final-closure-proof.md`; if they do not prove the same-session route family and persisted completion transition, stop and surface a blocker instead of forcing close-out.
2. Move R009 to validated with concrete proof notes, then use the GSD tool flow (`gsd_complete_task`, `gsd_complete_slice`, `gsd_validate_milestone`, `gsd_complete_milestone`) to render slice and milestone artifacts instead of editing generated files.
3. Read back `.gsd/STATE.md` and `.gsd/state-manifest.json`; if M007 or R009 still look stale after the render flow, treat that as an unresolved blocker and do not hand-edit system-managed state.

## Must-Haves

- [ ] R009 advances only with explicit proof references from T01-T03.
- [ ] Generated slice/milestone artifacts are created through GSD tools only.
- [ ] Rendered state no longer reports M007 as queued or M002 as active.

## Verification

- `test -s .gsd/milestones/M007/slices/S04/S04-SUMMARY.md && test -s .gsd/milestones/M007/slices/S04/S04-UAT.md && test -s .gsd/milestones/M007/M007-VALIDATION.md && test -s .gsd/milestones/M007/M007-SUMMARY.md`
- `rg -n "^R009 .*\(validated\)" .gsd/REQUIREMENTS.md`
- `python - <<'PY'
import json
from pathlib import Path
manifest = json.loads(Path('.gsd/state-manifest.json').read_text())
milestones = {item['id']: item for item in manifest['milestones']}
assert milestones['M007']['status'] == 'complete', milestones['M007']
assert milestones['M007']['title'], milestones['M007']
assert milestones['M002']['status'] != 'active', milestones['M002']
print('state-manifest ok')
PY`

## Observability Impact

- Signals added/changed: milestone validation verdict, rendered slice/milestone summaries, requirement status transition for R009, and generated-state read-back for M007/R009.
- How a future agent inspects this: read the rendered S04 summary/UAT, M007 validation/summary, `.gsd/STATE.md`, and `.gsd/state-manifest.json` after the GSD tool flow completes.
- Failure state exposed: whether close-out failed because proof was insufficient, validation failed, or generated state remained stale despite canonical DB/render operations.

## Inputs

- `.artifacts/m007-s04-final-closure-proof.md` — fresh same-session product proof
- `.artifacts/m007-s03-authority-audit.md` — pre-closeout generated-state drift audit
- `.gsd/REQUIREMENTS.md` — current R009 ownership and status
- `.gsd/STATE.md` — generated state read-back surface
- `.gsd/state-manifest.json` — generated structured state read-back surface
- `.gsd/milestones/M007/M007-ROADMAP.md` — current milestone closure contract

## Expected Output

- `.gsd/REQUIREMENTS.md` — R009 moved to validated with proof notes
- `.gsd/milestones/M007/slices/S04/S04-SUMMARY.md` — rendered slice summary
- `.gsd/milestones/M007/slices/S04/S04-UAT.md` — rendered slice UAT artifact
- `.gsd/milestones/M007/M007-VALIDATION.md` — rendered milestone validation artifact
- `.gsd/milestones/M007/M007-SUMMARY.md` — rendered milestone summary
- `.gsd/STATE.md` — updated generated state surface
- `.gsd/state-manifest.json` — updated generated structured state surface
