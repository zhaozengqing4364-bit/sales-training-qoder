# Gate 3 current Provider and Grounding runtime truth

## Scope and method

Read-only CodeGraph/source investigation on 2026-07-11 after Gate 2 commit `047c2b91` plus
strict snapshot fixes `3443320e`/`5f275113`. This records current call paths, ownership and
blast radius; it is not a target-state claim.

## Provider call path

```text
WebSocket route
-> training_runtime plugin selection
-> PresentationRealtimeEngineHandler / StepFunRealtimeHandler
-> LegacyPresentationStepFunRealtimeHandler / StepFunRealtimeSharedHandler
-> _connect_upstream()
-> StepFunTransport.connect()
-> raw WebSocket-like object
-> session.update
-> _receive_upstream_events(): recv -> json.loads
-> _handle_upstream_event(): classify + runtime side effects
```

Evidence:

- `backend/src/training_runtime/stepfun_transport.py`
  - `StepFunSessionConfig`
  - `build_stepfun_session_update_payload`
  - `StepFunTransport.connect/send_json/check_health/decide_backpressure/close`
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
  - `StepFunRealtimeSharedHandler.__init__` constructs transport, tool module and grounding
    pipeline.
  - `_connect_upstream` builds StepFun config and sends raw `session.update`.
- `backend/src/sales_bot/websocket/stepfun_realtime_upstream.py`
  - `_receive_upstream_events` owns raw `recv` + `json.loads`.
  - `_handle_upstream_event` owns classification, turn mutation, persistence, tools, Roleplay and
    client emission.
  - `_send_upstream` sends raw StepFun dict through `StepFunTransport`.
- `backend/src/sales_bot/websocket/components/stepfun_upstream_router.py`
  - `UpstreamEventRoute` and `classify_upstream_event` are a useful classifier, not a canonical
    ProviderEvent codec.
- `backend/src/sales_bot/websocket/phase4_local_provider.py`
  - `Phase4LocalStepFunProvider` is a raw WebSocket-like fixture, not a Port contract fake.

Outbound wire event types are constructed across mixins: `session.update`,
`input_audio_buffer.append/commit/clear`, `response.create/cancel`,
`conversation.item.create` and function-call output.

There is no current `RealtimeProviderPort`, provider capability contract, canonical event/command
DTO or complete typed error vocabulary. `StepFunTransport` is the existing implementation seam to
wrap, not duplicate.

## Grounding paths

### Strict KB lock

```text
final transcript/client text
-> _prepare_grounding_context
-> GroundingDecisionPipeline.evaluate
-> common.knowledge.kb_lock_guard.evaluate_kb_lock_decision
-> common.knowledge.internal_searcher.search_internal_knowledge
-> KnowledgeService
-> KbLockDecision
-> pending context or blocked response
```

### Non-strict prefetch

```text
_prepare_grounding_context
-> GroundingDecisionPipeline.retrieve
-> handler._retrieve_grounding_via_internal_knowledge
-> _tool_search_internal_knowledge
-> StepFunToolExecutionModule.execute_tool
-> search_internal_knowledge
-> GroundingDecisionPipeline.evaluate_retrieval
```

### Provider tool call

```text
function-call event
-> _execute_function_call
-> StepFunToolExecutionModule.decide_tool_routing
-> _tool_search_internal_knowledge
-> evaluate_retrieval
-> pending context/blocked text
-> function_call_output
-> response follow-up
```

### Overlay/block/guard

- `GroundingDecisionPipeline.build_instruction_overlay` feeds response instructions.
- `build_blocked_response` produces the existing fail-closed user text.
- `_create_response` avoids Provider generation when blocked and emits local browser-TTS.
- `apply_output_guard` trims partial/unsafe response text before flush.
- `common.knowledge.kb_lock_guard` remains the compatibility rule authority.

Presentation `LegacyPresentationStepFunRealtimeHandler._prepare_grounding_context` currently begins
and resolves Engine GroundingState around `super()._prepare_grounding_context`; Engine state is an
explicit audit projection, while Sales Mixin private fields remain the decision runtime.

## Duplicate realtime cache ownership

1. `GroundingDecisionPipeline._retrieve_cache`
   - key: query/top_k/metadata_filter JSON;
   - TTL but no explicit max-entry bound;
   - stats exist but are not one production diagnostics authority.
2. `StepFunToolExecutionModule._result_cache`
   - key: normalized query/top_k/metadata_filter;
   - TTL + max-entry clear-all policy;
   - prefetch can hit both caches in series.

KnowledgeService, Chroma, embedding and health/ready-doc caches are infrastructure Adapter caches;
they are intentionally outside this Gate's deletion scope.

## Diagnostics and metrics surfaces

- Engine: closed/versioned `GroundingState.diagnostics`.
- Legacy runtime: `_latest_knowledge_answer_diagnostics` free-form compatibility payload.
- Retrieval payload: `_diagnostics` and `_answerability`.
- Tool module: `ToolExecutionDiagnostics`, including its own cache counters.
- Grounding pipeline: `GroundingCacheStats`.
- Presentation façade: legacy top-level diagnostics plus additive Engine subtree.

Durable knowledge metrics flow through `_record_knowledge_runtime_metric` and the frozen voice
policy snapshot. KB lock metrics take a separate mutation path. Cache counters are not unified.

## Repository facts that constrain design

- There is no repository field named knowledge revision/version in the frozen realtime policy.
  Existing stable scope inputs are `instruction_contract_hash` and `knowledge_base_ids`; cache
  identity must use those rather than inventing `knowledge_revision_id`.
- Sales remains StepFun-only. Port introduction must not imply another production Provider.
- Presentation still imports Sales shared handler plus message/persistence helpers. Provider and
  Grounding extraction alone cannot truthfully remove the whole package edge.
- Current Handler mixins import Roleplay, prompt, evaluation and Sales capability code. Moving the
  entire shared handler into `training_runtime` during Gate 3 would invert dependencies and pull
  Gate 4 into scope.

## CodeGraph blast radius

- `StepFunTransport`: 56 affected symbols.
- `GroundingDecisionPipeline`: 105 affected symbols.
- `classify_upstream_event`: 30 affected symbols.
- `StepFunToolExecutionModule`: 90 affected symbols.
- `LegacyPresentationStepFunRealtimeHandler`: 69 affected symbols.

Mandatory regressions include transport/payload/router/tool/grounding unit tests, Sales handler and
reconnect tests, Presentation Engine/adapter/Golden tests, WebSocket status contract, Phase4 local
Provider E2E, architecture guard and final canonical gate.
