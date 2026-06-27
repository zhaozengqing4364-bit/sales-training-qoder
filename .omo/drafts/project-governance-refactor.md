---
slug: project-governance-refactor
status: drafting
intent: unclear
pending-action: finalize .omo/plans/project-governance-refactor.md
approach: staged governance refactor with guardrails first, compatibility-preserving extraction second, high-risk realtime boundary last
---

# Draft: project-governance-refactor

## Components (topology ledger)

| id | outcome | status | evidence path |
| --- | --- | --- | --- |
| C1 | Backend composition roots are explicit and domain contributors are bootstrapped separately from route mounting. | active | `.omo/teams/019ee483-f9de-7092-ba58-61131b087ec8/artifacts/member-a-backend-boundary-memo.md` |
| C2 | Backend dependency direction is enforced by tests and the existing reverse-dependency allowlist shrinks over time. | active | `backend/tests/unit/test_runtime_dependency_contract.py` |
| C3 | Frontend route pages stop owning business rules; presenters/controllers own route decisions and state transitions. | active | pending member B memo; direct evidence in `web/src/app/(dashboard)/sales-trainer/business-skills/page.tsx`, `web/src/app/admin/sales-trainer/paths/page.tsx` |
| C4 | Frontend API/types split by subdomain behind compatibility exports, avoiding a breaking call-site rewrite. | active | pending member B memo; direct evidence in `web/src/lib/api/domains/sales-trainer.ts`, `web/src/lib/api/types.ts` |
| C5 | Configuration, prompt, permissions, status, and audit have one lifecycle vocabulary even where storage remains split. | active | pending member C memo; direct evidence in `docs/api-contract/sales-trainer.md`, `backend/src/sales_trainer/services/path_config_service.py`, `backend/src/prompt_templates/service.py` |
| C6 | Tests, CI, migrations, scripts, and release verification become the execution rails for long Ultra Loop runs. | active | pending member D memo; direct evidence in `backend/pyproject.toml`, `package.json`, `.github/workflows/*`, `backend/alembic/versions/` |
| C7 | Realtime/WebSocket runtime boundary is repaired only after lower-risk guardrails and ports are stable. | active | member A memo; `docs/agents/audit-2026-06/03-websocket-realtime.md` |

## Open assumptions (announced defaults)

| assumption | adopted default | rationale | reversible? |
| --- | --- | --- | --- |
| Refactor scope | Consolidation cycle, not feature cycle. | User asked for governance clarity and sustainable architecture before Ultra Loop implementation. | Yes |
| Architecture strategy | No big-bang rewrite. | Existing code has working seams and tests; replacing them wholesale is higher risk than shrinking debt. | Yes |
| Compatibility | Preserve public API URLs, front-end `api.*` facade, and existing data tables during early waves. | Lets Ultra Loop proceed in small PRs and keeps user paths stable. | Yes |
| Backend boundary | Composition roots may import domains; `common/` should not import concrete scenario domains except temporary allowlisted debt. | Matches existing architecture docs and dependency contract tests. | Yes |
| Frontend boundary | Pages become route/layout shells; presenters/controllers and API domains own business decisions. | Reduces route-level coupling without UI rewrite. | Yes |
| Config governance | First unify lifecycle/audit/contract interfaces; do not immediately migrate all `SalesTrainerAssetRevision` data into `ConfigBundle`. | Member C evidence shows two tracks exist; interface convergence is lower risk than storage migration. | Yes |
| AI prompt governance | Keep `PromptTemplateService` as runtime authority; domain policy declares bindings, RBAC, and audit expectations. | Existing prompt governance is mature enough to reuse. | Yes |
| Testing approach | Characterization and guardrail tests first; behavior-preserving refactors must stay green throughout. | Long Ultra Loop needs tight rails to avoid silent drift. | Yes |
| Release strategy | Every wave must have a rollback path and one real surface proof, but not every wave needs full E2E. | Ponytail: smallest faithful check for the changed surface. | Yes |

## Findings (cited - path:lines)

