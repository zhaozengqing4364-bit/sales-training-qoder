---
estimated_steps: 4
estimated_files: 7
skills_used:
  - using-superpowers
  - safe-grow
  - test-driven-development
  - react-best-practices
  - vercel-react-best-practices
  - baseline-ui
  - verification-before-completion
---

# T02: Harden practice-page consumers and voice-mode affordances around the sales contract

**Slice:** S01 — 实时评分与训练页销售语义对齐
**Milestone:** M002

## Description

Make the user-facing practice page a reliable consumer of the aligned sales contract. The current frontend already renders the sales vocabulary, but `score_update` dedupe only compares `overall_score` + `turn_count`, so richer same-turn refreshes can be dropped silently. This task should harden websocket state updates, keep the ScorePanel sales-first while preserving explicit fallback rendering, and make the launch-page voice-mode wording stop implying a different scoring rubric.

## Steps

1. Read the existing websocket and ScorePanel tests, then add failing cases in `web/src/hooks/websocket/message-handlers.test.ts` for same-turn `score_update` refreshes where dimensions / `stage_name` / `suggestions` change without an `overall_score` change.
2. Update `web/src/hooks/websocket/message-handlers.ts` so score-update idempotence compares the full sales payload shape rather than only `overall_score` + `turn_count`, while keeping `evaluation_feedback` fallback behavior intact.
3. Keep `web/src/components/practice/ScorePanel.tsx` sales-first in ordering/copy, preserve unknown-dimension fallback visibility, and adjust the launch-page mode wording/tests in `web/src/app/(dashboard)/agents/[agentId]/page.tsx` so both selectable modes still point at the same sales scoring semantics on the practice page.
4. Re-run the focused web suites covering websocket state, ScorePanel rendering, launch-page mode copy, and runtime-lock behavior.

## Must-Haves

- [ ] Same-turn `score_update` refreshes with new dimensions / stage / suggestions are no longer dropped silently.
- [ ] ScorePanel still renders the five sales dimensions first and keeps unknown dimensions visible as compatibility fallback.
- [ ] Voice-mode copy/tests no longer imply a separate scoring vocabulary for classic mode.

## Verification

- `cd web && npm test -- --run 'src/hooks/websocket/message-handlers.test.ts' 'src/components/practice/ScorePanel.test.tsx' 'src/app/(dashboard)/agents/[agentId]/page.test.tsx' 'src/app/(user)/practice/[sessionId]/runtime-lock.test.ts'`
- `cd web && npm test -- --run 'src/hooks/use-practice-websocket.test.ts'`

## Observability Impact

- Signals added/changed: frontend websocket contract assertions for same-turn score refreshes, panel ordering/fallback rendering, and mode-selection copy that maps user choice back to one practice-page rubric.
- How a future agent inspects this: run the focused Vitest commands and inspect `web/src/hooks/websocket/message-handlers.test.ts` plus `web/src/components/practice/ScorePanel.test.tsx` for the expected sales payload/state shape.
- Failure state exposed: dropped score refreshes, hidden fallback dimensions, or misleading mode semantics now fail deterministic web tests before surfacing as browser-only confusion.

## Inputs

- `web/src/hooks/websocket/message-handlers.ts` — score-update consumer and idempotence logic.
- `web/src/hooks/websocket/message-handlers.test.ts` — focused websocket state coverage.
- `web/src/components/practice/ScorePanel.tsx` — user-facing score panel ordering/copy.
- `web/src/components/practice/ScorePanel.test.tsx` — panel rendering coverage for sales-first and fallback dimensions.
- `web/src/app/(dashboard)/agents/[agentId]/page.tsx` — launch-page voice-mode affordance and copy.
- `web/src/app/(dashboard)/agents/[agentId]/page.test.tsx` — launch-page behavior coverage.
- `web/src/app/(user)/practice/[sessionId]/runtime-lock.test.ts` — mode-lock guardrail once a session is created.

## Expected Output

- `web/src/hooks/websocket/message-handlers.ts` — score-update handling that preserves same-turn sales refreshes.
- `web/src/hooks/websocket/message-handlers.test.ts` — contract tests for sales vocabulary, refresh behavior, and fallback dimensions.
- `web/src/components/practice/ScorePanel.tsx` — practice-page panel that stays sales-first while keeping fallback dimensions visible.
- `web/src/components/practice/ScorePanel.test.tsx` — rendering assertions for sales-first and fallback cases.
- `web/src/app/(dashboard)/agents/[agentId]/page.tsx` — voice-mode wording aligned with the shared sales rubric.
- `web/src/app/(dashboard)/agents/[agentId]/page.test.tsx` — launch-page assertions for the updated mode semantics.
