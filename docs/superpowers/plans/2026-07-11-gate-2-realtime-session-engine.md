# Gate 2 Realtime Session Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce a neutral, explicit RealtimeSessionEngine and switch Presentation StepFun sessions to a composition façade without changing external realtime behavior or constructing Sales capabilities.

**Architecture:** A neutral `training_runtime.realtime` deep module owns typed Connection, Turn, Grounding and Evidence state plus invariant-checked transitions. Presentation composes that Engine with a compatibility StepFun runtime adapter; the adapter remains responsible for the existing wire protocol until Gate 3, but Presentation mode never constructs Sales capability objects. A server-side flag selects the new façade by default and can atomically roll back to the named compatibility handler.

**Tech Stack:** Python 3.11+, dataclasses, `StrEnum`, FastAPI WebSocket, pytest/pytest-asyncio, existing Redis `SessionStateSnapshot`, existing Trellis/architecture/critical quality gates.

## Global Constraints

- Preserve REST, WebSocket envelope, close codes, binary audio, auth/owner/RuntimeGate, frozen snapshot, KB fail-closed, epoch, scoring and report idempotency contracts.
- Do not call a real or paid Provider; all new tests use fakes and existing local seams.
- Do not add a database migration or a second score/report writer.
- `PRESENTATION_REALTIME_ENGINE_ENABLED=true` is the completion default; `false` is the scenario-wide rollback.
- Snapshot changes are additive and pre-Gate-2 snapshots must restore.
- Presentation production façade must not inherit `StepFunRealtimeSharedHandler` and Presentation mode must not construct SalesStage, FuzzyDetection or RealtimeScoring capability objects.
- Keep Sales construction and behavior unchanged by default.
- Run CodeGraph impact before shared edits and CodeGraph affected after them.
- Preserve the unrelated dirty file `docs/superpowers/plans/2026-07-10-readiness-decision-integrity.md` and never stage it.

---

## File structure

- Create `backend/src/training_runtime/realtime/state.py`: versioned state DTOs, serialization and validation.
- Create `backend/src/training_runtime/realtime/engine.py`: transition authority and Scenario Hook protocol.
- Create `backend/src/training_runtime/realtime/__init__.py`: narrow public barrel.
- Create `backend/src/presentation_coach/websocket/presentation_realtime_engine_handler.py`: production composition façade and Presentation hooks.
- Modify `backend/src/presentation_coach/websocket/presentation_stepfun_realtime_handler.py`: name the compatibility adapter, inject Engine, bridge snapshots/turn/grounding/evidence, remove disable-after-construction.
- Modify `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`: parameterize scenario and Sales capability construction while preserving Sales defaults.
- Modify `backend/src/sales_bot/websocket/stepfun_realtime_state.py`: type disabled capability slots without fabricating objects.
- Modify `backend/src/training_runtime/plugins.py`: scenario flag selection and diagnostics.
- Modify `backend/src/common/config.py`: validated server-side rollout flag.
- Create `backend/tests/fixtures/realtime/golden_conversation_contract_v1.json`: machine-readable contract inventory.
- Create `backend/tests/unit/test_realtime_session_engine.py`: state/transition/snapshot/idempotency tests.
- Create `backend/tests/unit/test_presentation_realtime_engine_handler.py`: façade, differential, rollback and diagnostics tests.
- Modify existing Presentation/plugin/router/Sales tests for the explicit compatibility and production class names.
- Create `.trellis/spec/backend/realtime-session-engine.md`: executable local contract after implementation is verified.
- Update design/ADR/roadmap/architecture docs only with implemented Gate 2 facts.

### Task 1: Freeze the Golden Conversation inventory and typed state

**Files:**
- Create: `backend/tests/fixtures/realtime/golden_conversation_contract_v1.json`
- Create: `backend/src/training_runtime/realtime/state.py`
- Create: `backend/src/training_runtime/realtime/__init__.py`
- Create: `backend/tests/unit/test_realtime_session_engine.py`

**Interfaces:**
- Produces: `ENGINE_STATE_VERSION`, `ConnectionState`, `TurnState`, `GroundingState`, `EvidenceState`, `RealtimeSessionState`, and `RealtimeStateTransitionError`.
- Serialization: every state exposes `to_dict()`; `RealtimeSessionState.from_dict(payload)` rejects unsupported future versions and tolerates absent optional fields from version 1.

- [x] **Step 1: Add the failing inventory and state tests**

Add tests that load the JSON fixture and require these IDs:

