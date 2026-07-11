# Gate 5 current locality and model-registry truth

Date: 2026-07-11 UTC

## Authority and scope

Gate 5 implements the already-approved Modular Monolith 2.0 direction. The user has authorized
continuous execution without another approval round and explicitly prohibited sub-agent dispatch.
The work therefore uses inline CodeGraph/Trellis discovery and keeps the existing REST, WebSocket,
RBAC, frozen snapshot, report and database contracts unchanged.

The Gate is a locality refactor, not a product redesign:

- Training Journey and Readiness Dossier should consume projections rather than foreign ORM rows;
- report UI mapping and actions should live beside the report route;
- Journey/Readiness/report type definitions and transport factories should have domain locality;
- `common/db/models.py` should become a compatibility registry over physically grouped model modules,
  while all classes keep the same `Base.metadata`, table names, constraints and import identities;
- Gate 6, not Gate 5, retires compatibility exports after consumer proof.

## CodeGraph and source facts

### Backend

- `TrainingJourneyService` is 2,855 lines and has 150 affected symbols. It mixes database lookup,
  active-revision outcome collection, Journey projection, analytics aggregation, role capability and
  learner-level policy. Its public callers are the Sales Trainer routes, Readiness Dossier, learner
  access checks, seed verification and focused tests.
- `ReadinessDossierService` is 1,284 lines and has 47 affected symbols. Database/RBAC orchestration is
  mixed with a large pure projection from Journey + records + review actions to dossier/workbench.
- Both classes directly import `User`; Journey also imports `PracticeSession` from
  `common.db.models`. These are the first approved cross-domain ORM reads to replace with immutable
  projection ports and SQL adapters.
- `common/db/models.py` is 2,663 lines and defines 65 public enum/entity classes plus `Base`, including
  52 mapped tables; importing the complete application model graph registers 98 tables on the same
  metadata. There are 224 source
  files with direct imports from this compatibility path. The file has string-based SQLAlchemy
  relationships and one shared `Base`, so it can be split physically without changing table/FK or
  deployment topology if every grouped module is imported by the registry before metadata use.
- Current dependency policy is green: 15 packages, 52 explained edges, 7-package historical SCC.

### Frontend

- `web/src/lib/api/types.ts` is 8,459 lines and `client.ts` is 4,825 lines.
- Domain builder files already exist, but `types/sales-trainer.ts` and
  `types/newcomer-training.ts` are shallow pass-through exports back to the global type barrel.
- Journey/Readiness types are still defined in global `types.ts`; 19 Journey/Readiness consumers
  import the global barrel. The Sales Trainer domain builder also imports Journey types from the
  global barrel.
- The session report page is 3,350 lines, imports 20 report-related global types, owns mapping/label/
  action URL rules and orchestration in the same file. Its data hook also reaches the global `api`
  façade and global type barrel.
- Focused frontend baseline is 6 files / 91 tests green.

## Historical co-change evidence

For 201 commits since 2026-01-01 that touched at least one hotspot:

| File | Commits |
|---|---:|
| `training_journey_service.py` | 5 |
| `readiness_dossier_service.py` | 3 |
| `common/db/models.py` | 38 |
| report `page.tsx` | 46 |
| global `types.ts` | 110 |
| global `client.ts` | 95 |

Observed pair co-change: Journey + global types 4/5; Dossier + global types 3/3; report page + global
types 22 times; report page + global client 10 times; global types + global client 55 times. These
figures justify a Gate 5 locality target and provide a Gate 6 comparison baseline.

## Options considered

1. **Recommended — vertical strangler slices with compatibility registries.** Introduce immutable
   projection ports/adapters, move pure projection rules behind deep Modules, move domain type/transport
   definitions to domain files, and turn old paths into tested re-export registries. This maximizes
   locality and leverage while preserving Hyrum-law import surfaces and rollback.
2. **Big-bang directory rewrite.** Move every model/type/client method and all consumers at once. This
   might produce a cleaner final tree but creates an unreviewable blast radius across 224 backend
   importers and hundreds of frontend imports. Rejected as second-system risk.
3. **Add new façades without moving authority.** This is mechanically safe but fails the deletion test:
   removing the new modules would remove complexity rather than move it back to callers. Rejected as
   shallow modules and false closure.

## Selected deepening opportunities

1. **Journey/Readiness projection Module** — SQL adapters return immutable learner/session projections;
   orchestration stays in application services while deterministic status, evidence, competencies,
   next actions and analytics move behind a small projection interface. Tests call the same interface
   as production, improving testability and locality.
2. **Report route Module** — report DTO mapping, labels, navigation/retraining actions and asynchronous
   load state live beside the route behind explicit pure interfaces. Page JSX consumes ViewModels rather
   than repeating transport-field interpretation.
3. **Domain transport/type Modules** — real Journey/Readiness/report definitions and request builders
   live in domain files. Global barrels remain compatibility exports only; a new domain change no longer
   requires editing `types.ts` or `client.ts`.
4. **Physical ORM registry Modules** — entity implementations are grouped by identity, governance,
   training/evidence, evaluation/supervision, platform and knowledge. `common.db.models` remains the
   stable compatibility interface and imports every group into the same `Base.metadata`.

## Immutable baseline

- Backend Journey + Dossier: `31 passed`.
- Backend model/ownership/architecture: `39 passed` (the first repo-root invocation was invalid because
  architecture tests require backend as cwd; the corrected command is the baseline).
- Frontend report/Journey/readiness/domain builders: 6 files / `91 passed`.
- Direct architecture guard: `[architecture] dependency policy satisfied`.

No external provider, production data, schema migration, push or deployment is part of Gate 5.
