# S04: 最终集成验证与封板 — UAT

**Milestone:** M007
**Written:** 2026-03-28T13:38:35.000Z

# S04: 最终集成验证与封板 — UAT

**Milestone:** M007
**Written:** 2026-03-28

## UAT Type
- UAT mode: integrated proof + generated-state reconciliation
- Why this mode is sufficient: this slice only closes if the shipped localhost same-session proof and the GSD-rendered project state agree on the same closure story.

## Preconditions
- `.artifacts/m007-s04-final-closure-proof.md` exists and still records one localhost StepFun session moving `in_progress -> scoring -> completed` with same-session replay unlock.
- `.artifacts/m007-s03-authority-audit.md` exists and documents the stale pre-closeout `STATE.md` / `state-manifest.json` mismatch.
- `R009` is rendered as validated in `.gsd/REQUIREMENTS.md` via the requirement-update flow, not by manual edit.
- The current route family remains `/practice/{sessionId}` -> `/practice/{sessionId}/report` -> `/practice/{sessionId}/replay` on `localhost` hosts.

## Smoke Test
1. Re-read `.artifacts/m007-s04-final-closure-proof.md`.
2. Confirm it includes the persisted-completion marker, same-session replay `200` unlock, optional-noise classification, and `Final verdict: Pass`.
3. Open `.gsd/REQUIREMENTS.md` and confirm R009 now renders as `validated` with explicit T01-T03 proof notes.
4. **Expected:** the product proof and requirement state agree before slice/milestone render-backed close-out begins.

## Test Cases

### 1. Focused regression and localhost proof still justify close-out
1. Inspect the completed task summaries for `T01`, `T02`, and `T03`.
2. Confirm T01 covers the real `db=None` own-session finalization path, T02 covers same-session report/replay gating and parity, and T03 records the localhost route-family proof.
3. **Expected:** the combined evidence line proves persisted completion plus same-session replay unlock on the shipped route family; there is no need to reopen M002 authority or invent a new debug surface.

### 2. Generated slice and milestone artifacts are render-backed, not hand-edited
1. Confirm `S04-SUMMARY.md`, `S04-UAT.md`, `M007-VALIDATION.md`, and `M007-SUMMARY.md` exist after the close-out flow.
2. Confirm they were produced by the GSD completion/validation tools rather than direct manual edits.
3. **Expected:** the generated artifacts exist, are non-empty, and tell the same closure story as the proof artifact and requirement row.

### 3. Generated state read-back agrees with the closure story
1. Open `.gsd/STATE.md` and `.gsd/state-manifest.json` after the GSD render flow completes.
2. Confirm `STATE.md` no longer treats M007 as queued/incomplete and does not keep M002 as the active unresolved owner.
3. Confirm `state-manifest.json` reports `M007.status == "complete"`, carries a non-empty M007 title, and does not leave `M002.status == "active"`.
4. **Expected:** the system-managed read-back surfaces now agree with the canonical proof and no manual patching was required.

## Edge Cases
- If the proof artifact loses the persisted-completion or same-session replay-unlock markers, stop and rerun live proof instead of forcing close-out.
- If milestone validation returns anything except `pass`, keep the failure explicit and do not hand-edit generated artifacts to manufacture completion.
- If `STATE.md` or `state-manifest.json` still show stale milestone ownership/status after the render flow, treat that as unresolved generated-state drift and investigate the generator/DB state rather than patching files.

## Failure Signals
- R009 says `validated` but its notes do not reference the T01-T03 evidence chain.
- `S04-SUMMARY.md`, `S04-UAT.md`, `M007-VALIDATION.md`, or `M007-SUMMARY.md` are missing or empty after the close-out flow.
- `state-manifest.json` still reports `M007` as `queued` or `M002` as `active` after milestone completion.
- Close-out reasoning depends on suppressing or deleting observable `kb_not_ready` / trigger-side optional-noise diagnostics rather than classifying them correctly.

## Requirement Proved By This UAT
- R009 — proves realtime coaching can now be marked complete only because the final regression evidence, live localhost same-session proof, requirement status transition, and generated-state read-back all agree on the same closure truth.

## Notes for Tester
- Treat `.artifacts/m007-s04-final-closure-proof.md` as the canonical live product proof and `.gsd/state-manifest.json` / `.gsd/STATE.md` as the final read-back surfaces.
- Do not hand-edit system-managed state files if they drift; rerun or investigate the generator-backed GSD flow instead.
- Concurrent `kb_not_ready`, `no_scoring_context_available`, and `report_generation_failed [NO_STAGE_RESULTS]` signals remain valid diagnostics. They are only non-blocking when the same session still persists `completed` and unlocks report/replay/highlights on the shipped route family.
