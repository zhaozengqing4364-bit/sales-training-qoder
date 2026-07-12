# Training Locality and Model Registry

> Executable contract for Gate 5 backend model registration, Journey reads, and Readiness projections.

## 1. Scope / Trigger

Read this spec before changing any of:

- `common.db.model_registry` or the `common.db.models` compatibility surface;
- `TrainingJourneyService`, `TrainingJourneyProjection`, or Journey read queries;
- `ReadinessDossierService` or `ReadinessDossierProjection`;
- learner/roleplay fields consumed by Journey or Readiness;
- Alembic metadata discovery or model import order.

The purpose is locality: SQLAlchemy owns persistence shape, application services orchestrate use cases,
and pure projections own deterministic policy. A change must not require editing all three layers unless the
external contract genuinely changes.

## 2. Signatures

```python
class JourneyReadRepository(Protocol):
    async def learner(self, learner_id: str) -> JourneyLearnerProjection | None: ...

    async def learners(
        self,
        *,
        team_department: str | None,
        department: str | None,
        limit: int | None,
        offset: int = 0,
        include_development_admin: bool = True,
    ) -> JourneyLearnerPage: ...

    async def roleplay_sessions(
        self,
        *,
        learner_ids: frozenset[str],
    ) -> tuple[JourneyRoleplaySessionProjection, ...]: ...

class TrainingJourneyService:
    def __init__(
        self,
        db: AsyncSession,
        *,
        read_repository: JourneyReadRepository | None = None,
        projection: TrainingJourneyProjection | None = None,
    ) -> None: ...

class ReadinessDossierService:
    def __init__(
        self,
        db: AsyncSession,
        *,
        read_repository: JourneyReadRepository | None = None,
        projection: ReadinessDossierProjection | None = None,
    ) -> None: ...

class TrainingJourneyProjection:
    def module_stage(self, module: JourneyModule, latest: dict[str, Any] | None) -> TrainingStage: ...
    def overall_progress(self, modules: list[dict[str, Any]]) -> dict[str, int]: ...
    def journey_stage(self, modules: list[dict[str, Any]], path_enabled: bool) -> TrainingStage: ...

class ReadinessDossierProjection:
    def dossier_payload(
        self,
        journey: dict[str, Any],
        *,
        records: list[dict[str, Any]],
        review_actions: list[dict[str, Any]],
        generated_at: datetime,
        evidence_limit: int | None = None,
    ) -> dict[str, Any]: ...
    def workbench_groups(self, dossiers: list[dict[str, Any]]) -> dict[WorkbenchGroupKey, dict[str, Any]]: ...
    def validate_dossier_approval(self, dossier: dict[str, Any]) -> None: ...
```

Registry identity is part of the compatibility signature:

```python
from common.db import models
from common.db.model_registry import User

assert models.User is User
assert models.User.__module__ == "common.db.models"
```

## 3. Contracts

### Model registration

- `model_registry/base.py` owns the only declarative `Base`.
- Group modules contain declarations; `model_registry/__init__.py` imports all groups in a stable order.
- `common.db.models` is an explicit, rule-free compatibility façade.
- All mapped classes share one `Base.metadata`.
- The current complete application metadata contains 98 tables. A fresh registry/models import registers the
  52 tables owned by the compatibility registry. The full metadata SHA-256 contract is
  `cc9bb58232ea600b9c88574bceac9f495feab4e18e02ae8d21af7165f7eeb63b`.
- Changing a table, constraint, default, FK, index, enum, or public class inventory requires an intentional
  migration/contract update; moving a class does not.

### Read projections

- Repository DTOs are `@dataclass(frozen=True, slots=True)` and contain no ORM object.
- JSON snapshots are recursively frozen: mappings use read-only mappings and arrays become tuples.
- `SqlAlchemyJourneyReadRepository` owns `User` and `PracticeSession` query details.
- Learner pages are ordered by `created_at DESC, user_id ASC`; roleplay sessions are ordered by `session_id ASC`.
- `include_development_admin=True` preserves the Journey development-login exception. Readiness fallback lists
  must pass `False` to preserve learner-only semantics.
- A team department mismatch returns an empty page, not a cross-department query.

### Application and projection ownership

- Application services own permission checks, async reads, transaction boundaries, table-existence checks,
  operation-log validation/writes, and exception translation.
- `TrainingJourneyProjection` owns stage/completion/next-action, overall status, learner-level matching/defaults,
  diagnostics, and pure analytics aggregation.
