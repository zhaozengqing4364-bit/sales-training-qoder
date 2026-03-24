---
estimated_steps: 4
estimated_files: 5
skills_used:
  - using-superpowers
  - safe-grow
  - test-driven-development
  - react-best-practices
  - baseline-ui
  - verification-before-completion
---

# T03: Surface the aligned coach conclusion on replay and admin read surfaces

**Slice:** S04 — 训练中建议与报告结论一致性
**Milestone:** M002

## Description

Make the backend alignment visible to users and supervisors. Today replay already shows `stage_summary`, but it does not render `main_issue` / `next_goal`, so users cannot visually confirm that training-time guidance and the final report agree. At the same time, the shared label helper still misses newer sales issue/goal types. This task should add a read-only replay conclusion card, extend label maps for the current sales vocabulary, and re-prove that replay/report/admin all render the aligned conclusion without client-side re-derivation.

## Steps

1. Extend `web/src/lib/session-evidence.ts` so the shared issue/goal label maps cover the current sales vocabulary exposed by S04 (for example `value_translation_gap`, `evidence_gap`, `objection_handling_gap`, `next_step_gap`, `value_to_benefit_translation`, `evidence_backing`, `objection_reframe`, `next_step_commitment`, plus insufficient-evidence fallbacks).
2. Update `web/src/app/(user)/practice/[sessionId]/replay/page.tsx` to render a compact read-only “本场教练结论” block before stage evidence whenever replay data includes `main_issue` and/or `next_goal`, reusing the API payload directly and avoiding any new client-side coaching heuristics.
3. Add or update focused tests in `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx`, `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`, and `web/src/app/admin/users/[id]/page.test.tsx` so replay visibly shows the same conclusion family as report and admin badges remain readable with the updated vocabulary.
4. Run the focused frontend test command and verify the replay page still handles null / not-evaluable / no-highlight states cleanly after the new conclusion block is added.

## Must-Haves

- [ ] Replay page renders the aligned `main_issue` / `next_goal` directly from API data and does not invent its own decision rules.
- [ ] Shared label maps cover the current sales issue/goal vocabulary so admin/replay badges do not silently disappear.
- [ ] Existing replay null / degraded / no-highlight states continue to render cleanly.

## Verification

- `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'`

## Inputs

- `backend/src/common/conversation/session_evidence.py` — stable projection-backed `main_issue` / `next_goal` contract from T02.
- `web/src/app/(user)/practice/[sessionId]/replay/page.tsx` — current replay UI that already renders `stage_summary` but not coach conclusion.
- `web/src/lib/session-evidence.ts` — shared label maps for issue/goal/stage badges.
- `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx` — current replay UI assertions.
- `web/src/app/admin/users/[id]/page.test.tsx` — current admin read-surface assertions.

## Expected Output

- `web/src/lib/session-evidence.ts` — updated sales issue/goal label coverage.
- `web/src/app/(user)/practice/[sessionId]/replay/page.tsx` — replay conclusion card rendering aligned `main_issue` / `next_goal`.
- `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx` — replay proof for visible conclusion alignment.
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx` — report regression proof for the same conclusion family.
- `web/src/app/admin/users/[id]/page.test.tsx` — admin badge coverage for the updated sales vocabulary.
