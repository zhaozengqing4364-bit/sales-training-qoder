# Realtime Session Engine

> Executable contract for the Gate 2 Presentation tracer bullet, its rollback adapter,
> state transitions, snapshot compatibility, diagnostics, and single-writer boundary.

## 1. Scope / Trigger

Apply this contract when a change:

- modifies `training_runtime/realtime/`, `PresentationRealtimeEngineHandler`, or
  `LegacyPresentationStepFunRealtimeHandler`;
- changes Presentation realtime handler selection, its app-root factory map, or
  `PRESENTATION_REALTIME_ENGINE_ENABLED`;
- changes connection, turn, grounding, evidence, reconnect, tool-follow-up, or audio-turn
  behavior;
- adds/removes snapshot or runtime-diagnostics fields;
- touches shared StepFun construction used by Sales and Presentation; or
- changes the Golden Conversation differential or realtime release-gate selection.

Gate 2 is a Presentation tracer bullet. It establishes explicit Engine state and a composition
façade while keeping the StepFun wire/persistence implementation in a compatibility adapter.
It does **not** complete Gate 3: `RealtimeProviderPort`, the provider event codec, and one
Grounding cache/state authority remain future work. The temporary
`presentation_coach -> sales_bot` implementation edge is therefore still real.

## 2. Signatures

```python
class RuntimeHandlerFactoryKey(StrEnum):
    PRESENTATION_REALTIME_ENGINE = "presentation_realtime_engine"


@dataclass(frozen=True)
class ScenarioRuntimeHandlerSelection:
    scenario_type: str
    runtime_mode: str
    websocket_route: str
    handler_factory_path: str
    handler_factory_name: str
    factory_key: RuntimeHandlerFactoryKey | None = None


class RealtimeSessionEngine:
    def __init__(self, *, scenario_type: str, hooks: ScenarioTurnHooks) -> None: ...
    @property
    def state(self) -> RealtimeSessionState: ...
    def snapshot(self) -> dict[str, object]: ...
    def restore(self, payload: Mapping[str, object]) -> None: ...

    def begin_connection(self, session_id: str) -> None: ...
    def mark_connected(self) -> None: ...
    def mark_degraded(self, *, reason: str) -> None: ...
    def begin_close(self, *, reason: str) -> None: ...
    def mark_disconnected(self, *, reason: str) -> None: ...

    def begin_turn(self, *, request_id: int, stream_id: str) -> None: ...
    def mark_response_started(self, *, response_id: str) -> None: ...
    def mark_streaming(self) -> None: ...
    def complete_turn(
        self, *, request_id: int, reason: str = "response_done"
    ) -> bool: ...
    def interrupt_turn(self, *, request_id: int, reason: str) -> None: ...
    def timeout_turn(self, *, request_id: int, reason: str) -> None: ...

    def begin_grounding(self, *, decision_id: str, policy_hash: str) -> None: ...
    def resolve_grounding(
        self,
        *,
        outcome: str,
        mode: str,
        diagnostics: Mapping[str, object] | None = None,
    ) -> None: ...

    def record_evidence(
        self,
        *,
        evidence_key: str,
        evidence_type: str,
        turn_number: int,
        payload: bytes,
    ) -> bool: ...
    def record_evidence_digest(
        self,
        *,
        evidence_key: str,
        evidence_type: str,
        turn_number: int,
        payload_digest: str,
    ) -> bool: ...
    def mark_evidence_pending(self, evidence_key: str) -> bool: ...
    def acknowledge_evidence(self, evidence_key: str) -> bool: ...


class PresentationRealtimeEngineHandler:
    async def handle_connection(self, websocket, session_id, token, trace_id=None): ...
    async def send_message(self, message): ...
    async def close(self, code=1000, reason="Session closed"): ...
    async def sync_lifecycle_transition(self, transition): ...
    def get_runtime_diagnostics(self) -> dict[str, Any]: ...
```

Selection and app-root construction:

```python
PRESENTATION_REALTIME_ENGINE_ENABLED: bool = True

_RUNTIME_HANDLER_ENGINE_FACTORIES = MappingProxyType({
    RuntimeHandlerFactoryKey.PRESENTATION_REALTIME_ENGINE: RealtimeSessionEngine,
})
```

