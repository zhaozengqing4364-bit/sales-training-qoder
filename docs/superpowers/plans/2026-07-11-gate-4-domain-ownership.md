# Gate 4 Domain Ownership Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: execute this plan inline with
> `superpowers:executing-plans`; the user explicitly prohibited subagents. Steps use checkbox
> (`- [ ]`) syntax for tracking.

**Goal:** Neutralize Roleplay Contract/Situation Pack and ConfigBundle ownership, introduce
Evaluation Evidence/Scenario ports, and remove Evaluation's concrete scenario/Admin reverse imports
without changing external behavior.

**Architecture:** Use Strangler Fig and Dependency Inversion. New `roleplay` and
`configuration_governance` packages own deep domain interfaces; Curriculum/Admin become adapters,
while Evaluation owns the ports it consumes. Golden/differential tests precede migration, one
constructor-time flag selects each authority, and Gate 6 removes proven-unused compatibility paths.

**Tech Stack:** Python 3.12, FastAPI, Pydantic 2, SQLAlchemy 2 async, pytest, Ruff, mypy, YAML AST
architecture guard, Trellis, CodeGraph.

## Global Constraints

- Preserve REST/OpenAPI, WebSocket event/close-code/binary frame, auth/permission, RuntimeGate,
  frozen snapshots, KB fail-closed, epoch, score and report contracts.
- Never recompute persisted Roleplay hashes or historical reports.
- Missing Evidence is non-evaluable; it is never converted to a zero score or verified claim.
- No new external dependency, migration, microservice, production write, push or paid Provider call.
- Every temporary edge/flag has owner, reason, retire condition and 2026-10-31 expiry at latest.
- Preserve and never stage the user's dirty readiness plan.

---

## File ownership map

### New neutral Roleplay bounded context

- `backend/src/roleplay/contracts.py`: schema constants, canonical hashing, compliance decision DTO/API.
- `backend/src/roleplay/situation_packs.py`: immutable Situation Pack DTO, canonical hash, source port and
  bundled source.
- `backend/src/roleplay/compiler.py`: compiler, freeze, disclosure transition and turn-context APIs.
- `backend/src/roleplay/rollout.py`: constructor-time authority selection and named Legacy rollback.
- `backend/src/roleplay/__init__.py`: deliberately small public API.
- Existing `common/roleplay_contracts.py` and
  `curriculum_practice/services/roleplay_contracts.py`: compatibility adapters only by Gate 4 end.

### New Configuration Governance bounded context

- `backend/src/configuration_governance/contracts.py`: bundle/version/lifecycle immutable DTOs and ports.
- `backend/src/configuration_governance/lifecycle.py`: `ConfigBundleLifecycleService` orchestration and
  audit decisions.
- `backend/src/configuration_governance/sqlalchemy_adapter.py`: existing async SQL/BusinessRule adapter.
- `backend/src/configuration_governance/rollout.py`: authority factory and Legacy rollback selector.
- `backend/src/admin/config_bundles/composition.py`: admin inventory and projection adapter wiring.
- Existing admin lifecycle/adapters paths: forwarding compatibility only.

### Evaluation ports and adapters

- `backend/src/evaluation/ports/evidence.py`: `SessionEvidence` and `SessionEvidencePort`.
- `backend/src/evaluation/ports/scenario.py`: scenario input/result, port, factory and frozen registry.
- `backend/src/evaluation/adapters/sql_session_evidence.py`: frozen SQL evidence projection.
- `backend/src/presentation_coach/services/presentation_evaluation_adapter.py`: Presentation adapter.
- `backend/src/evaluation/composition.py`: configured port access without importing scenario packages.
- `backend/src/scenario_composition.py`: application-root concrete registration.

---

### Task 1: Freeze Gate 4 behavior and dependency truth