```python
REQUIRED_GOLDEN_CONTRACT_IDS = {
    "admission.invalid_session",
    "admission.runtime_gate",
    "admission.unauthorized",
    "admission.owner_scope",
    "conversation.connect_start_text_audio_response_done",
    "transport.binary_audio",
    "transport.timeout_backpressure_degraded",
    "snapshot.frozen_policy_kb_fail_closed",
    "reconnect.epoch_monotonic",
    "evidence.transcript_score_report_idempotent",
    "roleplay.observation_record_only",
    "rollout.single_writer_rollback",
}
```

Also assert default states, round-trip equality, future-version rejection, duplicate evidence-key idempotency, conflicting evidence-key rejection and pending/ack validation.

- [x] **Step 2: Run the tests and verify Red**

Run:

```bash
cd backend && .venv/bin/pytest tests/unit/test_realtime_session_engine.py -q
```

Expected: collection/import failure because `training_runtime.realtime` and the fixture do not exist.

- [x] **Step 3: Implement the minimal typed state**

Use string enums for phases and slots dataclasses. Evidence records persist only a digest and stable metadata, never raw transcript or audio:

```python
@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    evidence_key: str
    evidence_type: str
    turn_number: int
    payload_digest: str

@dataclass(slots=True)
class EvidenceState:
    records: dict[str, EvidenceRecord] = field(default_factory=dict)
    pending_flush_keys: set[str] = field(default_factory=set)
    acknowledged_keys: set[str] = field(default_factory=set)
```

Validate non-empty IDs, non-negative epochs/turns and allowlisted phases. Return deep-copy-safe plain dictionaries from serialization.

- [x] **Step 4: Add the versioned JSON inventory**

Each contract object must contain `id`, `category`, `stable_expectation`, `evidence` and `rollback_relevance`. Do not include secrets, live URLs or mutable generated IDs.

- [x] **Step 5: Run focused tests and static checks**

Run:

```bash
cd backend && .venv/bin/pytest tests/unit/test_realtime_session_engine.py -q
cd backend && .venv/bin/ruff check src/training_runtime/realtime tests/unit/test_realtime_session_engine.py
cd backend && .venv/bin/mypy src/training_runtime/realtime
```

Expected: all pass.

### Task 2: Implement the RealtimeSessionEngine and Scenario Hook seam

**Files:**
- Create: `backend/src/training_runtime/realtime/engine.py`
- Modify: `backend/src/training_runtime/realtime/__init__.py`
- Modify: `backend/tests/unit/test_realtime_session_engine.py`

**Interfaces:**
- Consumes: state DTOs from Task 1.
- Produces: `RealtimeTransition`, `ScenarioTurnHooks`, `NoopScenarioTurnHooks`, `RealtimeSessionEngine`.
- `RealtimeSessionEngine.snapshot() -> dict[str, object]` and `restore(payload) -> None` are the only persistence-facing methods.

- [x] **Step 1: Add failing transition tests**

Cover exact legal and illegal paths:

```python
engine.begin_connection("session-1")
engine.mark_connected()
engine.begin_turn(request_id=1, stream_id="stream-1")
engine.mark_response_started(response_id="response-1")
engine.mark_streaming()
engine.begin_grounding(decision_id="g-1", policy_hash="sha256:policy")
engine.resolve_grounding(outcome="ready", mode="grounded")
engine.record_evidence(
    evidence_key="transcript:1:user",
    evidence_type="transcript",
    turn_number=1,
    payload=b"learner transcript",
)
engine.complete_turn(request_id=1)
engine.begin_close(reason="client_disconnect")
engine.mark_disconnected(reason="client_disconnect")
```

Assert hook event order, active-turn re-entry rejection, stale completion rejection, grounding
resolve-before-prepare rejection, monotonic reconnect epoch and idempotent replay.

- [x] **Step 2: Run the focused tests and verify Red**

Run the same pytest command as Task 1. Expected: missing Engine symbols/tests fail.

- [x] **Step 3: Implement Engine transitions**

Use one mutation boundary that validates, updates state, then invokes the injected hook:

```python
class ScenarioTurnHooks(Protocol):
    scenario_type: str

    def on_transition(self, transition: RealtimeTransition) -> None: ...

class RealtimeSessionEngine:
    def __init__(self, *, scenario_type: str, hooks: ScenarioTurnHooks) -> None:
        if hooks.scenario_type != scenario_type:
            raise ValueError("scenario_hook_mismatch")
        self._state = RealtimeSessionState(scenario_type=scenario_type)
        self._hooks = hooks
```

