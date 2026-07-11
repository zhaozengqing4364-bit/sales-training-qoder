# Gate 3 Provider Port and Grounding Authority Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce a neutral realtime Provider Port/StepFun codec and make one neutral Grounding
module the only realtime decision/cache authority without changing current user, wire,
persistence, scoring, report or reconnect behavior.

**Architecture:** Keep FastAPI/WebSocket I/O in the compatibility delivery adapter. A closed
`RealtimeProviderPort` separates canonical commands/events/capabilities/errors from StepFun wire,
while a StepFun adapter composes the existing transport. A neutral Grounding deep module owns
request identity, immutable resolution, bounded single-flight cache and diagnostics projection;
`common.knowledge.kb_lock_guard` retains existing rule semantics. Both cuts use construction-time
server flags and never shadow or double-write.

**Tech Stack:** Python 3.12, asyncio, dataclasses/Protocol/StrEnum, FastAPI WebSocket, existing
`StepFunTransport`, pytest/pytest-asyncio, Ruff, mypy, CodeGraph and the repository canonical
quality gate. No new dependency or database migration.

## Global Constraints

- StepFun remains the only production realtime Provider; do not call or enable a paid/live
  Provider.
- Preserve REST, WebSocket event/close-code, binary audio, auth/admission, frozen snapshot,
  RuntimeGate, KB fail-closed, epoch, score/report idempotency and record-only Roleplay behavior.
- Provider credentials/raw wire/error text cannot enter Engine state, snapshots, diagnostics,
  logs or frontend events. Recognized errors keep existing safe messages; generic UNKNOWN raw text
  is intentionally replaced with `Realtime 服务返回错误` as the one approved safety difference.
- `REALTIME_PROVIDER_PORT_ENABLED` and `REALTIME_GROUNDING_MODULE_ENABLED` default to `true`, are
  read once during handler construction and are server-only.
- Exactly one selected Provider path, connection, Grounding module/cache, retrieval side effect,
  durable metric writer and message/score/report writer exists per session.
- Cache identity uses fields that exist: normalized query, top_k/filter, frozen
  `instruction_contract_hash` and sorted `knowledge_base_ids`; do not invent a KB revision field.
- Cache non-empty successful validated results only; TTL/max-entry bounded, deep-copy safe,
  same-key single-flight, owner-level timeout, async close, and no error/cancel/invalid/no-hit
  negative cache.
- Existing durable `last_query/recent_queries` fields remain for frozen snapshot compatibility and
  only the existing metric writer may mutate/persist them; Engine/frontend/log/new surfaces never
  receive raw query data.
- Do not move Roleplay/config/evaluation ownership, ORM models or frontend locality work into this
  Gate. Do not remove architecture exceptions until the actual import disappears.
- TDD is mandatory. Each task ends in a logical commit and independent spec/quality review.
- Preserve the unrelated user edit
  `docs/superpowers/plans/2026-07-10-readiness-decision-integrity.md`.

---

## File and responsibility map

Create:

- `backend/src/training_runtime/realtime/provider.py` — closed Provider DTOs, errors and Protocol.
- `backend/src/training_runtime/realtime/stepfun_codec.py` — the only raw StepFun command/event
  translation boundary.
- `backend/src/training_runtime/realtime/stepfun_provider.py` — Port adapter around the existing
  StepFun transport and connection.
- `backend/src/training_runtime/realtime/grounding_cache.py` — bounded TTL/single-flight result
  authority.
- `backend/src/training_runtime/realtime/grounding.py` — request/result/diagnostics and
  prepare/retrieve/decide/overlay/block orchestration.
- `backend/tests/fixtures/realtime/provider_contract_v1.json` — machine-readable Provider surface.
- `backend/tests/unit/test_realtime_provider_contract.py` — shared Fake/StepFun Port contracts.
- `backend/tests/unit/test_stepfun_provider_codec.py` — StepFun wire golden/mutation tests.
- `backend/tests/unit/test_realtime_grounding_module.py` — Grounding/cache/state matrix.
- `.trellis/spec/backend/realtime-provider-grounding.md` — executable Gate 3 contract.

Modify:

- `backend/src/training_runtime/realtime/__init__.py` — stable public exports only.
- `backend/src/training_runtime/stepfun_transport.py` — retain low-level mechanics; only add seams
  needed by the Adapter.
- `backend/src/common/config.py` — two validated default-on server flags.
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` — construction-time Port and
  Grounding selection/injection.
- `backend/src/sales_bot/websocket/stepfun_realtime_upstream.py` — canonical ProviderEvent/
  ProviderCommand consumption and one Grounding result path.
- `backend/src/sales_bot/websocket/grounding_decision_pipeline.py` — compatibility re-export only.
- `backend/src/sales_bot/websocket/stepfun_tool_execution.py` — remove result-cache ownership;
  keep call routing/dedupe/execution.
- `backend/src/sales_bot/websocket/stepfun_realtime_state.py` — typed selected runtime/decision
  projection declarations.
- `backend/src/presentation_coach/websocket/presentation_stepfun_realtime_handler.py` — consume one
  Grounding resolution and project it into Engine state.
- focused unit/integration/E2E tests named below; authority docs and architecture policy only when
  repository truth changes.

---

### Task 1: Freeze the Provider vocabulary and neutral Port contract

**Files:**
- Create: `backend/tests/fixtures/realtime/provider_contract_v1.json`
- Create: `backend/src/training_runtime/realtime/provider.py`
- Create: `backend/tests/unit/test_realtime_provider_contract.py`
- Modify: `backend/src/training_runtime/realtime/__init__.py`

**Interfaces:**
- Consumes: Gate 2 `RealtimeSessionEngine` IDs/epoch and existing StepFun event inventory.
- Produces:

```python
class ProviderCapability(StrEnum):
    TEXT = "text"
    AUDIO_INPUT = "audio_input"
    AUDIO_OUTPUT = "audio_output"
    INPUT_TRANSCRIPTION = "input_transcription"
    FUNCTION_TOOLS = "function_tools"
    SERVER_VAD = "server_vad"
    HEALTH_CHECK = "health_check"
    RECONNECT = "reconnect"

