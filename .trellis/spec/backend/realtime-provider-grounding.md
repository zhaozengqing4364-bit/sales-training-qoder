# Realtime Provider and Grounding Authority

> Executable Gate 3 contract for the neutral Provider Port, StepFun codec/adapter, one selected
> Grounding decision/cache authority, rollout rollback, diagnostics and lifecycle cleanup.

> **Foundation boundary (2026-07-18):** this contract governs the independent Sales and Presentation realtime products only. Realtime customer voice roleplay is absent from the newcomer Foundation Path union, standard seed, navigation, OpenAPI and release gate. Its Provider smoke must not be used as evidence for Foundation AI Coach, audio-file ASR/scoring or `foundation_ready`.

## 1. Scope / Trigger

Apply this contract when a change touches:

- `training_runtime/realtime/provider.py`, `stepfun_provider.py`, `grounding.py`, or
  `grounding_cache.py`;
- Provider command/event/capability/error DTOs or StepFun raw codec behavior;
- shared Sales/Presentation upstream connect/send/receive/reconnect/backpressure code;
- strict KB lock, prefetch, model tool retrieval, answerability overlay/block/output guard;
- `REALTIME_PROVIDER_PORT_ENABLED` or `REALTIME_GROUNDING_MODULE_ENABLED`;
- Provider/Grounding diagnostics, cache/metric ownership, timeout or session close; or
- the Sales 2x2, Presentation 2x2x2, Fake Provider, Golden differential or architecture policy.

Gate 3 neutralizes Provider and Grounding ownership inside the modular monolith and adds no second
production Provider. Gate 6 subsequently removed the `presentation_coach -> sales_bot` domain edge:
the application root composes Presentation behavior with the retained shared transport. The three
constructor-time rollback flags and Legacy Grounding cache/adapter remain active until their release
evidence and deprecation windows satisfy the Gate 6 retirement contract.

## 2. Signatures

```python
@dataclass(frozen=True, slots=True)
class ProviderCommand:
    kind: ProviderCommandKind
    data: Mapping[str, JsonValue]

@dataclass(frozen=True, slots=True)
class ProviderEvent:
    kind: ProviderEventKind
    connection_epoch: int
    data: Mapping[str, JsonValue]
    request_id: int | None = None
    response_id: str | None = None
    stream_id: str | None = None
    call_id: str | None = None
    error_category: ProviderErrorCategory | None = None
    error_reason: ProviderErrorReason | None = None

class RealtimeProviderPort(Protocol):
    @property
    def capabilities(self) -> RealtimeProviderCapabilities: ...
    async def connect(self, config: RealtimeProviderSessionConfig) -> None: ...
    async def send(self, command: ProviderCommand) -> ProviderSendResult: ...
    async def receive(self, *, connection_epoch: int) -> ProviderEvent: ...
    async def check_health(
        self, *, timeout_seconds: float | None = None
    ) -> ProviderHealthResult: ...
    def decide_backpressure(
        self, command: ProviderCommand, *, pending_bytes: int
    ) -> ProviderBackpressureResult: ...
    async def close(self) -> None: ...

class StepFunEventCodec:
    def encode_command(self, command: ProviderCommand) -> dict[str, JsonValue]: ...
    def decode_event(
        self, raw: str | bytes, *, connection_epoch: int
    ) -> ProviderEvent: ...

@dataclass(frozen=True, slots=True)
class GroundingRequest:
    decision_id: str
    query: str
    frozen_policy_hash: str
    knowledge_base_ids: tuple[str, ...]
    top_k: int
    metadata_filter: Mapping[str, JsonValue]

class GroundingRetrievalCache:
    async def get_or_retrieve(
        self, request: GroundingRequest, retriever: GroundingRetrieverPort
    ) -> GroundingRetrievalResult: ...
    def stats(self) -> GroundingCacheStats: ...
    async def close(self) -> None: ...

class RealtimeGroundingModule:
    async def prepare(
        self, request: GroundingRequest, *, policy: Mapping[str, JsonValue]
    ) -> GroundingDecisionResult: ...
    async def retrieve(self, request: GroundingRequest) -> GroundingRetrievalResult: ...
    def decide(
        self,
        request: GroundingRequest,
        retrieval: GroundingRetrievalResult,
        *,
        policy: Mapping[str, JsonValue],
    ) -> GroundingDecisionResult: ...
    def cache_stats(self) -> GroundingCacheStats: ...
    async def close(self) -> None: ...

class GroundingDecisionResult:
    def to_engine_outcome(self) -> str: ...
    def to_engine_diagnostics(
        self, *, cache_stats: GroundingCacheStats | None = None
    ) -> dict[str, str | int | float | bool]: ...
    def to_compatibility_diagnostics(...): ...
    def to_frontend_diagnostics(...): ...
```