- `ReadinessDossierProjection` owns evidence, module/competency summaries, state precedence, approval eligibility,
  retraining comparison, realtime gate, next actions, workbench grouping, and blocked snapshots.
- Projection time is supplied by application orchestration (`generated_at`); a projection must not read the clock,
  database, environment, FastAPI request, or operation log.
- Application services call only the projection's explicit non-underscored interface. Private projection helpers
  are not a cross-class API; this keeps the seam discoverable and prevents hidden-interface coupling.
- Public REST/WS payloads, RuntimeGate, snapshots, scoring/report single writers, and audit semantics are unchanged.

## 4. Validation & Error Matrix

| Condition | Required result |
|---|---|
| Learner ID missing | `[TRAINING_RECORD_NOT_FOUND]`, 404 |
| Viewer department differs from learner | same 404; do not reveal existence |
| Viewer lacks record capability | `[ROLE_REQUIRED]`, 403 |
| Active path revision missing | Journey fails closed; Readiness projects `blocked_by_config` |
| Unknown review capability | `[READINESS_DOSSIER_CAPABILITY_INVALID]`, 400 |
| Unknown/inaccessible evidence | `[READINESS_DOSSIER_EVIDENCE_INVALID]`, 400 |
| Approval with config blocker | `[READINESS_DOSSIER_CONFIG_BLOCKED]`, 409 |
| Approval without pending evidence | `[READINESS_DOSSIER_NOT_READY]`, 409 |
| Team filter conflicts with scoped department | empty page, total 0 |
| Roleplay snapshot is malformed | frozen empty mapping; no exception or policy guess |
| Model metadata digest changes without migration intent | Gate 5 locality contract fails |

## 5. Good / Base / Bad Cases

- **Good:** add a Journey status rule in `TrainingJourneyProjection`, cover it with pure fixtures, and leave SQL
  and HTTP orchestration untouched.
- **Base:** add one persisted learner field in its owner registry group, map it immediately in the SQLAlchemy
  adapter, then expose only the immutable field required by policy.
- **Bad:** import `common.db.models.User` into Journey/Readiness application code and branch on SQLAlchemy fields.
- **Bad:** create a second declarative `Base`, or rely on accidental import order to register tables.
- **Bad:** return ORM rows, mutable JSON dicts, or lazy relationships through `JourneyReadRepository`.

## 6. Tests Required

Run from `backend/`:

```bash
.venv/bin/python -m pytest -q --no-cov \
  tests/unit/test_gate5_locality_contracts.py \
  tests/unit/test_journey_read_repository.py \
  tests/unit/test_training_journey_projection.py \
  tests/unit/test_readiness_dossier_projection.py \
  tests/unit/test_sales_trainer_training_journey_service.py \
  tests/unit/test_sales_trainer_readiness_dossier_service.py \
  tests/contract/test_sales_trainer_phase2_contract.py
.venv/bin/ruff check src tests
.venv/bin/mypy src
.venv/bin/python scripts/architecture_dependency_guard.py --check
```

Assertion points:

- exact public class inventory, object identity, qualified module names, import-order parity, and metadata digest;
- frozen DTO mutation fails, nested snapshots are read-only, ordering/scope are deterministic;
- complete Journey/Dossier payloads remain differential-equivalent;
- review writes validate before one commit and continue to emit the same audit log fields;
- application modules contain no `common.db.models` `User`/`PracticeSession` import.
- application services contain no calls to private (`_...`) projection methods.
- when deterministic branches move from a critical service into its projection, migrate the changed-coverage
  floors as a tested pair: combined covered count and ratio must not fall, and the new critical projection must
  have full changed-branch coverage before the canonical gate can pass.

## 7. Wrong vs Correct

### Wrong

```python
class TrainingJourneyService:
    async def learners(self):
        rows = await self._db.execute(select(User))
        return [self._decide_stage(row) for row in rows.scalars()]
```

This couples query shape, ORM lifetime, and Journey policy in one high-fan-in service.

### Correct

```python
page = await self._read_repository.learners(
    team_department=team_department,
    department=department,
    limit=limit,
    include_development_admin=True,
)
journeys = [await self._build_journey(learner=item, viewer=viewer) for item in page.items]
```

The adapter owns persistence, frozen DTOs cross the seam, and the projection owns deterministic interpretation.

## Gate 6 Retirement Conditions

`common.db.models` may be reduced only after import inventory proves no required compatibility consumer remains,
Alembic imports the canonical registry, fresh-process import-order tests stay Green, and one release deprecation
window has passed. Do not delete the façade merely because new code uses owner-specific imports.
