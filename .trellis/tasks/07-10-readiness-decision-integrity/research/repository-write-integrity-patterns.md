# Repository Write-Integrity Patterns for Readiness Decisions

## Research Question

Which existing repository patterns should Readiness review actions reuse for business-state persistence, idempotency, concurrency and audit?

## Sources Inspected

- `backend/src/sales_trainer/models.py`
- `backend/src/sales_trainer/services/readiness_dossier_service.py`
- `backend/src/sales_trainer/services/operation_log_service.py`
- `backend/src/sales_trainer/services/asset_revision_service.py`
- `backend/src/sales_trainer/services/quiz_service.py`
- `backend/src/sales_trainer/regrade_schemas.py`
- `backend/alembic/versions/20260707_1200_091_sales_trainer_quiz_attempt_client_token.py`
- `backend/tests/unit/test_sales_trainer_readiness_dossier_service.py`
- `backend/tests/unit/test_newcomer_training_path_permissions.py`

## Existing Patterns

### 1. Quiz Attempt client-token idempotency

- `sales_trainer_quiz_attempts.client_token` has a partial unique index.
- The pattern prevents duplicate attempt creation when the same client request is replayed.
- It does not protect against reusing the same token with different business content unless the service also compares a canonical request hash.
- Readiness should reuse the unique-key idea but add request-hash validation because a review decision has higher business impact than a quiz submission.

### 2. Asset revision append-only state and payload hash

- `SalesTrainerAssetRevisionService` creates immutable revision rows and uses a separate active-reference record.
- `_payload_hash()` normalizes JSON and hashes it with SHA-256.
- This provides a strong local precedent for hashing a normalized Readiness request and retaining append-only action history.
- Asset revision activation does not currently provide the expected-latest conflict contract required for simultaneous human review, so Readiness needs an additional concurrency precondition.

### 3. Dedicated Regrade business records

- Regrade uses a dedicated business record and preserves before/after snapshots rather than treating an operation log as state.
- This supports the rule that OperationLog is an audit Adapter, not the canonical state machine.
- Readiness review actions similarly need queryable fields and constraints that JSON metadata in a generic log cannot safely provide.

### 4. OperationLog audit Adapter

- `OperationLogService.record()` already captures actor, role, action, target, request ID, IP, User-Agent, metadata and timestamp.
- It flushes but does not commit, so a caller can write business state and audit in the same transaction.
- This is the correct audit seam to retain; the change should remove only its responsibility as the sole business-state store.

### 5. Current Readiness gaps

- `ReadinessDossierService.create_review_action()` generates retraining task IDs from floating timestamps.
- It uses trace `request_id` as audit context but has no business idempotency key.
- It reconstructs state from a limited OperationLog window.
- The route uses the same guard as records GET, so write responsibility is not modeled separately.

## Feasible Approaches

### Approach A: Dedicated append-only action table plus audit Adapter — Recommended

- New table stores normalized business fields, idempotency key, request hash, expected previous action and audit-log reference.
- Lock the learner row before checking idempotency/current version and inserting.
- Write the action and OperationLog in one transaction.
- Dossier dual-reads the new table and legacy logs during compatibility rollout.
- The optimistic-concurrency baseline must also dual-read: before the first canonical action exists, the latest legacy OperationLog ID is the expected version; audit mirrors created for canonical actions are excluded from the legacy candidate set.

Benefits:

- Database-enforced uniqueness and queryable state.
- Explicit concurrency conflict instead of last-write-wins.
- Clear separation between business state and audit trail.
- Additive migration and compatible application rollback.

Costs:

- New model, migration and dual-read adapter.
- Frontend and backend request contract must be deployed together.

### Approach B: Continue using OperationLog and add metadata conventions

- Add idempotency key and expected version to metadata.
- Query logs before writing.

Benefits:

- Fewer files and no new table.

Costs:

- No portable JSON uniqueness constraint for the required key.
- State remains dependent on log query limits and untyped metadata.
- Concurrency and migration semantics stay fragile.

Conclusion: reject for this task.

### Approach C: Mutable single-row learner readiness state

- Store only the latest decision/version on a learner readiness row and keep history in logs.

Benefits:

- Fast latest-state reads and straightforward compare-and-swap.

Costs:

- Business history and audit history can diverge.
- Retraining comparisons need additional history structures.
- Harder rollback and weaker explanation than append-only decisions.

Conclusion: not needed for current scale; an aggregate snapshot can be added later if reads become a measured bottleneck.

## Recommendation

Use Approach A. It has the highest alignment with existing repository patterns while closing the specific Readiness integrity gaps. Keep the public Dossier Interface stable where possible, make the review request preconditions explicit, and treat legacy OperationLog actions as read-only compatibility data.