Every transition includes a stable event name and a post-transition snapshot. Hook failures
must fail visibly in tests; do not swallow them.

- [x] **Step 4: Verify state, type and lint contracts**

Run Task 1 checks plus `python -m compileall -q src/training_runtime/realtime`.

### Task 3: Stop constructing Sales capabilities for Presentation mode

**Files:**
- Modify: `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
- Modify: `backend/src/sales_bot/websocket/stepfun_realtime_state.py`
- Modify: `backend/src/presentation_coach/websocket/presentation_stepfun_realtime_handler.py`
- Modify: `backend/tests/unit/test_presentation_stepfun_realtime_handler.py`
- Modify: `backend/tests/unit/test_stepfun_realtime_handler.py`

**Interfaces:**
- `StepFunRealtimeSharedHandler.__init__(..., scenario: str = "sales", sales_capabilities_enabled: bool = True)` preserves every existing caller.
- `LegacyPresentationStepFunRealtimeHandler` passes `scenario="presentation"` and `sales_capabilities_enabled=False`.
- A temporary backwards import alias may forward the old class name but plugin production selection must not use it.

- [x] **Step 1: Add failing constructor boundary tests**

Patch the three Sales capability constructors and assert none is called for Presentation;
assert all existing Sales defaults remain enabled and typed. Assert Presentation scenario is
correct from the first base constructor call rather than rewritten afterward.

- [x] **Step 2: Run Red tests**

```bash
cd backend && .venv/bin/pytest \
  tests/unit/test_presentation_stepfun_realtime_handler.py \
  tests/unit/test_stepfun_realtime_handler.py -q
```

Expected: capability constructors are currently called before being disabled.

- [x] **Step 3: Split generic and Sales-only initialization**

Keep the default signature compatible and initialize disabled slots without constructing
domain capability objects:

```python
self._sales_stage_enabled = sales_capabilities_enabled
self._sales_stage_capability = (
    SalesStageCapability(self._sales_stage_runtime_config)
    if sales_capabilities_enabled
    else None
)
```

Apply the same rule to fuzzy detection and realtime scoring. Update annotations to optional
and keep every Sales call path guarded by its existing enabled flag.

- [x] **Step 4: Rename the compatibility handler and remove disable-after-construction**

`LegacyPresentationStepFunRealtimeHandler` must call the new constructor mode directly and
must not contain `_disable_sales_capabilities()` or instantiate Sales capability classes.

- [x] **Step 5: Run Presentation and Sales regression tests**

Run the Red set plus:

```bash
cd backend && .venv/bin/pytest \
  tests/integration/test_sales_realtime_reconnect_flow.py \
  tests/integration/test_websocket_status_contract.py -q
```

Expected: all pass.

### Task 4: Compose the Presentation Engine façade and bridge reconnect state

**Files:**
- Create: `backend/src/presentation_coach/websocket/presentation_realtime_engine_handler.py`
- Modify: `backend/src/presentation_coach/websocket/presentation_stepfun_realtime_handler.py`
- Create: `backend/tests/unit/test_presentation_realtime_engine_handler.py`
- Modify: `backend/tests/unit/test_presentation_stepfun_realtime_handler.py`

**Interfaces:**
- Produces: `PresentationScenarioHooks`, `PresentationRealtimeEngineHandler`.
- Façade exposes `handle_connection`, `send_message`, `close`, `sync_lifecycle_transition`,
  `get_runtime_diagnostics`, and stable read-only runtime properties used by SessionManager.
- Compatibility adapter receives `runtime_engine: RealtimeSessionEngine | None` and bridges
  only state observation/snapshot; existing wire/persistence methods remain single-writer.

- [x] **Step 1: Add failing façade and snapshot tests**

Assert:

```python
handler = PresentationRealtimeEngineHandler(runtime_adapter_factory=fake_factory)
assert not isinstance(handler, StepFunRealtimeSharedHandler)
assert handler.engine.state.scenario_type == "presentation"
```

Verify lifecycle delegation, heartbeat/send/close delegation, sanitized diagnostics,
pre-Gate snapshot restoration, Engine snapshot round-trip and epoch agreement with legacy
`reconnect_state.connection_epoch`.

- [x] **Step 2: Implement the composition façade**

The façade owns Engine and adapter exactly once. It must not use a general-purpose
`__getattr__` proxy; expose the small SessionManager surface explicitly so the boundary stays
deep and reviewable.

- [x] **Step 3: Bridge adapter state without dual writes**

Additive snapshot shape:

```python
runtime_state["realtime_engine"] = self._runtime_engine.snapshot()
```

On restore, derive an Engine state from legacy fields when that key is absent. Record only
evidence key/digest metadata. Do not call a repository, score service or report service from
Engine callbacks.

- [x] **Step 4: Bridge turn, grounding and evidence events**

Use request IDs captured before/after existing adapter operations. Completion accepts an
expected request ID so a tool-followup response cannot accidentally complete the next turn.
Audio evidence stores length/digest only. Transcription evidence is recorded after existing
normalization/dedupe and uses the same turn number.

- [x] **Step 5: Run façade, Presentation, snapshot and lifecycle tests**

```bash
cd backend && .venv/bin/pytest \
  tests/unit/test_realtime_session_engine.py \
  tests/unit/test_presentation_realtime_engine_handler.py \
  tests/unit/test_presentation_stepfun_realtime_handler.py \
  tests/unit/test_session_runtime_authority.py \
  tests/integration/test_websocket_status_contract.py -q
