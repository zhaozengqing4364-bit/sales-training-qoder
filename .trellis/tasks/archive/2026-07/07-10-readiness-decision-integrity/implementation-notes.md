# Implementation Notes

## Deviations

### Final review: route-scoped async responses

The original plan froze the submission before POST but did not cover a dynamic
learner route change while GET or POST was still in flight. The implementation
now uses learner/request generations, clears the learner-scoped form on route
change, and ignores stale completions. Deferred frontend regressions cover both
GET and POST races.

### Final review: empty selection semantics

The backend compatibility contract treats empty capability/evidence arrays as
“use current Dossier defaults”. The original confirmation displayed zero while
the backend would persist non-empty defaults. The page now resolves, selects,
freezes, displays, and sends the effective defaults before confirmation.
Frontend and backend risk sets are explicitly aligned on `ai_failed`,
`pending_review`, and `needs_retraining`.

### Final review: learner retraining projection

The initial implementation moved Dossier state to the canonical action table,
but `TrainingJourney.retraining_requests[]` still rebuilt learner state directly
from OperationLog. `ReadinessReviewActionService.list_merged_for_learner()` is
now the shared canonical-plus-legacy reader for Dossier, optimistic concurrency,
and learner retraining projection. A canonical-without-audit-mirror regression
proves OperationLog is no longer required as the new business-state source.

## Verification Notes

- Focused RED tests failed for all three deviations before production changes.
- Relevant backend suite: 91 passed.
- Relevant frontend suite: 7 files, 84 passed.
- Ruff check/format, ESLint, TypeScript, new service mypy, Alembic head, shell
  syntax, and `git diff --check` passed.
- Full critical smoke/provider/Playwright gate and real PostgreSQL dual-session
  concurrency remain release-stage verification.
