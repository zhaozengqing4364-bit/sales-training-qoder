# backend/alembic/ — Migration Authority

## Overview

Alembic is the only schema migration authority for backend database changes.

## Structure

```
backend/alembic/
├── env.py             # imports all metadata and rewrites async DB URLs to sync
├── script.py.mako     # migration template
└── versions/          # ordered revision files
```

## Where to Look

| Need | Location | Notes |
|------|----------|-------|
| Metadata imports | `env.py` | Add model imports here when autogenerate misses new tables. |
| Existing revisions | `versions/` | Check nearby revisions before adding a new one. |
| Runtime models | `backend/src/common/db/models.py`, domain `models.py` | Migration must match model ownership. |
| Migration command | `backend/AGENTS.md`, `CLAUDE.md` | Run from `backend/`: `alembic upgrade head`. |

## Conventions

- Generate with `cd backend && alembic revision --autogenerate -m "..."`
- Keep revisions small and named by the real domain change.
- Data migrations must be idempotent or have a clear guard.
- New non-null columns on existing tables need a compatible default/backfill path.
- Index, unique constraint, and enum/state changes must mention rollback risk in delivery.

## Anti-Patterns

- Do not edit production data manually instead of writing a migration or repair script.
- Do not create a migration without checking current heads and merge revisions.
- Do not drop columns/tables without confirming references and rollback strategy.
- Do not rely on async drivers inside Alembic; `env.py` converts URLs for sync migration execution.
