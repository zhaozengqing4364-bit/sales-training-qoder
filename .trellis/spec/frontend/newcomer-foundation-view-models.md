# Newcomer Foundation ViewModel Contract

> Target contract accepted on 2026-07-16; implementation and final release gates completed on 2026-07-18. The canonical learner Journey, five Activity Workspaces, Task/Notification recovery, Evidence Dossier, readiness review, server-first learner entry, unified Admin workspace, shared DTO-to-ViewModel layer, Legacy cleanup, and rendered release checks are all active contracts.

## 1. Scope / Trigger

Apply when implementing or changing the learner Journey, Activity Workspace, Task Status, Evidence Dossier, admin queues, their API DTOs, presenters, routes, filters, permissions, or recovery states from `docs/api-contract/newcomer-training-v2.md`.

The public page-model names are `JourneyProjectionV1`, `ActivityWorkspaceV1`, `TaskStatusV1`, `EvidenceDossierV1`, and `AdminQueueV1`. Data must flow `API DTO -> Domain Model -> pure ViewModel -> UI`; a page may not combine cross-domain DTOs to calculate readiness.

`/newcomer-training` is the only learner entry and the reachable navigation contains only current training, history, profile, and notifications/tasks. Quiz start disclosure renders question count, pass threshold, max attempts, retry interval, estimated duration, time limit and frozen-snapshot behavior from the server contract; it does not hard-code business thresholds. The editable Admin workspace and ReleasePlan UI live under `/admin/newcomer-training`; retired learner/admin route files are absent from runtime composition and OpenAPI.

## 2. Signatures

```typescript
type ActivityTypeV1 =
  | "lesson"
  | "quiz"
  | "audio_assessment"
  | "ai_coach"
  | "assignment";

type PageLoadState =
  | "loading"
  | "ready"
  | "first_use_empty"
  | "filtered_no_result"
  | "partial"
  | "recoverable_error"
  | "fatal_error"
  | "permission_denied"
  | "stale_conflict"
  | "submitting"
  | "retrying"
  | "cancelled"
  | "offline_degraded"
  | "background_pending";

type ContractMetaV1 = Readonly<{
  contractVersion: "1";
  generatedAt: string;
  dataFreshness: "fresh" | "stale" | "partial";
  capabilities: readonly string[];
}>;

type AssignmentSegmentV1 = Readonly<{
  segmentId: string;
  title: string;
  objective: string;
  timeLimitSeconds: number;
  state: "not_started" | "uploading" | "processing" | "needs_review" | "completed";
  taskId?: string;
  outcomeId?: string;
}>;

type AssignmentRunnerV1 = Readonly<{
  kind: "assignment";
  segmentCount: 3;
  segments: readonly [AssignmentSegmentV1, AssignmentSegmentV1, AssignmentSegmentV1];
}>;

type PresenterResult<T> = Readonly<{
  state: PageLoadState;
  data?: T;
  message?: string;
  recoveryAction?: Readonly<{ label: string; command: string }>;
}>;

type ReadinessExceptionPreviewV1 = Readonly<{
  contract_version: "readiness_exception_preview_v1";
  dossier_version: number;
  snapshot_id: string;
  impact: Readonly<{
    contract_version: "readiness_exception_impact_v1";
    overridden_competency_gaps: readonly string[];
    risk_reasons: readonly string[];
    competency_keys: readonly string[];
    evidence_ids: readonly string[];
    reason: string;
  }>;
  preview_token: string;
  impact_hash: string;
  expires_at: string;
}>;

declare function toJourneyViewModel(
  dto: JourneyProjectionV1Dto,
  context: PresenterContext,
): PresenterResult<JourneyProjectionV1>;

declare function toActivityWorkspaceViewModel(
  dto: ActivityWorkspaceV1Dto,
  context: PresenterContext,
): PresenterResult<ActivityWorkspaceV1>;

declare function toTaskStatusViewModel(
  dto: TaskStatusV1Dto,
  context: PresenterContext,
): PresenterResult<TaskStatusV1>;

declare function toEvidenceDossierViewModel(
  dto: EvidenceDossierV1Dto,
  context: PresenterContext,
): PresenterResult<EvidenceDossierV1>;

declare function toAdminQueueViewModel(
  dto: AdminQueueV1Dto,
  context: PresenterContext,
): PresenterResult<AdminQueueV1>;
```

`PresenterContext` contains locale, current route/query, clock, and projected capabilities only. It must not contain ORM rows, Provider clients, scoring thresholds, or permission overrides.

## 3. Contracts