**Files:**
- Create: `backend/tests/unit/test_gate4_domain_ownership.py`
- Create: `backend/tests/golden/roleplay/gate4-roleplay-contracts.json`
- Create: `backend/tests/golden/evaluation/gate4-scenario-reports.json`
- Modify: `.trellis/tasks/07-11-modular-monolith-2-gate-4/implementation-notes.md`

**Interfaces:**
- Consumes: current Roleplay compiler/hash, ConfigBundle lifecycle and report services.
- Produces: byte-stable oracle helpers and AST edge assertions used by every later task.

- [x] **Step 1: Write Golden capture tests before moving code**

  Add parametrized fixtures for published and legacy Roleplay contracts, Situation Pack hashes,
  initial/triggered disclosure states, compliance allow/warn/block decisions, Sales report and
  Presentation report. Assert compact sorted JSON or complete mapping equality, not selected fields.

- [x] **Step 2: Write architecture Red tests**

  Use `collect_edges()` to assert the desired final absence of:

  ```python
  forbidden = {
      ("evaluation", "admin"),
      ("evaluation", "curriculum_practice"),
      ("evaluation", "presentation_coach"),
      ("evaluation", "sales_bot"),
      ("curriculum_practice", "admin"),
  }
  assert forbidden.isdisjoint(collect_edges(SRC_ROOT, packages))
  ```

  Verify this test initially fails and preserve the failure in implementation notes.

- [x] **Step 3: Run the immutable baseline**

  Run the existing Roleplay, ConfigBundle, comprehensive/presentation report and architecture tests.
  Expected: existing behavior green; new final-edge test Red only.

- [x] **Step 4: Commit the executable baseline**

  Commit fixtures/tests/notes as `test(architecture): freeze gate 4 ownership contracts`.

### Task 2: Establish neutral Roleplay primitives and Situation Pack contract

**Files:**
- Create: `backend/src/roleplay/__init__.py`
- Create: `backend/src/roleplay/contracts.py`
- Create: `backend/src/roleplay/situation_packs.py`
- Modify: `backend/src/common/roleplay_contracts.py`
- Modify: `backend/src/common/business_rules/defaults.py`
- Modify: `backend/src/curriculum_practice/services/roleplay/situation_pack_dto.py`
- Modify: `backend/src/curriculum_practice/services/roleplay/situation_pack_hasher.py`
- Test: `backend/tests/unit/test_roleplay_contracts.py`
- Test: `backend/tests/unit/test_situation_pack_dual_read.py`

**Interfaces:**
- Produces:
  - `roleplay_contract_hash(payload: object) -> str`
  - `RoleplayComplianceDecision.as_dict() -> dict[str, object]`
  - `check_roleplay_output(...) -> dict[str, object]` (compatibility public surface)
  - `SituationPackSnapshot.from_ruleset_entry(...)`
  - `situation_pack_content_hash(snapshot) -> str`
  - `SituationPackPort.get_published(code)`
- Compatibility paths return the same dict shapes as before.

- [x] **Step 1: Write import-boundary and parity Red tests**

  Assert the new package exposes immutable DTOs, imports no protected domain, and old/new hash plus
  decision output are exactly equal across the Golden fixture matrix.

- [x] **Step 2: Implement pure domain primitives**

  Move the algorithm and the actual Roleplay bundled defaults to `roleplay`; keep public dict adapters
  so callers do not receive a response-shape change. Volatile-field lists and JSON serialization bytes
  must be copied exactly from the baseline.

- [x] **Step 3: Convert old locations to forwarding compatibility**

  Old modules may re-export but may not contain a second decision implementation. Mark compatibility
  with owner `platform-architecture`, retire condition `Gate 6 consumer inventory is empty`, expiry
  `2026-10-31`.

- [x] **Step 4: Run parity, hash and architecture checks**

  Run focused tests, Ruff for touched files, mypy for `roleplay`, and architecture guard. Expected:
  Golden hashes unchanged and no new SCC.

