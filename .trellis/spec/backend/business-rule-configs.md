# Business Rule Configs

> Governed runtime policy configuration for adjustable business rules. Use this when thresholds, labels, actions, toggles, templates, or operator-managed rules affect backend behavior or admin UI.

---

## Core Convention

Adjustable business rules must enter the shared business-rule lifecycle instead of environment variables, page constants, or service-local dictionaries.

Required backend pieces:

- `backend/src/common/business_rules/defaults.py` defines the key, bundled default, and `BusinessRuleDefinition`.
- `backend/src/common/business_rules/validators.py` validates and normalizes the value.
- Runtime code calls `BusinessRuleConfigService.resolve_active_config()` through a domain resolver.
- Admin/API payloads expose the effective source, fallback state, management entry, permission, and effective timing.

Do not create one-off config tables or ad hoc service constants unless the shared lifecycle cannot carry the rule and the reason is documented in the task/ADR.

---

## Scenario: Sales Trainer Phase 2 Closed-Loop Policy

### 1. Scope / Trigger

- Trigger: Sales Trainer Phase 2 uses configurable thresholds, manager actions, remediation templates, and dashboard record limits across backend services, API responses, and admin UI.
- This is a cross-layer contract. Code-spec depth is mandatory because changing the rule shape affects `business_rule_configs`, settings payloads, dashboard payloads, training-record projections, and frontend API types.
- Business rules in scope: weak-score threshold, repeated-practice threshold, dashboard window size, manager action labels/priorities, remediation reason/path templates.
- Stable code in scope: score projection algorithm, team-scope authorization, record-type allowlist, and fallback mechanics.

### 2. Signatures

Backend constants and defaults:

```python
SALES_TRAINER_PHASE2_CLOSED_LOOP_POLICY_KEY = "sales_trainer.phase2.closed_loop_policy"
DEFAULT_SALES_TRAINER_PHASE2_POLICY: dict[str, Any]
```

Business-rule definition shape:

```python
BusinessRuleDefinition(
    key=SALES_TRAINER_PHASE2_CLOSED_LOOP_POLICY_KEY,
    domain="sales_trainer",
    schema_version=BUSINESS_RULE_SCHEMA_VERSION,
    default_value=DEFAULT_SALES_TRAINER_PHASE2_POLICY,
    type="rule_json",
    range_or_allowlist={...},
    read_path="sales_trainer.services.phase2_policy.resolve_phase2_policy",
    admin_entry="/admin/business-rules/sales-trainer-phase2",
    permission="admin_publish_only",
    audit_policy="draft/validate/preview/publish/rollback require actor, before/after version, reason, trace_id",
    fallback_policy="use bundled default phase-2 policy when database config is missing, invalid, or disabled",
    rollback_policy="restore a prior archived/published phase-2 policy version",
)
```

Validation and runtime resolution:

```python
def validate_business_rule_value(key: str, value: dict[str, Any]) -> dict[str, Any]: ...

async def BusinessRuleConfigService.resolve_active_config(
    key: str,
    *,
    fallback_value: dict[str, Any] | None = None,
    fallback_source: str = "default",
) -> BusinessRuleResolution: ...

async def resolve_phase2_policy(
    db: AsyncSession | None = None,
) -> tuple[SalesTrainerPhase2Policy, dict[str, Any]]: ...
```

Admin API consumers:

```http
GET /api/v1/admin/sales-trainer/settings
GET /api/v1/admin/sales-trainer/manager-dashboard
GET /api/v1/admin/sales-trainer/training-records/detail/{record_type}/{record_id}
```

Database authority:

- `business_rule_configs`: versioned value, default value, status, read path, admin entry, permission, validation errors.
- `business_rule_config_audit_logs`: draft, validate, preview, publish, rollback, disable, delete-draft audit trail.

### 3. Contracts

Config value:

```typescript
interface SalesTrainerPhase2ClosedLoopPolicyConfig {
  version: string;
  enabled: boolean;
  low_score_threshold: number; // 0..100, default 70
  repeat_practice_threshold: number; // 1..20, default 2
  dashboard_record_limit: number; // 1..5000, default 500
  manager_actions: Array<{
    code: "not_passed" | "low_score" | "repeated_practice" | "fallback";
    label: string;
    priority: "low" | "medium" | "high";
  }>;
  remediation_actions: Array<{
    record_type: "audio_submission" | "quiz_attempt" | "ai_coach_session" | "default" | "no_action";
    action_label: string;
    reason_template: string;
    target_path_template: string;
    priority: "low" | "medium" | "high";
  }>;
}
```

Template placeholders accepted by `reason_template` and `target_path_template`:

- `{record_id}`
- `{record_type}`
- `{unit_id}`
- `{module_key}`
- `{score}`
- `{threshold}`
- `{result_path}`

Policy diagnostic payload returned by settings/dashboard:

```typescript
interface SalesTrainerPhase2PolicyPayload {
  key: "sales_trainer.phase2.closed_loop_policy";
  version: string;
  enabled: boolean;
  low_score_threshold: number;
  repeat_practice_threshold: number;
  dashboard_record_limit: number;
  source: "database" | "database_previous" | "default";
  config_id?: string | null;
  config_version?: number | null;
  status?: string | null;
  fallback_applied: boolean;
  fallback_reason?: string | null;
  management_entry: "/admin/business-rules/sales-trainer-phase2";
  permission: "admin_publish_only";
  effective_timing: "request_time";
}
```

Resolution source semantics:

