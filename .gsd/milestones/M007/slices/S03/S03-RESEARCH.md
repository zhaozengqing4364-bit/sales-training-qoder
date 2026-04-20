# S03 Research — M002 remediation 归并与权威切换

## Summary

S03 supports **R009** by removing artifact and authority drift after **M007/S01-S02** already changed the real product truth. This slice is primarily **GSD artifact reconciliation**, not runtime/application code.

The critical facts are:
- **Historical M002 artifacts are accurate as a dated failed close-out audit.** `M002-SUMMARY.md` and `M002-VALIDATION.md` correctly say M002 could not be sealed and that only `S01-S04` existed.
- **Current authority already moved to M007.** `PROJECT.md`, `REQUIREMENTS.md`, `M007-CONTEXT.md`, `M007-ROADMAP.md`, `M007/S01-SUMMARY.md`, and `M007/S02-SUMMARY.md` all say the unfinished realtime-coaching closure work now belongs to M007.
- **The biggest drift is in state/rendered status surfaces.** `STATE.md` shows M002 as completed, `state-manifest.json` shows M002 as `active`, and `PROJECT.md` shows M002 still open and absorbed by M007.

This slice matches the repo-level AGENTS rule for **forced writeback when the task boundary changes**: the unfinished M002 remediation work has already been re-scoped into M007, so the specs/artifacts must be rewritten before anyone treats the closure work as done.

## Requirement Focus

- **R009 (active)**
  - Primary owner: `M007/S01`
  - Supporting slices: `M007/S02`, `M007/S03`, `M007/S04`
  - S03’s job is not to add new runtime semantics; it is to make the artifact authority line truthful so the remaining R009 closure work is unambiguously owned by M007.

## Skills Discovered

- Process skill used: **writing-plans**
  - Relevant rule: use **exact file paths** and **bite-sized tasks**. This slice should decompose into a few precise artifact tasks, not one vague “clean up M002” pass.
- No new tech-specific skill was needed. This slice is GSD artifact/state reconciliation rather than framework-specific implementation.

## Implementation Landscape

### 1. Historical artifacts that must stay historical, not become fake current truth

**Files:**
- `.gsd/milestones/M002/M002-ROADMAP.md`
- `.gsd/milestones/M002/M002-SUMMARY.md`
- `.gsd/milestones/M002/M002-VALIDATION.md`
- `.gsd/milestones/M002/slices/` (contains only `S01`–`S04`)

**What they currently say:**
- M002 delivered the core semantics through `S01-S04`
- M002 **did not** pass close-out
- missing work was framed as remediation slices `S07` / `S08`
- no `S07` / `S08` slice directories actually exist

**Planner implication:**
- Do **not** rewrite M002 as “actually complete.”
- Do **not** invent missing `M002/S07` or `M002/S08` artifacts.
- Treat these files as the preserved record of the 2026-03-25 failed audit.

### 2. Current authority already lives in M007-facing docs

**Files:**
- `.gsd/PROJECT.md`
- `.gsd/REQUIREMENTS.md`
- `.gsd/milestones/M007/M007-CONTEXT.md`
- `.gsd/milestones/M007/M007-ROADMAP.md`
- `.gsd/milestones/M007/slices/S01/S01-SUMMARY.md`
- `.gsd/milestones/M007/slices/S02/S02-SUMMARY.md`

**What they currently say:**
- M007 exists specifically to absorb unfinished M002 realtime-coaching closure work
- `M007/S01` retired the degraded/resumed learner-visible truth gap
- `M007/S02` retired same-session vocabulary drift and isolated the remaining blocker to the StepFun terminal scoring wedge
- `REQUIREMENTS.md` already notes that S03 owns the authority transfer itself

**Planner implication:**
- S03 is mostly about making every current-facing artifact point to this M007 story consistently.
- The runtime/product side is already advanced enough that stale M002 remediation language can now mislead future agents more than missing code can.

### 3. The sharpest drift is state/status, not code

**Files:**
- `.gsd/STATE.md`
- `.gsd/state-manifest.json`
- `.gsd/PROJECT.md`

**Observed mismatch:**
- `STATE.md` says `✅ M002`
- `state-manifest.json` says `M002.status = "active"`
- `PROJECT.md` milestone list shows M002 unchecked and explicitly says its remaining closure authority moved to M007

**Planner implication:**
- Do not trust a single state surface.
- `STATE.md` and `state-manifest.json` are **system-managed**; they are verification surfaces, not the primary hand-edited source of truth.
- S03 should update the canonical milestone/requirement/decision sources and then verify what the rendered state still says.

### 4. The old M002 remediation mapping is no longer 1:1

**Historical M002 remediation intent:**
- `M002/S07` — coach degraded/resumed observability
- `M002/S08` — final live same-session closure proof

**Current M007 mapping:**
- `M007/S01` effectively delivers the old `M002/S07` observability gap
- `M007/S02` delivers same-session vocabulary closure and the blocker proof
- `M007/S04` is now the actual final validation/close-out surface that must retire the remaining StepFun scoring wedge

