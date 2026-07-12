# Gate 5 Training Locality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Execute this plan inline with `superpowers:executing-plans`; sub-agent dispatch is prohibited by the user. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deepen Training Journey, Readiness Dossier, session report and ORM registry Modules so domain changes remain local without changing external behavior, schema or compatibility imports.

**Architecture:** Use vertical strangler slices. Immutable read projections separate Sales Trainer policy from foreign ORM, pure projection Modules own deterministic Journey/Dossier rules, report-local mappers/actions own UI interpretation, and compatibility registries preserve global Python/TypeScript import surfaces until Gate 6. SQLAlchemy entities remain on one `Base.metadata`; frontend pages continue calling the outward `api` façade.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2 async, pytest, Ruff, mypy, Next.js 16, React 19, TypeScript strict, Vitest, Playwright, CodeGraph, Trellis.

**Execution status (2026-07-11 UTC):** Tasks 1–7 are implemented, verified and committed through their
respective slices; Task 8 exclusively owns the independent Brooks/Trellis audit, clean-start canonical gate,
authority evidence and Trellis closure.

## Global Constraints

- Preserve REST/WS paths, OpenAPI, RBAC, RuntimeGate, frozen snapshots, KB fail-closed, epoch, score/report single-writer and audit behavior.
- No database migration, table/column/index/constraint/default change, new dependency, microservice, paid Provider, production write, push, PR or deployment.
- Keep `common.db.models` and global frontend barrels as rule-free compatibility seams until Gate 6.
- Do not add skip/xfail/retry/`|| true`; failures use Red → Green → Refactor.
- Do not stage or edit `docs/superpowers/plans/2026-07-10-readiness-decision-integrity.md`.
- No sub-agent dispatch. Inline execution is the approved implementation mode.

---

## File map

### Backend model registry

- `backend/src/common/db/model_registry/base.py` — one `Base` and JSONB-compatible type factory.
- `backend/src/common/db/model_registry/enums.py` — existing public enum definitions.
- `backend/src/common/db/model_registry/identity.py` — user, permission, preference and password entities.
- `backend/src/common/db/model_registry/governance.py` — business/config/prompt/scoring governance entities.
- `backend/src/common/db/model_registry/training.py` — scenario, presentation, session, task, conversation and highlight entities.
- `backend/src/common/db/model_registry/evaluation.py` — evaluation run/report/supervision/retraining entities.
- `backend/src/common/db/model_registry/platform.py` — achievement, notification, goal, intervention, leaderboard, logs, release and audio entities.
- `backend/src/common/db/model_registry/knowledge.py` — knowledge-answer control-plane entities.
- `backend/src/common/db/model_registry/__init__.py` — complete, ordered registry exports.
- `backend/src/common/db/models.py` — compatibility-only re-export surface.

### Backend Journey/Readiness

- `backend/src/sales_trainer/services/journey_read_repository.py` — immutable read DTOs, queries and Protocol.
- `backend/src/sales_trainer/services/journey_sqlalchemy_adapter.py` — ORM → read DTO adapter.
- `backend/src/sales_trainer/services/training_journey_projection.py` — deterministic module/status/action/analytics projection.
- `backend/src/sales_trainer/services/readiness_dossier_projection.py` — deterministic dossier/workbench projection.
- Existing Journey/Dossier services — application orchestration and transaction only.

### Frontend locality

- `web/src/lib/api/types/training-journey.ts` — Journey/Readiness DTO authority.
- `web/src/lib/api/types/session-report.ts` — report/replay/supervisor DTO authority.
- `web/src/lib/api/domains/sessions.ts` — session report/replay/history transport builder.
- `web/src/app/(user)/practice/[sessionId]/report/report-view-model.ts` — pure DTO → UI mapper.
- `web/src/app/(user)/practice/[sessionId]/report/report-actions.ts` — pure route/action builder.
- `web/src/app/admin/sales-trainer/readiness/[learnerId]/readiness-view-model.ts` — dossier display mapper.
- Existing global `types.ts`, `client-domains.ts`, `client.ts` — composition/re-export only for moved knowledge.

---

### Task 1: Freeze Gate 5 behavior, import and metadata truth

**Files:**
- Create: `backend/tests/unit/test_gate5_locality_contracts.py`
- Create: `web/src/lib/api/gate5-locality.test.ts`
- Modify: `.trellis/tasks/07-11-modular-monolith-2-gate-5/implementation-notes.md`

