# Backend Development Guidelines

> Coding guidance for the FastAPI backend (`backend/`). Source of truth for `trellis-implement` / `trellis-check` when working on backend tasks.

---

## Pre-Development Checklist

Before writing backend code, read the guides relevant to your change:

| Change type | Read first |
|-------------|------------|
| Any backend work | This index + `backend/AGENTS.md` |
| Cross-cutting platform code | `.kiro/steering/backend-principles.md`, `backend/src/common/AGENTS.md` |
| Sales realtime / WebSocket | `backend/src/sales_bot/AGENTS.md` |
| New module or file placement | [Directory Structure](./directory-structure.md) |
| DB models / queries / migrations | [Database Guidelines](./database-guidelines.md) |
| Governed business rules / configurable policies | [Business Rule Configs](./business-rule-configs.md) |
| Service failures / API errors | [Error Handling](./error-handling.md) |
| Logging / trace_id | [Logging Guidelines](./logging-guidelines.md) |
| Tests / lint / type-check | [Quality Guidelines](./quality-guidelines.md) |
| API / WS contract changes | `docs/api-contract/README.md`, `backend/tests/contract/` |

### Project non-negotiables (from CLAUDE.md Constitution)

- **UX never interrupted** — user-safe `error` / `fallback` responses; no raw stack traces to H5.
- **Modular scenarios** — `sales_bot` and `presentation_coach` stay independent.
- **Observability** — structlog + `trace_id` on all request-scoped logs.

---

## Guidelines Index

| Guide | Description | Status |
|-------|-------------|--------|
| [Directory Structure](./directory-structure.md) | Module layout, routes, services, WebSocket handlers | Ready |
| [Database Guidelines](./database-guidelines.md) | SQLAlchemy 2.0 async, Alembic, query patterns | Ready |
| [Business Rule Configs](./business-rule-configs.md) | Governed runtime policy config, validation, fallback, audit | Ready |
| [Sales Trainer Audio Evaluation Scenarios](./sales-trainer-audio-evaluation-scenarios.md) | Newcomer audio assessment scenarios, material policy, path binding compatibility | Ready |
| [Sales Trainer Learning Topic Governance](./sales-trainer-learning-topic-governance.md) | Newcomer learning topics as future-only asset revisions, separate from required path gates | Ready |
| [Sales Trainer Path Prerequisite Gates](./sales-trainer-path-prerequisite-gates.md) | Ordered prerequisite validation, active-revision evidence, Journey projection, and direct-entry enforcement | Ready |
| [Sales Trainer Readiness Review Decisions](./sales-trainer-readiness-review-decisions.md) | Readiness review authorization, append-only state, idempotency, optimistic concurrency, audit, and Web confirmation | Ready |
| [Prompt Template Governance](./prompt-template-governance.md) | Prompt defaults, scenario bindings, system-template lock, governance repair | Ready |
| [Realtime Roleplay V1 Runtime Contract](./realtime-roleplay-v1.md) | Fixed IT-leader realtime roleplay contract, state card, knowledge guard, scoring projection | Ready |
| [Error Handling](./error-handling.md) | `Result[T]`, API responses, middleware fallbacks | Ready |
| [Quality Guidelines](./quality-guidelines.md) | pytest, ruff, mypy, forbidden patterns | Ready |
| [Logging Guidelines](./logging-guidelines.md) | structlog, trace_id, redaction | Ready |

---

## Verification Commands

Run from `backend/`:

```bash
pytest tests/unit/          # unit tests
ruff check src/             # lint
ruff format src/            # format
mypy src/                   # type check
alembic upgrade head        # apply migrations
```

---

**Language**: English (matches codebase comments and AGENTS docs).