**Planner implication:**
- S03 should record this mapping explicitly.
- Future agents should not go looking for missing executable `M002/S07` / `M002/S08` slices.

### 5. Useful precedent already exists: active requirement ownership can move forward without falsifying history

**File:**
- `.gsd/milestones/M001/M001-VALIDATION.md`

That validation explicitly says **R011 remains active by design with primary ownership in M004** even though M001 itself passed.

**Planner implication:**
- S03 does **not** need to force M002 into a fake complete state to make M007 the closure owner.
- The right pattern is: preserve the historical milestone result, but point the unfinished requirement/closure authority forward to the new milestone.

### 6. Canonical update seams vs generated surfaces

**Use canonical tools/sources for:**
- `gsd_decision_save` → authority-switch decision
- `gsd_requirement_update` → if R009 note/status text needs tightening
- GSD milestone planning/reassess tools → any roadmap rewrite (`M002-ROADMAP.md`, `M007-ROADMAP.md` are rendered artifacts)

**Verify only; do not hand-edit as primary source:**
- `.gsd/STATE.md`
- `.gsd/state-manifest.json`

**Planner implication:**
- If S03 changes roadmap wording, prefer the canonical GSD render path instead of direct markdown surgery that will drift on the next render.
- Summary/validation markdown for M002 should be handled carefully: those files are historical records first, not the place to retroactively claim new execution happened under M002.

## Recommendation

Treat S03 as **three small tasks**, in this order:

1. **Record the authority switch explicitly**
   - Add one new decision that M002 remains the historical failed close-out / partial foundation, while all remaining R009 closure authority now belongs to M007.
   - Put the mapping from historical `M002/S07-S08` intent to current `M007/S01-S04` work in a durable, current-facing source.

2. **Make the current docs unambiguous**
   - Update M007-side planning/current-state surfaces so future agents see one clear closure story.
   - If M002-facing docs are touched, add only a **dated historical note / pointer**; do not rewrite the failed audit as if M002 later completed.

3. **Verify rendered state instead of patching it by hand**
   - After canonical updates, re-check `STATE.md`, `state-manifest.json`, and milestone lists.
   - If system-managed state still drifts, record the exact remaining generator mismatch as a blocker or follow-up rather than silently editing generated files.

## Natural Task Seams

### Seam A — Decision + mapping source of truth

**Files/surfaces:**
- `.gsd/DECISIONS.md`
- `.gsd/REQUIREMENTS.md`
- `.gsd/milestones/M007/slices/S03/S03-PLAN.md`

**Goal:**
- Establish one explicit mapping and authority statement that future slices can cite.

### Seam B — Historical milestone framing

**Files/surfaces:**
- `.gsd/milestones/M002/M002-ROADMAP.md`
- `.gsd/milestones/M002/M002-SUMMARY.md`
- `.gsd/milestones/M002/M002-VALIDATION.md`

**Goal:**
- Preserve the failed 2026-03-25 audit as historical truth while adding a durable pointer that unfinished closure work moved to M007.

### Seam C — Current milestone authority + rendered-state verification

**Files/surfaces:**
- `.gsd/PROJECT.md`
- `.gsd/milestones/M007/M007-ROADMAP.md`
- `.gsd/STATE.md` *(verify only)*
- `.gsd/state-manifest.json` *(verify only)*

**Goal:**
- Make M007 the only active closure story for R009 and confirm the rendered state no longer misleads the next agent.

## Verification

Use artifact verification, not app/runtime suites.

**Inventory truth**
- `find .gsd/milestones/M002/slices -maxdepth 1 -mindepth 1 -type d | sort`
  - Confirms only `S01-S04` actually exist under M002.

**Authority-line grep**
- `rg -n "M002|M007|R009|needs-remediation|historical|authority|S07|S08" .gsd/milestones/M002 .gsd/milestones/M007 .gsd/PROJECT.md .gsd/REQUIREMENTS.md .gsd/STATE.md .gsd/state-manifest.json`
  - Confirms all current-facing docs tell one consistent authority story.

**Read-back spot checks after updates**
- Read the top sections of:
  - `.gsd/milestones/M002/M002-SUMMARY.md`
  - `.gsd/milestones/M002/M002-VALIDATION.md`
  - `.gsd/milestones/M007/M007-ROADMAP.md`
  - `.gsd/PROJECT.md`
  - `.gsd/STATE.md`
- Confirm:
  - M002 is still historical / not falsely complete
  - M007 is the active closure owner
  - no current doc still instructs future work under live `M002` remediation slice IDs

## Risks / Watchouts

- **Over-correcting** by marking M002 complete would falsify the failed audit and erase why M007 exists.
- **Under-correcting** by only updating M007 leaves future agents exposed to stale M002 / STATE clues.
- **Broad state-manifest cleanup** across old milestones looks larger than S03. Keep scope on R009 authority cues unless the GSD tooling can safely rerender the affected state from canonical milestone sources.
- If roadmap text is changed manually instead of through the canonical planning/render path, the next GSD render may overwrite the fix and reintroduce the same ambiguity.