## 3. Contracts

### Provider authority

- The default shared handler freezes `REALTIME_PROVIDER_PORT_ENABLED=true` at construction and
  lazily creates exactly one `StepFunRealtimeProvider`. `false` selects only the named raw
  `StepFunTransport` compatibility path. Runtime environment mutation cannot switch an existing
  session.
- Capability validation occurs before socket connect. Unsupported requirements fail with a typed,
  closed Provider error; no raw credential, URL, token or provider error text enters public DTOs.
- Commands and events are immutable, recursively frozen and versioned by their closed enums. The
  codec is the only raw StepFun shape translator.
- Every received event is bound to the current connection epoch. Stale epoch/request/response/
  stream/call correlation cannot mutate the active turn.
- Disconnect recovery and proactive refresh share one generation rollover authority. Close-only
  terminal/pause intent cannot be upgraded to reconnect; failed close remains retryable.
- Provider backpressure preserves the existing accepted/drop semantics for binary audio evidence.

### Grounding authority

- The default handler freezes `REALTIME_GROUNDING_MODULE_ENABLED=true` and constructs one
  `RealtimeGroundingModule` plus one `GroundingRetrievalCache` per session. `false` constructs only
  `LegacyRealtimeGroundingAdapter` and `LegacyToolResultCache` for rollback.
- `StepFunToolExecutionModule` owns call-id/turn de-duplication, routing and execution only. It has
  no result-cache state or cache API.
- Strict KB lock, preferred prefetch and model tool retrieval build the same immutable request and
  share one low-level retrieval for an identical query/top-k/filter/frozen-policy/KB scope.
- Scope/hash mismatch fails closed. Runtime never substitutes latest policy or KB scope for the
  frozen request.
- Only validated non-empty success is cached. Error, invalid, timeout, cancellation and no-hit are
  never negative-cached. Entries are deep-copied, TTL/LRU bounded and session-local.
- Same-key concurrent callers share one owner task. Canceling one waiter does not cancel the owner;
  owner timeout/cancel/error does not cache. Session close cancels and awaits every owner and clears
  active decision authority.
- Decision IDs contain connection epoch plus a monotonic session sequence. A late older result
  cannot overwrite the latest decision, pending context or compatibility diagnostics.

### Projection, metrics and privacy

- One immutable `GroundingDecisionResult` projects Engine state, internal compatibility fields,
  pending context, blocked response and output guard. Consumers do not re-evaluate answerability.
- Engine diagnostics remain schema v1. `duration_ms` becomes `latency_ms`; `hit/shared` becomes
  `cache_hit=true`; `miss/bypass` becomes `false`. Exact disposition is absent from Engine state and
  remains on the decision/internal compatibility projection.
- Engine projection is validated by `GroundingState.validate_diagnostics` and contains no query,
  citation text, prompt, transcript, provider error or secret.
- Frontend/runtime diagnostics omit rewritten query, snippet, claim, frozen hash and raw errors;
  bounded citation identity/title/score remains available.
- The low-level knowledge search callback is the only query-bearing durable metric writer. A cache
  hit does not execute the tool and fabricates no second durable event. Existing
  `last_query/recent_queries` persistence remains unchanged.