```

Expected: all pass with no live Provider.

### Task 5: Wire the rollout flag and prove differential behavior

**Files:**
- Modify: `backend/src/common/config.py`
- Modify: `backend/src/training_runtime/plugins.py`
- Modify: `backend/tests/unit/test_training_runtime_plugins.py`
- Modify: `backend/tests/unit/test_main_presentation_ws_runtime.py`
- Modify: `backend/tests/unit/test_presentation_realtime_engine_handler.py`

**Interfaces:**
- `Settings.PRESENTATION_REALTIME_ENGINE_ENABLED: bool` defaults to `True`.
- `PresentationScenarioPlugin` accepts an injected rollout resolver for deterministic tests.
- Engine selection points to `PresentationRealtimeEngineHandler`; rollback selection points
  to `LegacyPresentationStepFunRealtimeHandler`.

- [x] **Step 1: Add failing rollout tests**

Assert default new-path selection, explicit false rollback, legacy voice mode unaffected,
persisted voice mode still overrides client query, and diagnostics identify both paths.

- [x] **Step 2: Implement flag and plugin selection**

Keep the flag server-side; do not add it to the public frontend feature-flag payload. The
selection must occur before instantiation so one session never constructs both handlers.

- [x] **Step 3: Add the Golden differential test**

Load the versioned fixture, drive the same representative connect/start/text/binary/
transcription/response.done/reconnect sequence through:

1. `LegacyPresentationStepFunRealtimeHandler` with fake StepFun transport; and
2. `PresentationRealtimeEngineHandler` with the same fake adapter collaborators.

Normalize timestamps and generated IDs, then compare ordered event types, stable payload
fields, final legacy snapshot fields, persistence keys/write count and close result. Separately
assert the Engine state contains the expected connection epoch, completed turn, grounding
outcome and deduped evidence keys.

- [x] **Step 4: Run plugin/router/differential tests**

```bash
cd backend && .venv/bin/pytest \
  tests/unit/test_training_runtime_plugins.py \
  tests/unit/test_main_presentation_ws_runtime.py \
  tests/unit/test_presentation_realtime_engine_handler.py -q
```

Expected: all pass; no dual adapter construction.

### Task 6: Verify architecture, document the executable contract and close Gate 2

**Files:**
- Create: `.trellis/spec/backend/realtime-session-engine.md`
- Modify: `.trellis/spec/backend/index.md`
- Modify: `docs/architecture.md`
- Modify: `docs/adr/2026-07-10-modular-monolith-2-ai-native-governance.md`
- Modify: `docs/superpowers/specs/2026-07-10-modular-monolith-2-design.md`
- Modify: `docs/superpowers/plans/2026-07-10-modular-monolith-2-roadmap.md`
- Modify: `docs/architecture/module-dependency-policy.yaml` only if the actual edge set changes.

**Interfaces:**
- Produces an executable seven-section Trellis contract for future Engine/adapter changes.
- Records Gate 2 as complete only after canonical verification succeeds.

- [x] **Step 1: Run CodeGraph sync and affected selection**

```bash
codegraph sync .
codegraph impact RealtimeSessionEngine --depth 3
codegraph impact PresentationRealtimeEngineHandler --depth 3
codegraph affected \
  backend/src/training_runtime/realtime/state.py \
  backend/src/training_runtime/realtime/engine.py \
  backend/src/presentation_coach/websocket/presentation_realtime_engine_handler.py \
  backend/src/presentation_coach/websocket/presentation_stepfun_realtime_handler.py \
  backend/src/sales_bot/websocket/stepfun_realtime_handler.py
