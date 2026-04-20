---
id: S03
parent: M008
milestone: M008
provides:
  - Learner-visible retrieval-truth section on the report page that reads from `effectiveness_snapshot.retrieval_facts`.
  - Shared helpers (`extractRetrievalFacts`, `formatRetrievalStatusLabel`, `formatLatestAttemptCopy`, `formatMissExplanation`, `formatSearchFailedExplanation`, `formatWeakEvidenceRetrievalNote`) for downstream reuse.
  - 17 focused Vitest assertions covering hit/miss/search_failed/absent/malformed retrieval_facts, PPT suppression, and coexistence with claim-truth.
requires:
  - slice: S02
    provides: Canonical `build_retrieval_facts()` normalizer and projection overlay that persists retrieval_facts in effectiveness_snapshot for the report page to read.
affects:
  []
key_files:
  - web/src/lib/api/types.ts
  - web/src/lib/session-evidence.ts
  - web/src/app/(user)/practice/[sessionId]/report/page.tsx
  - web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
key_decisions:
  - Treat `effectiveness_snapshot.retrieval_facts` as the learner report page's primary retrieval-truth source, keeping `/knowledge-check` supplemental-only (D122).
  - Keep claim-truth messaging separate from retrieval status — they are orthogonal signals.
  - PPT reports continue to skip the retrieval section entirely and do not call `getKnowledgeCheck`.
patterns_established:
  - Report page renders core content from the unified report payload; optional supplemental fetches are decorative only and their failure must not hide canonical data.
  - Shared `session-evidence.ts` helpers extract and format retrieval truth with defensive normalization — malformed fields are silently dropped rather than crashing the UI.
  - Sales-only UI sections are gated by `isPresentationScenario` check, keeping PPT path clean.
observability_surfaces:
  - none
drill_down_paths:
  - T01-SUMMARY.md
  - T02-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-03-29T19:17:39.505Z
blocker_discovered: false
---

# S03: 报告页检索事实可见化

**Report page now renders canonical retrieval truth (KB binding, status, hit/miss/search_failed explanations, weak-evidence note) from `effectiveness_snapshot.retrieval_facts`, keeping `/knowledge-check` supplemental-only so its failure no longer hides retrieval facts.**

## What Happened

S03 wired the learner report page to display canonical retrieval facts directly from the unified report payload instead of depending on the optional `/knowledge-check` supplemental fetch.

T01 added typed `RetrievalFacts` interfaces in `web/src/lib/api/types.ts` and shared extraction/formatting helpers in `web/src/lib/session-evidence.ts` (`extractRetrievalFacts`, `formatRetrievalStatusLabel`, `formatLatestAttemptCopy`, `formatMissExplanation`, `formatSearchFailedExplanation`, `formatWeakEvidenceRetrievalNote`). The report page (`web/src/app/(user)/practice/[sessionId]/report/page.tsx`) was updated to render a retrieval-truth section from `report.effectiveness_snapshot.retrieval_facts` for sales sessions only (PPT sessions skip it), with bounded stats (KB count, attempt count, hit count, hit rate), latest-attempt copy, result summaries, and miss/failure/weak-evidence explanations. Claim-truth messaging remains separate and orthogonal. The section safely omits itself when retrieval_facts are absent and survives malformed latest_attempt data. Focused Vitest coverage proved canonical retrieval hit + weak-evidence coexistence even when `/knowledge-check` rejects.

T02 expanded the test suite with canonical retrieval-facts fixtures for `status="miss"` and `status="search_failed"`, both under rejected supplemental knowledge-check. New assertions verify that the report page renders the correct miss/failure explanation from the unified report payload. The presentation regression was tightened to assert PPT reports keep the retrieval section absent while `getKnowledgeCheck` remains uncalled. No production code changes were needed in T02 — the runtime already matched the contract.

The full suite now runs 17/17 tests passing, covering: sales rollup, replay deep-links, retry launch, degraded replay, unsupported claim truth, canonical retrieval (hit/miss/search_failed), absent retrieval_facts, malformed latest_attempt, PPT scenarios, evidence contract stability, and replay lock.

## Verification

Ran `pnpm --dir web exec vitest run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'` — 17/17 tests passing, including the new canonical retrieval hit/miss/search_failed cases, absent/malformed retrieval_facts guards, PPT retrieval suppression, and existing report-page regressions.

## Requirements Advanced

- R005 — Report page now shows concrete retrieval evidence (KB binding, hit/miss/failure explanations) alongside score and coaching conclusions, making reports more actionable and grounded in real retrieval truth.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

None.

## Known Limitations

None.

## Follow-ups

None.

## Files Created/Modified

- `web/src/lib/api/types.ts` — Added RetrievalFacts, RetrievalFactsStatus, RetrievalLatestAttempt, RetrievalResultSummary, and raw/normalized interfaces for canonical retrieval truth.
- `web/src/lib/session-evidence.ts` — Added extraction and formatting helpers: extractRetrievalFacts, formatRetrievalStatusLabel, formatRetrievalStatusTone, formatLatestAttemptCopy, formatMissExplanation, formatSearchFailedExplanation, formatWeakEvidenceRetrievalNote, getRetrievalStatusClasses.
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx` — Wired retrieval-truth section to render from effectiveness_snapshot.retrieval_facts for sales sessions; keeps claim-truth separate and /knowledge-check supplemental-only.
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx` — Expanded from 15 to 17 tests with canonical retrieval hit/miss/search_failed fixtures, absent/malformed guards, PPT retrieval suppression, and coexistence with weak-evidence claims.
