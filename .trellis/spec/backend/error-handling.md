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
