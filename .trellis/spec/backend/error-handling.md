# Error Handling

> How errors are handled in this project.

---

## Overview

Business failures use **`Result[T]`** in services. HTTP APIs return JSON envelopes with **`trace_id`**. There are **multiple response paths** — know which field name applies (`error` vs `fallback`). The frontend must never show raw stack traces (Constitution: UX never interrupted).

Reference: `common/error_handling/result.py`, `common/api/response.py`, `common/error_handling/middleware.py`, `app_factory.py`.

---

## Error Types

### Result[T]

Defined in `common/error_handling/result.py`:

- `Result.ok(value)` — success wrapper.
- `Result.fail(fallback: str)` — failure with a **string code**, often bracketed: `"[SESSION_NOT_FOUND]"`, `"[HISTORY_FAILED]"`.
- Helpers: `is_success`, `unwrap_or()`, `map()`.

Used in services such as `common/analytics/history_service.py`, `curriculum_practice/services/learning_progress_service.py`.

### HTTP error codes

Fallback strings follow `[UPPER_SNAKE_OR_BRACKETED_CODE]` convention.

---

## Error Handling Patterns

### Service layer

```python
async def load_history(...) -> Result[HistoryPayload]:
    try:
        data = await fetch(...)
        return Result.ok(data)
    except SomeDomainError:
        return Result.fail("[HISTORY_FAILED]")
```

Prefer `Result.fail()` over raising for expected business failures.

### API layer (explicit business errors)

Use helpers from `common/api/response.py`:

- `success_response(data, trace_id=...)`
- `error_response(error_code, trace_id=..., message=...)`

These return **`error`** (not `fallback`) in the JSON body.

### Global handlers (two layers)

| Path | Handler | Response field | When |
|------|---------|----------------|------|
| Business API | `error_response()` | `error` | Expected failure from route code |
| HTTPException | `http_exception_handler` | `error`, `message`, `detail` | FastAPI HTTPException (common in admin) |
| Middleware | `ErrorHandlerMiddleware` | `fallback` | Only catches `RuntimeError`, `ValueError` |
| Unhandled | `global_exception_handler` | `fallback` | Any other `Exception` |

`ErrorHandlerMiddleware` does **not** catch all exceptions — most unhandled errors reach `global_exception_handler`.

Also see `common/api/server_error.py` / `server_error_response` for structured 5xx in some admin paths.

Special case: `RequestValidationError` on `/api/v1/prompt-templates` maps to `error_response("[PROMPT_DATA_INVALID]", ...)`.

---

## API Response Shapes

**Success (all paths):**
```json
{"success": true, "data": {...}, "trace_id": "..."}
```

**Business failure (`error_response`):**
```json
{"success": false, "error": "[ERROR_CODE]", "trace_id": "...", "data": null, "message": "..."}
```

**Degraded / unhandled (`fallback` from middleware or global handler):**
```json
{"success": false, "fallback": "[PLEASE_TRY_AGAIN]", "trace_id": "..."}
```

Contract tests: `backend/tests/contract/test_error_envelopes.py`.

## Scenario: ORM-backed write responses

### 1. Scope / Trigger

- Trigger: a FastAPI write route creates or updates an SQLAlchemy entity and returns
  fields from that entity.
- Scope: route response models, ORM-to-DTO mapping, transaction ordering, rollback,
  and generated OpenAPI.
- Why: FastAPI/Pydantic may fail while serializing an arbitrary ORM object after the
  handler has returned. If the route already committed, the client receives a 500
  even though the write succeeded and may create a duplicate when it retries.

### 2. Signatures

```python
@router.post(
    "/resources/{resource_id}/items",
    status_code=201,
    response_model=ItemResponse,
)
async def create_item(...) -> ItemResponse | JSONResponse: ...

class ItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
```

The response DTO must be an explicit Pydantic model with
`ConfigDict(from_attributes=True)` when it reads ORM attributes. Do not annotate an
ORM-returning route as `Any`.

### 3. Contracts

- Normalize and validate the request before constructing the ORM entity.
- Use this success order:
  `add -> flush -> refresh -> DTO model_validate -> commit -> return DTO`.
- The route decorator's `response_model` and the return annotation must describe the
  same public DTO. Internal ORM fields are not part of the API contract.
- SQLAlchemy failures must roll back before returning the module's normalized 5xx
  response.
- Regenerate committed OpenAPI after changing the response schema and require runtime
  parity.

### 4. Validation & Error Matrix

