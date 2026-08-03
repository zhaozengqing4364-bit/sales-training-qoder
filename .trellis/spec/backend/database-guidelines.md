# Database Guidelines

> ORM, migrations, and query patterns for this project.

---

## Overview

PostgreSQL in deployed environments, SQLite in isolated tests. All application access is **async SQLAlchemy 2.0** via `AsyncSession`. Alembic is the only runtime/deployment schema authority; application startup verifies the exact active head and never executes DDL.

Reference: `common/db/session.py`, `common/db/models.py`, `alembic/env.py`, `backend/AGENTS.md`.

---

## Engine and Session

- `create_async_engine` + `AsyncSessionLocal` in `common/db/session.py`.
- FastAPI dependency: `get_db()` yields `AsyncSession`.
- Callers **explicitly `commit()`**; no implicit auto-commit on exit.

```python
# Pattern in API routes
async def get_scenario(db: AsyncSession = Depends(get_db)) -> ...:
    result = await db.execute(select(Scenario).where(...))
    rows = result.scalars().all()
```

Example: `sales_bot/api/scenarios.py`.

---

## Query Patterns

Use SQLAlchemy 2.0 style exclusively:

```python
from sqlalchemy import select

stmt = select(Scenario).where(Scenario.id == scenario_id)
result = await session.execute(stmt)
scenario = result.scalar_one_or_none()
```

- Prefer `select()` + `await session.execute()`.
- Use `.scalars().all()` / `.scalar_one_or_none()` for results.
- Use `select(Model)` with filters; never `session.query(Model)`.

### Managed account status concurrency

- Treat deactivate/activate as lifecycle transitions, not physical deletion; preserve training, team, and audit history.
- On databases with row-lock support, lock active platform-admin rows in a stable order before changing an administrator's active state, then lock the target account in the same transaction.
- Reject stale writes with an expected credential version. Deactivation and temporary-password reset invalidate existing credentials by incrementing that version.
- Enforce self-protection and the final-active-admin rule in the shared backend transition path, including compatibility endpoints; frontend button visibility is not an authorization boundary.

---

## Models

- `class Base(DeclarativeBase)` and the compatibility import facade live in `common/db/models.py`.
- Shared ORM definitions are split by responsibility under `common/db/model_registry/`; the facade imports them so model identity and legacy import paths remain stable.
- Domain-specific tables may live in `{module}/models.py` (e.g. `agent/models.py`) and must be registered through the authoritative model registry used by Alembic.
- UUIDs stored as `String(36)` for SQLite/PostgreSQL compatibility.
- Table/column names: **snake_case**.

Examples: `common/db/models.py`, `agent/models.py`.

Note: `common/conversation/models.py` re-exports from `common/db/models.py` for backward-compatible imports.

### Pydantic schemas

Schemas are **not** always `{module}/schemas.py`. Common locations:

- `{module}/schemas.py` — e.g. `agent/schemas.py`, `evaluation/schemas.py`
- `common/db/schemas.py` — shared DTOs used by presentation and other modules
- `common/{domain}/schemas.py` — e.g. `common/conversation/schemas.py`

Use `ConfigDict(from_attributes=True)` (Pydantic v2), not `orm_mode = True`.

---

## Migrations

- **Authority**: `backend/alembic/` — run `alembic upgrade head` before application startup.
- **Launch baseline**: `20260715_0000_001`; archived pre-launch revisions are historical evidence, not an executable dependency of a new database.
- **Current platform head**: `20260716_2300_002`, the single follow-up revision that introduces Durable Task/Outbox and governed AI persistence. It must remain the only active head until a later ordered revision is added.
- Autogenerate: `alembic revision --autogenerate -m "description"`.
- `alembic/env.py` imports all models so `target_metadata = Base.metadata` is complete.
- `common.db.session.verify_database_schema()` compares the database revision with the exact active Alembic head and fails closed when the database is empty, behind, ahead, or on another branch.
- `Base.metadata.create_all()` / `drop_all()` are allowed only inside isolated test fixtures. Development, staging, reset, recovery, and production flows use Alembic.
- Ad-hoc schema repair/reset scripts are forbidden. Pre-launch rebuilding uses the guarded `launch_reset` workflow below.