- [x] **Step 5: Commit**

  Commit as `refactor(roleplay): establish neutral contract primitives`.

### Task 3: Move compiler, disclosure and turn context behind neutral ports

**Files:**
- Create: `backend/src/roleplay/compiler.py`
- Create: `backend/src/roleplay/rollout.py`
- Create: `backend/src/curriculum_practice/services/roleplay/curriculum_adapter.py`
- Modify: `backend/src/common/config.py`
- Modify: `backend/src/common/conversation/replay.py`
- Modify: `backend/src/curriculum_practice/api.py`
- Modify: `backend/src/curriculum_practice/services/practice_report_contributor.py`
- Modify: `backend/src/curriculum_practice/services/published_asset_refs.py`
- Modify: `backend/src/curriculum_practice/services/publishing_gates.py`
- Modify: `backend/src/curriculum_practice/services/roleplay_contracts.py`
- Modify: `backend/src/curriculum_practice/services/runtime_dossier.py`
- Modify: `backend/src/curriculum_practice/services/runtime_gate_contributor.py`
- Modify: `backend/src/curriculum_practice/services/snapshots.py`
- Modify: `backend/src/curriculum_practice/services/support_runtime_contributor.py`
- Modify: `backend/src/evaluation/services/roleplay_contract_eval.py`
- Modify: `backend/src/sales_bot/services/it_leader_roleplay_v1.py`
- Modify: `backend/src/sales_bot/services/roleplay_compliance_checker.py`
- Modify: `backend/src/sales_bot/services/voice_runtime_policy.py`
- Modify: `backend/src/sales_bot/websocket/components/stepfun_roleplay_runtime_helpers.py`
- Modify: `backend/src/sales_bot/websocket/stepfun_realtime_policy.py`
- Modify: `backend/src/sales_bot/websocket/stepfun_realtime_upstream.py`
- Test: `backend/tests/unit/test_roleplay_contracts.py`
- Test: `backend/tests/evaluation/test_roleplay_contract_eval.py`
- Test: realtime Roleplay/Golden suites selected by CodeGraph impact.

**Interfaces:**
- `RoleplayContractCompiler(reference_reader=None, situation_packs=None)` remains source compatible.
- Neutral `RoleplayReferenceReader` returns mappings; neutral `PublishedAssetReference` and
  `RoleplayCompileFailure` do not expose Curriculum Pydantic models.
- `select_roleplay_authority(enabled: bool)` returns exactly one Neutral or Legacy compiler factory.

- [x] **Step 1: Write compiler/differential Red tests**

  Cover template/persona/legacy compilation, frozen refs, missing/unpublished pack, hash mismatch,
  version mismatch, prompt conflict, visible/hidden validation, disclosure triggers and runtime turn
  context. Instantiate both authorities with the same fake ports and assert full output equality.

- [x] **Step 2: Extract the compiler as a deep module**

  Keep curriculum candidate/GateResult conversion in the Curriculum adapter. The neutral compiler
  accepts mappings/Protocols only and owns no SQLAlchemy session or HTTP concept.

- [x] **Step 3: Route production factories through one constructor-time flag**

  `ROLEPLAY_NEUTRAL_OWNER_ENABLED=true` is read once per compiler/factory construction. The false path
  is explicitly named Legacy and remains behaviorally frozen; diagnostics expose only selected path and
  schema version, never prompts or hidden payload.

- [x] **Step 4: Migrate Evaluation and runtime consumers**

  Evaluation imports neutral Roleplay public API. Sales/Presentation runtime helpers consume the
  neutral compliance/turn-context contract. Curriculum keeps asset adapters and publishing gates.

- [x] **Step 5: Run focused and affected matrices**

  Use CodeGraph impact before/after; run all affected Roleplay/runtime/reconnect/report tests, Ruff,
  mypy and architecture guard. Expected: `evaluation -> curriculum_practice` disappears.

