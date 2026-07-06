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

## Anti-Patterns

- Returning HTTP 500 with exception message body to the practice UI.
- Using `Result.unwrap()` on user-facing paths (can raise `ValueError`).
- `print()` for errors — use structlog (see Logging Guidelines).
- `raise HTTPException(500, detail=str(e))` in new practice/scenario code.
- Assuming all failures use the `error` field — check whether the path returns `fallback`.

---

## Common Mistakes

- Forgetting `trace_id` on manual JSON responses — use `success_response` / `error_response`.
- Mixing bracketed codes and plain strings — stay consistent with existing fallbacks in the same module.
- Swallowing errors silently — log with context, return safe fallback to client.

---

## Verification

- Contract tests: `backend/tests/contract/`
- Unit tests for Result consumers: `backend/tests/unit/test_*`