## 3. Contracts

### Rollout, rollback, and declarative selection

- Default `true` selects `PresentationRealtimeEngineHandler` for persisted
  `stepfun_realtime` Presentation sessions.
- Explicit `false` selects `LegacyPresentationStepFunRealtimeHandler`; route admission,
  persisted voice mode, WebSocket protocol, close codes, and snapshot fields stay compatible.
- Selection reads the flag exactly once. It is frozen/hashable and carries only scalar strings
  plus the closed `RuntimeHandlerFactoryKey`; no dict, callable, class, or runtime object crosses
  the plugin boundary.
- The application root owns the static read-only key-to-factory map. Unknown keys fail closed
  before handler construction.
- Exactly one handler is instantiated per session. Rollout is never a shadow path.

### State authority and transitions

- Engine snapshots are versioned (`ENGINE_STATE_VERSION == 1`) and callers receive copies, not
  mutable internal state.
- Connection follows
  `disconnected -> connecting -> connected|degraded -> closing -> disconnected`.
  Reconnect epoch is monotonic; a restored session uses persisted epoch + 1.
- Turn follows
  `idle|completed|interrupted|timed_out -> receiving -> generating -> streaming -> completed`.
  Active-turn re-entry, stale request IDs, and stale completion fail closed.
- `response.done` captures the current request before flush. Presentation completes that Engine
  turn in `_after_response_flushed_before_followup` before a function/tool follow-up may create
  the next response. The shared Sales default hook is a no-op.
- Grounding follows `empty|ready|blocked|degraded -> preparing -> ready|blocked|degraded` and
  retains the frozen policy hash, decision ID, mode, and sanitized diagnostics.
- Evidence keys are idempotent. Same key + same type/turn/digest is replay-safe; a conflicting
  record fails. Acknowledgement is legal only after `mark_evidence_pending`.

### Snapshot and diagnostics compatibility

- Gate 2 adds only `runtime_state.realtime_engine`; all legacy snapshot keys retain their
  meaning. Pre-Gate snapshots without this key are derived into a valid Engine state.
- Restore accepts only the current Engine version and matching scenario. Restore into a
  non-pristine Engine fails. An existing Engine payload keeps its persisted `scenario_type`
  through the adapter boundary so a mismatch cannot be normalized away.
- Snapshot string, boolean, and integer fields use exact JSON scalar types. Restore rejects
  coercible wrong types, including strings/floats/booleans in integer slots, instead of
  reinterpreting them as a different state.
- Engine evidence is record/dedupe metadata only. It does not create a second message, score,
  report, or audit writer.
- Shared binary input returns an explicit acceptance disposition. It is `True` only after a
  non-empty audio chunk passes lifecycle, upstream-ready, and backpressure checks, the upstream
  append is accepted, and the local audio flow is appended. Empty/invalid/interrupt, lifecycle or
  readiness rejection, upstream rejection, and backpressure drop all return `False` and create no
  audio evidence.
- Presentation maintains one O(1) per-user-turn audio accumulator only for accepted chunks:
  streaming SHA-256, chunk count, byte count, and a frozen transcript-resolved turn number. It
  never retains raw audio or a chunk list and never transitions Engine state per frame.
- After local input-audio commit succeeds and before response scheduling, the shared narrow hook
  records exactly one Presentation evidence key
  `audio:{turn}:chunks:{count}:bytes:{bytes}` through `record_evidence_digest`, then clears the
  accumulator. Sales uses the no-op hook. Duplicate commit creates no second record; identical
  bytes committed in different turns remain separate turn-scoped records.
- `record_evidence_digest` accepts only `sha256:` followed by 64 lowercase hexadecimal digits and
  reuses the same evidence idempotency, conflict, and transition semantics as `record_evidence`.
- The façade preserves legacy adapter diagnostics at their existing **top-level** keys:
  `session_status`, `ai_state`, `current_request_id`, `live_session_summary`, `claim_truth`,
  `coach_health`, `knowledge_answer_diagnostics`, `reconnect_state`, and `runtime_events`.
  Engine fields are additive: `selected_runtime`, `rollout_enabled`, `rollback_runtime`,
  `engine_state_version`, `engine_state`, `transition_count`, and `last_transition`.
