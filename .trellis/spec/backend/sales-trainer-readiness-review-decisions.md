# Sales Trainer Readiness Review Decisions

> Executable contract for the human decisions that open or keep closed the
> newcomer realtime-practice gate.

---

## 1. Scope / Trigger

Read this spec before changing any of the following:

- `review_readiness` capability projection or Sales Trainer reviewer roles;
- `POST /api/v1/admin/sales-trainer/readiness/dossiers/{learner_id}/review-actions`;
- `sales_trainer_readiness_review_actions` or migration `20260710_1200_092`;
- Dossier review-history merge, latest-action selection, or realtime gate logic;
- learner `TrainingJourney.retraining_requests[]` projection;
- the admin Readiness confirmation and retry flow.

The three supported decisions are business state, not generic audit events.
They therefore require a canonical append-only table, while
`SalesTrainerOperationLog` remains a same-transaction audit adapter.

---

## 2. Signatures

### Authorization

```python
def can_review_sales_trainer_readiness(user: User) -> bool:
    return is_sales_trainer_admin(user) or is_sales_trainer_manager(user)
```

- Platform administrators have global scope.
- Manager roles from the existing `SALES_TRAINER_MANAGER_ROLES` allowlist have
  same-department scope only.
- Operations roles may read global records and Dossiers but must have
  `review_readiness=false`.

### HTTP request

```python
class ReadinessDossierReviewActionCreate(BaseModel):
    decision: Literal[
        "approve",
        "require_retraining",
        "mark_manual_follow_up",
    ]
    reason: str                         # stripped, 1..1000
    capability_keys: list[str]          # maximum 20
    source_evidence_ids: list[str]      # maximum 50
    idempotency_key: str                # stripped, 16..100
    expected_latest_review_action_id: str | None  # key required, value nullable
```

### Canonical storage

```text
sales_trainer_readiness_review_actions
  action_id                      PK
  learner_id                     FK users.user_id
  actor_id                       FK users.user_id
  actor_role
  decision                       CHECK three-value allowlist
  reason
  capability_keys                JSON
  source_evidence_ids            JSON
  retraining_task                JSON nullable
  idempotency_key
  request_hash
  expected_previous_action_id    nullable
  audit_log_id                   nullable audit adapter reference
  created_at

UNIQUE (actor_id, idempotency_key)
INDEX  (learner_id, created_at)
```

### Decision service

```python
await ReadinessReviewActionService(db).create(
    learner_id=learner_id,
    actor=actor,
    team_department=team_department,
    decision=decision,
    reason=reason,
    capability_keys=persisted_capability_keys,
    source_evidence_ids=persisted_evidence_ids,
    request_capability_keys=raw_normalized_request_capability_keys,
    request_source_evidence_ids=raw_normalized_request_evidence_ids,
    idempotency_key=idempotency_key,
    expected_latest_review_action_id=expected_latest_review_action_id,
    audit_context=audit_context,
)
```

---

## 3. Contracts

### Authorization and object scope

- Both the route guard and `ReadinessReviewActionService` enforce write
  authorization. Hiding the Web form is not authorization.
- A department-scoped reviewer without a department fails closed.
- A department reviewer targeting another department receives 404
  `[TRAINING_RECORD_NOT_FOUND]`; do not reveal whether that learner exists.
- `view_records` and `review_readiness` are independent capabilities. Never use
  the records-view guard for this POST route.

### Append-only state and audit

- New decisions are inserted only into the canonical action table. Do not
  update or delete an earlier decision to change the latest state.
- The action flush and `SalesTrainerOperationLog` flush happen in one database
  transaction, followed by one commit. Audit failure must leave no committed
  action.
- `require_retraining` derives a stable task ID as
  `retraining:{action_id}`; timestamps are not identifiers.
- Do not add notification, HTTP, model, queue, or other external I/O inside the
  locked decision transaction.

### Idempotency

- Idempotency scope is `(actor_id, idempotency_key)` and is enforced by the
  database unique constraint.
- The request hash contains learner, decision, stripped reason, and sorted raw
  normalized capability/evidence lists. It deliberately excludes
  `expected_latest_review_action_id` and mutable Dossier-derived defaults.
- Same key and same hash returns the original action before version checking
  and creates no second audit row. Same key and different hash returns 409.
- A uniqueness race may require `AsyncSession.rollback()`. Cache primitive
  actor fields before that rollback; ORM instances are expired by rollback and
  async attribute access can otherwise raise `MissingGreenlet`.
- Only the named actor/idempotency unique violation may enter replay recovery.
  Other `IntegrityError` instances must propagate.

### Optimistic concurrency and legacy compatibility

- Lock the learner row before selecting the version baseline and inserting.
- The current version is the newest of the canonical action and unmirrored
  legacy OperationLog review actions. Exclude logs referenced by canonical
  `audit_log_id` and logs marked `state_storage=readiness_review_action`.
- Compare candidates by `(created_at UTC, action_or_log_id)` everywhere. The
  write path and Dossier read path must use the same deterministic tie-break.
- `ReadinessReviewActionService.list_merged_for_learner()` is the shared
  canonical-plus-legacy reader for Dossier, write-version selection, and
  learner retraining projection. It returns actions newest first and de-dupes
  canonical audit mirrors. Do not reconstruct learner business state directly
  from a bounded OperationLog query.
