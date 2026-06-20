# F5 Manual QA Surface

Date: 2026-06-20

## Mode

External manual gate required.

## Preconditions

The F4 quality gate did bootstrap a local smoke stack and seeded the smoke admin user, but the Playwright smoke phase failed due frontend dev-server/runtime instability before this verification wave could rely on browser state for the plan's manual admin and learner routes.

## Planned Routes

- `/admin/sales-trainer/paths`
- `/admin/sales-trainer/operation-logs`
- `/sales-trainer/business-skills`
- `/sales-trainer/business-skills/coach`

## Executed

Not executed as a release-valid manual QA pass.

Reason:

- F4 failed in Playwright smoke before the release candidate gate completed.
- Frontend logs include Turbopack HMR/internal failures and a Turbopack fatal panic.
- The manual QA preconditions require a stable full app stack with seeded admin and learner users. The available smoke stack was not stable enough to treat the route checks as release evidence.

## Partial Browser Evidence From F4

The F4 smoke run did exercise browser paths and produced these results:

- Passed: unauthenticated learning path redirect.
- Passed: login smoke.
- Passed: dashboard smoke.
- Passed: training entry smoke.
- Failed: practice session smoke.
- Passed: report smoke.
- Passed: replay smoke.
- Passed: admin analytics smoke.
- Failed: support runtime smoke.

Evidence is stored under:

- `.sisyphus/evidence/task-9-quality-gate.txt`
- `.sisyphus/evidence/task-9-test-results/`
- `.omo/evidence/project-governance-refactor/quality-gate/f4-critical-quality-gate.md`

## Release Decision

Do not claim release readiness.

Manual QA for the planned admin/learner sales-trainer routes remains required after the F4 quality gate is green or explicitly waived by release owners.