- [x] **Step 6: Commit**

  Commit as `refactor(roleplay): move compiler and runtime authority`.

### Task 4: Move ConfigBundle lifecycle to Configuration Governance

**Files:**
- Create: `backend/src/configuration_governance/__init__.py`
- Create: `backend/src/configuration_governance/contracts.py`
- Create: `backend/src/configuration_governance/lifecycle.py`
- Create: `backend/src/configuration_governance/sqlalchemy_adapter.py`
- Create: `backend/src/configuration_governance/rollout.py`
- Create: `backend/src/admin/config_bundles/composition.py`
- Create: `backend/src/curriculum_practice/services/config_version_binding.py`
- Modify: `backend/src/admin/api/config_bundles.py`
- Modify: `backend/src/admin/config_bundles/lifecycle.py`
- Modify: `backend/src/admin/config_bundles/adapters.py`
- Modify: `backend/src/curriculum_practice/services/practice_template_publish_gate_factory.py`
- Modify: `backend/src/common/config.py`
- Test: ConfigBundle unit/integration/contract suites.

**Interfaces:**
- `ConfigBundleLifecycleService` receives session-bound repository, adapter registry and
  projection-sync capabilities; the core never accepts an ORM row.
- Lifecycle methods preserve current keyword signatures and `ConfigLifecycleResult` response semantics.
- SQL adapter owns AsyncSession/ORM mapping; core lifecycle decisions use immutable snapshots/ports.

- [ ] **Step 1: Write lifecycle/HTTP differential Red tests**

  Exercise list/versions, draft, validate, preview, publish, rollback, disable, not-found, schema-invalid,
  audit before/after/reason/trace and Situation Pack projection success/failure. Assert API status/body and
  database rows exactly match Legacy.

- [ ] **Step 2: Implement contracts and lifecycle orchestration**

  Preserve caller-owned commit/rollback. Projection failure remains observable in the lifecycle result;
  no network I/O is introduced inside the transaction.

- [ ] **Step 3: Make Admin a delivery/composition adapter**

  Admin permission dependencies, request validation, response mapping and transaction control remain;
  domain transitions move to Configuration Governance. Existing import paths forward only.

  Curriculum resolves only the immutable active `bundle_id/version_id` projection through
  `curriculum_practice.services.config_version_binding`; it no longer imports Admin lifecycle.

- [ ] **Step 4: Add default-on rollback selection**

  `CONFIGURATION_GOVERNANCE_ENABLED=true` selects one lifecycle at construction. False selects named
  Legacy. No request may invoke both or double-write audit/version rows.

- [ ] **Step 5: Run ConfigBundle matrix and static checks**

  Run ConfigBundle/Situation Pack/API contract tests, Ruff, mypy and architecture guard.

- [ ] **Step 6: Commit**

  Commit as `refactor(config): neutralize bundle lifecycle ownership`.

### Task 5: Introduce Evaluation Evidence and Scenario ports

**Files:**
- Create: `backend/src/evaluation/ports/__init__.py`
- Create: `backend/src/evaluation/ports/evidence.py`
- Create: `backend/src/evaluation/ports/scenario.py`
- Create: `backend/src/evaluation/adapters/sql_session_evidence.py`
- Create: `backend/src/evaluation/adapters/config_binding.py`
- Create: `backend/src/evaluation/composition.py`
- Create: `backend/src/presentation_coach/services/presentation_evaluation_adapter.py`
- Create: `backend/src/scenario_composition.py`
- Modify: `backend/src/app_factory.py`
- Modify: `backend/src/evaluation/services/comprehensive_report.py`
- Modify: `backend/src/evaluation/services/evaluation_run_service.py`
- Modify: `backend/src/evaluation/api.py`
- Modify: `backend/src/presentation_coach/services/presentation_report_service.py`
- Modify: `backend/src/router_registry.py`
- Test: Evaluation and Presentation report unit/integration/contract suites.