class ProviderCommandKind(StrEnum):
    APPEND_AUDIO = "append_audio"
    COMMIT_AUDIO = "commit_audio"
    CLEAR_AUDIO = "clear_audio"
    CREATE_RESPONSE = "create_response"
    CANCEL_RESPONSE = "cancel_response"
    CREATE_CONVERSATION_ITEM = "create_conversation_item"
    TOOL_OUTPUT = "tool_output"

class ProviderEventKind(StrEnum):
    SESSION_READY = "session_ready"
    INPUT_AUDIO_COMMITTED = "input_audio_committed"
    CONVERSATION_ITEM = "conversation_item"
    TRANSCRIPTION_DELTA = "transcription_delta"
    TRANSCRIPTION_FINAL = "transcription_final"
    SPEECH_STARTED = "speech_started"
    SPEECH_STOPPED = "speech_stopped"
    RESPONSE_CREATED = "response_created"
    RESPONSE_TEXT_DELTA = "response_text_delta"
    RESPONSE_TRANSCRIPT_DELTA = "response_transcript_delta"
    RESPONSE_TRANSCRIPT_FINAL = "response_transcript_final"
    RESPONSE_AUDIO_DELTA = "response_audio_delta"
    THINKING_DELTA = "thinking_delta"
    THINKING_DONE = "thinking_done"
    FUNCTION_ARGUMENTS_DELTA = "function_arguments_delta"
    FUNCTION_ARGUMENTS_DONE = "function_arguments_done"
    RESPONSE_DONE = "response_done"
    ERROR = "error"
    UNKNOWN = "unknown"

class ProviderErrorCategory(StrEnum):
    AUTHENTICATION = "authentication"
    QUOTA = "quota"
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"
    PROTOCOL = "protocol"
    BACKPRESSURE = "backpressure"
    DISCONNECTED = "disconnected"

class ProviderErrorReason(StrEnum):
    INVALID_CREDENTIALS = "invalid_credentials"
    FORBIDDEN = "forbidden"
    QUOTA_EXHAUSTED = "quota_exhausted"
    RATE_LIMITED = "rate_limited"
    ASR_UNAVAILABLE = "asr_unavailable"
    VOICE_UNAVAILABLE = "voice_unavailable"
    IDLE_TIMEOUT = "idle_timeout"
    UPSTREAM_UNAVAILABLE = "upstream_unavailable"
    INVALID_EVENT = "invalid_event"
    CONNECTION_CLOSED = "connection_closed"
    BACKPRESSURE_LIMIT = "backpressure_limit"
    UNKNOWN = "unknown"

@dataclass(frozen=True, slots=True)
class RealtimeProviderCapabilities:
    supported: frozenset[ProviderCapability]
    input_audio_formats: tuple[str, ...] | None = None
    output_audio_formats: tuple[str, ...] | None = None

@dataclass(frozen=True, slots=True)
class RealtimeProviderSessionConfig:
    model: str
    voice: str
    temperature: float
    input_audio_format: str
    output_audio_format: str
    modalities: tuple[str, ...]
    turn_detection: Mapping[str, JsonValue] | None
    input_transcription_enabled: bool
    input_transcription_language: str
    input_transcription_model: str
    instructions: str
    tools: tuple[Mapping[str, JsonValue], ...]

@dataclass(frozen=True, slots=True)
class ProviderSendResult:
    accepted: bool
    error_category: ProviderErrorCategory | None = None
    error_reason: ProviderErrorReason | None = None

@dataclass(frozen=True, slots=True)
class ProviderHealthResult:
    healthy: bool
    error_category: ProviderErrorCategory | None = None
    error_reason: ProviderErrorReason | None = None

@dataclass(frozen=True, slots=True)
class ProviderBackpressureResult:
    accepted: bool
    error_reason: ProviderErrorReason | None = None

class RealtimeProviderError(RuntimeError):
    category: ProviderErrorCategory
    reason: ProviderErrorReason
    retryable: bool

@dataclass(frozen=True, slots=True)
class ProviderCommand:
    kind: ProviderCommandKind
    data: Mapping[str, JsonValue]

@dataclass(frozen=True, slots=True)
class ProviderEvent:
    kind: ProviderEventKind
    provider_event_type: str
    connection_epoch: int
    request_id: int | None = None
    response_id: str | None = None
    stream_id: str | None = None
    call_id: str | None = None
    event_id: str | None = None
    turn_id: str | None = None
    timestamp_ms: float | None = None
    duration_ms: float | None = None
    data: Mapping[str, JsonValue] = field(default_factory=dict)
    error_category: ProviderErrorCategory | None = None
    error_reason: ProviderErrorReason | None = None

class RealtimeProviderPort(Protocol):
    @property
    def capabilities(self) -> RealtimeProviderCapabilities: ...
    async def connect(self, config: RealtimeProviderSessionConfig) -> None: ...
    async def send(self, command: ProviderCommand) -> ProviderSendResult: ...
    async def receive(self, *, connection_epoch: int) -> ProviderEvent: ...
    async def check_health(self, *, timeout_seconds: float | None = None) -> ProviderHealthResult: ...
    def decide_backpressure(self, command: ProviderCommand, *, pending_bytes: int) -> ProviderBackpressureResult: ...
    async def close(self) -> None: ...
```

- [ ] **Step 1: Write the inventory/validation tests first**

Tests must load `provider_contract_v1.json` whose rows map raw StepFun type -> canonical kind ->
required/optional fields -> production consumers -> exact tests. Assert exact enum parity; thinking,
assistant transcript final, input-audio committed, normalized response.done function outputs,
emotion timing and ASR/voice/idle-timeout reasons; strict scalar/container validation; immutable
copies; no numeric coercion; redacted `repr`; capability mismatch; and a local Fake implementing
every Port method.

- [ ] **Step 2: Run Red**

```bash
cd backend
.venv/bin/python -m pytest -c pyproject.toml -o addopts=--import-mode=importlib \
  tests/unit/test_realtime_provider_contract.py -q