```

Run every reported relevant test family in addition to the planned set.

- [x] **Step 2: Run focused quality gates**

```bash
backend/.venv/bin/python backend/scripts/architecture_dependency_guard.py --check
cd backend && .venv/bin/ruff check src tests/unit/test_realtime_session_engine.py tests/unit/test_presentation_realtime_engine_handler.py
cd backend && .venv/bin/mypy src
cd backend && .venv/bin/pytest tests/unit tests/contract -q
```

Expected: architecture guard clean, Ruff/mypy clean, unit+contract green.

- [x] **Step 3: Run the canonical quality gate from a clean start**

```bash
bash scripts/critical-quality-gate.sh
```

Expected: natural exit 0 and final `Critical quality gate passed`; the real paid Provider case
may remain only under its existing conditional skip.

- [x] **Step 4: Write the Trellis executable contract**

The spec must contain Scope/Trigger, Signatures, Contracts, Validation/Error Matrix,
Good/Base/Bad cases, Tests Required, and Wrong/Correct examples. Include the flag default,
rollback, snapshot compatibility, single-writer and no-Sales-capability requirements.

- [x] **Step 5: Update authority docs with implemented facts**

Record exact test evidence, default/rollback behavior, remaining Gate 3 boundary and any
still-temporary dependency edge. Do not claim Provider/Grounding neutrality before Gate 3.

- [x] **Step 6: Commit logical slices**

Create local commits without the unrelated Readiness file:

```text
feat(realtime): add explicit session engine state
refactor(presentation): compose realtime engine tracer bullet
test(realtime): freeze presentation golden conversation contract
docs: close modular monolith Gate 2
```

Run `git diff --check` before each commit and inspect staged paths with `git diff --cached --name-only`.

## Self-review

- Spec coverage: every Gate 2 deliverable maps to Tasks 1–6; Gate 3 Provider/cache work is
  explicitly excluded.
- Placeholder scan: the plan contains no TBD/TODO or unspecified implementation step.
- Type consistency: state names, Engine methods, handler names, flag and snapshot key are
  consistent across tasks.
- Risk containment: Sales defaults remain unchanged, only one Presentation handler is
  instantiated, snapshots are additive, and rollback is one server-side flag.

## Closure record — 2026-07-11

Status: **Completed**. Gate 2 shipped as the following logical commits:

- `acaae127` — explicit realtime state;
- `3c8940d5`, `f71feb55`, `9dffaabf` — snapshot and grounding invariant hardening;
- `ab1a7335`, `a9d5f116` — Presentation capability split and Engine composition;
- `3bcbbaa0`, `050aef84`, `f979ef5f` — real Golden differential and terminal state;
- `875220e4`, `d08d8313`, `d287d635` — declarative selection, diagnostics, follow-up ownership;
- `6c97d8a3` — shared manager test isolation;
- `31549c90` — seven-section Trellis executable contract.

CodeGraph final evidence: `RealtimeSessionEngine` impact 65 symbols,
`PresentationRealtimeEngineHandler` impact 20 symbols, and the broad changed-source affected
set 363 test files. Architecture guard passed without policy changes; the actual
`presentation_coach -> sales_bot` temporary edge remains because the compatibility Adapter still
uses Sales StepFun mixins.

Canonical `critical-quality-gate.sh` was rerun from clean start after a first environment-only
Chromium loader failure was minimized to a missing local-library loader path. The complete rerun
naturally exited 0 with:

- backend unit+contract `2846 passed, 1 skipped`;
- Vitest 209 files / `1329 passed, 6 skipped`;
- Playwright generic/smoke/newcomer/presentation/sales `3/9/11/2/1 passed`, plus the one existing
  conditional real paid Provider skip;
- selected backend integration/E2E `598 passed, 21 skipped`;
- changed executable lines 723/799（90.49%）, no changed critical-branch gaps or floor regression;
- final `Critical quality gate passed`.

Gate 3 remains responsible for `RealtimeProviderPort`, provider event codec, Fake Provider
contract suite, one Grounding state/cache authority, and retirement of the temporary dependency
edge. Gate 2 does not claim those boundaries or the full modular-monolith migration complete.