**Interfaces:**
- `SessionEvidence` contains immutable frozen snapshots, transcript/evidence references and scenario key;
  raw ORM rows are not exposed.
- `EvaluationScenarioRegistry.register(scenario_type, factory)` rejects duplicates and freezes before
  request handling; the factory receives the request-scoped DB capability and creates one adapter.
- `ComprehensiveReportService` receives ports or the frozen configured registry; it never imports a
  concrete scenario.

- [ ] **Step 1: Write port and failure-matrix Red tests**

  Prove duplicate/late registration rejection, unknown scenario fail-closed, missing transcript/
  insufficient evidence non-evaluable, frozen snapshot use, and fake scenario extensibility without a
  Sales/Evaluation code edit.

- [ ] **Step 2: Implement immutable ports and SQL projection**

  Read persisted ConversationMessage first. Legacy in-memory Sales context, if still required by a
  compatibility test, is supplied by a Sales adapter at root rather than imported by Evaluation.

- [ ] **Step 3: Implement Presentation adapter and root wiring**

  Presentation maps its deterministic review to `EvaluationScenarioResult`; Evaluation maps that result
  once to the existing `ComprehensiveReport` and remains the report persistence single writer.

- [ ] **Step 4: Remove concrete Evaluation imports**

  Replace Admin lifecycle lookup with an Evaluation-owned immutable config-binding projection. Replace
  Curriculum Roleplay import with neutral Roleplay. Remove Presentation and Sales implementation imports.
  Mount `admin.api.scoring_rulesets` directly from the root router registry at the unchanged
  `/api/v1/admin/scoring-rulesets` path instead of nesting the Admin router inside Evaluation.

- [ ] **Step 5: Run differential and idempotency tests**

  Compare complete Sales/Presentation report payloads, DB writes and second-run behavior. Run reconnect
  and report-trigger tests to prove no duplicate evaluation/report.

- [ ] **Step 6: Commit**

  Commit as `refactor(evaluation): consume evidence and scenario ports`.

### Task 6: Move reusable realtime helpers behind neutral ownership seams