```

Expected: collection/import failure because `training_runtime.realtime.provider` does not exist.

- [ ] **Step 3: Implement the closed DTO/Protocol module**

Define a local recursive `FrozenJsonMapping`/tuple freeze in
`training_runtime.realtime.provider`, with Mapping semantics and `__deepcopy__` returning the
immutable value; do not use `MappingProxyType` or Sales-owned `FrozenDict`. Define `JsonValue`
recursively without `Any`; reject unknown fields per command/event kind. Credential, endpoint and
raw error text are not DTO fields. `RealtimeProviderSessionConfig.required_capabilities()` returns
the requested set. Unknown audio-format capability is `None`, not an invented allowlist/limit.

- [ ] **Step 4: Run Green and static checks**

```bash
cd backend
.venv/bin/python -m pytest -c pyproject.toml -o addopts=--import-mode=importlib \
  tests/unit/test_realtime_provider_contract.py tests/unit/test_realtime_session_engine.py -q
.venv/bin/ruff check src/training_runtime/realtime tests/unit/test_realtime_provider_contract.py
.venv/bin/mypy src/training_runtime/realtime
```

Expected: all pass; no `Any` on the Port boundary and no secret-bearing field.

- [ ] **Step 5: Commit**

```bash
git add backend/src/training_runtime/realtime/provider.py \
  backend/src/training_runtime/realtime/__init__.py \
  backend/tests/fixtures/realtime/provider_contract_v1.json \
  backend/tests/unit/test_realtime_provider_contract.py
git diff --cached --name-only
git commit -m "feat(realtime): define provider port contract"
```

---

### Task 2: Implement StepFun codec and Provider Adapter

**Files:**
- Create: `backend/src/training_runtime/realtime/stepfun_codec.py`
- Create: `backend/src/training_runtime/realtime/stepfun_provider.py`
- Create: `backend/tests/unit/test_stepfun_provider_codec.py`
- Modify: `backend/src/training_runtime/stepfun_transport.py`
- Modify: `backend/tests/unit/test_stepfun_transport.py`
- Modify: `backend/tests/unit/test_stepfun_payload_snapshots.py`
- Modify: `backend/tests/unit/test_realtime_provider_contract.py`

**Interfaces:**
- Consumes: Task 1 Provider DTOs/Protocol and existing `StepFunTransport` results.
- Produces:

```python
class StepFunEventCodec:
    def encode_command(self, command: ProviderCommand) -> dict[str, JsonValue]: ...
    def decode_event(self, raw: str | bytes, *, connection_epoch: int) -> ProviderEvent: ...

class StepFunRealtimeProvider(RealtimeProviderPort):
    def __init__(
        self,
        *,
        api_key: str,
        url: str,
        transport: StepFunTransport | None = None,
        codec: StepFunEventCodec | None = None,
    ) -> None: ...
```

- [ ] **Step 1: Add golden codec/adapter failing tests**

Cover every inventory command/event, alternate transcript payloads already accepted by current
extractors, response/function IDs, bytes-vs-text, unknown event, malformed JSON/non-object payload,
StepFun 401/402/403/429 mapping, send failure, health timeout, backpressure and idempotent close.
Assert raw API key/URL/error body never appears in Event/repr/diagnostics.

- [ ] **Step 2: Run Red**

```bash
cd backend
.venv/bin/python -m pytest -c pyproject.toml -o addopts=--import-mode=importlib \
  tests/unit/test_stepfun_provider_codec.py tests/unit/test_realtime_provider_contract.py -q
```

Expected: missing codec/adapter imports.

- [ ] **Step 3: Implement codec and adapter by composing existing transport**

Do not duplicate endpoint/auth/send/health/backpressure logic. Adapter owns its connected socket;
constructor freezes credential/endpoint, while `connect(config)` validates capabilities, uses
`config.model`, opens the socket and sends exactly one encoded session update. There is no
`CONFIGURE` command. `receive` calls socket `recv` and decodes inside the adapter. Convert transport
failures to category+reason. Recognized reasons retain exact safe messages; UNKNOWN uses the fixed
fallback and never transports arbitrary raw text.

- [ ] **Step 4: Run Green and compatibility snapshots**

```bash
cd backend
.venv/bin/python -m pytest -c pyproject.toml -o addopts=--import-mode=importlib \
  tests/unit/test_stepfun_provider_codec.py tests/unit/test_realtime_provider_contract.py \
  tests/unit/test_stepfun_transport.py tests/unit/test_stepfun_payload_snapshots.py \
  tests/unit/test_stepfun_upstream_router.py -q
.venv/bin/ruff check src/training_runtime tests/unit/test_stepfun_provider_codec.py
.venv/bin/mypy src/training_runtime
```

Expected: StepFun payload snapshots byte-for-byte unchanged.

- [ ] **Step 5: Commit**

```bash
git add backend/src/training_runtime/realtime/stepfun_codec.py \
  backend/src/training_runtime/realtime/stepfun_provider.py \
  backend/src/training_runtime/stepfun_transport.py \
  backend/tests/unit/test_stepfun_provider_codec.py \
  backend/tests/unit/test_realtime_provider_contract.py backend/tests/unit/test_stepfun_transport.py \
  backend/tests/unit/test_stepfun_payload_snapshots.py
git diff --cached --name-only
git commit -m "feat(realtime): adapt stepfun to provider port"
```

---

### Task 3: Switch the shared production runtime through the Port

**Files:**
- Modify: `backend/src/common/config.py`
- Modify: `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
- Modify: `backend/src/sales_bot/websocket/stepfun_realtime_upstream.py`
- Modify: `backend/src/sales_bot/websocket/stepfun_realtime_state.py`
- Modify: `backend/src/presentation_coach/websocket/presentation_stepfun_realtime_handler.py`
- Modify: `backend/tests/unit/test_stepfun_realtime_handler.py`
- Modify: `backend/tests/unit/test_stepfun_realtime_upstream.py`
- Modify: `backend/tests/unit/test_stepfun_upstream_router.py`
- Modify: `backend/tests/unit/test_stepfun_tts_asr_contracts.py`
- Modify: `backend/tests/unit/test_stepfun_realtime_persistence.py`
- Modify: `backend/tests/unit/test_stepfun_realtime_p0_slice.py`
- Modify: `backend/tests/unit/test_ai_quality_event_inventory.py`
- Modify: `backend/tests/unit/test_presentation_realtime_engine_handler.py`
- Modify: `backend/tests/unit/test_training_runtime_plugins.py`
- Modify: `backend/tests/integration/test_sales_realtime_reconnect_flow.py`
- Modify: `backend/tests/integration/test_emotion_flow.py`
- Modify: `backend/tests/integration/test_thinking_scoring_flow.py`
- Modify: `backend/tests/integration/test_websocket_status_contract.py`

