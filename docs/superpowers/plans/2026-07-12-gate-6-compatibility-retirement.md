# Gate 6 Compatibility Retirement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` inline. The user explicitly
> prohibits sub-agent dispatch. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Retire consumer-free compatibility surfaces, remove dynamic runtime handler strings and the
Presentation-to-Sales package edge, then close Modular Monolith 2.0 with measured benefit evidence.

**Architecture:** Use consumer-proofed deletion and an application-root composition seam. Scenario plugins return
a closed factory key instead of executable strings; Presentation owns a behavior mixin while the root composes it
with the retained StepFun transport base. Compatibility with active consumers stays explicit and governed.

**Tech Stack:** Python 3.12, FastAPI WebSocket, pytest, mypy, Ruff, AST architecture guards, CodeGraph, Trellis.

## Global Constraints

- No sub-agents, user questions, pushes, deployment, paid-provider call or production-data mutation.
- Preserve REST/WS wire contracts, routes, snapshots, persistence, reconnect and evaluation/report single writer.
- Delete only after production consumer proof; retained rollback/deprecation seams need owner and retire condition.
- Use CodeGraph impact/affected before and after shared-interface changes.
- Preserve the user's dirty `docs/superpowers/plans/2026-07-10-readiness-decision-integrity.md` unchanged.

---

### Task 1: Freeze retirement contracts and benefit baseline

**Files:**
- Create: `backend/tests/unit/test_gate6_compatibility_retirement.py`
- Modify: `.trellis/tasks/07-12-modular-monolith-2-gate-6/implementation-notes.md`
- Modify: `.trellis/tasks/07-12-modular-monolith-2-gate-6/research/compatibility-retirement-inventory.md`

**Interfaces:**
- Consumes: `RuntimeHandlerFactoryKey`, dependency policy and current source tree.
- Produces: AST/import/consumer contracts that fail against the pre-Gate-6 structure.

- [x] **Step 1: Add Red contracts**

  Assert runtime selections have no `handler_factory_path/name`, plugins expose no executable descriptor API,
  Presentation source imports no `sales_bot`, `common.roleplay_contracts` is absent, root factories are exhaustive,
  unknown keys fail closed, model/frontend retain floors do not shrink accidentally, and the graph has at most 51
  edges with no `presentation_coach -> sales_bot`.

- [x] **Step 2: Run Red and record exact failures**

  Run `backend/.venv/bin/python -m pytest backend/tests/unit/test_gate6_compatibility_retirement.py --no-cov -q`.
  Expected failures are the old string fields, inherited import, forwarding module and 52-edge baseline only.

- [x] **Step 3: Save CodeGraph impact and commit**

  Record callers/affected tests for `ScenarioRuntimeHandlerSelection`, `LegacyPresentationStepFunRealtimeHandler`,
  `dispatch_scenario_plugin` and `common.roleplay_contracts`. Commit as
  `test(architecture): freeze gate 6 retirement contracts`.

### Task 2: Replace executable plugin strings with closed root factories

**Files:**
- Modify: `backend/src/training_runtime/plugins.py`
- Modify: `backend/src/training_runtime/__init__.py`
- Modify: `backend/src/websocket_routes.py`
- Modify: `backend/src/sales_bot/websocket/router.py`
- Modify: `backend/tests/unit/test_training_runtime_plugins.py`
- Modify: `backend/tests/unit/test_main_presentation_ws_runtime.py`

**Interfaces:**
- Produces: `RuntimeHandlerFactoryKey` values `SALES_STEPFUN`, `PRESENTATION_LEGACY`,
  `PRESENTATION_STEPFUN_ROLLBACK`, `PRESENTATION_REALTIME_ENGINE`; frozen selection always has one key.
- Consumes: explicit root `Mapping[RuntimeHandlerFactoryKey, Callable[..., object]]`.

- [x] **Step 1: Extend Red for all four selections and unknown key**

  Assert each mode resolves exactly one enum and root instantiation never imports a selection-provided module.

- [x] **Step 2: Delete shallow descriptor methods and string fields**

  Remove `ScenarioPluginEntrypoint`, lifecycle/evidence/report descriptor methods and helper builders. Keep scenario
  dispatch, selection and diagnostics; construct selections with a mandatory closed enum.

- [x] **Step 3: Add explicit root mappings**

  Sales and Presentation roots map known keys to local/imported factories. Reject missing or context-inappropriate
  keys before construction and preserve transcript sink / Engine factory kwargs.

- [x] **Step 4: Run focused Green and commit**

  Run plugin, Sales router and Presentation route tests plus Ruff/mypy for touched modules. Commit as
  `refactor(runtime): close scenario handler factories`.

### Task 3: Retire Presentation-to-Sales inheritance edge

**Files:**
- Create: `backend/src/runtime_composition.py`
- Modify: `backend/src/presentation_coach/websocket/presentation_stepfun_realtime_handler.py`
- Modify: `backend/src/presentation_coach/websocket/presentation_realtime_engine_handler.py`
- Modify: `backend/src/websocket_routes.py`
- Modify: `backend/tests/unit/test_presentation_stepfun_realtime_handler.py`
- Modify: `backend/tests/unit/test_presentation_realtime_engine_handler.py`
- Modify: `backend/tests/contract/test_practice_evidence_contract.py`
- Modify: `docs/architecture/module-dependency-policy.yaml`

