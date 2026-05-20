# Logging Guidelines

> Structured logging and trace correlation in this project.

---

## Overview

Logging uses **structlog** via a project wrapper. Every log line in request-scoped code should carry **`trace_id`**. Logs must not leak secrets (tokens, passwords, cookies).

Reference: `common/monitoring/logger.py`, `common/monitoring/trace_context.py`, `app_factory.py`.

---

## Configuration

- Startup: `configure_logging(LOG_LEVEL)` from `app_factory.py` (`os.getenv("LOG_LEVEL", "INFO")`).
- `structlog.configure()` in `common/monitoring/logger.py`.
- Production / non-DEBUG: `JSONRenderer`.
- DEBUG: `ConsoleRenderer`.
- File sink: `configure_logging` may write to `logs/app.log` (see `logger.py`).

Environment variables documented in root `.env.example` / `CLAUDE.md`: `LOG_LEVEL`, `ENABLE_TRACING`. Note: `ENABLE_TRACING` is not widely consumed in backend code today — trace correlation relies on structlog + request headers.

---

## Getting a Logger

```python
from common.monitoring.logger import get_logger

logger = get_logger(__name__)
logger.info("session_started", session_id=session_id, phase="connect")
```

`StructuredLogger` methods (`info`, `warning`, `error`, `debug`) **auto-inject** `trace_id=get_trace_id()`.

---

## Trace Context

Two modules cooperate:

| Module | Responsibility |
|--------|----------------|
| `common/monitoring/logger.py` | `trace_id_var` (`ContextVar`), `get_trace_id()`, `set_trace_id()` |
| `common/monitoring/trace_context.py` | W3C header parsing: `resolve_trace_headers`, `build_traceparent`, `generate_trace_id` |

- Set at request entry: `ErrorHandlerMiddleware` + `resolve_trace_headers`.
- Response headers: `X-Trace-ID`, W3C `traceparent` — aligns with frontend `lib/observability/trace-context.ts`.

WebSocket handlers should propagate or set trace context when a session starts.

---

## Log Levels

| Level | When to use |
|-------|-------------|
| `debug` | Verbose WS/event tracing (use sparingly in production) |
| `info` | Normal lifecycle (session start, turn complete, tool call) |
| `warning` | Degraded path (fallback TTS, retry, policy skip) |
| `error` | Failures requiring attention; include `error_code` or exception context |

Use structured kwargs (`session_id=`, `path=`, `phase=`) — not string interpolation of large payloads.

---

## Redaction

`sanitize_log_kwargs()` redacts fields whose names match sensitive patterns (`token`, `password`, `cookie`, `email`, etc.) → `[REDACTED]`.

Admin log surfaces use `ADMIN_LOG_ALLOWLIST_FIELDS` — only expose safe fields like `trace_id`, `error_code`, `phase`, `session_id`.

---

## Anti-Patterns

| Forbidden | Use instead |
|-----------|-------------|
| `print()` | `logger.info(...)` |
| Logging full API keys or JWTs | Omit or rely on sanitizer; prefer IDs |
| Unstructured f-strings for machine parsing | structlog key=value kwargs |
| Missing trace_id on new HTTP middleware | Call through existing trace resolution |

---

## Common Mistakes

- Logging entire WebSocket payloads at `info` in production — use `debug` or sample.
- Creating ad-hoc loggers without `get_logger(__name__)` — breaks consistent naming.
- Duplicate trace_id generation per sub-call — reuse context from middleware.
- Looking for `trace_id_var` in `trace_context.py` — it lives in `logger.py`.

---

## Verification

```bash
cd backend && ruff check src/   # catches print() in many cases
grep -r "print(" backend/src/   # should find no business usage
```
