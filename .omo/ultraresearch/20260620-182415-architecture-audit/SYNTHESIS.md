# Architecture Audit Synthesis

Date: 2026-06-20
Repository: `/Users/zhaozengqing/github/销售训练qoder`

## Executive conclusion

This project is not failing because of one bad abstraction. The main issue is architectural entropy from several AI-assisted growth lines moving at once:

- sales trainer async learning/configuration flow
- realtime roleplay/WebSocket runtime flow
- prompt governance and AI coach flow
- curriculum practice and question-bank flow
- admin governance pages and seed/backfill scripts
- broad compatibility/fallback work from previous refactors

The result is a codebase with useful pieces, but too many "soft composition roots":

- backend `router_registry.py`
- backend `websocket_routes.py`
- backend shared registries in `runtime_gate.py` and `practice_session_ports.py`
- frontend `api/client.ts`, `api/types.ts`, and route pages that own business orchestration
- large seed/backfill scripts that carry business logic outside normal services

Recommendation: do not start a broad refactor immediately. First freeze, stabilize, and add guardrails. Then refactor by boundary, not by file size.

## Evidence

Repository scale:

- 2381 source/doc files after excluding dependencies/generated dirs.
- Python/TypeScript/TSX scan reported 485764 total lines.
- 560 test files.
- Alembic has 89 version files and current head `20260616_086`.
- Working tree sample showed 120 dirty files; earlier breakdown showed 84 tracked modified and 35 untracked.

Large hotspots:

