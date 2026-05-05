# Delivery TODO

This file mirrors `DELIVERY_STATE.md` at task-list granularity. `DELIVERY_STATE.md` is the source of truth for phase status, verification evidence, commits, and blockers.

## Current Atomic Task

- [x] Phase 1.0: Create delivery state baseline.
- [x] Verify delivery state baseline.
- [x] Commit delivery state baseline.

## Phase 1: Baseline Falsification and Routing Audit

- [x] Generate `api_routing_audit.md` with OpenAPI paths, router sources, permission dependencies, and frontend call mapping.
- [x] Fix unmounted or wrongly mounted backend routes.
- [x] Fix frontend/backend API contract mismatches.
- [x] Fix frontend/backend lint errors.
- [x] Fix TypeScript type errors.
- [x] Normalize backend mypy invocation configuration.
- [x] Limit installed untyped third-party mypy noise.
- [x] Type backend entrypoint helpers.
- [x] Clean shared backoff helper mypy error.
- [x] Type retry focus page-number sanitation.
- [x] Type scoring ruleset schema literal constant.
- [x] Type document parse artifact loading contract.
- [x] Type OSS signing GET URL return contract.
- [x] Type admin permission dependency factory contract.
- [x] Type latency tracker constructor contract.
- [x] Type KB lock metric callback contract.
- [x] Type semantic cache hit payload contract.
- [x] Type Result generic helper contracts.
- [x] Type embedding service property contracts.
- [x] Type runtime event literal contracts.
- [x] Type assembler metadata contracts.
- [x] Type answerability metadata contracts.
- [x] Type evaluation harness payload contracts.
- [x] Type haystack adapter callback contracts.
- [x] Type HTML sanitizer URL callback contract.
- [x] Type auth middleware dispatch contract.
- [x] Type ingestion service lazy vector-store contract.
- [x] Type knowledge schema validator contracts.
- [x] Type RAG profile service sequence contract.
- [x] Type leaderboard success value contract.
- [x] Type admin training duration contract.
- [x] Type sales stage config read contract.
- [x] Type trigger context metadata contract.
- [x] Type point tracker state contract.
- [x] Type interruption detector constructor contract.
- [x] Type sales bot lazy chain contract.
- [x] Type TTS streaming callback contract.
- [x] Type persona prompt constructor contract.
- [x] Type growth safety policy resolver contract.
- [x] Type vagueness detector constructor and pattern compiler contracts.
- [ ] Resolve backend mypy baseline blocker.
- [ ] Configure Vitest to isolate `node_modules`.
- [ ] Raise overall coverage to at least 60%.
- [ ] Raise `scoring`, `auth`, and `practice` coverage to at least 70%.

## Phase 2: Admin Governance Foundation and RBAC Loop

- [ ] Move scoring rulesets to `/api/v1/admin/scoring-rulesets`.
- [ ] Add scoring rulesets CRUD, publish, rollback, and dry-run.
- [ ] Sync frontend client and legacy path compatibility.
- [ ] Add RBAC schema, migrations, audit logs, and five seeded roles.
- [ ] Add action-level permission checks and audit persistence to high-risk admin APIs.
- [ ] Build RBAC admin UI.
- [ ] Enforce permission-based menus/buttons and direct-access 403 handling.

## Phase 3: User Dictionary Full Business Chain

- [ ] Add versioned and audited user dictionary model.
- [ ] Build user dictionary admin CRUD UI.
- [ ] Normalize ASR final transcripts through dictionary correction.
- [ ] Persist correction evidence to session messages.
- [ ] Use normalized text for knowledge retrieval grounding.
- [ ] Display correction traces in scoring evidence, six-dimensional reports, and Replay pages.

## Phase 4: Stable E2E for Both Training Flows

- [ ] Build auditable local mock provider for AI, ASR, and TTS.
- [ ] Add standard fixtures including corrupted PPT fixtures.
- [ ] Add sales training E2E success/degraded paths.
- [ ] Add presentation training E2E success path.
- [ ] Run both main E2E flows 3 consecutive times locally.
- [ ] Verify core API p95 latency below 500ms.

## Phase 5: Security Gate and Release Closure

- [ ] Extract frontend thresholds and operational copy into business configuration dictionaries.
- [ ] Validate defaults and fallback behavior for business configuration dictionaries.
- [ ] Run secret scan and reach 0 high-risk findings.
- [ ] Redact tokens and cookies from logs.
- [ ] Disable dev-login and default secrets in production.
- [ ] Create final `Release_Checklist.md`.

## Review

- 2026-05-06 Phase 1.3: backend `ruff check src tests`, frontend `npx eslint . --quiet`, frontend `npx tsc --noEmit`, and targeted touched-file tests passed. Backend mypy invocation is now normalized in `pyproject.toml`; direct `./.venv-test/bin/mypy src` reaches real checking and reports 2376 errors in 127 files after limiting installed untyped third-party library noise, typing backend entrypoint helpers, cleaning the shared backoff helper, typing retry focus page-number sanitation, typing the scoring ruleset schema literal constant, typing the document parse artifact loading contract, typing the OSS signing GET URL return contract, typing the admin permission dependency factory contract, typing the latency tracker constructor contract, typing the KB lock metric callback contract, typing the semantic cache hit payload contract, typing the Result generic helper contracts, typing the embedding service property contracts, typing the runtime event literal contracts, typing the assembler metadata contracts, typing the answerability metadata contracts, typing the evaluation harness payload contracts, typing the haystack adapter callback contracts, typing the HTML sanitizer URL callback contract, typing the auth middleware dispatch contract, typing the ingestion service lazy vector-store contract, typing the knowledge schema validator contracts, typing the RAG profile service sequence contract, typing the leaderboard success value contract, typing the admin training duration contract, typing the sales stage config read contract, typing the trigger context metadata contract, typing the point tracker state contract, typing the interruption detector constructor contract, typing the sales bot lazy chain contract, typing the TTS streaming callback contract, typing the persona prompt constructor contract, typing the growth safety policy resolver contract, and typing the vagueness detector constructor and pattern compiler contracts.
