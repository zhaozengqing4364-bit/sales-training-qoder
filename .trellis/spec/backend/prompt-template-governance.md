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

## Scenario: Sales Trainer AI Coach Chat-First Prompts

### 1. Scope / Trigger

- Trigger: changing newcomer-training AI coach generation, next-action generation, short-answer scoring, seed defaults, or prompt variables.
- Scope: `backend/src/sales_trainer/services/ai_coach_chat_*`, `AiCoachConfig`, `seed_newcomer_training_path.py`, and prompt templates used by `business_skills.ai_coach`.

### 2. Signatures

- Generation PromptTemplate: `prompt_type="stage"`, `business_purpose="ai_coach_conversation_generation"`, `category="sales_trainer_ai_coach"`.
- Short-answer scoring PromptTemplate: `prompt_type="scoring"`, same business purpose/category.
- JSON generation calls must use call-scoped LLM constraints:
  - `LLMService.generate(..., response_format=AI_COACH_JSON_RESPONSE_FORMAT)`
  - `LLMService.stream_generate(..., response_format=AI_COACH_JSON_RESPONSE_FORMAT)`
- Runtime events stay on the existing public types: `assistant_text`, `quiz_card`, `quiz_result`, `summary_card`, `followup_prompt`.

### 3. Contracts

- AI coach is Chat-First: `assistant_text` is always the natural coach response; `quiz_card` is an optional tool result, not a mandatory turn output.
- One assistant turn may produce at most one `quiz_card`; `max_cards_per_message` for business-skills seed/admin defaults is `1`.
- `mixed_drill` means "coach decides whether to call a practice-card tool", not random question generation.
- `scenario_judgment` may use single/multiple choice; `expression_rewrite` and `role_response` must use `short_answer`.
- Enabling `short_answer`, `expression_rewrite`, or `role_response` requires a valid `scoring_prompt_template_id`.
- Text-answer scoring must call `AiCoachSessionService.score_short_answer(...)` with the session scoring prompt id/revision/hash; do not score it with local text-length or answer-string rules.
- AI coach generation, next-action generation, and business-etiquette question draft generation must request OpenAI-compatible JSON mode per call. Do not put `response_format` into shared model configuration, because report writing, free-form copy, and other text consumers must remain unconstrained.

### 4. Validation & Error Matrix

| Condition | Expected behavior |
|---|---|
| LLM returns more quiz cards than `max_cards_per_message` | `502 [AI_COACH_INTERACTION_INVALID]` |
| LLM returns a training card outside `allowed_training_card_types` | `502 [AI_COACH_TRAINING_CARD_TYPE_NOT_ALLOWED]` |
| LLM returns short-answer card while config disallows `short_answer` | `502 [AI_COACH_INTERACTION_TYPE_NOT_ALLOWED]` |
| Short-answer scoring prompt missing/invalid | 409 prompt config error from scoring service |
| JSON-generating LLM call omits `response_format={"type":"json_object"}` | Test failure; runtime parser still treats non-JSON output as invalid and returns the existing typed error |
| `continue_drill` / `increase_difficulty` returns no quiz card | Valid; assistant may be explaining or asking a clarifying question |
| `summarize` / `end_session` omits summary card | `502 [AI_COACH_NEXT_ACTION_UI_EVENT_INVALID]` |

### 5. Good/Base/Bad Cases

- Good: learner asks a free question; AI returns `assistant_text` only, or `assistant_text + followup_prompt`.
- Good: learner needs practice; AI returns `assistant_text + one quiz_card`, using a configured card and interaction type.
- Good: each AI coach JSON-producing call binds `response_format` for that call only.
- Base: learner submits a short answer; backend records answer, calls scoring PromptTemplate, stores `score_result`, then optionally generates the next assistant turn.
- Bad: prompt says "always generate 3 questions" or scorer gives 0/100 based on text length before calling the configured model.
- Bad: a global LLM model config is edited to always force JSON output, breaking non-JSON text generation elsewhere.

### 6. Tests Required

- Unit: Chat response parser rejects disallowed card type and too many quiz cards.
- Unit: next-action validator accepts chat-only `continue_drill` and rejects multiple quiz cards.
- Unit: text quiz submission calls short-answer scoring with session scoring prompt id/revision/hash.
- Unit: chat generation, streamed generation, next-action generation, and question-draft generation pass the JSON `response_format` to `LLMService` when they expect machine-readable JSON.
- Seed test: business-skills AI coach seed enables single/multiple/short answer, all three training card types, `max_cards_per_message=1`, `plan_then_wait`, and a scoring prompt.
- Frontend test: coach page renders assistant text and cards in one chat timeline and only shows full coach judgment on summary.

### 7. Wrong vs Correct

#### Wrong

```python
if payload.variant == "text" and len(payload.text or "") < 5:
    return AiCoachScoreResultV1(score=0, feedback="回答过短。")
```

This bypasses the governed scoring prompt and makes the learner see fake AI evaluation.

#### Correct

```python
result = await self._scoring.score_short_answer(
    answer_text=payload.text or "",
    reference_answer=internal.answer_key.reference_answer or "",
    scoring_rubric=internal.scoring_rubric,
    session_id=str(event.session_id),
    scoring_prompt_template_id=config.get("scoring_prompt_template_id"),
    scoring_prompt_revision_id=config.get("scoring_prompt_revision_id"),
    scoring_contract_hash=config.get("scoring_contract_hash"),
)
```

The service resolves and compiles the scoring PromptTemplate, calls the configured model, validates the JSON score, and preserves auditability through prompt ids and hashes.

#### Wrong

```python
await llm.generate(prompt, session_id=session_id)
```

This relies on prompt wording alone to produce JSON and increases contract failures when the model returns natural language.

#### Correct

```python
await llm.generate(
    prompt,
    session_id=session_id,
    response_format=AI_COACH_JSON_RESPONSE_FORMAT,
)
```

The JSON constraint is bound to this call only, so other model consumers keep their normal text-generation behavior.
