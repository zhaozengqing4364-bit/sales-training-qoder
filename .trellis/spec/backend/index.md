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
| [Prompt Template Governance](./prompt-template-governance.md) | Prompt defaults, scenario bindings, system-template lock, governance repair | Ready |
| [Realtime Roleplay V1 Runtime Contract](./realtime-roleplay-v1.md) | Fixed IT-leader realtime roleplay contract, state card, knowledge guard, scoring projection | Ready |
| [Realtime Session Engine](./realtime-session-engine.md) | Gate 2 Presentation Engine state, rollout/rollback, snapshots, diagnostics, evidence, and Golden differential | Ready |
| [Realtime Provider and Grounding Authority](./realtime-provider-grounding.md) | Gate 3 Provider/Grounding authority plus StepAudio 2.5 manual-commit and codec compatibility | Ready |
| [Domain Ownership and Evaluation Ports](./domain-ownership-and-evaluation-ports.md) | Gate 4 neutral Roleplay/config ownership, Evidence/Scenario ports, root composition and realtime helper seams | Ready |
| [Training Locality and Model Registry](./training-locality-and-model-registry.md) | Gate 5 identity-preserving ORM registry, frozen Journey reads, and pure Journey/Readiness projections | Ready |
| [Compatibility Retirement and Root Composition](./compatibility-retirement-and-root-composition.md) | Gate 6 closed runtime factories, app-root composition, consumer-proven retirement, and governed retention | Ready |
| [Error Handling](./error-handling.md) | `Result[T]`, API responses, middleware fallbacks | Ready |
| [Quality Guidelines](./quality-guidelines.md) | pytest, ruff, mypy, forbidden patterns | Ready |
| [Platform Contract Truth](./platform-contract-truth.md) | Contributor registry isolation, effective route inventory, runtime-generated OpenAPI parity | Ready |
| [Architecture Fitness](./architecture-fitness.md) | Executable cross-package dependency policy, temporary exceptions, and SCC guard | Ready |
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