- `database`: active published config validated successfully.
- `database_previous`: active config was invalid, so the latest valid history before it was used.
- `default`: active config was missing, invalid with no valid history, disabled, or no DB was supplied.
- `database_disabled`: internal `BusinessRuleConfigService` source only. Domain resolvers must convert disabled active configs to bundled default payloads with `source="default"`, `fallback_applied=true`, and `fallback_reason="active_disabled"` when disabled means "do not use this runtime strategy".

Frontend contract:

- Add DTOs to `web/src/lib/api/types.ts`; do not define page-local duplicates.
- Add domain methods to `web/src/lib/api/client-domains.ts`.
- Admin pages may display policy diagnostics and link to `management_entry`, but must not edit governed policy inline outside the business-rule management surface.

### 4. Validation & Error Matrix

| Condition | Expected behavior |
|---|---|
| `low_score_threshold` missing | Normalize to `70.0` |
| `low_score_threshold` is not numeric | `BusinessRuleValidationError("low_score_threshold must be numeric")` |
| `low_score_threshold` outside `0..100` | `BusinessRuleValidationError("low_score_threshold must be within [0, 100]")` |
| `repeat_practice_threshold` outside `1..20` | `BusinessRuleValidationError("repeat_practice_threshold must be within [1, 20]")` |
| `dashboard_record_limit` outside `1..5000` | `BusinessRuleValidationError("dashboard_record_limit must be within [1, 5000]")` |
| `manager_actions` missing or empty | `BusinessRuleValidationError("manager_actions must be a non-empty list")` |
| Unknown manager action code | `BusinessRuleValidationError("unsupported manager action code: ...")` |
| Duplicate manager action code | `BusinessRuleValidationError("duplicate manager action code: ...")` |
| Missing required manager action code | `BusinessRuleValidationError("missing manager action codes: ...")` |
| Unknown remediation `record_type` | `BusinessRuleValidationError("unsupported remediation record_type: ...")` |
| Duplicate remediation `record_type` | `BusinessRuleValidationError("duplicate remediation record_type: ...")` |
| Missing required remediation `record_type` | `BusinessRuleValidationError("missing remediation record_types: ...")` |
| Invalid template placeholder | `BusinessRuleValidationError("<field> has invalid placeholders")` |
| Active DB config missing | Use bundled default; payload `fallback_applied=true`, `fallback_reason="active_missing"` |
| Active DB config invalid, previous valid config exists | Use previous valid config; payload `source="database_previous"`, `fallback_reason="active_invalid_used_previous"` |
| Active DB config invalid, no valid history | Use bundled default; payload `source="default"`, `fallback_applied=true` |
| Active DB config disabled | Use bundled default; payload `source="default"`, `fallback_applied=true`, `fallback_reason="active_disabled"` |
| `resolve_phase2_policy(db=None)` | Use bundled default; payload `fallback_reason="db_not_provided"` |
| Detail API `record_type` not in the allowlist | Return `[TRAINING_RECORD_TYPE_INVALID]` with HTTP 400 |
| Detail record missing or outside team scope | Return `[TRAINING_RECORD_NOT_FOUND]` with HTTP 404 |
| Frontend receives no `phase2_policy` | Render empty/unknown diagnostics and no inline editor |

### 5. Good/Base/Bad Cases

- Good: an admin publishes a valid database policy; dashboard and settings show `source="database"`, `fallback_applied=false`, and all remediation labels come from the policy.
- Base: no policy has been seeded or the active config is disabled; runtime still works with bundled defaults and exposes fallback diagnostics.
- Bad: a page hardcodes `70`, `2`, or remediation labels locally; operators cannot audit, rollback, or safely change the rule.

### 6. Tests Required

- Validator unit tests:
  - bundled default validates unchanged;
  - invalid thresholds fail with the exact validation message;
  - missing manager/remediation codes fail;
  - invalid template placeholders fail;
  - normalized defaults are applied when optional thresholds are omitted.
- Resolver tests:
  - active valid config returns `source="database"`;
  - active invalid config falls back to `database_previous` when available;
  - missing/disabled config returns bundled default and fallback diagnostics;
  - `db=None` returns `fallback_reason="db_not_provided"`.
- API tests:
  - settings response includes `phase2_policy`;
  - manager dashboard includes the same policy diagnostic payload;
  - detail endpoint rejects invalid `record_type`;
  - detail endpoint hides records outside `_team_scope`.
- Frontend tests:
  - `lib/api/types.ts` and `client-domains.ts` expose typed manager-dashboard and detail methods;
  - settings page renders policy source/version/fallback reason from API data;
  - pages do not define duplicate policy DTOs or hardcode thresholds.

### 7. Wrong vs Correct

#### Wrong

```python
LOW_SCORE_THRESHOLD = float(os.getenv("SALES_TRAINER_LOW_SCORE_THRESHOLD", "70"))

def needs_remediation(score: float | None) -> bool:
    return score is None or score < LOW_SCORE_THRESHOLD
```

This bypasses versioning, validation, admin visibility, audit logs, rollback, and frontend diagnostics.

#### Correct

```python
policy, policy_payload = await resolve_phase2_policy(db)

record["remediation"] = {
    "needed": score is None or score < policy.low_score_threshold,
    "action_label": policy.remediation_action(record_type, needed=True)["action_label"],
}
settings_payload["phase2_policy"] = policy_payload
```

The runtime uses one governed policy object, while the API exposes the effective source and fallback state for operators.