**Interfaces:**
- Consumes: `RealtimeProviderPort`, `StepFunRealtimeProvider`, canonical commands/events.
- Produces: default-on construction-time Provider selection and sanitized diagnostics.

- [ ] **Step 1: Write rollout and differential tests**

Add tests for flag unset true; normalized truthy/falsy; unknown value fail-safe Legacy false;
read-once semantics; one selected object; no shadow
connection, Fake Provider driving connect/text/audio/tool/response/reconnect, capability mismatch
before socket connect, and the 2x2 Presentation Engine/Provider matrix. Mutation probes must fail if
event order, persistence, epoch or tool follow-up changes.

- [ ] **Step 2: Run Red**

```bash
cd backend
.venv/bin/python -m pytest -c pyproject.toml -o addopts=--import-mode=importlib \
  tests/unit/test_stepfun_realtime_handler.py tests/unit/test_stepfun_realtime_upstream.py \
  tests/unit/test_presentation_realtime_engine_handler.py \
  tests/unit/test_training_runtime_plugins.py -q
```

Expected: new default selection and canonical event assertions fail on raw transport path.

- [ ] **Step 3: Implement Branch by Abstraction**

Extend `StepFunRealtimeSharedHandler.__init__` with an injected `provider_factory` and one frozen
selection boolean. Port path uses `connect/send/receive/check_health/decide_backpressure/close` and
canonical events; Legacy path preserves current `StepFunTransport` and raw receive methods. Keep
existing `_send_upstream` and `_handle_upstream_event` names only as compatibility façades that
construct/consume canonical DTOs on the new path. Do not put Provider selection in the client or
re-read settings during reconnect. Presentation consumes provider-neutral behavior through the
inherited compatibility adapter/local Protocol; do not add a static `presentation_coach ->
training_runtime` import absent from architecture policy.

- [ ] **Step 4: Run Green, reconnect and architecture checks**

```bash
cd backend
.venv/bin/python -m pytest -c pyproject.toml -o addopts=--import-mode=importlib \
  tests/unit/test_stepfun_realtime_handler.py tests/unit/test_stepfun_realtime_upstream.py \
  tests/unit/test_stepfun_upstream_router.py tests/unit/test_stepfun_tts_asr_contracts.py \
  tests/unit/test_stepfun_realtime_persistence.py tests/unit/test_stepfun_realtime_p0_slice.py \
  tests/unit/test_ai_quality_event_inventory.py \
  tests/unit/test_presentation_realtime_engine_handler.py \
  tests/unit/test_presentation_stepfun_realtime_handler.py \
  tests/unit/test_training_runtime_plugins.py \
  tests/integration/test_sales_realtime_reconnect_flow.py \
  tests/integration/test_emotion_flow.py tests/integration/test_thinking_scoring_flow.py \
  tests/integration/test_websocket_status_contract.py -q
.venv/bin/ruff check src/common/config.py src/training_runtime src/sales_bot/websocket \
  src/presentation_coach/websocket
.venv/bin/mypy src
.venv/bin/python scripts/architecture_dependency_guard.py --check
```

Expected: no wire/persistence/epoch mutation; architecture policy satisfied.

- [ ] **Step 5: Commit**

```bash
git add backend/src/common/config.py \
  backend/src/sales_bot/websocket/stepfun_realtime_handler.py \
  backend/src/sales_bot/websocket/stepfun_realtime_upstream.py \
  backend/src/sales_bot/websocket/stepfun_realtime_state.py \
  backend/src/presentation_coach/websocket/presentation_stepfun_realtime_handler.py \
  backend/tests/unit/test_stepfun_realtime_handler.py \
  backend/tests/unit/test_stepfun_realtime_upstream.py \
  backend/tests/unit/test_stepfun_upstream_router.py \
  backend/tests/unit/test_stepfun_tts_asr_contracts.py \
  backend/tests/unit/test_stepfun_realtime_persistence.py \
  backend/tests/unit/test_stepfun_realtime_p0_slice.py \
  backend/tests/unit/test_ai_quality_event_inventory.py \
  backend/tests/unit/test_presentation_realtime_engine_handler.py \
  backend/tests/unit/test_training_runtime_plugins.py \
  backend/tests/integration/test_sales_realtime_reconnect_flow.py \
  backend/tests/integration/test_emotion_flow.py \
  backend/tests/integration/test_thinking_scoring_flow.py \
  backend/tests/integration/test_websocket_status_contract.py
git diff --cached --name-only
git commit -m "refactor(realtime): route sessions through provider port"
```

---

### Task 4: Build the neutral Grounding result/cache deep module

**Files:**
- Create: `backend/src/training_runtime/realtime/grounding_cache.py`
- Create: `backend/src/training_runtime/realtime/grounding.py`
- Create: `backend/tests/unit/test_realtime_grounding_module.py`
- Modify: `backend/src/training_runtime/realtime/__init__.py`
- Modify: `backend/src/common/knowledge/kb_lock_guard.py`
- Modify: `backend/tests/unit/common/test_kb_lock_guard.py`
- Modify: `backend/tests/unit/test_grounding_decision_pipeline.py`

**Interfaces:**
- Consumes: existing `KbLockDecision`, `RetrievalGroundingDecision` and common KB helpers.
- Produces:

