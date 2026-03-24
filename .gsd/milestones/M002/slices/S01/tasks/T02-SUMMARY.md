---
id: T02
parent: S01
milestone: M002
provides:
  - Practice-page websocket consumers now preserve same-turn sales score refreshes and both voice-mode entry points describe one shared sales rubric.
key_files:
  - web/src/hooks/websocket/message-handlers.ts
  - web/src/hooks/websocket/message-handlers.test.ts
  - web/src/components/practice/ScorePanel.tsx
  - web/src/components/practice/ScorePanel.test.tsx
  - web/src/app/(dashboard)/agents/[agentId]/page.tsx
  - web/src/app/(dashboard)/agents/[agentId]/page.test.tsx
  - .gsd/DECISIONS.md
  - .gsd/KNOWLEDGE.md
key_decisions:
  - D034: Frontend score_update idempotence must compare the full ScoreUpdate payload instead of only overall_score + turn_count.
patterns_established:
  - Same-turn sales score refreshes can refine stage_name, suggestions, or dimension_scores without changing overall_score, so frontend consumers must not dedupe those payloads away.
observability_surfaces:
  - web/src/hooks/websocket/message-handlers.test.ts
  - web/src/components/practice/ScorePanel.test.tsx
  - web/src/app/(dashboard)/agents/[agentId]/page.test.tsx
  - web/src/hooks/use-practice-websocket.test.ts
duration: 15m
verification_result: passed
completed_at: 2026-03-24T19:18:31+0800
blocker_discovered: false
---

# T02: Harden practice-page consumers and voice-mode affordances around the sales contract

**Preserved same-turn sales score refreshes and aligned practice voice-mode copy to one rubric.**

## What Happened

I started from the existing slice state rather than re-planning. The pre-flight observability gap flagged in auto-mode was already fixed during T01, so I moved straight into TDD on the web consumer surfaces.

First I extended `web/src/hooks/websocket/message-handlers.test.ts` with the failure that mattered here: a `score_update` carrying the same `overall_score` and `turn_count` as the previous turn snapshot, but a newer `stage_name`, `suggestions`, and refined `dimension_scores`. That red test proved the current practice-page dedupe logic was silently dropping legitimate same-turn sales refreshes.

I then replaced the handler’s narrow `overall_score + turn_count` check with an explicit `isSameScoreUpdate(...)` helper that compares the full frontend payload boundary: `session_id`, `turn_count`, `overall_score`, `stage_name`, `suggestions`, and `dimension_scores`. Identical payloads still stay idempotent, but richer same-turn coaching now lands in state immediately. The existing `evaluation_feedback` fallback path stayed untouched.

On the rendering side, `ScorePanel` already kept unknown dimensions visible and sorted fallback fields after the sales ones, so I kept that structure and made the copy explicit: the section now says `销售维度得分`. I locked that behavior with a test that proves the five sales dimensions stay ahead of an unknown compatibility field.

Finally, I updated `web/src/app/(dashboard)/agents/[agentId]/page.tsx` so both voice-mode cards tell the same truth: whichever voice path the user chooses, the practice page still uses the same sales scoring dimensions and next-turn guidance. I recorded the idempotence rule as D034 and added a knowledge note for the frontend same-turn refresh gotcha.

## Verification

I ran the red-green loop on the focused web suite first, then reran the full task verification and the slice-level backend/web commands because this is the final task in S01. All slice verification commands passed fresh, so the frontend consumer fix did not disturb the backend runtime contract or the existing three-rollup practice evidence boundary.

Per the slice proof level, no live runtime/browser UAT was required here; the contract is enforced by deterministic Vitest and pytest surfaces.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_realtime_scoring.py tests/unit/test_effectiveness_sales_baseline.py tests/unit/test_stepfun_realtime_handler.py tests/unit/test_capability_processor.py` | 0 | ✅ pass | 5.80s |
| 2 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py tests/unit/test_capability_processor.py -k 'action_card or stage_update'` | 0 | ✅ pass | 5.82s |
| 3 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py` | 0 | ✅ pass | 6.08s |
| 4 | `cd web && npm test -- --run 'src/hooks/websocket/message-handlers.test.ts' 'src/components/practice/ScorePanel.test.tsx' 'src/app/(dashboard)/agents/[agentId]/page.test.tsx' 'src/app/(user)/practice/[sessionId]/runtime-lock.test.ts'` | 0 | ✅ pass | 1.12s |
| 5 | `cd web && npm test -- --run 'src/hooks/use-practice-websocket.test.ts'` | 0 | ✅ pass | 0.66s |

## Diagnostics

To inspect this task later, rerun:
- `cd web && npm test -- --run 'src/hooks/websocket/message-handlers.test.ts'`
- `cd web && npm test -- --run 'src/components/practice/ScorePanel.test.tsx' 'src/app/(dashboard)/agents/[agentId]/page.test.tsx'`
- `cd web && npm test -- --run 'src/hooks/use-practice-websocket.test.ts'`

The main failure surface for the original bug is `web/src/hooks/websocket/message-handlers.test.ts`, especially the same-turn `score_update` refresh case. `ScorePanel.test.tsx` now locks the sales-first ordering/copy plus fallback-dimension visibility, and `page.test.tsx` is the durable check that classic and realtime voice modes promise the same rubric.

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `web/src/hooks/websocket/message-handlers.ts` — widened `score_update` idempotence to the full sales payload so same-turn refreshes no longer get dropped.
- `web/src/hooks/websocket/message-handlers.test.ts` — added red/green coverage for same-turn sales refreshes and full-payload idempotence.
- `web/src/components/practice/ScorePanel.tsx` — kept sales-first ordering/fallback rendering and made the scoring section copy explicitly sales-focused.
- `web/src/components/practice/ScorePanel.test.tsx` — locked sales-first ordering ahead of fallback dimensions and the updated panel copy.
- `web/src/app/(dashboard)/agents/[agentId]/page.tsx` — rewrote voice-mode helper text so both modes point at the same sales scoring semantics.
- `web/src/app/(dashboard)/agents/[agentId]/page.test.tsx` — added launch-page coverage for the shared sales-rubric voice-mode wording.
- `.gsd/DECISIONS.md` — recorded D034 for full-payload frontend `score_update` idempotence.
- `.gsd/KNOWLEDGE.md` — recorded the same-turn sales refresh dedupe gotcha for future agents.
