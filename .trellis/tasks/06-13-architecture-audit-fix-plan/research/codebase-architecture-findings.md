# Codebase Architecture Findings

## Scope

Static architecture scan of the modular monolith in `backend/src` and `web/src`.

## Repo Constraints

- Backend is a FastAPI modular monolith.
- `backend/src/common/` is the shared kernel and must not contain scenario-specific logic.
- `backend/src/sales_bot/` and `backend/src/presentation_coach/` are independent realtime practice scenarios.
- `backend/src/sales_trainer/` is a separate async newcomer training product.
- Frontend is a pure backend consumer. No Next.js API routes are allowed.
- Frontend API access goes through `web/src/lib/api/client.ts` and domain builders.
- Adjustable business rules should use the shared business-rule lifecycle instead of local constants or environment-variable-only policy.

## Verified Architecture Hotspots

### Shared Kernel Reverse Dependency

- `backend/src/common/api/dashboard.py` imports `sales_trainer.services.path_service.SalesTrainerPathService`.
- `sales_trainer` imports `common` broadly, creating a top-level `common <-> sales_trainer` cycle.
- This conflicts with backend directory guidance that `common/` is shared kernel only.

### Curriculum and Sales Trainer Cross-Domain Coupling

- `backend/src/curriculum_practice/services/asset_reference_lineage.py` imports `SalesTrainerAssetActiveRevision` and `SalesTrainerAssetRevision`.
- `backend/src/sales_trainer/services/question_bank_adapter.py` imports `curriculum_practice.models.QuestionItem`.
- This is an intentional business integration, but it is implemented through direct model imports rather than an anti-corruption boundary.

### Support Runtime Aggregator Coupling

- `backend/src/support/services/runtime_status_service.py` imports several domain services/models directly:
  - `agent.models`
  - `curriculum_practice.services.roleplay.*`
  - `presentation_coach.services.presentation_report_service`
  - `sales_bot.services.voice_runtime_policy`
- This makes support runtime health depend on each domain's internal implementation.

### AI Coach Testability Seam

- `backend/src/sales_trainer/services/ai_coach_chat_service.py` constructs store/runtime/scorer/log/event collaborators directly in `__init__`.
- Tests currently replace internals after construction, which is workable but brittle.

### Permission Knowledge Duplication

- Backend sales trainer permissions are in `backend/src/sales_trainer/permissions.py`.
- Frontend admin sidebar repeats role-string decisions in `web/src/components/layout/admin-sidebar.tsx`.
- This should converge to backend capability projection for frontend navigation.

### Frontend API Surface Width

- `web/src/lib/api/types.ts` is over 6000 lines.
- `web/src/lib/api/client.ts` is over 4700 lines and imports many cross-domain types at top-level.
- Existing convention says pages should import `api` facade, but the backing files need domain splits to reduce change blast radius.

### Frontend Lib to Component Type Leak

- `web/src/lib/admin/template-form-preflight.ts` imports `AssetRefPickerOption` from `web/src/components/admin/asset-ref-picker.tsx`.
- Move shared type to `web/src/lib/admin/asset-ref-types.ts` or a domain contract file.

## Candidate Fix Lanes

### Lane A: Boundary Repair First

Break backend top-level dependency cycles before frontend cleanups.

- Pros: reduces highest architectural risk first.
- Cons: may touch dashboard, provider registration, tests, and possibly API payloads.

### Lane B: Low-Risk Cleanups First

Start with frontend type leak, AI Coach seam, and permission projection.

- Pros: smaller changes, easier to verify.
- Cons: leaves `common <-> sales_trainer` and `curriculum_practice <-> sales_trainer` cycles in place.

### Lane C: Vertical Slice Per Product

Fix only sales trainer related issues end-to-end.

- Pros: aligns with current active product work.
- Cons: support runtime and shared frontend API width remain as wider platform debt.

## Recommended Direction

Use Lane A as the roadmap, but implement in small PRs:

1. Break `common -> sales_trainer` through a recommendation provider boundary.
2. Introduce anti-corruption contracts for curriculum/sales trainer asset lineage.
3. Convert support runtime aggregation to contributor registration.
4. Add AI Coach dependency seams.
5. Centralize sales trainer permission capability projection.
6. Split frontend API types/domain files incrementally.
7. Move leaked UI option type out of component layer.

