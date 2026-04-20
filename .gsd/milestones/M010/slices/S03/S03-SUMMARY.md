---
id: S03
parent: M010
milestone: M010
provides:
  - Learner-facing report and replay rendering for projection-backed `conclusion_evidence` and four-layer `evidence_degradation`.
  - A shared frontend helper seam that owns provenance/degradation normalization, Chinese copy, and malformed-fragment omission across both learner pages.
  - Focused regression coverage proving replay does not reuse stale report-snapshot truth for provenance/degradation and that presentation sessions still suppress sales-only sections.
requires:
  - slice: S01
    provides: projection-backed `conclusion_evidence` carried consistently through report, replay, and knowledge-check
  - slice: S02
    provides: projection-backed four-layer `evidence_degradation` taxonomy shared across report, replay, and knowledge-check
affects:
  []
key_files:
  - web/src/lib/api/types.ts
  - web/src/lib/session-evidence.ts
  - web/src/app/(user)/practice/[sessionId]/report/page.tsx
  - web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
  - web/src/app/(user)/practice/[sessionId]/replay/page.tsx
  - web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx
  - .gsd/KNOWLEDGE.md
  - .gsd/PROJECT.md
key_decisions:
  - Normalize `conclusion_evidence` and `evidence_degradation` through shared `web/src/lib/session-evidence.ts` helpers before either page renders learner-facing copy.
  - Treat replay payload fields (`replayData.conclusion_evidence` / `replayData.evidence_degradation`) as canonical for replay, while any report snapshot loaded on the replay page remains retry-metadata-only.
  - Defend cross-page vocabulary parity with paired focused report/replay tests rather than duplicating token-to-copy logic in each page.
patterns_established:
  - Use `session-evidence.ts` as the single frontend authority seam for learner-facing evidence vocabulary; page components render helper output and do not interpret raw contract fragments themselves.
  - For cross-page parity work, keep one route-specific authority rule per page (report trusts report payload, replay trusts replay payload) and lock the difference with focused tests rather than fallback heuristics.
observability_surfaces:
  - Focused paired web gate: `npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx"`
  - Page-level failure handling still surfaces explicit replay completion-gate copy (`[SESSION_NOT_COMPLETED]`) and keeps canonical report-driven provenance/degradation visible when optional supplemental requests fail.
drill_down_paths:
  - .gsd/milestones/M010/slices/S03/tasks/T01-SUMMARY.md
  - .gsd/milestones/M010/slices/S03/tasks/T02-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-03-30T08:11:30.230Z
blocker_discovered: false
---

# S03: 前端出处渲染与端到端验证

**Learner report and replay now render canonical conclusion provenance and four-layer evidence degradation through shared `session-evidence.ts` helpers, with replay explicitly trusting replay payload truth instead of stale report snapshots.**

## What Happened

S03 finished the learner-facing half of M010’s evidence chain by taking the projection-backed `conclusion_evidence` and four-layer `evidence_degradation` contract from S01/S02 and rendering it on the two learner surfaces that matter: canonical report and replay. T01 extended the shared frontend API types, added defensive provenance/degradation normalization in `web/src/lib/session-evidence.ts`, and rewired the report page so it no longer parses raw provenance fragments locally. T02 mirrored that seam onto replay, but kept a hard authority boundary: replay copy comes from `replayData.conclusion_evidence` and `replayData.evidence_degradation`, while any report snapshot remains retry metadata only. Focused tests now prove three things that matter for downstream work: malformed payload fragments degrade to omission rather than crashes, supplemental `/knowledge-check` failures do not hide canonical report-driven provenance/degradation, and replay does not regress into stale report-snapshot truth even when one is available. The result is that completed sales sessions now explain both why each key conclusion is believed and which evidence layers are degraded, using one helper-owned vocabulary shared across report and replay instead of two drifting page-local parsers.

## Verification

Fresh slice-close verification passed `npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx"` with 33/33 Vitest tests green. The gate covered happy-path shared provenance/degradation vocabulary, malformed helper inputs, supplemental knowledge-check failure isolation on report, stale report-snapshot non-authority on replay, replay completion-gate behavior, retry CTA behavior, highlight/deep-link anchors, and presentation-null suppression across both learner pages.

## Requirements Advanced

- R027 — Completed the learner-facing delivery of canonical conclusion provenance and layered degradation on report and replay, so users can see why key conclusions are believed instead of relying on backend-only contract parity.
- R028 — Exposed the four-layer degradation taxonomy on the actual learner report/replay surfaces with shared copy and regression coverage, preventing page-local omission or stale fallback from hiding degraded evidence layers.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

None.

## Known Limitations

The slice acceptance proof is focused web verification only: `npm --prefix web test -- --run ...report/page.test.tsx ...replay/page.test.tsx`. Repo-wide frontend type health still has unrelated baseline failures outside the touched files, so this slice does not claim a clean global `tsc` baseline.

## Follow-ups

Reassess the remaining M010 roadmap now that learner-facing report/replay provenance and degradation rendering is complete; no additional slice-local follow-up was discovered.

## Files Created/Modified

- `web/src/lib/api/types.ts` — Extended the shared frontend evidence contract with typed `conclusion_evidence` support so report and replay consume one contract edge.
- `web/src/lib/session-evidence.ts` — Added shared helper normalization/formatting for conclusion provenance rows and four-layer degradation rows, including malformed-fragment omission and stable learner-facing copy.
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx` — Rendered canonical report-driven provenance and degradation through shared helpers while preserving existing report behaviors and optional supplemental knowledge-check handling.
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx` — Locked happy-path, degraded, malformed-input, supplemental-failure, and presentation-null report behavior around the new provenance/degradation surfaces.
- `web/src/app/(user)/practice/[sessionId]/replay/page.tsx` — Rendered canonical replay-driven provenance and degradation through shared helpers and kept report snapshot usage limited to retry metadata.
- `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx` — Added replay parity, stale-report-snapshot non-authority, degraded, malformed-input, completion-gate, retry, highlight-anchor, and presentation-null coverage.
- `.gsd/KNOWLEDGE.md` — Recorded the cross-page rule that report/replay provenance and degradation must stay helper-owned and replay must not fall back to stale report-snapshot truth.
- `.gsd/PROJECT.md` — Updated current-state documentation to reflect that M010 learner-facing provenance/degradation rendering is now shipped on report and replay.