| Condition | Expected behavior |
|---|---|
| Request or domain validation fails before `flush` | Return the existing 4xx contract; no write |
| `flush`, `refresh`, or `commit` raises `SQLAlchemyError` | Roll back and return the stable module error code |
| DTO validation fails after `refresh` | Do not commit; let the failure be visible and the session roll back |
| DTO and ORM field types differ but are convertible | `model_validate` performs the conversion before commit |
| Runtime OpenAPI differs from committed schema | Contract parity check fails |

### 5. Good/Base/Bad Cases

- Good: a create route maps the refreshed entity to its public DTO before commit,
  commits, and returns the already validated DTO.
- Base: an expected database constraint failure rolls back and returns a stable error
  envelope without exposing the exception.
- Bad: a route commits and returns a SQLAlchemy object as `Any`, leaving the first
  response validation to FastAPI after the write is durable.

### 6. Tests Required

- Contract test: create a real parent fixture, require the exact success status, parse
  the response with the public DTO, and verify one matching persisted row.
- Permission test: an unauthorized caller receives 401/403 and creates no row.
- Failure-path unit or integration test: force a database failure and assert rollback,
  the stable error code, and no durable write.
- OpenAPI parity test: the success response references the public DTO schema.

### 7. Wrong vs Correct

#### Wrong

```python
@router.post("/items", status_code=201)
async def create_item(...) -> Any:
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item
```

#### Correct

```python
@router.post("/items", status_code=201, response_model=ItemResponse)
async def create_item(...) -> ItemResponse | JSONResponse:
    try:
        db.add(item)
        await db.flush()
        await db.refresh(item)
        response = ItemResponse.model_validate(item)
        await db.commit()
        return response
    except SQLAlchemyError as exc:
        await db.rollback()
        return build_server_error("[ITEM_CREATE_FAILED]", exc=exc)
```

---

## WebSocket Errors

- Auth / policy failures: close with defined codes (e.g. `sales_bot/websocket/router.py` — `4001`, `4003`, `4410` under `SALES_WS_AUTH_POLICY`).
- Runtime errors: handle inside handler; do not crash the whole session without a client-visible graceful state.
- Same principle: no unhandled stack traces to the H5 client.

Reference: `backend/src/sales_bot/AGENTS.md`.

## Scenario: WebSocket Send and Session-State Startup Failures

### 1. Scope / Trigger

- Trigger: WebSocket delivery and Redis-backed session snapshots are runtime infrastructure. Silent failure makes the UI believe a critical frame was delivered when it was not.
- Scope: `common.websocket.base_handler.ConnectionManager.send_json`, handler call sites, session-state startup in `common.websocket.session_state_service`, and lifespan health exposure.

### 2. Signatures

```python
@dataclass(frozen=True)
class WebSocketSendResult:
    success: bool
    skipped: bool = False
    message_type: str = "unknown"
    error_type: str | None = None
    error: str | None = None

async def ConnectionManager.send_json(...) -> WebSocketSendResult: ...
```

Environment keys:

- `SESSION_STATE_STARTUP_POLICY`: `required` (default), `optional`, or `disabled`.
- `SESSION_STATE_SNAPSHOT_ENABLED`: `true`/`false`; `false` explicitly disables snapshot storage.

### 3. Contracts

- `send_json` never reports success for missing sockets or send exceptions.
- Callers that need delivery semantics must inspect `result.success`; they must not rely on exceptions.
- `required` Redis startup policy is fail-fast.
- `optional` Redis startup policy degrades snapshot storage and exposes health as not ready/degraded.
- `disabled` policy or `SESSION_STATE_SNAPSHOT_ENABLED=false` disables snapshot writes intentionally and exposes the disabled reason.

### 4. Validation & Error Matrix

| Condition | Expected behavior |
|---|---|
| WebSocket is `None` | Return `success=false`, `skipped=true`, `error_type="MissingWebSocket"` |
| `websocket.send_json()` raises | Return `success=false`, log `websocket_send_failed`, increment send-failure and websocket-error metrics |
| Heartbeat/control send returns failure | Treat the connection as failed where the caller owns liveness |
| Redis ping fails with `required` | Startup raises a clear runtime error |
| Redis ping fails with `optional` | Startup continues with snapshot disabled/degraded health |
| Snapshot explicitly disabled | Runtime skips snapshot reads/writes without pretending Redis is connected |

### 5. Good/Base/Bad Cases

- Good: a failed heartbeat send returns `success=false`; liveness code unregisters the stale session and metrics identify the message type.
- Base: local development sets `SESSION_STATE_STARTUP_POLICY=optional` while Redis is down; realtime still runs without reconnect snapshots and health states why.
- Bad: `await websocket.send_json(...)` is wrapped in a broad `except` that only logs and returns `None`.

