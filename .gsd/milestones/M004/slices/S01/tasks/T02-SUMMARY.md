---
id: T02
parent: S01
milestone: M004
provides: []
requires: []
affects: []
key_files: ["web/src/lib/api/types.ts", "web/src/app/(user)/practice/[sessionId]/replay/page.tsx", "web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx", "web/src/components/highlights/HighlightList.tsx", "web/src/components/highlights/HighlightCard.tsx", "web/src/components/highlights/HighlightDetailModal.tsx", "web/src/components/highlights/HighlightList.test.tsx", "web/src/components/highlights/HighlightDetailModal.test.tsx", ".gsd/KNOWLEDGE.md"]
key_decisions: ["Bound replay and highlight UI components to the shared web API `HighlightItem`/`ReplayLearningEvidence` types instead of maintaining separate local interfaces.", "Rendered per-turn learning evidence directly inside the replay page’s highlighted message cards so the current replay surface stays informative even when the separate highlight panel is unavailable.", "Preserved compatibility fallbacks from flat fields like `stage_name`, `suggested_response`, and `context` while preferring the nested `learning_evidence` payload when it is present."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Fresh verification: `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' 'src/components/highlights/HighlightList.test.tsx' 'src/components/highlights/HighlightDetailModal.test.tsx'` passed with 3/3 files and 5/5 tests green. This covers the slice plan’s replay page and highlight component drift detectors for T02. The suite exercises the richer learning evidence on the existing replay/highlight surfaces, including nested evidence rendering, modal detail rendering, and the clean no-highlights state."
completed_at: 2026-03-25T11:09:39.337Z
blocker_discovered: false
---

# T02: Rendered shared learning evidence on the replay and highlight surfaces with focused UI tests.

> Rendered shared learning evidence on the replay and highlight surfaces with focused UI tests.

## What Happened
---
id: T02
parent: S01
milestone: M004
key_files:
  - web/src/lib/api/types.ts
  - web/src/app/(user)/practice/[sessionId]/replay/page.tsx
  - web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx
  - web/src/components/highlights/HighlightList.tsx
  - web/src/components/highlights/HighlightCard.tsx
  - web/src/components/highlights/HighlightDetailModal.tsx
  - web/src/components/highlights/HighlightList.test.tsx
  - web/src/components/highlights/HighlightDetailModal.test.tsx
  - .gsd/KNOWLEDGE.md
key_decisions:
  - Bound replay and highlight UI components to the shared web API `HighlightItem`/`ReplayLearningEvidence` types instead of maintaining separate local interfaces.
  - Rendered per-turn learning evidence directly inside the replay page’s highlighted message cards so the current replay surface stays informative even when the separate highlight panel is unavailable.
  - Preserved compatibility fallbacks from flat fields like `stage_name`, `suggested_response`, and `context` while preferring the nested `learning_evidence` payload when it is present.
duration: ""
verification_result: passed
completed_at: 2026-03-25T11:09:39.338Z
blocker_discovered: false
---

# T02: Rendered shared learning evidence on the replay and highlight surfaces with focused UI tests.

**Rendered shared learning evidence on the replay and highlight surfaces with focused UI tests.**

## What Happened

I started with a red-green pass on the replay page and the highlight list/detail modal so the richer evidence language was locked before changing production code. The new assertions covered the existing entrypoints only: the replay page’s full dialogue view, the highlight list cards, and the highlight detail modal.

To keep the frontend on the same authority line that T01 established, I replaced the duplicate local highlight shapes with the shared web API types and extended those types to include the nested `learning_evidence` payload plus the compatibility fallbacks (`stage_name`, `suggested_response`, `context`). That let the replay page and highlight components consume one contract instead of hand-maintaining parallel interfaces.

On the UI side, `HighlightList` now derives stage, issue-family, reason, next-goal, and suggested-response copy from the nested evidence object while still falling back to the flat fields when needed. `HighlightCard` now shows the richer explanation summary inline, and `HighlightDetailModal` now renders the linked issue, next goal, better response, and labeled nearby context blocks directly from the same payload.

On the replay page, I kept the current surface and added a per-turn learning-evidence card inside highlighted messages in the full dialogue stream. That means the replay route itself explains why a turn mattered, what stage it belongs to, what issue family it maps to, what the next goal is, and what a better response looks like even if the separate highlight panel is unavailable. I also preserved the highlight fetch fallback so the page still shows unified replay evidence when `/highlights` degrades.

After the UI changes I recorded the shared-type contract decision in `.gsd/DECISIONS.md`, added a frontend-testing gotcha to `.gsd/KNOWLEDGE.md`, and reran the focused replay/highlight suite until it was clean.

## Verification

Fresh verification: `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' 'src/components/highlights/HighlightList.test.tsx' 'src/components/highlights/HighlightDetailModal.test.tsx'` passed with 3/3 files and 5/5 tests green. This covers the slice plan’s replay page and highlight component drift detectors for T02. The suite exercises the richer learning evidence on the existing replay/highlight surfaces, including nested evidence rendering, modal detail rendering, and the clean no-highlights state.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' 'src/components/highlights/HighlightList.test.tsx' 'src/components/highlights/HighlightDetailModal.test.tsx'` | 0 | ✅ pass | 18900ms |


## Deviations

Minor local adaptation: the task plan named the replay page and highlight UI files, but the current code also needed `web/src/lib/api/types.ts` because the existing highlight components were using duplicate local interfaces that could not represent the nested `learning_evidence` contract safely. I also added the focused component tests referenced by the task verification command because they were missing from the repository.

## Known Issues

None.

## Files Created/Modified

- `web/src/lib/api/types.ts`
- `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`
- `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx`
- `web/src/components/highlights/HighlightList.tsx`
- `web/src/components/highlights/HighlightCard.tsx`
- `web/src/components/highlights/HighlightDetailModal.tsx`
- `web/src/components/highlights/HighlightList.test.tsx`
- `web/src/components/highlights/HighlightDetailModal.test.tsx`
- `.gsd/KNOWLEDGE.md`


## Deviations
Minor local adaptation: the task plan named the replay page and highlight UI files, but the current code also needed `web/src/lib/api/types.ts` because the existing highlight components were using duplicate local interfaces that could not represent the nested `learning_evidence` contract safely. I also added the focused component tests referenced by the task verification command because they were missing from the repository.

## Known Issues
None.