- DTOs retain API `snake_case`; the domain mapper normalizes dates, stable codes, closed unions, and opaque IDs; presenters produce user-language fields and never mutate DTOs.
- Every page model carries `ContractMetaV1`. Unknown `contract_version` is a fatal contract error, not a best-effort cast.
- Exactly one visible `primaryAction` is allowed in Journey and Activity Workspace. Secondary and destructive actions remain distinct and capability-gated.
- `available_commands` is authoritative for affordance, but the backend still enforces permission and state. The UI never enables a command by role-name inference.
- The first-launch activity union is exactly five types. Realtime has no target DTO, renderer, navigation item, seed entry, fallback, or unknown-type coercion.
- Assignment is only `AssignmentRunnerV1`: exactly three asynchronous customer-scenario audio segments with stable segment identities, per-segment objective/time limit, Task/Outcome references, and review state. Text/file homework payloads are invalid.
- Task pages have a stable `resultLocation`; refresh/back/navigation can recover running and terminal state. An important success or partial failure is persisted, never toast-only.
- The Coach runner is a discriminated typed-card workspace, never a blank chat surface. It renders exactly one current card, backend-projected checkpoint/progress/config limits, source labels, persisted feedback/assistance and one dominant command from `available_commands`.
- Coach feedback labels deterministic output as a rule judgment and language evaluation as AI inference. The runner never presents model-reported mastery as a verified fact and never hard-codes the mastery threshold or remediation limit.
- Evidence Dossier renders facts, deterministic rules/calculations, AI inference, recommendations, and human decision as separate typed sections. Presenters never calculate `foundation_ready`.
- Exception approval is an inline two-step command, not a generic confirmation dialog: preview the current version/Snapshot/reason/references, render the returned gaps and risk reasons, require an explicit checkbox, then submit the exact preview token and impact hash. Editing any bound input clears the preview and confirmation locally; the backend still revalidates everything.
- Admin queues preserve server `applied_filters`, `sort`, pagination, freshness, object scope, and per-row capabilities. A 403 is `permission_denied`, never an empty queue.
- Ordinary UI never renders Phase/Module, raw enum, Prompt, Provider, trace ID, raw JSON, database ID, Mock, Seed, internal error code, or model output as a verified fact.
- UX analytics uses the closed `newcomer_foundation.*` counter vocabulary only: journey/activity entry, activity start/complete, progress save/draft restore, upload interruption, task waiting, remediation, review requested and review completed. The dimension is limited to the five activity types, background task or review; free-form answers, transcripts, Prompt, learner/object IDs and raw errors are never accepted. Delivery is non-blocking and failure cannot change the business command result.

## 4. Validation & Error Matrix

| Input / condition | Presenter or route result |
|---|---|
| `contract_version !== "1"` | `fatal_error`; block commands; offer refresh/support path |
| Unknown activity type | `fatal_error`; do not coerce to Assignment or a generic renderer |
| Assignment has not exactly three unique segment IDs matching the frozen ActivityDefinition | `fatal_error`; no upload/complete command |
| Required field absent but API marks data partial | `partial`; preserve valid data and show recovery |
| Required field absent without partial marker | `fatal_error`; contract telemetry; no fabricated default |
| Capability absent | hide/disable action as specified and retain explanatory state; never infer authorization |
| API 403/404 scoped denial | `permission_denied` or safe not-found copy; no existence leak |
| API 409 idempotency/state conflict | preserve input; query current result; show actionable conflict |
| API 412 version conflict | `stale_conflict`; preserve input and require reload/review |
| Exception confirmation has no current preview | Disable confirm; retain reason/notes; offer “预览例外影响” |
| Exception preview expires or impact changes | Preserve reason/notes; clear confirmation; request a new preview |
| Timeout after a possible write | keep submitting context; retry with the same idempotency key |
| Background Task retryable failure | `recoverable_error` with stable task/result location |
| Background Task terminal partial result | `partial`; list succeeded/failed/skipped scopes and next action |
| Unknown enum/status label | safe explicit “状态暂不可识别”; retain raw value only in authorized diagnostics |
| Offline with cached safe projection | `offline_degraded`; disable writes and expose freshness |

## 5. Good / Base / Bad Cases

- **Good**: after refresh, an Assignment workspace restores three segment states and one running Task; two completed segments stay complete, the failed segment offers one retry action, and the Attempt is not presented as complete.
- **Base**: Journey renders the frozen Enrollment revision, current Stage, one primary action, server-projected progress, and no Realtime entry. A same-key uncertain retry returns the original accepted command.
- **Bad**: JSX reads several raw DTOs, calculates readiness from scores, treats 403 as an empty list, maps unknown activity types to a generic card, or accepts `{text, file}` for Assignment.

## 6. Tests Required

- Contract: generated OpenAPI DTOs and frontend DTO types have field/union parity for all five page models and every list filter/sort allowlist.
- Unit: each presenter is pure and covers unknown contract/activity/status, partial data, permission, long content, large values, stale freshness, and no fabricated defaults.
- Unit: Assignment rejects zero/two/four/duplicate/unknown segment IDs and accepts only the exact three-segment tuple frozen by ActivityDefinition.
- Route/component: cover every applicable `PageLoadState`, same-token retry after uncertain writes, input preservation, one dominant action, and persistent success/partial result.
- Route/component: exception approval cannot submit before preview plus explicit confirmation; preview risk/gaps are visible; editing reason/notes invalidates local preview; confirm sends the same token/hash.
- Security: 403/cross-organization/object denial never renders empty success or leaks object existence; action visibility matches capabilities but backend denial remains handled.
- Playwright: one learner path, all five Activity workspaces, Assignment refresh recovery, one manager review, cross-organization denial, 360px, 200% zoom, keyboard/focus, long Chinese/English text, slow network, and background Task recovery.

## 7. Wrong vs Correct

### Wrong: page derives a formal result from raw DTOs

```typescript
const ready = attempts.every((item) => (item.score ?? 0) >= 80);
return <Badge>{ready ? "已达标" : "未达标"}</Badge>;
```

This invents a threshold, ignores evidence validity and human review, and bypasses the Dossier authority.

### Correct: pure presenter renders the contracted projection

```typescript
const result = toEvidenceDossierViewModel(dto, presenterContext);
return <EvidenceDossierScreen result={result} />;
```

The API/domain projection distinguishes evidence, AI assessment, deterministic Gate, and human decision. The component renders that ViewModel and submits only commands advertised by the contract.

The existing `types.ts`, `client.ts`, Phase/Module projections, generic text/file Assignment, and realtime renderer are Legacy migration sources until their owning slices remove the corresponding consumers.