```python
@dataclass(frozen=True, slots=True)
class GroundingRequest:
    decision_id: str
    query: str
    frozen_policy_hash: str
    knowledge_base_ids: tuple[str, ...]
    top_k: int
    metadata_filter: Mapping[str, JsonValue] = field(default_factory=dict)

class GroundingOutcome(StrEnum):
    READY = "ready"
    BLOCKED = "blocked"
    DEGRADED = "degraded"
    SKIPPED = "skipped"

class GroundingMode(StrEnum):
    GROUNDED = "grounded"
    BLOCKED = "blocked"
    DEGRADED = "degraded"
    SKIPPED = "skipped"
    UNRESTRICTED = "unrestricted"
    KB_LOCK = "kb_lock"
    NOT_APPLICABLE = "not_applicable"

class GroundingCacheDisposition(StrEnum):
    HIT = "hit"
    MISS = "miss"
    SHARED = "shared"
    BYPASS = "bypass"

@dataclass(frozen=True, slots=True)
class GroundingCacheStats:
    hit_count: int
    miss_count: int
    shared_count: int
    bypass_count: int
    eviction_count: int
    cache_size: int
    inflight_count: int

@dataclass(frozen=True, slots=True)
class GroundingDiagnostics:
    schema_version: int
    status: str
    reason_code: str
    source: str
    mode: str
    degraded: bool
    blocked: bool
    cache_disposition: GroundingCacheDisposition
    result_count: int
    duration_ms: float

@dataclass(frozen=True, slots=True)
class GroundingCitation:
    knowledge_base_id: str
    knowledge_base_name: str
    document_title: str
    snippet: str
    claim: str
    score: float | None = None

@dataclass(frozen=True, slots=True)
class GroundingEvidence:
    citations: tuple[GroundingCitation, ...]
    rewritten_queries: tuple[str, ...]
    answerability: str
    source_status: str
    retrieval_mode: str

@dataclass(frozen=True, slots=True)
class GroundingRetrievalResult:
    status: str
    result_count: int
    retrieval_mode: str
    evidence: GroundingEvidence
    diagnostics: GroundingDiagnostics
    error_reason: str | None = None

@dataclass(frozen=True, slots=True)
class GroundingDecisionResult:
    decision_id: str
    frozen_policy_hash: str
    outcome: GroundingOutcome
    mode: GroundingMode
    allow_generation: bool
    grounding_context: str
    blocked_response: str
    output_guard_required: bool
    evidence: GroundingEvidence
    cache_disposition: GroundingCacheDisposition
    diagnostics: GroundingDiagnostics

class GroundingRetrieverPort(Protocol):
    async def __call__(self, request: GroundingRequest) -> GroundingRetrievalResult: ...

class RealtimeGroundingRuntime(Protocol):
    async def prepare(self, request: GroundingRequest, *, policy: Mapping[str, JsonValue]) -> GroundingDecisionResult: ...
    async def close(self) -> None: ...

class GroundingRetrievalCache:
    def __init__(
        self,
        *,
        ttl_seconds: float,
        max_entries: int,
        timeout_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None: ...
    async def get_or_retrieve(
        self,
        request: GroundingRequest,
        retriever: GroundingRetrieverPort,
    ) -> GroundingRetrievalResult: ...
    def stats(self) -> GroundingCacheStats: ...
    async def close(self) -> None: ...

class RealtimeGroundingModule:
    def __init__(
        self,
        *,
        retriever: GroundingRetrieverPort,
        cache: GroundingRetrievalCache,
        kb_lock_evaluator: Callable[..., Awaitable[KbLockDecision]] = evaluate_kb_lock_decision,
    ) -> None: ...
    async def prepare(self, request: GroundingRequest, *, policy: Mapping[str, JsonValue]) -> GroundingDecisionResult: ...
    async def retrieve(self, request: GroundingRequest) -> GroundingRetrievalResult: ...
    def decide(self, request: GroundingRequest, retrieval: GroundingRetrievalResult, *, policy: Mapping[str, JsonValue]) -> GroundingDecisionResult: ...
    def build_overlay(self, result: GroundingDecisionResult) -> str: ...
    def build_blocked_response(self, result: GroundingDecisionResult) -> str: ...
    def apply_output_guard(self, text: str, result: GroundingDecisionResult) -> str: ...
    async def close(self) -> None: ...
```

`common.knowledge.kb_lock_guard` defines its own local callable Protocol matching the existing
keyword-only search seam; it must not import `training_runtime`:

```python
class KbLockRetriever(Protocol):
    async def __call__(
        self,
        *,
        arguments_obj: dict[str, Any],
        effective_policy: dict[str, Any],
        session_factory: Callable[[], Any],
        knowledge_service_cls: Callable[[Any], Any],
        record_metric: Callable[..., Awaitable[None]],
    ) -> dict[str, Any]: ...
```

- [ ] **Step 1: Write complete result/cache failing matrix**

Test strict request/evidence validation and exact citation/rewritten-query legacy round trip;
canonical hashed key; frozen policy/KB isolation; deep copy; TTL;
deterministic LRU max entries; non-empty-success-only cache; no error/timeout/cancel/invalid/empty negative
cache; concurrent same-key single-flight; owner-level timeout; waiter cancellation shield; async
close cancel+await; no orphan/late cache/late metric/projection; different keys parallel; cache stats;
strict KB/no KB/not-ready/partial/grounded parity; and citations driving output guard while Engine
diagnostics contain closed scalars only. Cover the full existing Engine mode vocabulary, including
`kb_lock`, `unrestricted`, and `not_applicable`.

- [ ] **Step 2: Run Red**

```bash
cd backend
.venv/bin/python -m pytest -c pyproject.toml -o addopts=--import-mode=importlib \
  tests/unit/test_realtime_grounding_module.py -q
```

Expected: missing Grounding modules.

- [ ] **Step 3: Implement minimal deep modules**

Use `OrderedDict` + monotonic clock for bounded TTL and an in-flight task map keyed by digest. Put
the configured timeout inside the shared owner coroutine; shield waiters; store only non-empty
validated success; always remove owner entries in `finally`; `close()` cancels/awaits every owner and
blocks new calls. Store/return deep copies. Extend `evaluate_kb_lock_decision` with an optional
retriever seam whose default preserves current direct search; the Module injects its cache-backed
retriever. Keep free-form citation evidence separate from closed diagnostics and preserve current
thresholds/Chinese user messages.