- Diagnostics never expose token, raw prompt, raw transcript, raw audio, or provider secrets.
- Grounding diagnostics require schema version 1, an allowlisted field set, finite bounded
  numeric values, and closed vocabularies for status/reason/source/mode/error/fallback. Free-form
  provider error text cannot cross the Engine boundary.

### Scenario and persistence boundary

- `PresentationRealtimeEngineHandler` is a composition façade, not a
  `StepFunRealtimeSharedHandler` subclass and not a `__getattr__` proxy.
- Its real adapter may temporarily reuse `sales_bot` StepFun mixins during Gate 2, but is created
  with `scenario="presentation"` and `sales_capabilities_enabled=False` from the first base
  initialization.
- Presentation must not construct SalesStage, FuzzyDetection, or RealtimeScoring capability
  objects. Sales defaults remain `scenario="sales"` and `sales_capabilities_enabled=True`.
- Existing adapter persistence remains the single writer for messages, scores, reports, and
  reconnect state. Engine hooks observe/validate state; they do not call repositories.

### Golden differential

- The differential drives a real Legacy handler and the real façade's real compatibility
  adapter through connect/start/text/binary/transcription/`response.done`/reconnect/close.
- It compares ordered stable downstream events, upstream events, persistence writes, close
  result, and every legacy snapshot field after removing only the additive Engine subtree and
  genuinely nondeterministic timestamps/trace/generated IDs.
- The Engine terminal contract requires reconnect epoch 2 for the fixture, completed turn,
  ready grounding with the frozen policy hash, and one deduped audio plus one transcript
  evidence record for turn 2.
- Mutation probes must fail when an event, persistence write, legacy snapshot field, epoch,
  grounding result, or evidence record changes.

## 4. Validation & Error Matrix

| Condition | Required result |
|---|---|
| Flag unset/default | Select Engine façade (`true`) |
| Flag explicitly `false` | Select named Legacy adapter only; no Engine factory key |
| Unknown/invalid factory key | `ValueError("unknown_runtime_handler_factory_key")`; construct nothing |
| Selection contains dict/callable/class | Contract failure; keep selection declarative/frozen |
| Hook scenario differs from Engine scenario | Fail with `scenario_hook_mismatch` |
| Unsupported Engine version or scenario on restore | Fail closed; do not partially restore |
| Snapshot scalar field has a coercible wrong type | `ValueError`; do not reinterpret the persisted state |
| Restore after Engine state has progressed | Fail with `engine_restore_requires_pristine_state` |
| Connection transition is out of order | `RealtimeStateTransitionError`; state unchanged |
| Reconnect snapshot epoch is `n` | Restored connection epoch is `n + 1` |
| Active turn re-entry or stale request/completion | `RealtimeStateTransitionError`; next turn not created early |
| Tool follow-up after `response.done` | Complete captured turn before follow-up `begin_turn` |
| Grounding diagnostics have unknown field/free text/NaN/out-of-range value | `ValueError`; grounding state unchanged |
| Grounding knowledge is blocked/degraded | Closed `blocked`/`degraded` outcome and reason vocabulary |
| Same evidence key and same payload replay | Return `False`; count unchanged |
| Same evidence key with conflicting metadata/digest | `RealtimeStateTransitionError` |
| Evidence acknowledgement without pending state | `RealtimeStateTransitionError` |
| 1,000 accepted chunks followed by one local commit | One audio evidence/transition; accumulator and snapshot growth remain O(1) |
| Empty/invalid/interrupt/rejected/dropped audio | Return `False`; zero audio evidence |
| Duplicate commit without newly accepted local audio | No hook effect; evidence count unchanged |
| Same committed audio bytes in different turns | Separate frozen turn-scoped evidence keys |
| Pre-Gate snapshot lacks `realtime_engine` | Derive valid Engine state and preserve every legacy field |
| Façade diagnostics are read by practice API | Legacy top-level fields remain available |
| Adapter reports token/raw prompt/transcript fields | Sanitize; do not propagate |
| Presentation constructor path | Zero Sales capability construction |
| Sales constructor path | Existing Sales capability objects remain enabled and typed |

