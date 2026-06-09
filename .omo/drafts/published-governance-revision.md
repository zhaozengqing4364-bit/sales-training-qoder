# Draft: Published Governance Revision Plan

## Requirements (confirmed)
- Generate only a plan document, not production code.
- Save the final plan to `.omo/plans/published-governance-revision-plan.md`.
- Upgrade the system from "published objects cannot be edited / copy draft / manual rebinding" to "natural editing with automatic immutable revisions, frozen history snapshots, future-only activation, audit, rollback, and explicit high-risk regrading".
- Include dbs-goal style target audit: tangible deliverables, falsifiability, done state, context constraints, and failure standards.

## Skills Survey
- `omo:ulw-plan`: primary workflow because the user explicitly requested a decision-complete implementation plan.
- `dbs-goal`: used as a style framework for target audit and failure standards.
- `goal-generator`: used as context for plan-generator goals; this task is plan-only rather than implementation.
- `omo:programming`: not used for edits because no `.py/.ts/.tsx` code will be changed; source files are read-only references.
- `browser:control-in-app-browser`: not used because this turn creates a plan, not UI verification.

## Technical Decisions
- Plan will prioritize `sales_trainer` first, then generalize to `curriculum_practice`.
- Target model will be `logical_id` plus immutable `revision_id` or an equivalent existing-project-compatible model.
- Historical attempts/sessions/results must reference snapshots or revision ids captured at submission/runtime start.
- Normal admin UI must expose business actions: edit, save, publish, history, rollback, regrade; technical ids only in diagnostic expanders.

## Research Findings
- Pending: required docs and source inventory.

## Open Questions
- None blocking. The user already specified the target model and plan-only scope.

## Scope Boundaries
- INCLUDE: plan document, object-level audit, dependency order, data/API/backend/frontend/permission/audit/test plan.
- EXCLUDE: source code changes, database migrations, UI implementation, test implementation.
