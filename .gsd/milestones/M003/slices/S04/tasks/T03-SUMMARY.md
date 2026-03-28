---
id: T03
parent: S04
milestone: M003
provides: []
requires: []
affects: []
key_files: ["web/src/lib/session-evidence.ts", "web/src/app/(user)/practice/[sessionId]/report/page.tsx", "web/src/app/(user)/practice/[sessionId]/replay/page.tsx", "web/src/app/(user)/practice/[sessionId]/report/page.test.tsx", "web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx", ".gsd/DECISIONS.md", ".gsd/KNOWLEDGE.md", ".codex/loop/state.json", ".codex/loop/log.md"]
key_decisions: ["Learner report and replay now source claim-truth from the canonical completed-session `effectiveness_snapshot.claim_truth` via a shared frontend helper instead of using `/knowledge-check` as the primary truth line.", "The shared frontend formatter maps the four backend statuses to stable learner-facing explanations and optional evidence/closure notes while keeping presentation report/replay flows free of the sales-only truth card."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Fresh verification ran from the task-plan command: `cd web && /usr/bin/time -p npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx'`. It passed with 7/7 tests green across the two focused page suites, covering weak-evidence, unsupported-claim, evidence-pending, and evidence-verified rendering on the learner report/replay surfaces while confirming presentation report routes still do not show the sales-only truth card. I also reran `cd web && /usr/bin/time -p npx tsc --noEmit` to check for broader type drift; it failed only on the pre-existing unrelated admin knowledge page error `src/app/admin/knowledge/[id]/page.tsx(294,29): Property 'reprocessKnowledgeDocument' does not exist ...`, and no new S04 type errors remained after the shared claim-truth parser fix."
completed_at: 2026-03-25T07:07:24.754Z
blocker_discovered: false
---

# T03: Rendered canonical claim-truth states on learner report and replay surfaces.

> Rendered canonical claim-truth states on learner report and replay surfaces.

## What Happened
---
id: T03
parent: S04
milestone: M003
key_files:
  - web/src/lib/session-evidence.ts
  - web/src/app/(user)/practice/[sessionId]/report/page.tsx
  - web/src/app/(user)/practice/[sessionId]/replay/page.tsx
  - web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
  - web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx
  - .gsd/DECISIONS.md
  - .gsd/KNOWLEDGE.md
  - .codex/loop/state.json
  - .codex/loop/log.md
key_decisions:
  - Learner report and replay now source claim-truth from the canonical completed-session `effectiveness_snapshot.claim_truth` via a shared frontend helper instead of using `/knowledge-check` as the primary truth line.
  - The shared frontend formatter maps the four backend statuses to stable learner-facing explanations and optional evidence/closure notes while keeping presentation report/replay flows free of the sales-only truth card.
duration: ""
verification_result: mixed
completed_at: 2026-03-25T07:07:24.755Z
blocker_discovered: false
---

# T03: Rendered canonical claim-truth states on learner report and replay surfaces.

**Rendered canonical claim-truth states on learner report and replay surfaces.**

## What Happened

I followed a red-green loop on the planned web seams. First I tightened `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx` and `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx` so the learner-facing routes had to show claim-truth labels and explanations from the unified evidence contract. The first red run failed for the intended missing UI on replay, and it also exposed one edit mistake where I had dropped a report test wrapper; I fixed that syntax slip before moving on.

On the implementation side, I extended `web/src/lib/session-evidence.ts` with a shared claim-truth parser and formatter that reads `effectiveness_snapshot.claim_truth`, validates the canonical status vocabulary (`unsupported_claim`, `weak_evidence`, `evidence_pending`, `evidence_verified`), and produces stable learner-facing explanations plus optional evidence/closure notes. I then reused that helper on both `web/src/app/(user)/practice/[sessionId]/report/page.tsx` and `web/src/app/(user)/practice/[sessionId]/replay/page.tsx` to render a dedicated `主张证据状态` card on sales sessions while leaving presentation flows untouched.

That keeps completed-session report and replay on the same canonical evidence line instead of borrowing runtime knowledge-check copy, which matters because kb-lock chain failures are operational diagnostics and should not overwrite the learner-facing truth line for a finished session. I recorded that contract choice in `.gsd/DECISIONS.md`, added the unrelated repo-wide web typecheck gotcha to `.gsd/KNOWLEDGE.md`, and updated the safe-grow continuity files so the next agent sees T03 as done rather than resuming stale T01/T02 state.

## Verification

Fresh verification ran from the task-plan command: `cd web && /usr/bin/time -p npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx'`. It passed with 7/7 tests green across the two focused page suites, covering weak-evidence, unsupported-claim, evidence-pending, and evidence-verified rendering on the learner report/replay surfaces while confirming presentation report routes still do not show the sales-only truth card. I also reran `cd web && /usr/bin/time -p npx tsc --noEmit` to check for broader type drift; it failed only on the pre-existing unrelated admin knowledge page error `src/app/admin/knowledge/[id]/page.tsx(294,29): Property 'reprocessKnowledgeDocument' does not exist ...`, and no new S04 type errors remained after the shared claim-truth parser fix.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd web && /usr/bin/time -p npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx'` | 0 | ✅ pass | 1430ms |
| 2 | `cd web && /usr/bin/time -p npx tsc --noEmit` | 1 | ❌ fail | 1370ms |


## Deviations

None.

## Known Issues

`cd web && npx tsc --noEmit` still fails on the pre-existing unrelated admin knowledge page error in `src/app/admin/knowledge/[id]/page.tsx` because `api.reprocessKnowledgeDocument` is missing on the client type. The S04 claim-truth files no longer add any extra type errors.

## Files Created/Modified

- `web/src/lib/session-evidence.ts`
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
- `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`
- `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx`
- `.gsd/DECISIONS.md`
- `.gsd/KNOWLEDGE.md`
- `.codex/loop/state.json`
- `.codex/loop/log.md`


## Deviations
None.

## Known Issues
`cd web && npx tsc --noEmit` still fails on the pre-existing unrelated admin knowledge page error in `src/app/admin/knowledge/[id]/page.tsx` because `api.reprocessKnowledgeDocument` is missing on the client type. The S04 claim-truth files no longer add any extra type errors.