## 5. Good / Base / Bad Cases

- **Good**: the flag is enabled, the app root resolves the closed Engine factory key, the façade
  composes one Presentation adapter, a reconnect restores epoch 2, and the Golden differential
  matches Legacy events/writes/snapshots while Engine terminal evidence is deduped.
- **Base**: the flag is disabled, the named Legacy adapter runs alone with unchanged wire and
  persistence behavior; Sales keeps its existing default constructor and reconnect flow.
- **Bad**: a plugin passes a factory callable or kwargs dict, the façade nests/removes legacy
  diagnostics, Engine writes a second message/score/report, `response.done` completes the new
  follow-up turn, rejected or per-frame audio creates evidence, raw chunks accumulate in memory,
  audio keys use mutable `turn_count`, or documentation claims Provider/Grounding neutrality while
  the compatibility adapter still imports `sales_bot` mixins.

## 6. Tests Required

- Engine state/validation: `backend/tests/unit/test_realtime_session_engine.py`.
- Façade, snapshots, follow-up ordering, diagnostics, evidence, and real Golden differential:
  `backend/tests/unit/test_presentation_realtime_engine_handler.py`.
- Presentation constructor/event/persistence compatibility:
  `backend/tests/unit/test_presentation_stepfun_realtime_handler.py`.
- Rollout/default/rollback/immutable selection:
  `backend/tests/unit/test_training_runtime_plugins.py` and
  `backend/tests/unit/test_main_presentation_ws_runtime.py`.
- Real diagnostics consumer: `backend/tests/contract/test_practice_evidence_contract.py`.
- Sales defaults/shared upstream/reconnect/status regression:
  `backend/tests/unit/test_stepfun_realtime_handler.py`,
  `backend/tests/unit/test_stepfun_realtime_upstream.py`,
  `backend/tests/integration/test_sales_realtime_reconnect_flow.py`, and
  `backend/tests/integration/test_websocket_status_contract.py`.
- Architecture: run `backend/scripts/architecture_dependency_guard.py --check`; do not remove
  the `presentation_coach -> sales_bot` temporary edge until the actual import disappears.
- Quality: Ruff, mypy, backend unit+contract, and a fresh natural
  `bash scripts/critical-quality-gate.sh` run. Do not add `xfail`, permanent skip, or `|| true`.

## 7. Wrong vs Correct

### Wrong: executable factory in selection and double writing

```python
return ScenarioRuntimeHandlerSelection(
    ...,
    handler_factory_kwargs={"runtime_engine_factory": RealtimeSessionEngine},
)

await legacy_adapter.persist_message(message)
await engine_repository.persist_message(message)  # second writer
```

This crosses an executable object through the declarative boundary and creates rollback and
idempotency ambiguity.

### Correct: closed key, app-root resolution, and record-only Engine evidence

```python
selection = ScenarioRuntimeHandlerSelection(
    ...,
    factory_key=RuntimeHandlerFactoryKey.PRESENTATION_REALTIME_ENGINE,
)

factory = _RUNTIME_HANDLER_ENGINE_FACTORIES[selection.factory_key]
handler = PresentationRealtimeEngineHandler(runtime_engine_factory=factory)

await legacy_adapter.persist_message(message)  # only writer
engine.record_evidence(
    evidence_key="transcript:2:user",
    evidence_type="transcript",
    turn_number=2,
    payload=normalized_transcript.encode("utf-8"),
)
```

### Wrong: complete after creating a tool follow-up

```python
await super()._handle_upstream_response_done(event)  # may create request 2
engine.complete_turn(request_id=engine.state.turn.request_id)
```

### Correct: capture and complete between flush and follow-up

```python
expected_request_id = active_response.request_id
had_active_response = await self._flush_active_response(event)
if had_active_response:
    await self._after_response_flushed_before_followup(
        expected_request_id=expected_request_id,
        event=event,
    )
# Only now may the shared path create a tool follow-up response.
```

The closed selection, transition hook, additive snapshot, and single writer make rollback
observable and safe without claiming Gate 3 is already complete.
