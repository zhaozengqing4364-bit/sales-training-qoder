# backend/src/common — Shared Platform Kernel

This directory is the cross-cutting infrastructure layer of the backend. Code here is consumed by `sales_bot/`, `presentation_coach/`, `agent/`, `admin/`, and other domains. Changes ripple widely — treat this area with extra caution.

## What Lives Here

High-level routing map for major subdomains:

- `api/` — Common API utilities and cross-domain endpoints (e.g. `practice.py`)
- `analytics/` — Event tracking, metrics aggregation, and reporting primitives
- `audio/` — ASR/TTS wrappers and audio processing utilities
- `auth/` — JWT authentication, token validation, and identity helpers
- `conversation/` — Dialogue engine, session state, and replay infrastructure
- `db/` — SQLAlchemy 2.0 models, session management, and migration helpers (`models.py`)
- `effectiveness/` — Scoring and effectiveness evaluation primitives
- `knowledge/` — Vector storage, document ingestion, and retrieval helpers (ChromaDB)
- `knowledge_engine/` — Higher-level knowledge orchestration and query planning
- `services/` — Shared service facades used across multiple domains
- `storage/` — File/blob storage abstractions and helpers
- `websocket/` — Base WebSocket handlers and connection management utilities

## Impact Rules

- **NEVER** introduce business-specific logic for a single domain here. If it only serves `sales_bot/`, it belongs in `backend/src/sales_bot/`.
- **ALWAYS** keep common interfaces stable. Other modules depend on them.
- **Verify broader tests** after changes. Run `pytest` across unit and integration suites before declaring a common change safe.
- **Prefer thin abstractions**. Add indirection only when at least two domains need it.

## Where to Look for Rules

| Concern | Document |
|---------|----------|
| Backend coding rules | `.kiro/steering/backend-principles.md` |
| API contracts | `docs/api-contract/README.md` |
| Domain-specific guidance | `backend/src/sales_bot/AGENTS.md` |
| Root routing & workflows | `backend/AGENTS.md` |

## Entry Points You Will Touch

- `backend/src/common/db/models.py` — Shared SQLAlchemy models
- `backend/src/common/api/practice.py` — Cross-domain practice APIs
- `backend/src/common/websocket/base_handler.py` — Base WebSocket handler