- Dossier exposes `state_storage` only in the API DTO. Ordinary UI must not
  render storage names, raw IDs, trace IDs, or raw JSON.

### Web confirmation and retry

- Freeze learner, decision, stripped reason, capability keys, evidence IDs,
  expected latest ID, and a new UUID idempotency key before confirmation.
- Empty UI selections mean “use current Dossier defaults”. Resolve those
  defaults into the frozen snapshot so the confirmation exactly matches the
  capability/evidence references sent and persisted.
- The confirmation action rechecks the frozen learner/version against the
  current route and Dossier synchronously before sending.
- Guard GET and POST continuations with learner/request generations. A response
  started for learner A must not mutate learner B state after a dynamic-route
  switch; reset the form draft and status when the learner changes.
- Network retry reuses the same frozen snapshot and token. Editing any business
  field, manual refresh, success, route change, or version change discards it.
- A 409 version conflict refreshes the Dossier and requires a new confirmation;
  it must never automatically replay the old decision.
- Read-only users see the Dossier and a read-only explanation, not the form.

---

## 4. Validation & Error Matrix

| Condition | Result |
|---|---|
| Missing/invalid HTTP request field | FastAPI 422 native `detail[]`; Web client maps locally to `[REQUEST_VALIDATION_ERROR]` |
| Actor lacks `review_readiness` | 403 `[READINESS_REVIEW_ROLE_REQUIRED]` |
| Learner missing or outside reviewer department | 404 `[TRAINING_RECORD_NOT_FOUND]` |
| Direct service call uses invalid decision | 400 `[READINESS_REVIEW_DECISION_INVALID]` |
| Direct service call uses blank reason | 400 `[READINESS_REVIEW_REASON_REQUIRED]` |
| Direct service call uses invalid idempotency key | 400 `[READINESS_IDEMPOTENCY_KEY_INVALID]` |
| Same actor/key, different request hash | 409 `[READINESS_IDEMPOTENCY_KEY_REUSED]` without details |
| Expected latest differs from merged current version | 409 `[READINESS_REVIEW_VERSION_CONFLICT]` with `details.latest_review_action_id` |
| Unknown capability/evidence reference | 400 typed Dossier error with only unknown identifiers in API details |
| Approve before pending-review evidence is ready | 409 `[READINESS_DOSSIER_NOT_READY]` |
| Non-realtime configuration blocks approval | 409 `[READINESS_DOSSIER_CONFIG_BLOCKED]` |
| Canonical action flush succeeds but audit flush fails | Transaction fails; neither action nor audit commits |

---

## 5. Good / Base / Bad Cases

- **Good:** a training manager confirms a same-department learner using a
  frozen snapshot; a timed-out retry returns the same action and one audit row.
- **Base:** a learner has only historical OperationLog decisions; the Dossier
  displays them and accepts the latest legacy log ID as the first canonical
  write's expected version.
- **Bad:** an ops user can POST because the route reused `view_records`.
- **Bad:** a caller hashes Dossier-expanded default evidence; a retry after new
  evidence appears is falsely treated as a different request.
- **Bad:** the Web client refreshes after 409 and automatically resends the old
  approval against the new version.

---

## 6. Tests Required

- Permission unit and API integration: platform admin global; every configured
  manager role same-department; cross-department 404; ops read-only 403;
  content admin and ordinary user denied.
- Service unit: three-value allowlist, same-body replay, different-body reuse,
  real unique-constraint recovery, unrelated `IntegrityError` propagation,
  stale canonical version, legacy version baseline, deterministic time ties,
  stable retraining task ID, audit failure rollback, newest-first append-only
  list.
- Dossier unit: canonical/legacy merge, audit mirror de-duplication, latest
  source, approve/retraining/manual-follow-up gate projections, mutable-default
  idempotency replay.
- TrainingJourney unit: a canonical retraining action remains visible even if
  no OperationLog mirror is available; a newer approve clears the projection.
- Frontend API test: token and expected-latest pass through unchanged.
- Page test: explicit confirmation before POST; frozen snapshot; duplicate-click
  guard; empty-selection effective defaults; same-token network retry;
  edit/refresh/route/version invalidation; stale GET/POST completion after a
  learner switch; 409 refresh without replay; read-only ops surface; safe error
  copy; no raw IDs or internal terms.
- Migration verification: isolated `091 -> 092 -> 091 -> 092`; downgrade drops
  only the canonical table and preserves historical OperationLog rows.

---

## 7. Wrong vs Correct

### Wrong

```python
# Read access accidentally grants a high-impact write, and generic logs become
# the only business state.
if can_view_sales_trainer_records(actor):
    await operation_logs.record(action="readiness.review_action.created", ...)
    await db.commit()
```

### Correct

```python
if not can_review_sales_trainer_readiness(actor):
    raise ReadinessReviewActionError(
        "[READINESS_REVIEW_ROLE_REQUIRED]",
        "当前账号无权执行训练达标复核。",
        403,
    )

action = SalesTrainerReadinessReviewAction(...)
db.add(action)
await db.flush()
audit = await operation_logs.record(...)
action.audit_log_id = str(audit.log_id)
await db.commit()
```

The service owns authorization, idempotency, locking, state insertion, and
audit orchestration. The Dossier owns evidence validation and compatible
read-model projection; the Web client owns confirmation UX, not authorization.
