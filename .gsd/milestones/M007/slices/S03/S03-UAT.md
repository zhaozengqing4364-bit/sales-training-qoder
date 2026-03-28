# S03: M002 remediation 归并与权威切换 — UAT

**Milestone:** M007
**Written:** 2026-03-28T10:17:50.742Z

# S03: M002 remediation 归并与权威切换 — UAT

**Milestone:** M007
**Written:** 2026-03-28

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: this slice changes milestone authority, preserved historical records, and generator-backed state read-backs rather than application runtime code. The credible proof is that canonical docs, preserved M002 artifacts, and generated surfaces now tell one truthful story with any remaining drift made explicit.

## Preconditions

- The completed task summaries for `M007/S03/T01-T03` exist.
- `.artifacts/m007-s03-authority-audit.md` exists.
- `R009` has been re-rendered from the GSD database so the live owner/supporting slices reflect M007.
- The repo still contains only the preserved historical M002 slice directories that actually shipped.

## Smoke Test

Open `.gsd/REQUIREMENTS.md` and confirm the `R009` row says:
- **Primary owning slice:** `M007/S04`
- **Supporting slices:** `M007/S01, M007/S02, M007/S03`
- **Notes:** M007 is the only live owner and there is no continuing `M002/S07` or `M002/S08`

## Test Cases

### 1. Current-facing GSD sources point all remaining closure work to M007

1. Open `.gsd/PROJECT.md`, `.gsd/REQUIREMENTS.md`, `.gsd/milestones/M007/M007-CONTEXT.md`, and `.gsd/milestones/M007/M007-ROADMAP.md`.
2. Open `.gsd/DECISIONS.md` and locate `D106` plus `D107`.
3. Confirm these sources consistently say M002 is preserved historical failed-closeout foundation only, M007 is the sole current authority for unfinished R009 closure work, and current work should not continue under `M002/S07` or `M002/S08`.
4. **Expected:** every current-facing source points future execution and final validation at M007, not at a phantom M002 remediation branch.

### 2. Preserved M002 artifacts still read as failed-closeout history with a forward pointer

1. Open `.gsd/milestones/M002/M002-SUMMARY.md`.
2. Open `.gsd/milestones/M002/M002-VALIDATION.md`.
3. Confirm each file contains a dated 2026-03-28 historical handoff note that points readers to M007 / D106.
4. Confirm the original 2026-03-25 failed / `needs-remediation` record, slice inventory, and remediation gaps are still present.
5. **Expected:** M002 remains an accurate historical failed-closeout record, not a retroactively completed milestone and not an active execution plan.

### 3. M002 inventory truth shows there were never executable remediation slices under M002

1. List directories under `.gsd/milestones/M002/slices/`.
2. Confirm only `S01`, `S02`, `S03`, and `S04` exist.
3. Confirm no `S07` or `S08` directories or summary/UAT artifacts exist under M002.
4. **Expected:** the repository inventory matches the historical story: M002 delivered S01-S04 only, and later closure work was absorbed into M007 instead of being executed under new M002 slices.

### 4. Generated-state drift is recorded explicitly instead of being silently patched away

1. Open `.artifacts/m007-s03-authority-audit.md`.
2. Read the sections for `.gsd/STATE.md` and `.gsd/state-manifest.json`.
3. Open `.gsd/STATE.md` and verify it shows `Active Milestone: M007` / `Active Slice: S03` while still rendering M002 too optimistically.
4. Open `.gsd/state-manifest.json` and verify the audit’s quoted drift still matches the file (`M002 active`, `M007 queued`, blank titles, `completed_at: null`).
5. **Expected:** the audit precisely documents the remaining mismatch, and the generated files were not hand-edited to manufacture agreement.

## Edge Cases

### Grep results include preserved plans and summaries

1. Run the broad authority grep from the slice plan.
2. Notice that many matches come from preserved task plans/summaries and prior milestone artifacts.
3. Use the targeted `STATE.md` / `state-manifest.json` read-back to identify the exact live mismatch.
4. **Expected:** noisy historical matches are treated as context, not as proof that current-facing docs still have split authority.

### Historical M002 failure remains visible after the handoff

1. Re-read the top of `M002-SUMMARY.md` and `M002-VALIDATION.md` after the forward-pointer note.
2. Check that neither file claims M002 later completed successfully.
3. **Expected:** the handoff note clarifies current ownership without erasing the original failed audit.

## Failure Signals

- Any current-facing source still instructs future work under `M002/S07` or `M002/S08`.
- `R009` points at a completed slice or still splits ownership between M002 and M007.
- `M002-SUMMARY.md` or `M002-VALIDATION.md` imply the milestone later completed instead of preserving the failed 2026-03-25 record.
- `.artifacts/m007-s03-authority-audit.md` is missing or does not quote the exact `STATE.md` / `state-manifest.json` drift.
- Generated state files were manually patched to look aligned without a real generator-backed lifecycle change.

## Requirements Proved By This UAT

- R009 — proves the remaining closure/proof authority is now documented under M007/S04, with M002 preserved as historical context only, so final validation can proceed on one truthful milestone story.

## Not Proven By This UAT

- This UAT does not prove the realtime coaching runtime itself is complete or validated.
- This UAT does not retire the generator-backed `STATE.md` / `state-manifest.json` drift; it only proves the drift is explicit and accurately documented for S04.
- This UAT does not replace the live same-session proof and final integrated validation still required in M007/S04.

## Notes for Tester

- Treat `.gsd/PROJECT.md`, `.gsd/REQUIREMENTS.md`, `.gsd/DECISIONS.md`, and the preserved M002 close-out artifacts as the canonical human-maintained authority. `STATE.md` and `state-manifest.json` are verification surfaces, not primary sources.
- If the broad grep looks noisy, that is expected: preserved task artifacts intentionally retain historical wording. Use the targeted read-back plus the audit artifact to judge whether the live authority story is aligned.