- [ ] **Step 4: Run Green and common KB parity**

```bash
cd backend
.venv/bin/python -m pytest -c pyproject.toml -o addopts=--import-mode=importlib \
  tests/unit/test_realtime_grounding_module.py tests/unit/test_grounding_decision_pipeline.py \
  tests/unit/common/test_kb_lock_guard.py -q
.venv/bin/ruff check src/training_runtime/realtime tests/unit/test_realtime_grounding_module.py
.venv/bin/mypy src/training_runtime/realtime
```

- [ ] **Step 5: Commit**

```bash
git add backend/src/training_runtime/realtime/grounding.py \
  backend/src/training_runtime/realtime/grounding_cache.py \
  backend/src/training_runtime/realtime/__init__.py \
  backend/src/common/knowledge/kb_lock_guard.py \
  backend/tests/unit/test_realtime_grounding_module.py \
  backend/tests/unit/test_grounding_decision_pipeline.py \
  backend/tests/unit/common/test_kb_lock_guard.py
git diff --cached --name-only
git commit -m "feat(realtime): centralize grounding decisions and cache"
```

---

### Task 5: Cut prefetch and tool retrieval to one Grounding authority

**Files:**
- Modify: `backend/src/common/config.py`
- Modify: `backend/src/sales_bot/websocket/grounding_decision_pipeline.py`
- Create: `backend/src/sales_bot/websocket/legacy_grounding_runtime.py`
- Modify: `backend/src/sales_bot/websocket/stepfun_tool_execution.py`
- Modify: `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
- Modify: `backend/src/sales_bot/websocket/stepfun_realtime_upstream.py`
- Modify: `backend/src/sales_bot/websocket/stepfun_realtime_state.py`
- Modify: `backend/tests/unit/test_stepfun_tool_execution.py`
- Modify: `backend/tests/unit/test_stepfun_realtime_handler.py`
- Modify: `backend/tests/unit/test_stepfun_realtime_upstream.py`
- Modify: `backend/tests/unit/test_grounding_decision_pipeline.py`

**Interfaces:**
- Consumes: `RealtimeGroundingModule` and its immutable result/cache.
- Produces: one selected Grounding path and a cache-free Tool execution module.

- [ ] **Step 1: Add default/rollback and one-retrieval failing tests**

Assert Grounding flag normalization/read-once, one Module/cache, strict/prefetch/tool non-empty
cacheable success with identical frozen request executes the low-level retriever once, inverse order
also once, concurrent calls single-flight, different frozen policy/KB scope misses, sequential
no-hit executes twice, and Legacy false preserves current behavior. Assert
`StepFunToolExecutionModule` no longer exposes or stores result-cache state on the default path.

- [ ] **Step 2: Run Red**

```bash
cd backend
.venv/bin/python -m pytest -c pyproject.toml -o addopts=--import-mode=importlib \
  tests/unit/test_stepfun_tool_execution.py tests/unit/test_grounding_decision_pipeline.py \
  tests/unit/test_stepfun_realtime_handler.py tests/unit/test_stepfun_realtime_upstream.py -q
```

- [ ] **Step 3: Integrate one Module and remove duplicate cache ownership**

Construct Grounding selection once. The new low-level retriever calls
`StepFunToolExecutionModule.execute_tool` without caching; both prefetch and function-tool routes
call `RealtimeGroundingModule.retrieve/decide`. Remove result-cache ownership from Tool execution.
Move the exact old Pipeline + result-cache behavior into named `LegacyRealtimeGroundingAdapter` and
`LegacyToolResultCache`, constructed only when flag false and retained to Gate 6. Keep call-id/turn
dedupe and tool response unchanged. Session close always awaits selected Grounding runtime close.

- [ ] **Step 4: Run Green and behavior matrix**

```bash
cd backend
.venv/bin/python -m pytest -c pyproject.toml -o addopts=--import-mode=importlib \
  tests/unit/test_realtime_grounding_module.py tests/unit/test_grounding_decision_pipeline.py \
  tests/unit/test_stepfun_tool_execution.py tests/unit/test_stepfun_realtime_handler.py \
  tests/unit/test_stepfun_realtime_upstream.py tests/unit/common/test_kb_lock_guard.py -q
.venv/bin/ruff check src/sales_bot/websocket src/training_runtime/realtime
.venv/bin/mypy src
```

- [ ] **Step 5: Commit**

```bash
git add backend/src/common/config.py \
  backend/src/sales_bot/websocket/grounding_decision_pipeline.py \
  backend/src/sales_bot/websocket/legacy_grounding_runtime.py \
  backend/src/sales_bot/websocket/stepfun_tool_execution.py \
  backend/src/sales_bot/websocket/stepfun_realtime_handler.py \
  backend/src/sales_bot/websocket/stepfun_realtime_upstream.py \
  backend/src/sales_bot/websocket/stepfun_realtime_state.py \
  backend/src/training_runtime/realtime/grounding.py \
  backend/src/training_runtime/realtime/grounding_cache.py \
  backend/tests/unit/test_stepfun_tool_execution.py \
  backend/tests/unit/test_grounding_decision_pipeline.py \
  backend/tests/unit/test_stepfun_realtime_handler.py \
  backend/tests/unit/test_stepfun_realtime_upstream.py \
  backend/tests/unit/test_realtime_grounding_module.py
git diff --cached --name-only
git commit -m "refactor(realtime): use one grounding retrieval authority"
```

---

### Task 6: Unify Grounding projections, diagnostics, timeouts and metrics

**Files:**
- Modify: `backend/src/training_runtime/realtime/grounding.py`
- Modify: `backend/src/training_runtime/realtime/state.py`
- Modify: `backend/src/presentation_coach/websocket/presentation_stepfun_realtime_handler.py`
- Modify: `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
- Modify: `backend/src/sales_bot/websocket/stepfun_realtime_upstream.py`
- Modify: `backend/src/sales_bot/websocket/components/stepfun_runtime_metrics_helpers.py`
- Modify: `backend/tests/unit/test_realtime_session_engine.py`
- Modify: `backend/tests/unit/test_presentation_realtime_engine_handler.py`
- Modify: `backend/tests/unit/test_stepfun_realtime_handler.py`
- Modify: `backend/tests/contract/test_practice_evidence_contract.py`