Durable execution persistence rules:

- Task/AI ownership and Outbox delivery use short PostgreSQL transactions plus `FOR UPDATE SKIP LOCKED`/fencing; no transaction remains open across Provider or other external I/O.
- Task and Outbox logical idempotency, Attempt number, result reference, consumer receipt, AI logical invocation, Provider attempt and Usage Ledger effect are protected by database uniqueness, not only process locks.
- Claim/order indexes must match both the normal priority lane and the aged anti-starvation lane, with equivalent task-type-prefixed indexes for isolated workers. Performance tests assert a compatible plan and separately assert every required index exists; they do not require PostgreSQL to choose one arbitrary equivalent index on an empty table.
- A migration that seeds permissions owns fixed IDs and removes only those exact rows on downgrade. Custom rows with the same permission text are preserved. Circular result-artifact foreign keys are explicitly created/dropped and deferred where one transaction must insert both sides.
- Migration verification for a platform revision uses an isolated real PostgreSQL schema and covers empty-to-head, baseline-to-head, downgrade/upgrade, repeated upgrade, `alembic check`, FK presence and owned-seed cleanup.

Migration naming example: `alembic/versions/20260715_0000_001_launch_baseline.py`.

## Scenario: First-Launch Baseline And Scoped Data-Plane Reset

### 1. Scope / Trigger

- Trigger: rebuilding an unpublished development environment from zero, changing the active baseline, or adding a reset-owned storage/config adapter.
- Scope: PostgreSQL schema and business data, explicitly selected Redis DB/prefixes, Chroma directories, configured local project data roots, and explicit COS project prefixes.
- Out of scope: production, an unlisted database, an entire shared Redis service, an entire COS bucket, source/config files, connection endpoints, model names, credentials, API keys, and secrets.

### 2. Signatures

```bash
cd backend
PYTHONPATH=src python -m launch_reset inspect --manifest <manifest.json>
PYTHONPATH=src python -m launch_reset dry-run --manifest <manifest.json>
PYTHONPATH=src python -m launch_reset apply \
  --manifest <manifest.json> \
  --snapshot <snapshot.json> \
  --target-fingerprint <fingerprint> \
  --confirm-token <one-time-token> \
  --admin-email <email> \
  --admin-name <name>
PYTHONPATH=src python -m launch_reset verify \
  --manifest <manifest.json> \
  --snapshot <snapshot.json> \
  --admin-email <email>
```

Schema/startup signatures:

```bash
cd backend && alembic upgrade head
cd backend && alembic current
cd backend && alembic check
```

```python
await common.db.session.verify_database_schema()
```

### 3. Contracts

