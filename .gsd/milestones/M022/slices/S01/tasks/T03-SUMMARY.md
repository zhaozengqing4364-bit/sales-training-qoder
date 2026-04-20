---
id: T03
parent: S01
milestone: M022
key_files:
  - docs/api-contract/README.md
  - docs/api-contract/effectiveness.md
  - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
  - web/src/app/(user)/practice/[sessionId]/report/page.tsx
key_decisions:
  - Preserve the existing learner report headline summary copy and introduce methodology-aware rubric semantics in a separate explainer card so user-facing tests stay stable while the new contract language becomes visible.
duration: 
verification_result: passed
completed_at: 2026-04-14T05:37:21.238Z
blocker_discovered: false
---

# T03: Clarified methodology-aware sales rubric semantics in learner reports and manager-facing contract docs.

**Clarified methodology-aware sales rubric semantics in learner reports and manager-facing contract docs.**

## What Happened

I wrote the methodology-aware rubric semantics back into the user and manager explanation surfaces instead of leaving them only in backend contract code. `docs/api-contract/README.md` now points learner/manager readers to the effectiveness contract and explicitly frames the first-round rubric scope as `discovery / qualification`, `value`, `evidence`, `objection`, and `next-step`, with the qualification boundary called out honestly. `docs/api-contract/effectiveness.md` now adds dedicated learner-facing and manager-facing interpretation rules so report, history, admin, and coaching copy all explain `main_issue` and `next_goal` as methodology gap / next-action handles sourced from canonical evidence rather than a second score system. `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md` now records the T03 write-back rule and boundary rule so downstream M022 work reuses the same outward language. On the learner report page, `web/src/app/(user)/practice/[sessionId]/report/page.tsx` now renders a dedicated sales rubric explainer card that makes the five first-round rubric lenses visible and states the current qualification boundary in-product. I kept the existing top-line score intro sentence stable so the shipped learner report contract and tests did not churn unnecessarily; the new methodology explanation lives in the added explainer card and docs.

## Verification

Ran the focused learner report test suite to confirm the added rubric explainer copy did not break the existing unified report contract UI: `npm --prefix web test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'` passed with 24/24 tests green. Then ran the exact task-plan grep gate `rg -n "qualification|discovery|value|objection|next-step|rubric" docs/api-contract .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md 'web/src/app/(user)/practice/[sessionId]/report/page.tsx'`, which confirmed the methodology terms and boundary language now exist in the contract docs, architecture scan, and learner-facing report page.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `npm --prefix web test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'` | 0 | ✅ pass | 2771ms |
| 2 | `rg -n "qualification|discovery|value|objection|next-step|rubric" docs/api-contract .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md 'web/src/app/(user)/practice/[sessionId]/report/page.tsx'` | 0 | ✅ pass | 36ms |

## Deviations

Kept the existing learner report header intro sentence unchanged and added a dedicated rubric explainer card instead, because the current report page test contract already locks that summary line and the new explainer card/doc updates satisfy the task goal without unnecessary UI contract churn.

## Known Issues

None.

## Files Created/Modified

- `docs/api-contract/README.md`
- `docs/api-contract/effectiveness.md`
- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
