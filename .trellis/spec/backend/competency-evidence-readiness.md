# Competency Evidence and Readiness Review

> Executable Slice 5 contract for canonical competency evidence, readiness
> dossiers, frozen review snapshots, human decisions, retraining, appeals, and
> exception approval previews.

## 1. Scope / Trigger

Apply this contract when changing:

- `competency_evidence/`, `readiness/`, or `foundation_readiness_composition.py`;
- an Activity Outcome writer that contributes to newcomer competency evidence;
- `/newcomer-training/dossier` or `/admin/newcomer-training/reviews*`;
- the Slice 5 Alembic schema, Evidence/Dossier rebuild, review permissions, or
  exception approval behavior.

`newcomer_training` remains the only writer of Enrollment, Attempt, and
`ActivityOutcome`. `competency_evidence` is the only writer of competency
catalog/mapping/evidence. `readiness` is the only writer of Dossier, Snapshot,
Decision, exception preview, retraining, appeal, calibration, and readiness
audit records. Root composition may coordinate these writers in one
transaction; domain packages must not import each other's ORM models.

## 2. Signatures

```python
class CompetencyEvidenceService:
    async def append_outcome(...) -> tuple[CompetencyEvidenceProjection, ...]: ...
    async def invalidate(...) -> CompetencyEvidenceProjection: ...

class ReadinessService:
    async def project(...) -> dict[str, object]: ...
    async def preview_exception_decision(
        *,
        actor: ReadinessActor,
        dossier_id: str,
        command: ExceptionDecisionPreviewInput,
        idempotency_key: str,
    ) -> dict[str, object]: ...
    async def record_decision(
        *,
        actor: ReadinessActor,
        dossier_id: str,
        command: ReviewDecisionInput,
        idempotency_key: str,
    ) -> dict[str, object]: ...
    async def assign_retraining(...) -> dict[str, object]: ...

class ExceptionDecisionPreviewInput(BaseModel):
    expected_dossier_version: int
    snapshot_id: str
    reason: str
    notes: str | None
    competency_keys: tuple[str, ...]
    evidence_ids: tuple[str, ...]

class ReviewDecisionInput(BaseModel):
    decision_type: Literal[
        "approve_foundation_ready",
        "request_retraining",
        "request_more_evidence",
        "reject_due_to_integrity_issue",
        "close_without_decision",
        "exception_approved",
    ]
    expected_dossier_version: int
    snapshot_id: str
    reason: str
    competency_keys: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    exception_confirmed: bool
    preview_token: str | None
    impact_hash: str | None
```

HTTP signatures, relative to `/api/v1`:

```text
GET  /newcomer-training/dossier
POST /newcomer-training/dossier/appeals
GET  /admin/newcomer-training/reviews
GET  /admin/newcomer-training/reviews/{dossier_id}
POST /admin/newcomer-training/reviews/{dossier_id}/commands/preview-exception
POST /admin/newcomer-training/reviews/{dossier_id}/commands/record-decision
POST /admin/newcomer-training/reviews/{dossier_id}/commands/assign-retraining
```

Mutation headers are `Idempotency-Key` and, for versioned dossier commands,
`If-Match: W/"<dossier_version>"`.

Schema authority is Alembic revision `20260717_1230_005`. The authoritative
tables include `canonical_competencies`, `canonical_competency_revisions`,
`competency_mappings`, `competency_evidence_records`,
`competency_evidence_validity_events`, `readiness_dossiers`,
`readiness_dossier_snapshots`, `readiness_review_decisions`,
`readiness_exception_previews`, `readiness_retraining_assignments`,
`readiness_appeals`, `readiness_calibration_sessions`,
`readiness_ai_summaries`, and `readiness_command_audits`.

## 3. Contracts

- The standard competency keys are exactly `product_knowledge`,
  `customer_understanding`, `needs_discovery`, `value_expression`,
  `objection_handling`, `process_compliance`, and
  `communication_structure`. Definitions are revisioned; history is never
  rewritten.
- One `(organization_id, outcome_id, outcome_version,
  competency_revision_id)` creates at most one Evidence record. Regrade adds a
  new Outcome/Evidence and `supersedes_*` lineage; invalidation appends a
  validity event.
- `pending_review`, `insufficient_quality`, `invalidated`, and superseded
  evidence cannot satisfy readiness. A quality/technical failure is not a zero
  score.
- One Enrollment has one Dossier. Incremental projection and full rebuild use
  the same immutable Evidence and policy revision and must converge.
- A Snapshot freezes evidence IDs, competency revisions, policy revision,
  PathRevision, and projection. New effective evidence marks the old Snapshot
  and Dossier stale; it never mutates review material silently.
- Only a human actor with `readiness.review` and organization/Team object scope
  may record a formal decision. `approve_foundation_ready` additionally
  requires an eligible current Snapshot plus non-empty competency/evidence
  references from that Snapshot.
- `exception_approved` is not normal approval. Preview persists a 15-minute
  record bound to reviewer, Dossier/Snapshot/version, reason, notes hash, and
  exact competency/evidence references. Confirmation must consume the same
  token and impact hash with `exception_confirmed=true`. A changed version,
  Snapshot, reviewer, reason, notes, or reference set invalidates the preview.