**Files:**
- Create: `backend/src/training_runtime/realtime/events.py`
- Create: `backend/src/training_runtime/realtime/text_payloads.py`
- Create: `backend/src/training_runtime/realtime/message_persistence.py`
- Modify: `backend/src/sales_bot/websocket/components/stepfun_event_payloads.py`
- Modify: `backend/src/sales_bot/websocket/components/stepfun_helpers.py`
- Modify: `backend/src/sales_bot/websocket/components/stepfun_message_helpers.py`
- Modify: `backend/src/presentation_coach/websocket/presentation_stepfun_realtime_handler.py`
- Modify: `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
- Test: Gate 2/3 Golden differential, Sales 2x2 and Presentation 2x2x2 matrices.

**Interfaces:**
- Neutral helpers accept explicit message/evidence ports and return immutable command/result DTOs.
- Sales-only stage/scoring/objection behavior remains in Sales.
- Presentation has no direct dependency on Sales message, prompt, Roleplay or report implementation;
  the remaining shared-handler inheritance is named Gate 6 compatibility only.

- [ ] **Step 1: Write ownership and differential Red tests**

  Assert Presentation protected imports are reduced to the explicitly retained Gate 6 handler seam and
  full wire/snapshot/persistence outputs remain equal.

- [ ] **Step 2: Move only scenario-neutral helpers**

  Preserve function names and payload normalization. Do not move Sales stage, fuzzy detection, realtime
  scoring or objection rules.

- [ ] **Step 3: Inject Roleplay/Evaluation capabilities**

  Both scenarios consume neutral contracts; fake/new scenario composition requires no Sales modification.

- [ ] **Step 4: Run realtime regression and static checks**

  Run Golden, reconnect, provider/grounding, report single-writer and architecture tests; run Ruff/mypy.

- [ ] **Step 5: Commit**

  Commit as `refactor(realtime): move shared domain capabilities behind ports`.

### Task 7: Close dependency policy, SCC and executable spec

**Files:**
- Modify: `docs/architecture/module-dependency-policy.yaml`
- Create: `.trellis/spec/backend/domain-ownership-and-evaluation-ports.md`
- Modify: `.trellis/spec/backend/index.md`
- Modify: `docs/architecture.md`
- Modify: ADR/design/roadmap and this plan.
- Test: `backend/tests/unit/test_gate4_domain_ownership.py`
- Test: `backend/tests/unit/test_architecture_dependency_guard.py`

**Interfaces:**
- Policy declares both new packages, stable directions and only observed temporary edges.
- Every exception remains lifecycle-complete and stale entries fail the guard.

- [ ] **Step 1: Run CodeGraph impact and AST inventory**

  Record before/after direct edges, SCC membership, affected symbols/tests and remaining Gate 6
  compatibility consumers in implementation notes.

- [ ] **Step 2: Remove stale policy exceptions**

  Delete the five vanished edges from policy in the same change. Do not add a baseline SCC or allowlist
  to accommodate a new cycle; fix the direction instead.

- [ ] **Step 3: Write the 7-section executable Trellis contract**

  Specify scope, signatures, contracts, error matrix, good/base/bad cases, tests and wrong/correct
  examples for Roleplay, Config Governance and Evaluation ports.

- [ ] **Step 4: Synchronize authority docs truthfully**

  Mark Gate 4 implementation complete only after focused checks and policy evidence are green; leave
  canonical/closure status explicit until Task 8.

- [ ] **Step 5: Run design artifact audit and commit**

  Audit all seven dimensions, fix contradictions, validate Trellis JSONL, run `git diff --check`, then
  commit as `docs(architecture): codify gate 4 domain ownership`.

### Task 8: Independent verification, canonical gate and Trellis closure

**Files:**
- Modify: Task PRD/notes and Gate 4 plan checkboxes.
- Modify: authority docs with exact final evidence.
- Modify: Trellis spec only if verification reveals a durable lesson.

**Interfaces:**
- Consumes every prior task and the unique canonical quality gate.
- Produces review finding=0, clean-start gate evidence, commits, archive and journal.

- [ ] **Step 1: Run whole-branch Brooks Architecture Audit**

  Audit dependency direction, deep-module interfaces, compatibility ownership, hidden coupling and test
  quality. Fix all Critical/Important findings and repeat until zero.

- [ ] **Step 2: Run independent Trellis check**

  Verify PRD/spec/context compliance, cross-layer data flow, reuse, Ruff, mypy, focused tests and
  architecture. Fix/repeat until blocking finding=0.

- [ ] **Step 3: Run one clean-start canonical gate**

  Run `bash scripts/critical-quality-gate.sh` from repository root and wait for natural exit. Preserve
  exact backend/Vitest/Playwright/selected/coverage counts and final line. Diagnose any failure with
  Red → Green → Refactor; never skip or weaken assertions.

- [ ] **Step 4: Close authority documents and Trellis state**

  Check all PRD/plan criteria, record exact evidence, validate JSONL, commit task files excluding the
  user's readiness edit, archive the task and add the journal session. Then continue directly to Gate 5.

---

## Exact verification command matrix

All focused pytest commands run with `--no-cov`; the canonical gate owns fresh branch coverage.
Expected result for every focused command is exit 0 with no newly introduced skip/xfail/retry.

### Task 1

```bash
cd backend
.venv/bin/python -m pytest \
  tests/unit/test_gate4_domain_ownership.py \
  tests/unit/test_roleplay_contracts.py \
  tests/unit/test_config_bundle_roleplay_situation_packs.py \
  tests/unit/evaluation/test_comprehensive_report_service.py \
  tests/unit/test_presentation_report_service.py --no-cov -q