**Interfaces:**
- Produces: `PresentationStepFunRuntimeMixin` and root concrete `PresentationStepFunRealtimeAdapter`.
- Produces: root factories for legacy rollback and `PresentationRealtimeEngineHandler(runtime_adapter_factory=...)`.
- Consumes: existing `StepFunRealtimeSharedHandler` only at the root composition module.

- [ ] **Step 1: Add composition and 2x2x2 Red tests**

  Assert Presentation files contain no Sales import, concrete MRO is mixin then shared transport, Engine façade
  requires an injected adapter factory, and every rollout constructs exactly one selected authority.

- [ ] **Step 2: Convert Presentation concrete adapter to behavior mixin**

  Remove the Sales base import, declare only the structural attributes/hooks the mixin consumes under type checking,
  retain wire behavior, and rename the old misleading `Legacy...Handler` surface.

- [ ] **Step 3: Compose at application root and remove policy edge**

  Build the concrete adapter in `runtime_composition.py`, inject it through root factory mappings, then remove only
  `sales_bot` from the Presentation temporary target list after the graph proves the edge absent.

- [ ] **Step 4: Run Golden/affected Green and commit**

  Run Presentation Engine/adapter, StepFun transport/provider/grounding, snapshot, main route, practice evidence,
  architecture guard, Ruff and full mypy. Commit as `refactor(presentation): compose legacy transport at root`.

### Task 4: Delete consumer-free Roleplay forwarding façade

**Files:**
- Delete: `backend/src/common/roleplay_contracts.py`
- Modify: `backend/src/curriculum_practice/services/roleplay_contracts.py`
- Modify: `backend/tests/unit/test_roleplay_contracts.py`
- Modify: `backend/tests/unit/test_gate4_domain_ownership.py`
- Modify: `backend/tests/unit/test_roleplay_observability_contract.py`
- Modify: `backend/tests/unit/test_gate6_compatibility_retirement.py`

**Interfaces:**
- Consumes: canonical `roleplay.contracts` public functions.
- Produces: no `common.roleplay_contracts` module; function identity/hash/Golden output unchanged.

- [ ] **Step 1: Migrate the only production consumer and compatibility tests**

  Import canonical symbols from `roleplay`; replace compatibility identity assertions with absence and parity
  assertions against the owner.

- [ ] **Step 2: Delete forwarding module and run parity**

  Run Roleplay contract, observability, curriculum, Gate 4 and Gate 6 tests. Keep `common -> roleplay` temporary
  target because `common.business_rules.defaults` remains an active source.

- [ ] **Step 3: Commit**

  Commit as `refactor(roleplay): retire common forwarding facade`.

### Task 5: Codify retained seams and measured benefits

**Files:**
- Create: `.trellis/spec/backend/compatibility-retirement-and-root-composition.md`
- Modify: `.trellis/spec/backend/index.md`
- Create: `.trellis/tasks/07-12-modular-monolith-2-gate-6/research/benefit-review.md`
- Modify: `.trellis/tasks/07-12-modular-monolith-2-gate-6/implementation-notes.md`
- Modify: authority architecture/ADR/roadmap documents.

**Interfaces:**
- Produces: seven-section executable spec and a `retired/retained/follow-up` decision table.
- Consumes: final CodeGraph graph, Git co-change baseline, import fan-in and focused timing evidence.

- [ ] **Step 1: Rerun graph, affected, fan-in and co-change measures**

  Record exact before/after edges, SCC, removed symbols, retained importer counts, affected tests and elapsed time.

- [ ] **Step 2: Write the executable spec**

  Include Scope/Trigger, Signatures, Contracts, Validation/Error Matrix, Good/Base/Bad, Tests Required and Wrong vs
  Correct. Encode closed factory and root-only composition constraints.

- [ ] **Step 3: Update authority documents and commit**

  Mark every original Gate 6 item completed, retained with evidence or follow-up decision. Commit as
  `docs(architecture): codify gate 6 retirement`.

### Task 6: Independent audit, canonical gate and closure

**Files:**
- Create: Gate 6 Brooks/Trellis reports under task `research/`.
- Modify: Gate 6 PRD/plan/evidence and authority docs with exact final counts.

**Interfaces:**
- Produces: zero findings, one clean-start canonical result, work commits, task archive and journal.

- [ ] **Step 1: Run Brooks whole-branch audit to 100/100 and zero findings**

  Recheck depth, deletion test, dynamic dispatch, root composition, hidden mixin interface, retained compatibility,
  dependency direction and testability; fix and repeat.

- [ ] **Step 2: Run Trellis check to blocking finding 0**

  Verify PRD/spec/data flow/reuse, Ruff, full mypy, architecture, OpenAPI, TypeScript/ESLint/Vitest, affected backend
  and relevant Playwright paths.

- [ ] **Step 3: Run one clean-start canonical gate**

  Run `bash scripts/critical-quality-gate.sh` from the repository root and wait for natural exit. The required final
  line is `Critical quality gate passed`; no skip/assertion weakening is accepted.

- [ ] **Step 4: Close, archive and journal**

  Write exact evidence, complete all checkboxes, validate JSONL, commit excluding the user readiness document, use
  Trellis update/finish workflows, archive the task and record all Gate 6 work commits.