- `inspect` derives a secret-free manifest from current configuration; `dry-run` refreshes inspection and issues a plan-bound one-time confirmation token. Neither mutates the data plane.
- `apply` requires `LAUNCH_RESET_APPLY_ENABLED=true`, an environment in `LAUNCH_RESET_ALLOWED_ENVIRONMENTS`, a database in `LAUNCH_RESET_ALLOWED_DATABASES`, the current target fingerprint, and the dry-run token.
- The initial managed administrator password is read from `LAUNCH_ADMIN_INITIAL_PASSWORD` by default (or the env name supplied by `--admin-password-env`); the value never appears in the manifest or CLI output.
- Redis defaults to prefix-only cleanup. Whole-DB cleanup additionally requires `LAUNCH_RESET_REDIS_EXCLUSIVE_DB=true` and therefore means that configured Redis DB is dedicated to this project.
- COS is excluded when unconfigured. When configured, `LAUNCH_RESET_COS_PREFIXES` is mandatory and every prefix must be relative, end in `/`, and contain no `..` segment.
- Local/Chroma roots are explicit resolved directories. Protected ancestors, symlinks, repository/control paths, and broad roots fail closed.
- Before deletion, configuration is exported to a mode-`0600`, checksum-bound snapshot. Reset restores governed model, RAG, voice, prompt, published-rule, scoring, and system-dictionary state without changing endpoint/secret environment configuration.
- Stage status is persisted in the manifest. A retry skips completed stages and resumes the first failed stage only when the manifest, snapshot, live scopes, fingerprint, and confirmation authority still match.
- A fresh PostgreSQL database upgrades directly to `20260715_0000_001`. Follow-up revisions use that baseline as `down_revision`; archived pre-launch revisions are never reintroduced into the active chain.
- Independent verification accepts the single managed launch admin in either lifecycle-valid state: `temporary` with a password immediately after bootstrap, or `active` with both a password and non-null `password_changed_at` after the required first password change. Role, activation, count, and optional email checks still fail closed.

### 4. Validation & Error Matrix

| Condition | Required result |
|---|---|
| Environment is production or not allowlisted | `[RESET_ENVIRONMENT_NOT_ALLOWED]`; no cleanup stage starts |
| Apply switch disabled or database not allowlisted | `[RESET_APPLY_NOT_ENABLED]` / `[RESET_DATABASE_NOT_ALLOWLISTED]` |
| Fingerprint, live scope, checksum, token, or snapshot binding differs | Fail closed before destructive continuation |
| Shared Redis scope has no safe explicit prefix | Reject the scope; never issue `FLUSHDB` |
| COS is configured without explicit project prefixes | `[RESET_COS_EXPLICIT_PREFIXES_REQUIRED]` |
| Cleanup root includes repository, home, broad ancestor, symlink, manifest, or snapshot | Reject with a scoped safety error |
| A stage fails after earlier stages completed | Persist `failed` plus a safe error code; same authorized run may resume without repeating completed stages |
| Database is not at the exact active Alembic head on service startup | Startup fails with an instruction to run `alembic upgrade head`; no DDL executes |
| Final verification finds business rows or external scoped data | Apply/verify fails; partial work is never reported as complete |
| Admin is `temporary` with a managed password | Verification succeeds before first password change |
| Admin is `active` with a managed password and `password_changed_at` | Verification succeeds after legitimate first password change |
| Admin is `reset_required`, inactive, missing a password, email-mismatched, or `active` without `password_changed_at` | `[RESET_ADMIN_STATE_INVALID]` |

### 5. Good / Base / Bad Cases

- Good: an isolated database and dedicated Redis DB are inspected, dry-run output is reviewed, apply uses the exact fingerprint/token, baseline and minimum system state are restored, and independent verification passes.
- Base: Redis or COS is shared; only explicit project prefixes are deleted while unrelated keys/objects remain untouched. Re-running verify after the launch admin completes first password change remains valid.
- Bad: call `Base.metadata.drop_all/create_all`, `FLUSHALL`, bucket-wide deletion, a hand-written repair script, or require the administrator to remain `temporary` forever.

### 6. Tests Required

- Unit: environment/database/fingerprint/token guards; protected paths and control-path collision; Redis shared-prefix versus exclusive-DB behavior; COS explicit-prefix validation; manifest/snapshot checksum and stage-resume behavior.
- Contract: one active Alembic head, baseline table/constraint/index parity with ORM metadata, archived history excluded, and retired mutation bypass scripts absent.
- Integration: empty PostgreSQL `upgrade -> downgrade base -> upgrade`; `alembic check`; a generated no-op follow-up revision upgrades/downgrades from the baseline.
- Isolated reset proof: inspect, dry-run, apply, forced mid-run failure, resume, independent verify, configuration fingerprint preservation, and temporary managed-admin login/password-change path.
- Verifier lifecycle unit tests: accept `temporary`; accept `active` only with `password_changed_at`; reject `reset_required`, inactive, missing-password, wrong-role, wrong-email, and incomplete active state.
- Startup: exact head succeeds with `ddl_executed=false`; empty/behind/ahead/divergent revision fails without creating or altering tables.

