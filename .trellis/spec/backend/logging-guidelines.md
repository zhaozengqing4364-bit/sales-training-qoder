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

### Durable Task and AI telemetry

- Worker/Dispatcher lifecycle logs contain instance/dispatcher ID, task/event type counts, safe error code, attempt/failure count and probe state; never lease tokens, payload JSON, transcript, Prompt or Provider raw response.
- AI audit records may expose invocation/task/business-object references, Prompt/route revision, Provider/model, latency, tokens, cost, currency, retry and result classification. Sensitive input/output remains in access-controlled artifacts subject to retention, not logs.
- Task health metrics use an explicit time window for retry rate and processing latency. AI cost metrics always include currency in filters and grouping. Queue depth, expired leases, dead-letter count and Outbox lag are operator metrics, not learner-facing diagnostics.

---

## Scenario: Operational URL Userinfo Redaction

### 1. Scope / Trigger

- Trigger: an operator script prints a startup summary, diagnostic, evidence file, or error containing `DATABASE_URL`, `REDIS_URL`, or another connection URL.
- Scope: terminal output and persisted operational logs. Passing the original URL to the child process through its environment remains allowed.

### 2. Signatures

```bash
redact_url_userinfo "postgresql+asyncpg://user:secret@db.internal:5432/app"
# postgresql+asyncpg://[REDACTED]@db.internal:5432/app
```

The local stack implementation is `scripts/dev-up.sh:redact_url_userinfo`; `print_summary` must render only its result.

### 3. Contracts

- Keep the effective connection URL unchanged for the backend/worker process; redact only the value sent to stdout/stderr or a log.
- If a URL contains `<scheme>://<userinfo>@<location>`, replace the complete userinfo segment with `[REDACTED]`.
- A URL without userinfo may be displayed unchanged only when it has no secret-bearing query/fragment. Secret query parameters must be omitted or separately allowlisted/redacted.
- Never rely on file mode alone as permission to write a raw password into a log.

### 4. Validation & Error Matrix

| Input | Required output |
|---|---|
| `postgresql+asyncpg://user:password@host/db` | `postgresql+asyncpg://[REDACTED]@host/db` |
| `redis://:password@host/0` | `redis://[REDACTED]@host/0` |
| `redis://host/0` | Unchanged |
| URL with a token in query/fragment | Do not print it through this helper alone; omit or apply field-aware redaction |

### 5. Good / Base / Bad Cases

- Good: the summary preserves scheme, host, port, database/DB number, and therefore remains diagnosable while hiding all userinfo.
- Base: a local password is low-value; it is still redacted so the same script is safe when pointed at a shared environment.
- Bad: print the raw effective URL because the terminal is local or the captured file is mode `0600`.

### 6. Tests Required

- Source the script without running `main`, set database and Redis URLs with distinct sentinel secrets, run `print_summary`, and assert neither sentinel appears.
- Assert the rendered summary still includes `[REDACTED]`, scheme, host, port, and path.
- Run `bash -n scripts/dev-up.sh` and the script-focused pytest regression.

### 7. Wrong vs Correct

#### Wrong

```bash
printf 'DATABASE_URL: %s\n' "${EFFECTIVE_DATABASE_URL}"
```

#### Correct

```bash
safe_database_url="$(redact_url_userinfo "${EFFECTIVE_DATABASE_URL}")"
printf 'DATABASE_URL: %s\n' "${safe_database_url}"
```

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