- Review decisions are append-only. A later valid decision supersedes the prior
  row; replay with the same idempotency key and payload returns the original
  row.
- Learner projections omit risk bands/reasons, reviewer private notes, raw AI
  drafts, Evidence lineage/source refs, and other learners' data. AI summaries
  are auxiliary and cannot grant readiness.
- Retraining is assigned within the Dossier. Existing activities must be
  published; a quick draft remains non-executable until governance completes.
  Only a newer terminal Outcome can complete an assignment.

## 4. Validation & Error Matrix

| Condition | Required result |
|---|---|
| Outcome replay with same version | Return existing Evidence; no duplicate row |
| Regrade supersedes an older Outcome | Append Evidence and preserve old history |
| Unscorable/pending/invalid Evidence | Exclude from formal Gate; explain quality state |
| Dossier version differs from `If-Match`/command | HTTP 412 `[DOSSIER_VERSION_CONFLICT]`; audit rejection |
| Snapshot is stale/not current | HTTP 412 `[DOSSIER_SNAPSHOT_STALE]`; preserve input and audit |
| AI/system identity submits a decision | HTTP 403 `[READINESS_HUMAN_REVIEW_REQUIRED]`; no Decision |
| Normal approval is not eligible | HTTP 409 `[DOSSIER_NOT_ELIGIBLE]`; no Decision |
| Formal approval omits Evidence/competency references | HTTP 422 `[DOSSIER_DECISION_REFERENCES_REQUIRED]` |
| Reference is outside frozen Snapshot | HTTP 422 `[DOSSIER_REFERENCE_INVALID]` |
| Exception has no preview/token/hash/confirm | HTTP 409 `[READINESS_EXCEPTION_CONFIRMATION_REQUIRED]` |
| Exception preview is expired/used/wrong reviewer or context | HTTP 409 typed preview error; no Decision |
| Exception payload differs from preview | HTTP 409 `[READINESS_EXCEPTION_IMPACT_CHANGED]`; re-preview |
| Open appeal or retraining precedes approval | HTTP 409 `[DOSSIER_BLOCKING_FOLLOW_UP]` |
| Cross-organization or out-of-Team access | Safe 404/403 according to endpoint; audit; no existence leak |
| Same idempotency key with different payload | HTTP 409 `[READINESS_IDEMPOTENCY_CONFLICT]` |

## 5. Good / Base / Bad Cases

- **Good**: an Outcome is stored once, projected to seven immutable Evidence
  records, frozen into a Dossier Snapshot, reviewed by an in-scope human, and
  approved with exact Evidence references. A later regrade marks the Snapshot
  stale and requires a new review without changing the old Decision.
- **Base**: AI summary generation fails. The deterministic Dossier remains
  usable; a Reviewer can inspect Evidence, assign retraining, or record a
  non-approval decision.
- **Bad**: an activity domain writes `readiness_dossiers` directly, the UI
  averages scores to infer readiness, a boolean alone grants an exception, a
  regrade overwrites Evidence, or a stale Snapshot is silently refreshed while
  a Reviewer is deciding.

## 6. Tests Required

- Unit: seven-key catalog stability; Evidence idempotency, supersession,
  invalidation, quality exclusion, latest-shortfall behavior, incremental vs
  rebuild convergence.
- Unit: human-only approval, required Snapshot references, stale/version
  rejection audit, same-key replay, competing Reviewer conflict, durable
  exception preview replay/impact binding/consumption.
- Integration: learner/admin route contract, role capability matrix,
  organization/Team denial, export denial, and response redaction.
- Migration: upgrade creates all authoritative tables/constraints/indexes and
  downgrade removes only Slice 5 schema.
- Frontend: learner redaction, risk queue, formal decision, inline retraining,
  appeal input preservation, and exception preview plus explicit confirmation.
- Run focused Ruff/mypy/ESLint/Vitest, generated OpenAPI parity, architecture
  dependency guard, and the CodeGraph-selected focused regression tests. Real
  PostgreSQL concurrency and browser E2E remain final release-gate evidence.

## 7. Wrong vs Correct

### Wrong

```python
if command.decision_type == "exception_approved" and command.confirmed:
    dossier.state = "decided"
```

This does not prove what impact the Reviewer saw and allows changed evidence,
reason, or scope to be approved after the confirmation UI was rendered.

### Correct

```python
preview = await service.preview_exception_decision(
    actor=reviewer,
    dossier_id=dossier_id,
    command=preview_input,
    idempotency_key=preview_key,
)
decision = await service.record_decision(
    actor=reviewer,
    dossier_id=dossier_id,
    command=ReviewDecisionInput(
        decision_type="exception_approved",
        preview_token=preview["preview_token"],
        impact_hash=preview["impact_hash"],
        exception_confirmed=True,
        **same_frozen_inputs,
    ),
    idempotency_key=decision_key,
)
```

The service rechecks current version/Snapshot/scope, recomputes the impact,
consumes the durable preview, and records the immutable Decision in one
transaction.