### 7. Wrong vs Correct

#### Wrong

```python
async with engine.begin() as connection:
    await connection.run_sync(Base.metadata.create_all)
```

```python
if admin["credential_status"] != "temporary":
    raise ResetExecutionError("[RESET_ADMIN_STATE_INVALID]")
```

```bash
redis-cli FLUSHALL
cos-delete --bucket "$TENCENT_COS_BUCKET" --all
```

#### Correct

```bash
cd backend && alembic upgrade head
PYTHONPATH=src python -m launch_reset dry-run --manifest /secure/control/reset.json
# Review exact scopes and counts before separately authorizing `apply`.
```

```python
valid_lifecycle = status == "temporary" or (
    status == "active" and password_changed_at is not None
)
```

## Scenario: RBAC Role Vocabulary Schema Width

### 1. Scope / Trigger

- Trigger: adding or centralizing persisted RBAC roles.
- Scope: `common.db.models.User.role`, role check constraints, Alembic migrations, and tests that validate the canonical role vocabulary.

### 2. Signatures

```python
class User(Base):
    role: Mapped[str] = mapped_column(String(32), default="user")
```

Migration shape:

```python
def upgrade() -> None: ...
def downgrade() -> None: ...
```

### 3. Contracts

- The DB column width must fit every value in the canonical role enum/set.
- `newcomer_content_admin` is a persisted role and therefore requires at least 22 characters.
- Downgrades that would shrink role width must first check for over-length role values and refuse destructive truncation.

### 4. Validation & Error Matrix

| Condition | Expected behavior |
|---|---|
| New role value length exceeds column width | Add a migration before exposing the role |
| Role is not in the check constraint | Update the constraint/migration or map the product concept to an existing persisted role |
| Downgrade finds a role longer than target width | Raise and keep data intact |
| Empty or unknown role from API input | Reject in validation / permission layer |

### 5. Good/Base/Bad Cases

- Good: centralized role constants include a max-length test and schema migration widens the column before role writes.
- Base: frontend route visibility consumes backend capabilities and does not invent new persisted roles.
- Bad: a role string is added to permission code but the DB column remains `String(20)`.

### 6. Tests Required

- Unit test asserting all canonical role values fit `User.role.type.length`.
- RBAC matrix tests for admin/content/ops/auditor roles.
- Alembic head check and targeted upgrade validation for the new migration.

### 7. Wrong vs Correct

#### Wrong

```python
CONTENT_ADMIN_ROLES = {"content_admin", "newcomer_content_admin"}
# User.role stays String(20)
```

#### Correct

```python
assert max(len(role) for role in CANONICAL_USER_ROLES) <= USER_ROLE_COLUMN_LENGTH
```

The schema and role authority evolve together.

---

## Test Database

Integration tests use in-memory SQLite:

- Fixture in `tests/conftest.py`: `sqlite+aiosqlite:///:memory:`.
- `Base.metadata.create_all` in test setup.
- Import domain models in conftest so metadata is registered.

---

## Anti-Patterns

| Forbidden | Use instead |
|-----------|-------------|
| `session.query(Model)` | `select(Model)` + `execute` |
| Sync DB drivers / blocking calls | `AsyncSession` + asyncpg |
| `orm_mode = True` | `from_attributes=True` |
| Production schema via `create_all` | Alembic migrations |
| Missing model import in `alembic/env.py` | Import new models before autogenerate |

---

## Common Mistakes

- Forgetting to register a new model in `alembic/env.py` → incomplete migrations.
- Implicit commit assumptions — always commit after writes in the service/API layer.
- Cross-module FK without importing both models in Alembic env.

