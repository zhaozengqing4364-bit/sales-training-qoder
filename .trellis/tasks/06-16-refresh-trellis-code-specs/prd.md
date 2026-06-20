# Refresh Trellis Code Specs

## Goal

Refresh the existing `.trellis/spec/` coding guidance so future agents can implement safely from the real repository structure, contracts, and repeated local patterns instead of generic templates.

## What I already know

* The user invoked `trellis-spec-bootstarp`.
* This repository already has Trellis specs for `backend`, `frontend`, and `guides`.
* The app is a single-repo project with a FastAPI backend and Next.js frontend.
* Current spec files are mostly project-specific, not empty templates.
* GitNexus/ABCoder MCP tools are not currently exposed in this Codex session, so repository analysis will use direct source reads, project docs, language manifests, and `rg`/`find`.
* The working tree contains many pre-existing uncommitted product-code changes. This task must not revert or silently include unrelated product changes.
* Initial audit found the clearest current spec drift in frontend API client guidance: specs describe `client-domains.ts` as the domain-method location, while current code uses `client-domains.ts` as an aggregation seam and newer high-growth domains live in `web/src/lib/api/domains/*`.

## Assumptions

* Scope is documentation/spec refresh only: `.trellis/spec/**` plus task notes/research artifacts.
* Product source code, API contracts, database migrations, and runtime behavior are out of scope unless the user explicitly expands scope.
* Because specs already exist, the highest-value path is to audit and refresh stale/missing guidance rather than regenerate every file from scratch.

## Requirements

* Inspect the current `.trellis/spec/` tree and its indexes.
* Analyze repository architecture from source-backed evidence:
  * top-level project docs and AGENTS files;
  * backend package layout, route registration, service patterns, tests, and migrations;
  * frontend app layout, shared components, hooks, API client/types, tests, and route conventions.
* Identify stale, generic, missing, or misleading spec guidance.
* Refresh the frontend API client guidance so future work preserves the public `api` facade while allowing domain factories under `lib/api/domains/*`.
* Update relevant `.trellis/spec/` files with concrete local patterns, file paths, examples, anti-patterns, and verification commands.
* Keep `index.md` files consistent with the final spec file set.
* Do not leave placeholder text, empty headings, or copied boilerplate.

## Decision (ADR-lite)

**Context**: Initial audit found existing specs are already mostly project-specific. The clearest source-backed drift is frontend API client guidance: current code preserves a public `api` facade in `web/src/lib/api/client.ts`, keeps `web/src/lib/api/client-domains.ts` as an aggregation seam, and has extracted newer high-growth domains into `web/src/lib/api/domains/*`.

**Decision**: Use the narrow refresh scope selected by the user: update frontend API-client guidance only, rather than regenerating all backend/frontend/guides specs.

**Consequences**: The task stays low risk and avoids noisy documentation churn. Backend spec refresh remains out of scope unless a later source-backed audit finds a concrete mismatch.

## Acceptance Criteria

* [x] Specs contain source-backed project guidance, not generic framework advice.
* [x] Any added or changed rule cites real repository files, tests, or project docs.
* [x] Frontend specs describe `client-domains.ts` as an aggregation seam and `lib/api/domains/*` as the place for extracted high-growth domain factories.
* [x] Frontend specs preserve the rule that UI layers import only the public `api` facade from `lib/api/client.ts`.
* [x] Index files match the final spec file set.
* [x] No placeholder/template markers remain in `.trellis/spec/` except legitimate domain words such as prompt-template fields.
* [x] The final diff is limited to `.trellis/spec/**` and Trellis task artifacts unless the user approves a wider scope.
* [x] Verification includes placeholder scan and link/index consistency checks.

## Definition of Done

* Relevant Trellis specs refreshed.
* Internal consistency checks completed.
* Existing unrelated dirty files left untouched.
* Delivery notes include what changed, evidence used, skipped areas, and remaining risks.

## Technical Approach

1. Audit existing spec tree and classify gaps.
2. Inspect representative backend/frontend source and tests.
3. Write or revise only the frontend specs with concrete API-client seam gaps.
4. Re-run scans for placeholders, broken index references, and unintended files.

## Implementation Plan

* Update `.trellis/spec/frontend/directory-structure.md` to describe the current API facade, `client-domains.ts` aggregation seam, and `lib/api/domains/*` extracted domain modules.
* Update `.trellis/spec/frontend/type-safety.md` with signatures/contracts for API domain factories, stream methods, boundary tests, and wrong/correct import examples.
* Update `.trellis/spec/frontend/quality-guidelines.md` so API contract test guidance points to the facade/domain boundary test and the relevant domain test files.
* Verify with placeholder scan and targeted diff review.

## Out of Scope

* Product source implementation changes.
* API contract behavior changes.
* Database migrations.
* Rewriting all specs from scratch when existing docs are already accurate.
* Installing or configuring GitNexus/ABCoder during this task.
* Broad backend spec rewrite; the initial pass did not find a source-backed structure drift that justifies it.

## Technical Notes

* Skill: `.agents/skills/trellis-spec-bootstarp/SKILL.md`
* References read:
  * `.agents/skills/trellis-spec-bootstarp/references/repository-analysis.md`
  * `.agents/skills/trellis-spec-bootstarp/references/spec-task-planning.md`
  * `.agents/skills/trellis-spec-bootstarp/references/spec-writing.md`
  * `.agents/skills/trellis-spec-bootstarp/references/mcp-setup.md`
* Project docs read:
  * `CLAUDE.md`
  * `backend/AGENTS.md`
  * `web/AGENTS.md`
* Existing spec files:
  * `.trellis/spec/backend/*.md`
  * `.trellis/spec/frontend/*.md`
  * `.trellis/spec/guides/*.md`
* Research:
  * `research/spec-audit.md`

## Verification

* Whitespace check passed for the three changed frontend spec files.
* Stale wording scan found no remaining references that describe `client-domains.ts` as the only domain-method location.
* Frontend index link check found no missing linked spec files.
* Placeholder scan only matched existing backend business-rule `template placeholder` contract wording; no unfilled template markers were found.
* Frontend lint/typecheck/tests were not run because this task changed only Markdown specs and Trellis task notes.