### Rollout matrix and rollback

- Sales has Provider/Grounding 2x2=4 construction selections.
- Presentation has Engine/Provider/Grounding 2x2x2=8 construction selections.
- Every combination constructs one handler, one selected Provider path and one selected Grounding
  path; it never shadows, double-connects, double-retrieves, double-scores or double-reports.
- Rollback flags do not rewrite frozen snapshots, historical evidence, scores or reports.

## 4. Validation & Error Matrix

| Condition | Required result |
|---|---|
| Provider/Grounding flag unset | Select default Port/Module path |
| Flag true/1/yes/on or false/0/no/off | Normalize case/whitespace and freeze once |
| Unknown flag value | Fail-safe Legacy false; operator warning excludes raw value |
| Provider capability mismatch | Typed failure before transport connect |
| Invalid raw JSON/shape or unknown event | Closed invalid/unknown event; no active-state mutation |
| Stale connection epoch or correlation ID | Ignore/fail closed |
| Provider send backpressure drop | No local accepted-audio evidence |
| Identical successful Grounding request | One retrieval; hit/shared on later/concurrent caller |
| Different policy hash/KB/top-k/filter | Cache miss |
| No-hit/error/timeout/invalid | Bypass cache; next request retrieves again |
| Waiter canceled | Owner may complete/cache; canceled waiter does not project |
| Owner canceled/timed out or session closes | No cache entry, late decision or orphan task |
| Scope/hash drift | Blocked configuration result |
| Older decision completes after newer decision | Older projection rejected |
| Engine diagnostics include exact disposition/free text | Validation/test failure |
| Frontend diagnostics include query/snippet/claim/raw error | Contract failure |
| Cache hit path calls durable metric callback | Single-writer test failure |

## 5. Good / Base / Bad Cases

- **Good**: one default Provider Port receives canonical commands/events, one Module shares a
  cacheable retrieval across prefetch/tool, exact disposition remains internal, Engine/frontend
  projections are closed/redacted, and close awaits Provider and Grounding owners.
- **Base**: all rollback flags are false; named Legacy paths preserve wire, persistence, user copy,
  frozen snapshot and single-writer behavior without constructing default authorities.
- **Bad**: Tool execution stores results, strict KB and tool retrieval use separate caches, an env
  change switches a live session, a stale epoch/result mutates current state, raw Provider text is
  logged/exposed, Presentation adds a direct neutral-runtime import, or the temporary cross-domain
  exception is removed while imports still exist.

## 6. Tests Required

- Provider contracts/codec: `test_realtime_provider_contract.py`,
  `test_stepfun_provider_codec.py`.
- Grounding/cache/projections: `test_realtime_grounding_module.py`,
  `test_grounding_decision_pipeline.py`, `test_stepfun_tool_execution.py`,
  `test_realtime_session_engine.py`.
- Shared production integration: `test_stepfun_realtime_handler.py`,
  `test_stepfun_realtime_upstream.py`.
- Presentation façade/rollback/Golden: `test_presentation_realtime_engine_handler.py`,
  `test_presentation_stepfun_realtime_handler.py`.
- Contract/integration/E2E: `test_practice_evidence_contract.py`,
  `test_sales_realtime_reconnect_flow.py`, `test_websocket_flow.py`.
- Run `backend/scripts/architecture_dependency_guard.py --check`, Ruff, full mypy and the canonical
  quality gate. Do not add skip/xfail/retry or a permanent exclusion.

## 7. Wrong vs Correct

### Wrong: two retrieval/cache authorities

```python
prefetch = await grounding_pipeline.retrieve(query)
tool_result = tool_execution.get_cached_result(key) or await tool_execution.execute_tool(...)
```

### Correct: one immutable request and Module

```python
request = build_grounding_request(query, frozen_policy_hash, kb_scope, top_k, metadata_filter)
retrieval = await grounding_module.retrieve(request)
decision = grounding_module.decide(request, retrieval, policy=frozen_policy)
apply_grounding_result(decision)  # rejects stale decision_id
```

