# Prompt Template Governance

> Executable backend contract for `backend/src/prompt_templates/` and the shared `prompt_templates` / `scenario_prompts` tables.

## Scenario: Operator-Safe Prompt Defaults And Bindings

### 1. Scope / Trigger

- Trigger: changing prompt template CRUD, default selection, scenario binding, governance repair, or response fields.
- Scope: `/api/v1/prompt-templates*`, `/api/v1/scenario-prompts*`, `PromptTemplateService`, Alembic constraints, and prompt governance audit logs.
- Not scope: live StepFun voice instruction contracts. Those are governed by `sessions`, `voice-runtime`, and `personas`.

### 2. Signatures

API signatures:

```http
GET  /api/v1/prompt-templates
GET  /api/v1/prompt-templates/{template_id}
PUT  /api/v1/prompt-templates/{template_id}
POST /api/v1/prompt-templates/{template_id}/set-default?prompt_type={type}
GET  /api/v1/prompt-templates/{template_id}/impact
POST /api/v1/prompt-templates/{template_id}/clone
POST /api/v1/prompt-templates/governance/repair-defaults?dry_run=true|false
POST /api/v1/scenario-prompts
PUT  /api/v1/scenario-prompts/{assignment_id}
DELETE /api/v1/scenario-prompts/{assignment_id}
```

DB signatures:

```sql
CREATE UNIQUE INDEX uq_prompt_templates_default_per_type
  ON prompt_templates (prompt_type)
  WHERE is_default = true;

CREATE UNIQUE INDEX uq_scenario_prompts_active_scope
  ON scenario_prompts (scenario_type, COALESCE(scenario_id, ''), prompt_type)
  WHERE is_active = true;
```

### 3. Contracts

- `variables` is always `list[str]` for new writes. Historical object/string values are governance issues until repaired.
- Only one active default is allowed per `prompt_type`.
- Only one active binding is allowed per `scenario_type + scenario_id + prompt_type`.
- System templates are read-only; operators clone them into custom templates before editing.
- `PromptTemplate` responses must include Chinese operator fields: `display_name`, `display_type`, `display_category`, `binding_count`, `is_runtime_effective`, `can_edit_directly`, `edit_block_reason`, and `governance_issues`.
- `impact` is read-only and must include default state, active scenario bindings, runtime consumers, allowed actions, block reasons, and recommended next steps.
- Governance repair supports `dry_run=true`; non-dry-run writes audit action `prompt_template.governance.repair_defaults`.

### 4. Validation & Error Matrix

| Condition | Expected behavior |
|---|---|
| Non-admin calls prompt governance API | `403 [PROMPT_TEMPLATE_EDIT_ADMIN_ONLY]` |
| Directly update or deactivate a system template | `409 [PROMPT_TEMPLATE_SYSTEM_LOCKED]` |
| Deactivate a default or active-bound template | `409 [PROMPT_TEMPLATE_IN_USE]` |
| Directly unset the current default | `409 [PROMPT_TEMPLATE_DEFAULT_REPLACEMENT_REQUIRED]` |
| Set default with inactive template | `409 [PROMPT_TEMPLATE_INACTIVE]` |
| Set default with prompt-type mismatch | `409 [PROMPT_TEMPLATE_TYPE_MISMATCH]` |
| Set default or bind template with governance issues | `409 [PROMPT_TEMPLATE_GOVERNANCE_BLOCKED]` |
| Scenario binding prompt type differs from template prompt type | `409 [SCENARIO_PROMPT_TYPE_MISMATCH]` |
| Duplicate active scenario binding scope | `409 [SCENARIO_PROMPT_DUPLICATE_ACTIVE]` |

### 5. Good/Base/Bad Cases

- Good: operator clones a system template, edits the custom copy, previews render output, sets it as default, and the old default is automatically cleared.
- Base: operator runs `repair-defaults?dry_run=true`, sees duplicate default rows, then runs `dry_run=false`; latest updated template remains default.
- Bad: list page sends raw `{variables: {foo: "bar"}}` or disables a system/default template directly. The backend must reject it instead of relying on frontend button hiding.

### 6. Tests Required

- Integration: multi-default repair leaves at most one default per `prompt_type`.
- Integration: system template update returns `409`, clone succeeds and creates `is_system=false`.
- Integration: active-bound template cannot be deactivated; impact lists the binding.
- Unit: `get_template_for_scenario` resolves duplicate historical defaults without `MultipleResultsFound` after governance hardening.
- Migration: legacy `variables` object/string/list-of-dict repairs to `list[str]`; unrecoverable rows are disabled.

### 7. Wrong vs Correct

#### Wrong

```python
template.is_default = True
await db.commit()
```

This can leave multiple defaults for the same `prompt_type` and break runtime selection.

#### Correct

```python
await service.set_default_template(
    template_id=template_id,
    prompt_type=PromptType.SCORING,
    actor=current_user,
    reason="operator_set_default",
)
```

The service validates active/type/governance state, clears old defaults, writes audit, commits, and invalidates prompt cache.
