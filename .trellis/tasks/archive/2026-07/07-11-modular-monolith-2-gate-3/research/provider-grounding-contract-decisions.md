# Gate 3 Provider and Grounding contract decisions

## Decision summary

Use Branch by Abstraction in two independently rollbackable slices:

1. wrap the existing `StepFunTransport` with a closed, neutral Provider Port + codec and switch the
   shared production handler at construction time;
2. move Grounding orchestration into a neutral deep module, make its bounded cache the only
   realtime retrieval-result cache, and keep common KB rule semantics unchanged.

No rewrite, no new Provider, no database migration and no handler relocation across bounded
contexts.

## Provider boundary

Target files:

```text
training_runtime/realtime/provider.py
training_runtime/realtime/stepfun_codec.py
training_runtime/realtime/stepfun_provider.py
```

`provider.py` owns closed DTO/Protocol vocabulary. `stepfun_codec.py` is the only raw StepFun JSON
translator. `stepfun_provider.py` composes the existing transport and credential/endpoint config.
The shared handler consumes the Port; it does not interpret raw JSON after the cutover.

Provider credentials/endpoint are injected into the StepFun Adapter factory and are never fields
on Provider events, snapshots or diagnostics. The frozen model/voice/audio/tool settings live in
`RealtimeProviderSessionConfig`; capability validation occurs before connection. `connect(config)`
opens the socket and sends exactly one session update, so there is no second configure command.

The versioned inventory maps every current raw type to one canonical kind, its required/optional
fields, production consumers and exact tests. It includes input-audio committed, assistant
transcript delta/final, thinking delta/done, response.done normalized function outputs, emotion
timing fields and closed ASR/voice/idle-timeout error reasons.

Recognized reasons keep current user-safe messages. Generic UNKNOWN errors intentionally no longer
forward arbitrary Provider text and use the fixed message `Realtime 服务返回错误`; this is the only
approved external behavior difference for Gate 3 and closes an existing raw-error leak.

The existing Phase4 local StepFun fixture remains a wire regression. A separate in-test
`FakeRealtimeProvider` implements the neutral Port so both Fake and StepFun Adapter can run the
same contract suite without pretending a raw WebSocket is the abstraction.

## Grounding boundary

Target files:

```text
training_runtime/realtime/grounding.py
training_runtime/realtime/grounding_cache.py
```

`grounding.py` owns requests, immutable citation/evidence/decision results, typed scalar diagnostics
and orchestration.
`grounding_cache.py` owns per-session cache/single-flight only. The existing Sales pipeline module
becomes a compatibility import shim during migration and is removed in Gate 6.

The Grounding request identity is derived from fields that really exist:

```text
sha256(canonical JSON(
  normalized query,
  top_k,
  canonical metadata filter,
  frozen instruction_contract_hash,
  sorted knowledge_base_ids
))
```

The digest, not raw query, is retained as the cache key. Non-empty successful validated results are
deep copied into a TTL/max-entry LRU. Timeout, cancellation, error, invalid result and empty/no-hit
results are not negative-cached. Concurrent identical calls share one internal owner task; its
timeout is enforced inside the task. Waiter cancellation does not cancel it. Module close cancels
and awaits owners and forbids late cache, metric or decision projection.

Strict KB rules keep using `common.knowledge.kb_lock_guard`; its public evaluator gains an optional
retriever seam while the default call remains compatible. The new module injects its cache-backed
retriever, then adapts the unchanged decision into one `GroundingDecisionResult`. Overlay, blocked
response and output guard consume immutable evidence/citations; Engine gets closed scalar
diagnostics while legacy projection retains bounded citations. The neutral mode vocabulary covers
the existing Engine values `grounded`, `blocked`, `degraded`, `skipped`, `kb_lock`, `unrestricted`
and `not_applicable`, so strict and no-lock projections do not lose meaning.

Citation fields use the actual compatibility shape: `knowledge_base_id`, `knowledge_base_name`,
`document_title`, `snippet`, `claim`, and optional `score`. Evidence also preserves bounded
`rewritten_queries`, answerability/source status and retrieval mode for the legacy projection.

## Rollout choice

- `REALTIME_PROVIDER_PORT_ENABLED=true` by completion default.
- `REALTIME_GROUNDING_MODULE_ENABLED=true` by completion default.
- Each is read once during handler construction; diagnostics record selection with no secret.
- Known truthy/falsy spellings are normalized; unknown values fail-safe to Legacy false.
- false selects named legacy code before Provider connection/Grounding object construction.
- Existing `PRESENTATION_REALTIME_ENGINE_ENABLED` remains independent and tested in the 2x2x2
  selection matrix.

This avoids shadow traffic and gives Provider vs Grounding failures separate kill switches while
preserving one selected implementation of each per session.

The default Grounding path does not construct legacy cache objects. A named
`LegacyRealtimeGroundingAdapter` and `LegacyToolResultCache` preserve flag-false rollback until
Gate 6; the Tool execution module itself no longer owns result caching.

Existing durable `last_query/recent_queries` fields remain for frozen snapshot compatibility and
are not exposed through Engine/frontend/log/new Provider/Grounding DTOs. The existing durable
metric function remains the only mutation/persistence writer. The low-level searcher invokes it
once on a cache miss. The new Module never invokes it again; cache disposition/counters stay in
decision/legacy compatibility diagnostics, and cache hits do not fabricate a durable retrieval
event. Engine diagnostics schema v1 remains unchanged: `duration_ms` projects to `latency_ms`,
`hit/shared` project to `cache_hit=true`, `miss/bypass` project to `cache_hit=false`, and aggregate
counters use existing fields. Exact `hit/miss/shared/bypass` disposition is not added to Engine v1.

## Rejected alternatives

### Rewrite the StepFun handler around a new async Engine runner

Rejected for Gate 3. It would combine Provider extraction with persistence, Roleplay, scoring and
delivery rewrites, creating a second-system risk. I/O stays in the compatibility WebSocket Adapter;
Engine remains protocol-neutral state authority.

### Move all Sales StepFun mixins into training_runtime

Rejected until Gate 4. Those mixins statically import Sales capability, Roleplay, prompt and
evaluation implementations; moving them now would invert dependencies rather than create a neutral
module.

### Reuse Phase4LocalStepFunProvider as the Port fake

Rejected. It speaks raw StepFun wire and therefore tests the codec implementation, not the neutral
Port contract. Keep it for end-to-end wire regression and add a true fake for Port tests.

### Put the new module in common

Rejected. `training_runtime.realtime` already owns Engine state and StepFun transport; placing
runtime orchestration in common would expand the shared kernel with volatile domain behavior.

### Cache by query only or invent a KB revision field

Rejected. Query-only keys leak results across frozen policy/KB scopes. The repository has no frozen
knowledge revision field; `instruction_contract_hash` + sorted KB IDs are the truthful scope.

### Delete all knowledge caches

Rejected. Knowledge Adapter caches serve Chroma/embedding/health concerns and are not duplicate
realtime orchestration authority. Only Grounding/Tool result cache duplication is removed.

## Verification strategy

- TDD for each Port/Codec/Grounding/cache contract.
- Golden StepFun payload/event fixtures and mutation-sensitive differential tests.
- Focused unit + Sales/Presentation reconnect/status contracts after every slice.
- CodeGraph impact/affected and architecture guard before task review.
- Independent task reviews, whole-branch review and Trellis check finding=0.
- One final clean-start canonical gate; real/paid Provider remains conditional/manual only.