**Interfaces:**
- Consumes: current `common.db.models`, Journey/Dossier public methods, global TS barrels and domain builders.
- Produces: immutable symbol/metadata/import/locality assertions every later task must keep green.

- [x] **Step 1: Write backend characterization tests**

  Define the exact 65 public enum/entity class names plus `Base`, assert each is importable from
  `common.db.models`, assert the 52 relocated mapped tables and the full 98-table metadata's complete
  every mapped table name/columns/PK/FK/index/unique/check/default signature, and assert all classes share
  `Base.metadata`. Add AST checks that identify current direct `User`/`PracticeSession` imports in the two
  application services and fail once the target architecture is not present.

- [x] **Step 2: Write frontend locality characterization tests**

  Assert Journey/Readiness/report symbols remain import-compatible from `types.ts`, domain builders remain
  composed by `client.ts`, pages do not import builder implementations directly, and define the target rule:

  ```ts
  expect(globalTypesSource).not.toMatch(/interface TrainingJourneyResponse/);
  expect(globalTypesSource).not.toMatch(/interface ReadinessDossier/);
  expect(globalTypesSource).not.toMatch(/interface PracticeSessionReport/);
  expect(globalClientSource).not.toContain('"/sales-trainer/journey"');
  expect(clientDomainsSource).not.toContain("getReport: async");
  expect(clientDomainsSource).not.toContain("/practice/sessions/${sessionId}/report");
  ```

- [x] **Step 3: Run Red and record only target failures**

  Run backend from `backend/` and frontend from `web/`. Expected: existing behavior/inventory assertions
  pass; target AST/locality assertions fail because the authority still resides in global/ORM files.

- [x] **Step 4: Save exact baselines and affected selection**

  Record `31 passed`, `39 passed`, frontend 6 files / `91 passed`, CodeGraph impact counts, 224 model
  compatibility importers and historical co-change values in implementation notes.

- [x] **Step 5: Commit executable Gate 5 baseline**

  Commit only tests/task evidence as `test(architecture): freeze gate 5 locality contracts`.

### Task 2: Split the physical ORM registry without schema drift

**Files:**
- Create: `backend/src/common/db/model_registry/{__init__,base,enums,identity,governance,training,evaluation,platform,knowledge}.py`
- Modify: `backend/src/common/db/models.py`
- Modify: `backend/alembic/env.py` only if an explicit registry import is required; external metadata symbol stays `Base.metadata`.
- Test: `backend/tests/unit/test_gate5_locality_contracts.py`
- Test: `backend/tests/unit/test_models.py`

**Interfaces:**
- Consumes: frozen symbol and metadata snapshot from Task 1.
- Produces: identity-preserving `common.db.models` compatibility registry and owner-specific model imports.

- [x] **Step 1: Move `Base`, JSONB helper and enums**

  `base.py` owns the only `DeclarativeBase`; `enums.py` imports no entity Module. No second metadata object is
  allowed.

- [x] **Step 2: Move entity groups without rewriting declarations**

  Copy declarations byte-for-byte except imports. Keep every `__tablename__`, SQL type, nullable/default,
  FK, index, constraint and string relationship unchanged. Cross-group relationships use existing string
  names and never import another entity only to satisfy typing.

- [x] **Step 3: Build the ordered registry and compatibility façade**

  `model_registry/__init__.py` imports every group and defines explicit `__all__`; `models.py` re-exports the
  same objects and preserve compatibility-qualified names. Assert, for example:

  ```python
  assert common.db.models.User is common.db.model_registry.identity.User
  assert common.db.models.ComprehensiveReport is common.db.model_registry.evaluation.ComprehensiveReport
  ```

- [x] **Step 4: Prove import-order and metadata parity**

  Run fresh interpreter subprocesses importing `models`, group modules and Alembic env in different orders.
  Compare the Task 1 snapshot, run SQLite `create_all/drop_all`, and run Alembic metadata comparison against
  the repository head; expected schema operations list is empty.

- [x] **Step 5: Run broad model consumers**

  Run model, auth, config, session, evaluation, knowledge and architecture suites selected by CodeGraph;
  run full Ruff and mypy for all moved files.

- [x] **Step 6: Commit physical registry**

  Commit as `refactor(db): split shared model registry`.