**Interfaces:**
- Consumes: immutable `GroundingDecisionResult`.
- Produces: one closed/redacted mapper feeding compatibility fields, Engine state and durable metric
  writer.

- [ ] **Step 1: Write projection/timeout/metrics failing tests**

For ready/blocked/degraded/timeout/error/partial, assert one result/evidence produces all three surfaces with
the same decision ID/outcome/cache status; existing top-level diagnostics and user messages remain;
Engine schema rejects citation/free text; legacy projection round-trips bounded
knowledge_base_id/name, document_title, snippet, claim, score and rewritten queries. A cache miss
invokes the low-level durable metric callback exactly once and the Module never calls it again; a
cache hit fabricates no durable event. Exact `hit/miss/shared/bypass` disposition remains on the
decision and legacy compatibility diagnostics. Engine schema v1 is not changed: project
`duration_ms` to `latency_ms`, project `hit/shared` to `cache_hit=true` and `miss/bypass` to
`cache_hit=false`, and use the existing hit/miss/count fields for aggregate counters.
Owner timeout/cancel/session close does not later overwrite the active decision. Engine/frontend/
log/new DTOs contain no raw query/token/prompt/transcript/provider error, while existing durable
`last_query/recent_queries` remain unchanged and single-writer. Include stale epoch and tool-followup.

- [ ] **Step 2: Run Red**

```bash
cd backend
.venv/bin/python -m pytest -c pyproject.toml -o addopts=--import-mode=importlib \
  tests/unit/test_realtime_session_engine.py \
  tests/unit/test_presentation_realtime_engine_handler.py \
  tests/unit/test_stepfun_realtime_handler.py \
  tests/contract/test_practice_evidence_contract.py -q
```

- [ ] **Step 3: Implement a single projection mapper**

Add `GroundingDecisionResult.to_engine_diagnostics()` and a compatibility projection with closed
status/reason/source/mode/error/fallback/cache fields. Handler assigns one `_grounding_result`;
the Engine mapper preserves diagnostics schema v1, maps `duration_ms -> latency_ms`, maps exact
cache disposition to the existing boolean/counter fields, and does not add a `cache_disposition`
Engine field. Exact disposition remains available only on the decision and legacy compatibility
diagnostics.
legacy `_latest_knowledge_answer_diagnostics`, pending context and blocked text become read-only
projections or narrow setters used only by the Legacy rollback. Presentation calls
`engine.resolve_grounding` from the same result without adding a Presentation import of
`training_runtime`. The low-level searcher's existing durable callback remains the only
query-bearing mutation. Module/cache outcomes do not call it and never persist independently; they
remain closed decision diagnostics.

- [ ] **Step 4: Run Green and broad realtime regression**

```bash
cd backend
.venv/bin/python -m pytest -c pyproject.toml -o addopts=--import-mode=importlib \
  tests/unit/test_realtime_session_engine.py tests/unit/test_realtime_grounding_module.py \
  tests/unit/test_presentation_realtime_engine_handler.py \
  tests/unit/test_presentation_stepfun_realtime_handler.py \
  tests/unit/test_stepfun_realtime_handler.py tests/unit/test_stepfun_realtime_upstream.py \
  tests/contract/test_practice_evidence_contract.py \
  tests/integration/test_sales_realtime_reconnect_flow.py -q
.venv/bin/ruff check src/training_runtime/realtime src/sales_bot/websocket \
  src/presentation_coach/websocket
.venv/bin/mypy src
```

- [ ] **Step 5: Commit**

```bash
git add backend/src/training_runtime/realtime/grounding.py \
  backend/src/training_runtime/realtime/state.py \
  backend/src/presentation_coach/websocket/presentation_stepfun_realtime_handler.py \
  backend/src/sales_bot/websocket/stepfun_realtime_handler.py \
  backend/src/sales_bot/websocket/stepfun_realtime_upstream.py \
  backend/src/sales_bot/websocket/components/stepfun_runtime_metrics_helpers.py \
  backend/tests/unit/test_realtime_session_engine.py \
  backend/tests/unit/test_presentation_realtime_engine_handler.py \
  backend/tests/unit/test_stepfun_realtime_handler.py \
  backend/tests/contract/test_practice_evidence_contract.py
git diff --cached --name-only
git commit -m "refactor(realtime): project one grounding decision"
```

---

### Task 7: Freeze rollout differential, architecture and executable documentation

**Files:**
- Modify: `backend/tests/unit/test_presentation_realtime_engine_handler.py`
- Modify: `backend/tests/unit/test_stepfun_realtime_handler.py`
- Modify: `backend/tests/e2e/test_websocket_flow.py`
- Create: `.trellis/spec/backend/realtime-provider-grounding.md`
- Modify: `.trellis/spec/backend/realtime-session-engine.md`
- Modify: `.trellis/spec/backend/index.md`
- Modify: `docs/architecture.md`
- Modify: `docs/adr/2026-07-10-modular-monolith-2-ai-native-governance.md`
- Modify: `docs/superpowers/specs/2026-07-10-modular-monolith-2-design.md`
- Modify: `docs/superpowers/plans/2026-07-10-modular-monolith-2-roadmap.md`
- Modify: `docs/architecture/module-dependency-policy.yaml` only if an import edge actually
  disappears.

**Interfaces:**
- Consumes: Tasks 1–6 public contracts and rollout diagnostics.
- Produces: machine-traceable Gate 3 completion evidence and executable Trellis contract.

- [ ] **Step 1: Add final differential and mutation tests**

