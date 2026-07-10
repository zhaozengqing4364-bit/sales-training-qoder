# Readiness Decision Integrity — Design Artifact Audit

## Overall Conclusion

Architecture direction is sound: a dedicated append-only business record plus an OperationLog audit Adapter fits the repository better than continuing to reconstruct Readiness state from generic log metadata.

First audit pass found five hard inconsistencies between the PRD, implementation plan and current callers. All five were corrected before final confirmation. One implementation-time check remains advisory: verify the Alembic head immediately before creating the migration.

## Dimension 1: Reference Pattern Reality

### Verified

- Quiz idempotency exists as `SalesTrainerQuizAttempt.client_token` plus a partial unique index.
- Asset revision hashing exists in `SalesTrainerAssetRevisionService._payload_hash()`.
- OperationLog `record()` flushes without commit, so business state and audit can share one transaction.
- Regrade and Attempt data use dedicated business records rather than treating logs as their only state.

### Result

The proposed action table is based on real repository patterns. The plan deliberately strengthens the quiz token pattern with a canonical request hash because a Readiness decision has higher integrity requirements.

## Dimension 2: Dependency Direction

### Verified

- The change stays inside the `sales_trainer` backend domain and first-party Web admin domain.
- No cross-domain runtime import or new dependency is required.
- The frontend continues to consume the existing admin sales-trainer API domain.

### Result

No package-direction or process-boundary violation found.

## Dimension 3: Type and Field Completeness

### 🔴 Fixed: required-null version field was accidentally optional

Evidence:

- PRD requires `expected_latest_review_action_id` on every request.
- The original plan used `Field(None, ...)`, which allowed callers to omit the key.

Correction:

- Plan now uses `expected_latest_review_action_id: str | None = Field(...)`.
- The key is required, while `null` remains valid only when no prior decision exists.

### 🔴 Fixed: capability addition affected strong TypeScript fixtures

Evidence:

- `SalesTrainerAdminCapabilities.capabilities` is a complete `Record<SalesTrainerAdminCapabilityKey, boolean>`.
- Strong fixtures exist in routes, sidebar, module-nav and client-domain tests.

Correction:

- Plan explicitly updates those four fixture locations with `review_readiness`.
- Untyped page mocks are not mechanically rewritten.

## Dimension 4: Transaction and IO Boundary

### Verified

- Current OperationLog writes are transaction-compatible because `record()` only flushes.
- Proposed flow contains Dossier validation, learner row lock, action insert and audit flush in one database transaction.
- No model call, notification, HTTP request or other slow external IO belongs in that transaction.

### Result

PRD and plan now state this boundary explicitly. Audit-log failure rolls back the business action.

## Dimension 5: Caller Semantics

### 🔴 Fixed: new error type was not mapped to the current API contract

Evidence:

- `admin_create_readiness_review_action` catches `ReadinessDossierError` only.
- A new `ReadinessReviewActionError` escaping directly would cause an unhandled 500.

Correction:

- Dossier remains the API-facing orchestration Interface.
- It catches the decision Module error and converts code, message, status and details into `ReadinessDossierError`.

### 🔴 Fixed: legacy latest decision was missing from concurrency baseline

Evidence:

- Dossier may return a legacy OperationLog action as `latest_review_action` before the first canonical action exists.
- Comparing expected version only against the new table would reject that first migrated write.

Correction:

- Plan computes the latest version across canonical actions and legacy review logs.
- Canonical action audit mirrors are excluded from legacy candidates.
- Tests cover legacy-ID success and incorrect-null conflict.

## Dimension 6: Immediate Test Impact

### 🔴 Fixed: existing API tests would fail after required request fields

Evidence:

- `backend/tests/integration/test_sales_trainer_api.py` already posts to review-actions twice without the new fields.
- The ordinary learner currently expects generic `[ROLE_REQUIRED]`.

Correction:

- Plan updates both requests with token and explicit null version.
- Expected permission error becomes `[READINESS_REVIEW_ROLE_REQUIRED]`.
- The Web API-domain test locks JSON body forwarding.

### Additional Coverage

- Permission role matrix and department scope.
- Idempotency replay and mismatched request hash.
- Optimistic concurrency conflict.
- Dossier canonical/legacy dual-read and deduplication.
- Frontend confirmation, retry-token reuse and 409 refresh.

## Dimension 7: Artifact Internal Consistency

### Verified

- PRD, research and implementation plan agree on the role boundary: platform admins global, manager allowlist department-scoped, ops read-only.
- All artifacts agree on the three MVP decisions and exclude revocation/delegation.
- All artifacts agree that request preconditions are mandatory in a coordinated first-party release.
- All artifacts agree that new business state is canonical-table-backed and legacy logs are compatibility-only.
- Acceptance criteria map to named tests and commands in the implementation plan.

## Advisory Item

### 🟡 Recheck migration head at implementation start

Current latest committed migration is `20260707_1200_091`. The plan reserves `20260710_1200_092`, but the working branch is active and dirty. Before creating the migration, run `alembic heads` and inspect `backend/alembic/versions/`; if another task has claimed 092, renumber this task's migration and update its down revision before any code is written.

## Stabilization Result

- Hard errors remaining: 0
- Advisory items: 1
- Requirements unresolved: 0
- Ready for user final confirmation: yes

## Second-Pass Verification

- PRD, research, design audit and implementation plan are non-empty, have balanced code fences and contain no unresolved placeholder markers.
- Core terms align across PRD and plan: `review_readiness`, `idempotency_key`, `expected_latest_review_action_id`, legacy OperationLog and append-only history.
- Alembic currently reports `20260707_1200_091 (head)`; the reserved 092 migration is valid at planning time and remains subject to the implementation-start recheck.
- The second seven-dimension pass found no new hard inconsistency.