### Task 3: Introduce immutable Journey read projections

**Files:**
- Create: `backend/src/sales_trainer/services/journey_read_repository.py`
- Create: `backend/src/sales_trainer/services/journey_sqlalchemy_adapter.py`
- Create: `backend/src/sales_trainer/services/training_journey_projection.py`
- Modify: `backend/src/sales_trainer/services/training_journey_service.py`
- Test: `backend/tests/unit/test_sales_trainer_training_journey_service.py`
- Test: `backend/tests/unit/test_gate5_locality_contracts.py`

**Interfaces:**
- Consumes: `JourneyLearnerProjection`, `JourneyRoleplaySessionProjection`, immutable query DTOs and existing
  RuntimeOutcome projections.
- Produces: `JourneyReadRepository` and `TrainingJourneyProjection`; public service signatures and payloads
  remain unchanged.

- [x] **Step 1: Add failing repository contract tests**

  Cover learner found/missing, admin department/role scope, inactive learner, roleplay outcome revision scope,
  frozen session fields and deterministic ordering. Assert returned dataclasses are frozen and contain no ORM.

- [x] **Step 2: Implement the SQLAlchemy adapter**

  Import owner-specific registry models, execute async `select`, map rows immediately and return tuples/page
  DTOs. The adapter owns query details; it does not decide Journey stage or next action.

- [x] **Step 3: Add failing projection differential tests**

  Feed frozen outcome fixtures for audio, quiz, learning topic, AI coach, realtime and regrade. Compare complete
  payloads with the current service for success, failure, remediation, manual review, transient/terminal error,
  legacy snapshot and missing config.

- [x] **Step 4: Move deterministic Journey policy behind one projection interface**

  Move module payload, stage, completion, next action, retraining target, progress, diagnostics, capability,
  learner-level and analytics pure logic. Keep DB/table-existence and operation-log reads in orchestration or
  adapters. `TrainingJourneyService` constructor accepts optional repository/projection and defaults to the SQL
  adapter plus production projection.

- [x] **Step 5: Remove foreign ORM imports and verify callers**

  The service may use immutable DTOs only. Run CodeGraph callers/impact, Journey/learner-access/API/seed tests,
  architecture guard, Ruff and mypy.

- [x] **Step 6: Commit Journey locality**

  Commit as `refactor(journey): project training state behind read ports`.

### Task 4: Extract the Readiness Dossier projection Module

**Files:**
- Create: `backend/src/sales_trainer/services/readiness_dossier_projection.py`
- Modify: `backend/src/sales_trainer/services/readiness_dossier_service.py`
- Modify: `backend/src/sales_trainer/services/journey_read_repository.py`
- Modify: `backend/src/sales_trainer/services/journey_sqlalchemy_adapter.py`
- Test: `backend/tests/unit/test_sales_trainer_readiness_dossier_service.py`
- Test: `backend/tests/contract/test_sales_trainer_phase2_contract.py`

**Interfaces:**
- Consumes: immutable learner projection, Journey payload, record projections and audit log payloads.
- Produces: pure `dossier`, `workbench`, approval eligibility/default selection and blocked-Journey outputs.

- [x] **Step 1: Add pure projection characterization tests**

  Cover evidence aggregation/dedup/order, module summaries, competencies, status precedence, config blocker,
  retraining before/after comparison, realtime gate, next actions, workbench grouping and redaction.

- [x] **Step 2: Move deterministic rules without changing payloads**

  Projection input is a frozen source DTO or recursively immutable mapping. Output mapping is freshly allocated;
  the Module has no DB, clock, FastAPI, ORM or operation-log import. Inject `generated_at` rather than reading time.

- [x] **Step 3: Keep transaction and permissions in application orchestration**

  Service loads viewer-scoped learner, Journey, records and logs; validates requested evidence/capabilities;
  writes one operation log and commits once. Approval remains fail closed and unknown IDs return the same codes.

- [x] **Step 4: Remove direct `User` ORM import and run differential matrix**

  Use the Journey repository for learner/page lookup. Run Dossier, phase2 contract, training records, Journey API,
  RBAC, audit and architecture tests; run Ruff/mypy.

- [x] **Step 5: Commit Dossier locality**

  Commit as `refactor(readiness): isolate dossier projection policy`.

