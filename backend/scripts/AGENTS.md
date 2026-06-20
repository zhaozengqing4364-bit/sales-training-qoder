# backend/scripts/ — Backend Operational Scripts

## Overview

These scripts seed, repair, verify, and evaluate backend data/configuration outside normal HTTP flows.

## Where to Look

| Need | Location | Notes |
|------|----------|-------|
| Auth / smoke bootstrap | `bootstrap_auth_admin.py`, `bootstrap_smoke_practice_evidence.py` | Used by local smoke flows. |
| Seed content | `seed_*.py`, `import_coo_learning_content.py` | Treat as data writes; keep repeatability in mind. |
| Repair jobs | `repair_*.py`, `relax_presales_completion_policies.py` | Prefer dry-run or clear affected-count output. |
| Runtime verification | `verify_*.py`, `run_roleplay_contract_eval.py` | Should fail loudly on missing config. |
| Prompt migration | `migrate_prompts.py` | Coordinate with `prompt_templates` governance and migrations. |

## Conventions

- Run from `backend/` unless the script explicitly supports repo-root execution.
- Import through `src` project modules; do not duplicate model or config definitions in scripts.
- Scripts that mutate DB/config must print affected counts and be safe to re-run where practical.
- Add `--dry-run` for broad repair/backfill scripts unless the write set is trivially bounded.
- Coordinate schema assumptions with `backend/alembic/` before touching persisted fields.
- Never log secrets, tokens, raw passwords, or private user data.

## Anti-Patterns

- Do not use backend scripts as hidden production control-plane features.
- Do not make seed scripts depend on “latest” mutable assets when a published snapshot is required.
- Do not swallow partial failures; report skipped rows and failure reasons.