### Wrong: expose internal evidence through Engine/frontend diagnostics

```python
engine.resolve_grounding(diagnostics={"query": query, "error": str(exc), "citations": rows})
```

### Correct: closed and audience-specific projection

```python
engine.resolve_grounding(
    outcome=decision.to_engine_outcome(),
    mode=decision.mode.value,
    diagnostics=decision.to_engine_diagnostics(cache_stats=module.cache_stats()),
)
public_diagnostics = decision.to_frontend_diagnostics(cache_stats=module.cache_stats())
```

## 8. Scenario: StepAudio 2.5 Client-Driven Audio Turn Compatibility

### 1. Scope / Trigger

- Trigger: StepFun model/config changes, browser `audio_end` handling, `turn_detection`, or
  `conversation.item.created` decoding for `stepaudio-2.5-realtime`.
- Why: StepFun rejects `input_audio_buffer.commit` while `server_vad` is active, and 2.5 may emit a
  pending audio item whose transcript is an empty string before final ASR arrives.

### 2. Signatures

```text
STEPFUN_REALTIME_TURN_DETECTION_MODE=manual_commit | policy
audio_chunk* -> audio_end -> input_audio_buffer.commit -> response.create
conversation.item.created(item.content[].transcript="") -> ProviderEvent(CONVERSATION_ITEM)
```

### 3. Contracts

- Production browser sessions use `manual_commit`: `session.update.turn_detection=null`, because
  the client explicitly closes each audio turn with `audio_end`.
- `policy` is the rollback mode and may project the frozen runtime Profile's `server_vad`; in that
  mode clients must not send `input_audio_buffer.commit` and must supply enough trailing silence.
- Unknown `STEPFUN_REALTIME_TURN_DETECTION_MODE` values fail safe to `manual_commit`; warnings must
  not include the raw value.
- A pending `conversation.item.created` with empty optional transcript is a valid lifecycle event.
  The codec preserves the content entry but must not project an empty top-level transcript.

### 4. Validation & Error Matrix

| Condition | Required result |
|---|---|
| `manual_commit` + client `audio_end` | Send one commit, await final ASR, then create response |
| `policy` + frozen `server_vad` | Send `turn_detection={type: server_vad}`; no manual commit contract |
| Unknown turn-detection mode | Select `manual_commit`, log only the safe fallback |
| Pending audio item with empty transcript | Decode as `CONVERSATION_ITEM`, omit top-level transcript |
| Non-empty final transcript event | Decode as `TRANSCRIPTION_FINAL` and preserve text |
| Manual commit while Server VAD is active | Upstream protocol failure; test/gate must fail visibly |

### 5. Good / Base / Bad Cases

- Good: production env selects `manual_commit`, browser `audio_end` yields one committed turn, and
  the pending empty transcript does not interrupt the session.
- Base: `policy` preserves an existing Server VAD deployment for rollback without mutating frozen
  runtime Profiles.
- Bad: enable Server VAD while keeping the client-driven commit path, or convert an empty pending
  transcript into `INVALID_EVENT`.

### 6. Tests Required

- Unit: env examples pin `manual_commit`; handler config overrides a Profile `server_vad` only in
  that mode; `policy` retains Server VAD.
- Codec: the StepAudio 2.5 pending audio-item shape decodes to `CONVERSATION_ITEM` without a
  top-level transcript.
- Real provider: `CRITICAL_GATE_MODE=newcomer-real-provider` must complete transcript, response,
  session end, Journey outcome and admin projection with a non-placeholder credential.

### 7. Wrong vs Correct

#### Wrong

```python
turn_detection = {"type": "server_vad"}
await send({"type": "input_audio_buffer.commit"})
data["transcript"] = ""
```

#### Correct

```python
turn_detection = None  # client sends audio_end / manual commit
if transcript:
    data["transcript"] = transcript
```