```

The final-edge assertion is expected to fail before implementation; all Golden behavior assertions
must pass.

### Tasks 2–3

```bash
cd backend
.venv/bin/python -m pytest \
  tests/unit/test_roleplay_contracts.py \
  tests/unit/test_situation_pack_dual_read.py \
  tests/unit/test_roleplay_compliance_checker.py \
  tests/evaluation/test_roleplay_contract_eval.py \
  tests/unit/test_stepfun_realtime_upstream.py \
  tests/unit/test_gate4_domain_ownership.py --no-cov -q
.venv/bin/ruff check src/roleplay src/common/roleplay_contracts.py \
  src/curriculum_practice/services/roleplay_contracts.py
.venv/bin/mypy src/roleplay src/curriculum_practice/services/roleplay_contracts.py
```

### Task 4

```bash
cd backend
.venv/bin/python -m pytest \
  tests/unit/test_config_bundle_inventory_facade.py \
  tests/unit/test_config_bundle_roleplay_situation_packs.py \
  tests/unit/test_situation_pack_projection_sync.py \
  tests/integration/test_practice_template_api.py \
  tests/contract/test_admin_governance_contract.py \
  tests/unit/test_gate4_domain_ownership.py --no-cov -q
.venv/bin/ruff check src/configuration_governance src/admin/config_bundles \
  src/admin/api/config_bundles.py src/curriculum_practice/services/config_version_binding.py
.venv/bin/mypy src/configuration_governance src/admin/config_bundles \
  src/curriculum_practice/services/config_version_binding.py
```

### Task 5

```bash
cd backend
.venv/bin/python -m pytest \
  tests/unit/evaluation/test_comprehensive_report_service.py \
  tests/unit/test_presentation_report_service.py \
  tests/integration/test_presentation_report_flow.py \
  tests/unit/test_curriculum_lineage.py \
  tests/integration/test_curriculum_lineage_flow.py \
  tests/integration/test_scoring_rulesets_api.py \
  tests/contract/test_scoring_rulesets_contract.py \
  tests/unit/test_gate4_domain_ownership.py --no-cov -q
.venv/bin/ruff check src/evaluation src/presentation_coach/services/presentation_evaluation_adapter.py \
  src/scenario_composition.py
.venv/bin/mypy src/evaluation src/presentation_coach/services/presentation_evaluation_adapter.py \
  src/scenario_composition.py
```

### Task 6

```bash
cd backend
.venv/bin/python -m pytest \
  tests/unit/test_realtime_session_engine.py \
  tests/unit/test_realtime_provider_contract.py \
  tests/unit/test_stepfun_provider_codec.py \
  tests/unit/test_stepfun_realtime_handler.py \
  tests/unit/test_presentation_stepfun_realtime_handler.py \
  tests/unit/test_presentation_realtime_engine_handler.py \
  tests/unit/test_stepfun_payload_snapshots.py \
  tests/unit/test_gate4_domain_ownership.py --no-cov -q
.venv/bin/ruff check src/training_runtime/realtime src/sales_bot/websocket/components \
  src/presentation_coach/websocket/presentation_stepfun_realtime_handler.py
.venv/bin/mypy src/training_runtime/realtime \
  src/presentation_coach/websocket/presentation_stepfun_realtime_handler.py
```

### Task 7

```bash
cd /home/dev/work/sales-training-qoder
backend/.venv/bin/python -m pytest \
  backend/tests/unit/test_gate4_domain_ownership.py \
  backend/tests/unit/test_architecture_dependency_guard.py --no-cov -q
backend/.venv/bin/python backend/scripts/architecture_dependency_guard.py --check
python3 ./.trellis/scripts/task.py validate \
  .trellis/tasks/07-11-modular-monolith-2-gate-4
git diff --check
```

### Task 8

```bash
cd /home/dev/work/sales-training-qoder
bash scripts/critical-quality-gate.sh
```

Expected final line: `Critical quality gate passed` and natural exit 0.
