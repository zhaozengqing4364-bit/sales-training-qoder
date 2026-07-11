# Gate 2 research: current Presentation realtime runtime and state

Date: 2026-07-11  
Method: CodeGraph `explore`/`node`/`impact`, followed by targeted source and policy inspection.

## Current composition truth

The persisted `stepfun_realtime` route is selected by
`training_runtime.plugins.PresentationScenarioPlugin.select_runtime_handler` and dynamically
instantiates `PresentationStepFunRealtimeHandler` from `websocket_routes.py` only after
RuntimeGate admission and object-owner authorization.

`PresentationStepFunRealtimeHandler` currently extends
`sales_bot.websocket.stepfun_realtime_handler.StepFunRealtimeSharedHandler`. Its constructor:

1. runs the Sales-owned shared constructor;
2. constructs SalesStage, FuzzyDetection, and RealtimeScoring capabilities as enabled;
3. rewrites the scenario to `presentation`;
4. reconstructs those three Sales capability objects as disabled.

This is the exact anti-pattern named by the approved design. The class does not inherit
`StepFunRealtimeSalesStageMixin`, but it still inherits the Sales shared state surface and
starts from Sales capability construction.

The only direct `presentation_coach -> sales_bot` imports are in
`presentation_stepfun_realtime_handler.py`. The architecture policy records this edge as a
temporary exception with owner, retirement condition, and 2026-10-31 expiry. Gate 2 should
remove the inheritance/capability-construction reason; Gate 3 may still be needed to remove
the remaining StepFun implementation dependency completely.

## Existing state authorities

The current shared handler has several overlapping state holders:

- connection/reconnect: `_connection_epoch`, `_last_disconnect_reason`, `_last_runtime_error`,
  upstream task/health timestamps, Redis `SessionStateSnapshot`;
- turn: `current_request_id`, `_active_response`, `RealtimeTurnCoordinator`, pending-response
  flags and function-call state;
- grounding: `_pending_grounding_context`, `_pending_blocked_response_text`,
  `GroundingDecisionPipeline`, the pipeline cache, and an additional tool retrieval cache;
- evidence: persisted-message keys, transcript dedupe fields, score/live-summary/claim fields,
  curriculum and objection state.

`StepFunRealtimeStateBase` exposes more than one hundred attributes, including Sales stage,
fuzzy detection, scoring, curriculum, objection and feedback state. The Mixin family relies
on this implicit private-field interface. `RealtimeTurnCoordinator` and
`GroundingDecisionPipeline` are already useful deep-module seeds, but neither is the whole
session authority.

## External contracts already enforced

- Route layer: session UUID validation, RuntimeGate admission, token resolution, owner/admin
  authorization and handler registration.
- Handler layer: a second fail-fast token check, exact close codes, StepFun key failure,
  connection-manager envelope, lifecycle mirror and reconnect snapshot.
- Presentation events: `connected`, `status`, `asr_transcript`, page/point events,
  `forbidden_word`, `feedback`, `interruption`, `interrupted`, `tts_audio`, `error`,
  `session_ended`, heartbeat.
- Binary audio: v1 frame identifiers remain owned by the existing StepFun path.
- Snapshot: reconnect-safe runtime data contains request epoch, reconnect epoch/reason/error,
  score/live-summary/claim/objection/feedback state; terminal or timeout exits delete it.
- Persistence: message keys suppress duplicate transcript writes; score/report idempotency is
  downstream and must not gain a second writer.

## Impact surface

CodeGraph impact reports 47 affected symbols for `PresentationStepFunRealtimeHandler`,
primarily its own methods and `test_presentation_stepfun_realtime_handler.py`.
`StepFunRealtimeSharedHandler.__init__` directly affects Sales reconnect initialization, so
any constructor split must keep the Sales default byte-for-byte equivalent and run the Sales
reconnect/integration tests in addition to Presentation tests.

## Safe migration seam

Gate 2 can establish composition without prematurely implementing Gate 3:

- a neutral `RealtimeSessionEngine` owns explicit typed state and invariant-checked
  transitions;
- a Presentation production façade owns the Engine and composes a Presentation StepFun
  runtime adapter;
- the adapter may temporarily reuse the current StepFun Mixin implementation, but it is
  created in `scenario="presentation"` mode and must not construct Sales capabilities;
- the old directly inherited Presentation handler remains as a named rollback adapter only;
- the engine adds an additive reconnect snapshot payload and diagnostics, never a second DB
  score/report write;
- an offline differential contract compares the old adapter and engine façade from the same
  Golden Conversation inputs.

This is a Strangler step, not the final Provider extraction. Gate 3 will move provider event
codec/transport and Grounding authority behind neutral ports, allowing the temporary
`presentation_coach -> sales_bot` implementation dependency to disappear.

## Test selection from impact

At minimum:

- `backend/tests/unit/test_realtime_session_engine.py`;
- `backend/tests/unit/test_presentation_realtime_engine_handler.py`;
- `backend/tests/unit/test_presentation_stepfun_realtime_handler.py`;
- `backend/tests/unit/test_training_runtime_plugins.py`;
- `backend/tests/unit/test_main_presentation_ws_runtime.py`;
- `backend/tests/unit/test_stepfun_realtime_handler.py`;
- `backend/tests/integration/test_sales_realtime_reconnect_flow.py`;
- `backend/tests/integration/test_websocket_status_contract.py`;
- architecture guard, Ruff, mypy and the canonical critical quality gate.