### Task 5: Move frontend DTO and session transport authority to domain Modules

**Files:**
- Create: `web/src/lib/api/types/training-journey.ts`
- Create: `web/src/lib/api/types/session-report.ts`
- Create: `web/src/lib/api/domains/sessions.ts`
- Modify: `web/src/lib/api/types.ts`
- Modify: `web/src/lib/api/types/sales-trainer.ts`
- Modify: `web/src/lib/api/domains/sales-trainer.ts`
- Modify: `web/src/lib/api/client-domains.ts`
- Modify: Gate 5 Journey/Readiness/report consumers and their tests.
- Test: `web/src/lib/api/gate5-locality.test.ts`
- Test: `web/src/lib/api/client-domains.test.ts`
- Test: `web/src/lib/api/sales-trainer.test.ts`

**Interfaces:**
- Consumes: unchanged backend snake_case contracts and shared `ApiRequest`/upload/stream seams.
- Produces: real domain type authorities and `createSessionsDomain`; global barrels remain compatibility exports.

- [x] **Step 1: Move complete type dependency closures**

  Move Journey/Readiness types together so no domain type file imports the global barrel. Move session report,
  replay, highlights, trends, supervisor and related nested types as one closure. `types.ts` explicitly re-exports
  those symbols for compatibility and does not redeclare them.

- [x] **Step 2: Extract the sessions domain builder**

  Move get report/replay/history/highlight/media methods from `client-domains.ts` to `domains/sessions.ts` without
  changing path, timeout, headers, loopback retry or error normalization. `client-domains.ts` re-exports the builder.

- [x] **Step 3: Migrate Gate 5 consumers to domain type imports**

  Journey/Readiness/report pages, hooks, ViewModels and tests import from the two new domain type Modules. Pages
  continue calling `api` from `client.ts`; direct domain-builder imports in UI remain forbidden.

- [x] **Step 4: Prove compatibility and locality**

  Run type-identity compile fixtures for both old/new import paths, domain request contract tests, strict typecheck,
  target ESLint and focused Vitest. The Task 1 locality Red tests must turn Green.

- [x] **Step 5: Commit frontend domain authority**

  Commit as `refactor(web): localize journey and report contracts`.

### Task 6: Extract report/readiness ViewModels and actions

**Files:**
- Create: `web/src/app/(user)/practice/[sessionId]/report/report-view-model.ts`
- Create: `web/src/app/(user)/practice/[sessionId]/report/report-view-model.test.ts`
- Create: `web/src/app/(user)/practice/[sessionId]/report/report-actions.ts`
- Create: `web/src/app/(user)/practice/[sessionId]/report/report-actions.test.ts`
- Modify: report `page.tsx` and `use-session-report-data.ts`
- Create: `web/src/app/admin/sales-trainer/readiness/[learnerId]/readiness-view-model.ts`
- Create: matching readiness ViewModel test.
- Modify: readiness detail `page.tsx` and test.

**Interfaces:**
- Consumes: domain DTOs from Task 5.
- Produces: user-language ViewModels, action descriptors and existing loading/retry state.

- [x] **Step 1: Characterize mapping and action behavior**

  Test score/status labels, evidence completeness/degradation, claim truth, Presentation page replay/retry,
  retraining task link, supervisor decisions/calibration, dossier evidence/result/retraining labels and unknown enum
  redaction. Test URL encoding with IDs containing reserved characters.

- [x] **Step 2: Implement pure ViewModel mappers**

  Mappers accept DTO + viewer capability and return render-ready labels/tone/sections/actions. They never call
  `api`, router, storage or React hooks and never expose raw internal codes as the fallback label.

- [x] **Step 3: Centralize side-effect actions**

  `report-actions.ts` owns URLSearchParams, retraining session-link clear/read/write and route intent payloads.
  Hooks/pages invoke action descriptors; no duplicate URL construction remains in JSX handlers.

- [x] **Step 4: Simplify route roots without redesign**

  Keep the existing JSX hierarchy and copy. Move only interpretation/action knowledge. Existing loading, empty,
  error, partial, permission, submitting and retry states remain visible and route tests stay behavior-equivalent.

- [x] **Step 5: Verify frontend locality**

  Run new pure tests, existing report/readiness/Journey route tests, typecheck, lint, full Vitest and CodeGraph
  affected selection.