- Backend composition root is already centralized: `backend/src/app_factory.py` is 199 lines and calls HTTP/router/WebSocket registration; `backend/src/main.py` is now a compatibility shim per member A memo.
- `backend/src/router_registry.py` is 380 lines and mixes contributor registration with route mounting; member A identifies this as the primary backend bootstrap pressure point.
- `backend/src/websocket_routes.py` is 352 lines and mounts presentation, curriculum examiner, and sales WebSocket surfaces; member A recommends keeping admission fail-fast and deferring high-risk runtime split.
- Existing backend dependency guardrail is valuable: `backend/tests/unit/test_runtime_dependency_contract.py:34-45` defines `COMMON_REVERSE_DEPENDENCY_ALLOWLIST`, `:129-140` fails new common reverse dependencies, `:143-166` keeps `sales_trainer` out of realtime modules, and `:188-206` prevents adapter exports of foreign ORM models.
- Known backend debt should be retired by shrinking allowlists, not by inventing a new system: `common/services/session_runtime_repair_service.py -> sales_bot` is allowlisted at `backend/tests/unit/test_runtime_dependency_contract.py:43`.
- Existing runtime/session port seam should be preserved: `backend/src/common/services/practice_session_ports.py` is 262 lines and already supports runtime policy resolver, descriptor builder, template identity, snapshot applier, session creator, and terminal handler registration.
- Frontend API/type blast radius is real: `web/src/lib/api/types.ts` is 6915 lines and `web/src/lib/api/domains/sales-trainer.ts` is 896 lines.
- Frontend route-owned business logic is real: `web/src/app/(dashboard)/sales-trainer/business-skills/page.tsx` is 1276 lines; `web/src/app/admin/sales-trainer/paths/page.tsx` is 237 lines and owns config load/save/publish/rollback orchestration per member B.
- Contract drift exists in newcomer completion rules: `docs/api-contract/sales-trainer.md:89-93` defines `audio_scored | paper_passed | all_audio_options_scored | placeholder_disabled`, while `backend/src/sales_trainer/schemas.py:62`, `:297`, `:1176` and `web/src/lib/api/types.ts:4733`, `:4866-4883` use `passed | scored | submitted`.
- Large operational scripts are release risk: backend script inventory shows `seed_presales_cio_first_visit.py` at 3136 lines and `seed_newcomer_training_path.py` at 2425 lines.
- Migration state currently has one Alembic head, `20260616_086`, but D is verifying whether migration graph tests have stale expected heads.
- Existing architecture audit rated overall health C+ and testing/observability/CI D; current plan should close execution rails before broad rewrites.
- Product roadmap already recommends focusing on recording-training capability composition before expanding realtime roleplay.

## Decisions (with rationale)

1. Start with guardrails and contract drift, not file splitting.
   - Rationale: dependency contract and API contract drift can catch future AI-generated regressions before they become another layer of confusion.

2. Keep and improve existing seams.
   - Backend: keep `practice_session_ports`.
   - Frontend: keep `api.salesTrainer` compatibility facade while splitting internals.
   - Prompt: keep `PromptTemplateService` as runtime authority.
   - Config: keep current storage tracks while unifying lifecycle and audit vocabulary.

3. Split responsibility before moving data.
   - Route mounting vs contributor bootstrap.
   - Page rendering vs view-model/controller decisions.
   - DTO/type authority vs API request implementation.
   - Domain policy vs prompt runtime compilation.

4. Defer high-risk realtime runtime inheritance repair.
   - Rationale: presentation/sales StepFun split is real debt, but has high blast radius and should follow characterization tests.

5. Treat existing Trellis/audit tasks as source material, not independent active roadmaps.
   - Rationale: 13 active tasks is itself governance entropy.

## Scope IN

- Architecture map and ADR for target governance model.
- Backend dependency guardrails and contributor bootstrap split.
- Contract drift detection for sales-trainer/newcomer path.
- Frontend sales-trainer route controller/presenter extraction.
- Frontend API/types sales-trainer subdomain split behind compatibility exports.
- Configuration lifecycle/audit/prompt governance facade.
- Script governance for large seed/backfill paths.
- CI/test/release gate alignment for long-running Ultra Loop.
- Final verification and review gates.

## Scope OUT (Must NOT have)

- No big-bang rewrite.
- No public route/API URL changes in early waves.
- No database storage migration until interfaces and tests are stable.
- No immediate presentation/sales StepFun runtime split before characterization.
- No new dependency unless an existing tool cannot do the job.
- No weakening tests, allowlists, or contracts to make refactor pass.
- No business feature expansion while governance refactor is running.

## Open questions

None blocking. User can veto adopted defaults in the final summary.

## Approval gate

status: approved-by-request

The user explicitly asked to generate a detailed comprehensive plan for later Ultra Loop execution. Approval covers writing the plan only, not implementation.