- `web/src/lib/api/types.ts`: 6915 lines.
- `web/src/lib/api/client.ts`: 4721 lines.
- `backend/src/sales_trainer/schemas.py`: 2716 lines.
- `backend/src/common/db/models.py`: 2661 lines.
- `backend/src/curriculum_practice/api.py`: 2551 lines.
- `backend/src/sales_bot/websocket/stepfun_realtime_upstream.py`: 2755 lines.
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx`: 3350 lines.
- `backend/scripts/seed_presales_cio_first_visit.py`: 3136 lines.

Cross-domain import scan:

- `sales_trainer -> curriculum_practice`: 11 imports across 9 files.
- `curriculum_practice -> sales_trainer`: 4 imports across 2 files.
- `sales_trainer -> prompt_templates`: 10 imports across 6 files.
- `evaluation -> prompt_templates`: 5 imports across 5 files.
- `evaluation -> admin/curriculum_practice/presentation_coach/sales_bot`: multiple direct edges.
- `sales_bot -> agent`: 37 imports across 10 files.

Existing internal docs already agree with this diagnosis:

- `docs/agents/audit-2026-06/00-executive-summary.md`: architecture C+, error handling D+, testing/observability/CI D.
- `docs/agents/audit-2026-06/01-architecture-boundary.md`: module boundaries and cross-domain inheritance issues.
- `docs/agents/audit-2026-06/03-websocket-realtime.md`: WebSocket/realtime coupling and protocol drift.
- `docs/agents/audit-2026-06/08-testing-observability-ci.md`: weak CI/coverage/observability gates.
- `.trellis/tasks/06-14-architecture-optimization-repair-plan/prd.md`: already contains a practical staged repair plan.
- `.trellis/tasks/06-16-project-development-roadmap/prd.md`: product direction should emphasize recording-training capability composition before expanding realtime roleplay.

## Main diagnosis

### 1. Backend composition roots are overloaded

`backend/src/app_factory.py` is the real FastAPI entrypoint. It wires HTTP and WebSocket registration.

`backend/src/router_registry.py` is not just a route list. It also runs contributor registration side effects, mounts RBAC-protected routers, and maintains legacy aliases. This makes it a high-risk global coupling point.

`backend/src/websocket_routes.py` is not just WebSocket registration. It mixes presentation session parsing, token resolution, owner checks, runtime admission, handler selection, and mounting three realtime lines: presentation, curriculum examiner, and sales bot.

Recommendation: first document and test these composition boundaries. Do not split them until guardrail tests exist.

### 2. Shared kernel exists, but is implicit

`backend/src/common/services/runtime_gate.py` and `backend/src/common/services/practice_session_ports.py` are already shared extension points.

The problem is that contributor registration depends on import order and process-global registries. That is workable, but fragile. Missing registration should fail with typed, visible diagnostics.

Recommendation: make registration contracts explicit before moving more code behind them.

### 3. Domain isolation is aspirational, not enforced

Project docs say sales trainer is async and should not depend on realtime runtime domains. The worst prohibited imports are not currently the main issue, but many softer cross-domain edges exist:

- sales trainer and curriculum practice import each other
- evaluation imports several product domains
- prompt templates are used as a cross-domain kernel
- sales bot depends on agent/curriculum/training runtime

Recommendation: add dependency contract tests before refactoring. This will stop AI-generated work from quietly reintroducing cross-domain shortcuts.

### 4. Frontend route pages own too much business flow

Sales trainer frontend has a consistent pattern:

- route page loads data
- route page filters/sorts
- route page owns status decisions
- route page owns action labels and error mapping
- route page calls API directly

Priority files:

- `web/src/app/(dashboard)/sales-trainer/business-skills/page.tsx`
- `web/src/app/(dashboard)/sales-trainer/page.tsx`
- `web/src/app/admin/sales-trainer/paths/page.tsx`
- `web/src/app/admin/sales-trainer/questions/page.tsx`
- `web/src/app/admin/sales-trainer/ai-coach/page.tsx`

Recommendation: move business decisions into `web/src/lib/sales-trainer/` presenters/controllers. Keep pages as route/layout shells.

### 5. Frontend API/type layer is a giant facade

`web/src/lib/api/types.ts` and `web/src/lib/api/client.ts` are too large to reason about locally. `web/src/lib/api/domains/sales-trainer.ts` is a partial domain split, but still mixes user/admin/config/audio flows.

Recommendation: do not rewrite the whole API layer. Start by extracting sales trainer subdomains while preserving existing facade imports:

- user learning
- admin config center
- question governance
- audio submissions
- AI coach

### 6. Scripts and seed files are operational risk

Several backend scripts exceed 1000 lines and contain business setup/backfill logic. This is acceptable during fast development, but unsafe as the product stabilizes.

Recommendation:

- keep CLI wrappers thin
- move reusable logic to services
- require dry-run/count/idempotency for data-changing scripts
- record affected counts and rollback strategy

### 7. Existing plans are useful but too many plans are open

The project already has audit docs, Trellis PRDs, ADRs, and generated plans. More documents will not reduce confusion unless one execution lane is chosen.

Recommendation: adopt one consolidation roadmap and archive or mark superseded duplicates.

## Recommended order

### Phase 0: Stop architecture drift

Goal: make the current state safe enough to refactor.

Actions:

- Stabilize dirty worktree: commit, shelve, or explicitly classify the 120 dirty files.
- Pick one source of truth for package/dependency locks; current root/backend/web locks are mixed.
- Create a short `docs/architecture/current-map.md` that names the real composition roots and active product lanes.
- Mark superseded Trellis/audit plans instead of adding new plans.

Success criteria:

- no broad refactor starts from a dirty, unknown state
- one current roadmap exists
- active vs archived architecture docs are clear

### Phase 1: Add guardrails before moving code

Goal: prevent new AI work from increasing coupling.

Actions:

- Add backend dependency-boundary tests for forbidden imports.
- Add frontend API/page ownership rules, at least as focused tests or lint-like checks.
- Add regression tests for under-covered core services, especially `SalesTrainerRegradeService`.
- Keep `router_registry.py` and `websocket_routes.py` behavior unchanged while tests lock down current mount behavior.

Success criteria:

- forbidden domain imports fail in CI
- route registration smoke tests pass
- critical sales trainer service flows have at least targeted coverage

### Phase 2: Refactor sales trainer frontend first

Goal: reduce day-to-day product confusion without touching risky runtime code.

Actions:

- Extract presenter/view-model from `business-skills/page.tsx`.
- Move dashboard path filtering/action-copy decisions into `web/src/lib/sales-trainer/`.
- Extract admin config center save/publish/rollback controller from `paths/page.tsx`.
- Extract question governance state/action controller from `questions/page.tsx`.

Success criteria:

- route pages mostly render and bind handlers
- business rules live in library modules with tests
- no UI rewrite or route change required

### Phase 3: Split frontend API/types incrementally

Goal: reduce API/type blast radius.

Actions:

- Split sales trainer DTOs from `types.ts` by subdomain.
- Split `domains/sales-trainer.ts` into user/admin/config/audio/AI coach files.
- Keep compatibility exports so existing pages do not change all at once.

Success criteria:

- existing `api.salesTrainer.*` call sites remain valid
- new code imports narrower DTOs
- `types.ts` stops being the default place for new sales trainer contracts

### Phase 4: Backend boundary repair

Goal: make domain and runtime boundaries explicit.

Actions:

- Add anti-corruption adapters between `sales_trainer` and `curriculum_practice`.
- Promote prompt templates to an explicit shared governance service contract.
- Separate contributor registration side effects from route mounting in `router_registry.py`.
- Make `runtime_gate` and `practice_session_ports` registration failure visible and typed.

Success criteria:

- fewer direct cross-domain imports
- missing runtime contributor produces actionable terminal failure
- route mounting still has one visible composition root

### Phase 5: Realtime/WebSocket repair

Goal: handle the riskiest architecture debt after guardrails and product flow stabilize.

Actions:

- Stop presentation realtime from inheriting or directly coupling to sales realtime internals.
- Extract shared realtime protocol/handler interfaces.
- Keep Terminal vs Transient failure semantics explicit.
- Verify at least one user journey from entry page to runtime connection.

Success criteria:

- presentation/sales/curriculum realtime lines share contracts, not implementation subclasses
- WebSocket auth/session/runtime errors are typed and visible
- no blind reconnect loop hides terminal failures

## What not to do

- Do not run a big-bang rewrite.
- Do not split every large file just because it is large.
- Do not add more product modules before stabilizing boundaries.
- Do not expand realtime roleplay before recording-training capability is coherent.
- Do not make `common/` a dumping ground for every cross-domain dependency.
- Do not accept more AI-generated fallback/backfill paths without tests and removal dates.

## Highest-value next PRs

1. Dependency guardrail tests for backend domain imports.
2. Sales trainer frontend presenter extraction for `business-skills/page.tsx`.
3. Sales trainer API type/domain split behind compatibility exports.
4. Config center controller extraction from admin `paths/page.tsx`.
5. Script governance wrapper pattern with dry-run/count/idempotency.
6. Explicit registration contract tests for `runtime_gate` and `practice_session_ports`.

## Risk rating

Overall architecture state: P1 important risk.

Reason:

- Not immediately production-destructive by itself.
- But affects core state flow, realtime connection semantics, admin config, AI prompt governance, and future refactor safety.
- Current dirty worktree makes direct refactor risk higher than normal.

## Final recommendation

Treat the next 1-2 weeks as a consolidation cycle, not a feature cycle.

The best route is:

1. freeze and classify current changes
2. install dependency and route guardrails
3. refactor sales trainer frontend/page/API hotspots
4. then repair backend shared runtime and websocket boundaries

This order gives visible clarity quickly while delaying the riskiest realtime surgery until there is enough test coverage and boundary enforcement.