Run Sales 2x2=4 and Presentation Engine/Provider/Grounding 2x2x2=8 selections. Compare downstream wire,
upstream StepFun wire, persistence, snapshot, Engine terminal state, grounding result/cache stats,
metric writes, reconnect epoch and score/report single writer. Mutation probes must fail for command,
event, decision, cache scope, metric or write changes. Keep the existing external Golden fixture
unchanged unless a true external contract change is separately approved; Gate 3 internal inventory
evidence uses exact `file::test_name` and semantic validation.

- [ ] **Step 2: Run focused Gate 3 verification**

```bash
cd backend
.venv/bin/python -m pytest -c pyproject.toml -o addopts=--import-mode=importlib \
  tests/unit/test_realtime_provider_contract.py tests/unit/test_stepfun_provider_codec.py \
  tests/unit/test_realtime_grounding_module.py tests/unit/test_realtime_session_engine.py \
  tests/unit/test_grounding_decision_pipeline.py tests/unit/test_stepfun_tool_execution.py \
  tests/unit/test_stepfun_realtime_handler.py tests/unit/test_stepfun_realtime_upstream.py \
  tests/unit/test_presentation_realtime_engine_handler.py \
  tests/unit/test_presentation_stepfun_realtime_handler.py \
  tests/contract/test_practice_evidence_contract.py \
  tests/integration/test_sales_realtime_reconnect_flow.py tests/e2e/test_websocket_flow.py -q
.venv/bin/python scripts/architecture_dependency_guard.py --check
.venv/bin/ruff check src tests/unit/test_realtime_provider_contract.py \
  tests/unit/test_stepfun_provider_codec.py tests/unit/test_realtime_grounding_module.py
.venv/bin/mypy src
```

- [ ] **Step 3: Write the executable 7-section Trellis contract and truthful authority docs**

Document Scope/Trigger, Signatures, Contracts, Validation & Error Matrix, Good/Base/Bad, Tests
Required and Wrong vs Correct. State current facts only. If `presentation_coach -> sales_bot` still
exists, keep the exception and explicitly defer full retirement; if a target disappeared, update the
policy in the same commit and prove no stale exception.

- [ ] **Step 4: Run design artifact audit and docs checks**

Trace every referenced type/flag/test/import to source, verify no invented knowledge revision,
ensure plan/PRD/spec terminology matches, run `git diff --check`, architecture guard, and grep for
unchecked implementation-plan boxes after marking completed work.

- [ ] **Step 5: Commit**

```bash
git add backend/tests/unit/test_presentation_realtime_engine_handler.py \
  backend/tests/unit/test_stepfun_realtime_handler.py \
  backend/tests/e2e/test_websocket_flow.py \
  .trellis/spec/backend/realtime-provider-grounding.md \
  .trellis/spec/backend/realtime-session-engine.md .trellis/spec/backend/index.md \
  docs/architecture.md docs/architecture/module-dependency-policy.yaml \
  docs/adr/2026-07-10-modular-monolith-2-ai-native-governance.md \
  docs/superpowers/specs/2026-07-10-modular-monolith-2-design.md \
  docs/superpowers/plans/2026-07-10-modular-monolith-2-roadmap.md \
  docs/superpowers/plans/2026-07-11-gate-3-provider-grounding.md
git diff --cached --name-only
git commit -m "docs(realtime): codify provider and grounding authority"
```

---

### Task 8: Whole-branch review, canonical gate and Trellis closure

**Files:**
- Modify only when verification reveals a real defect.
- Update: Gate 3 PRD evidence, authority exact counts, task notes, archive and journal.

**Interfaces:**
- Consumes: complete Gate 3 branch diff from its recorded base commit.
- Produces: Critical/Important finding=0, fresh release evidence and archived Trellis task.

- [ ] **Step 1: Run CodeGraph impact/affected and independent whole-branch review**

Record impact for Provider Port, StepFun Adapter/Codec, Grounding Module/cache, shared handler and
Presentation adapter. Generate a review package from Gate 3 base to HEAD and separately hand the
reviewer the active Trellis PRD/research/context paths, which remain Trellis-managed until archive.
Fix all Critical and Important findings with TDD and re-review until Approved/finding=0.

- [ ] **Step 2: Run independent `trellis-check`**

The check agent reads PRD, implement/check JSONL and every applicable spec; it fixes spec,
cross-layer, reuse, import, diagnostics and test-quality findings. Re-run focused checks after any
fix until finding=0.

- [ ] **Step 3: Run one clean-start canonical gate**

```bash
cd /home/dev/work/sales-training-qoder
LD_LIBRARY_PATH="/home/dev/work/sales-training-qoder/.sisyphus/playwright-libs/root/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
  bash scripts/critical-quality-gate.sh
```

Expected: natural exit 0 and final `Critical quality gate passed`; no retry, result splicing, new
skip/xfail or gate-script weakening. Restore generated audit/NFR artifacts and delete new UUID
screenshots before committing docs. If a production fix follows, repeat from clean start.

- [ ] **Step 4: Close documentation and Trellis state**

Write exact counts/coverage, mark all plan/PRD criteria complete, run `trellis-update-spec`, validate
context JSONL, commit any final authority-only evidence, archive
`07-11-modular-monolith-2-gate-3` (its auto-commit captures task.json/PRD/research/context), then
record the journal in a separate auto-commit. The final worktree must contain only the pre-existing
Readiness user edit.

---

## Plan self-review

- Spec coverage: all roadmap Gate 3 packages (Port, StepFun codec, Fake contract, Grounding phases,
  duplicate cache deletion, timeout/fallback/diagnostics/metrics) map to Tasks 1–7; Task 8 owns
  independent closure.
- Type consistency: all later tasks consume names/signatures introduced in Tasks 1 and 4.
- Reference truth: `StepFunTransport`, handler methods, existing flags, frozen policy fields and
  tests were verified with CodeGraph/source. No nonexistent knowledge revision is referenced.
- Scope: Roleplay/config/evaluation/front-end/ORM compatibility work stays in Gates 4–6.
- Placeholder scan: no TBD/TODO/"similar to" steps; each task has exact files, Red/Green commands,
  implementation contract and commit boundary.