- [x] **Step 6: Commit route locality**

  Commit as `refactor(report): isolate view models and actions`.

### Task 7: Codify Gate 5 architecture and executable knowledge

**Files:**
- Create: `.trellis/spec/backend/training-locality-and-model-registry.md`
- Create: `.trellis/spec/frontend/domain-locality-and-report-view-models.md`
- Modify: both Trellis indexes.
- Modify: `docs/architecture/module-dependency-policy.yaml` only if actual edges disappeared.
- Modify: `docs/architecture.md`, design, ADR, roadmap and this plan.
- Modify: Gate 5 task notes/PRD.

**Interfaces:**
- Consumes: final code graph, import inventory, metadata parity and co-change baseline.
- Produces: seven-section executable contracts and truthful `implementation complete / closure pending` state.

- [x] **Step 1: Run post-change CodeGraph impact/affected**

  Sync CodeGraph, capture changed dependency graph/SCC, model/global-barrel consumers, hotspot LOC and affected tests.

- [x] **Step 2: Write backend and frontend seven-section specs**

  Include Scope/Trigger, Signatures, Contracts, Validation/Error Matrix, Good/Base/Bad, Tests Required and Wrong vs
  Correct. Record model import identity, metadata registration order, projection immutability, UI façade rule and
  Gate 6 retirement conditions.

- [x] **Step 3: Run the design-artifact audit until zero**

  Audit PRD/plan/spec/research/ADR consistency, file existence, interface names, test commands and rollback claims.
  Fix every hard/advisory mismatch before starting closure.

- [x] **Step 4: Commit executable knowledge**

  Commit as `docs(architecture): codify gate 5 locality`.

### Task 8: Independent audit, canonical gate and Trellis closure

**Files:**
- Modify: Gate 5 task evidence and authority docs with exact final counts.
- Modify: Brooks history/report and Trellis check report.

**Interfaces:**
- Consumes: all Gate 5 slices and unique canonical quality gate.
- Produces: finding=0, clean-start gate evidence, commits, archive and journal.

- [ ] **Step 1: Run whole-branch Brooks Architecture Audit**

  Re-evaluate Depth, deletion test, dependency direction, compatibility registries, hidden ORM leakage, frontend
  locality, testability and remaining SCC. Fix all findings and rerun until Critical/Warning/Suggestion=0.

- [ ] **Step 2: Run independent Trellis check**

  Verify PRD/spec/data flow/reuse, metadata/schema parity, OpenAPI, Ruff, full mypy, typecheck, lint, focused and
  affected tests. Fix/repeat until blocking finding=0.

- [ ] **Step 3: Run one clean-start canonical gate**

  From repo root run `bash scripts/critical-quality-gate.sh` and wait for natural exit. Preserve backend, Vitest,
  every Playwright family, selected backend, changed coverage and final-line evidence. Diagnose failures without
  skips or weakened assertions.

- [ ] **Step 4: Close and archive**

  Mark all PRD/plan criteria only after evidence, validate JSONL, commit excluding the readiness document, use
  `trellis-update-spec`, `trellis-finish-work`, archive and journal. Continue directly to Gate 6.

---

## Verification matrix

```bash
cd backend
.venv/bin/python -m pytest \
  tests/unit/test_gate5_locality_contracts.py \
  tests/unit/test_models.py \
  tests/unit/test_sales_trainer_training_journey_service.py \
  tests/unit/test_sales_trainer_readiness_dossier_service.py \
  tests/contract/test_sales_trainer_phase2_contract.py --no-cov -q
.venv/bin/python scripts/architecture_dependency_guard.py --check
.venv/bin/ruff check src tests
.venv/bin/mypy src

cd ../web
npx tsc --noEmit
npm run lint
npm test -- --run \
  'src/lib/api/gate5-locality.test.ts' \
  'src/lib/api/client-domains.test.ts' \
  'src/lib/api/sales-trainer.test.ts' \
  'src/app/(user)/practice/[sessionId]/report' \
  'src/app/admin/sales-trainer/readiness' \
  'src/app/(dashboard)/sales-trainer'

cd ..
python3 ./.trellis/scripts/task.py validate \
  .trellis/tasks/07-11-modular-monolith-2-gate-5
git diff --check
bash scripts/critical-quality-gate.sh
```

Expected final line: `Critical quality gate passed` and natural exit 0.