---

## Verification

```bash
cd backend && alembic upgrade head
cd backend && pytest tests/integration/
```

---

## Operational Seed Scripts

Use `backend/scripts/` for idempotent, operator-run seed scripts that create demo or training configuration data without changing schema. These scripts are **data/config writers**, not migration authority.

### 1. Scope / Trigger

- Trigger: adding a runnable seed command such as `PYTHONPATH=src uv run python scripts/seed_<name>.py`.
- Scope: create or update existing ORM records needed for local demos, training samples, or admin-config bootstraps.
- Not scope: schema changes, production migrations, or one-off hidden manual SQL.

### 2. Signatures

Seed scripts must expose:

```bash
PYTHONPATH=src uv run python scripts/seed_<name>.py
PYTHONPATH=src uv run python scripts/seed_<name>.py --verify-only
```

Python entrypoint shape:

```python
async def run(verify_only: bool) -> tuple[int, dict[str, object]]: ...
def parse_args() -> argparse.Namespace: ...
def main() -> None: ...
```

### 3. Contracts

- Use `AsyncSessionLocal()` and SQLAlchemy 2.0 `select()` / `execute()` only.
- Scripts must be idempotent: first run creates records, second run updates existing records rather than duplicating them.
- `--verify-only` must not create or update records.
- Output must be a single JSON object written to stdout with:
  - `ok: bool`
  - `verify_only: bool`
  - `changes: {created: int, updated: int}`
  - `ids: {...}` for created/verified primary IDs
  - `counts: {...}` for core asset counts
  - `keys: {...}` for operator-facing lookup keys such as emails, versions, template names

### 4. Validation & Error Matrix

| Condition | Expected behavior |
|---|---|
| Missing expected record in `--verify-only` | Exit `1`, output `{"ok": false, "errors": [...]}` |
| Required asset not published/active | Exit `1`, explain the failed asset/state |
| Required child count mismatch | Exit `1`, include expected vs actual count |
| Relationship mismatch | Exit `1`, name the mismatched field |
| Successful seed or verify | Exit `0`, output summary JSON |

### 5. Good/Base/Bad Cases

- Good: seed creates a complete linked sample, then `--verify-only` confirms assets and relationships.
- Base: rerunning the seed returns `created=0` and updates the existing records.
- Bad: seed uses generated names without stable lookup keys, making reruns duplicate records.

### 6. Tests Required

- Minimum: `python3 -m py_compile scripts/seed_<name>.py` and `uv run ruff check scripts/seed_<name>.py`.
- If a writable dev database is available: run the script, rerun it once for idempotency, then run `--verify-only`.
- For reusable seed frameworks, add integration tests around the upsert/verify functions.

### 7. Wrong vs Correct

#### Wrong

```python
record = Model(name="Demo")
db.add(record)
await db.commit()
```

This duplicates data on every run and has no verification mode.

#### Correct

```python
record = await _first(db, select(Model).where(Model.name == NAME))
if record is None:
    record = Model(id=_uuid(), name=NAME)
    db.add(record)
    counters["created"] += 1
else:
    counters["updated"] += 1
record.status = "published"
```

Stable lookup keys make the script safe to rerun and easy to verify.

### Common Mistake: Renaming Seed-Managed Units Without Archiving Legacy Rows

When a seed script changes the operator-facing name of a stable logical unit
(`module_key`, `purpose`, `paper_key`, etc.), do not rely on the new display
name as the only lookup key. Existing installations may already contain the old
row, and backfilled path payloads can then see duplicate duration options or
duplicate module bindings.

Required behavior:

- Archive or migrate legacy rows that share the same stable logical key before
  deriving active path payloads.
- Add a regression test that starts with the legacy row and asserts the active
  revision references only the new/current rows.
- Keep historical submissions safe by changing future active config only; do
  not rewrite old score snapshots.