### 6. Tests Required

- Unit tests for `sent`, `skipped`, and failed send results.
- Call-site regression tests for heartbeat/control emitters that must react to `success=false`.
- Session-state startup tests for required, optional, and disabled policies.
- Observability tests asserting `/metrics` includes send failure / connection lifecycle counters.

### 7. Wrong vs Correct

#### Wrong

```python
await manager.send_json(websocket, {"type": "heartbeat"})
# caller assumes delivery because no exception was raised
```

#### Correct

```python
result = await manager.send_json(websocket, {"type": "heartbeat"})
if not result.success:
    await session_manager.unregister(session_id)
```

Delivery is explicit and testable.

---

## Known Mixed State (document reality)

- Some **admin** routes `raise HTTPException` (e.g. `admin/api/admin.py`, `admin/api/rag_profiles.py`).
- Other admin routes already use `success_response` / `error_response` (e.g. parts of `admin/api/config_bundles.py`).
- **New user-facing practice code** should prefer `Result` + `error_response`. Do not expand HTTPException in practice flows.

---

## Scenario: Newcomer learner activity errors (`learner_api._error`)

### 1. Scope / Trigger

- Trigger: learner submits audio / quiz / other activity evidence via `sales_trainer/orchestration/learner_api.py`.
- Scope: typed business errors vs unexpected exceptions; client-safe Chinese `message`; structured logs with `trace_id`.

### 2. Signatures

- `_error(exc, *, trace_id) -> JSONResponse`
- Business shapes: `NewcomerOrchestrationError`, `AudioSubmissionServiceError`, `MaterialServiceError`, `EffectiveAudioTrainingConfigError` (or duck-types with `code`/`message`/`status_code`).

### 3. Contracts

- Business errors: return original `code` + **client-safe** Chinese `message` + HTTP status; never forward env var names, secret keys, absolute paths, or raw `str(CosConfigError|OssConfigError)`.
- Unexpected errors: categorize into 上传失败 / 请求无效 / 服务暂不可用 / 通用失败; log `exc_info` + `trace_id` + `error_type` + truncated `exception_message`; response still includes `trace_id`.
- Frontend (`web/src/lib/api/client.ts`): prefer backend Chinese `message` over generic `API_ERROR_MESSAGE_MAP` when the message is already Chinese user copy.

### 4. Validation & Error Matrix

| Case | Client message | Log |
|---|---|---|
| Typed business error with safe Chinese message | Keep message | Normal |
| Typed business error whose message looks like env/config dump | Replace with safe Chinese fallback | `warning` with original server text |
| Unexpected upload-ish exception | 上传失败类中文 | `error` + `exc_info` |
| Unexpected other exception | 服务暂不可用 / 请重试 + `trace_id` | `error` + `exc_info` |

### 5. Good / Bad

- Good: COS not configured → learner sees「对象存储暂不可用…」, logs keep detail.
- Bad: `getattr(exc, "message", "训练操作失败，请重试。")` for all exceptions (hides root cause and may leak config strings).

### 6. Tests Required

- `backend/tests/unit/test_newcomer_learner_api_errors.py` — business passthrough, unsafe message scrub, unexpected categorization.
- Frontend: runner/client tests assert Chinese backend message is shown.

### 7. Wrong vs Correct

- Wrong: always return「训练操作失败，请重试」and skip `exc_info`.
- Correct: preserve actionable business messages; categorize unexpected failures; never leak COS/OSS env names to learners.

---

## Anti-Patterns

- Returning HTTP 500 with exception message body to the practice UI.
- Using `Result.unwrap()` on user-facing paths (can raise `ValueError`).
- `print()` for errors — use structlog (see Logging Guidelines).
- `raise HTTPException(500, detail=str(e))` in new practice/scenario code.
- Assuming all failures use the `error` field — check whether the path returns `fallback`.
- Collapsing all learner activity exceptions into one opaque「训练操作失败」string without logging `exc_info`.

---

## Common Mistakes

- Forgetting `trace_id` on manual JSON responses — use `success_response` / `error_response`.
- Mixing bracketed codes and plain strings — stay consistent with existing fallbacks in the same module.
- Swallowing errors silently — log with context, return safe fallback to client.
- Forwarding `str(CosConfigError)` / missing-env dumps to the learner UI.

---

## Verification

- Contract tests: `backend/tests/contract/`
- Unit tests for Result consumers: `backend/tests/unit/test_*`
