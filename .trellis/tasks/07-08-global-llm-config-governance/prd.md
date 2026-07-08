# PRD: Global LLM Configuration Governance

## Goal

Clarify whether the project should provide a global large language model configuration that most AI call sites consume by default, while allowing controlled per-scenario overrides where needed.

## Current Findings

- The project already has a database-backed model registry through `model_configs`.
- `ConfigManager.get_effective_config()` prefers the default active DB LLM config, then falls back to environment variables.
- `LLMService` consumes this effective config when no explicit `ModelConfig` is passed.
- Local `.dev/local.db` currently has zero rows in `model_configs`, so the local runtime mainly uses `.env` fallback.
- `.env` is configured for DeepSeek-compatible LLM usage through `LLM_BASE_URL`, `LLM_MODEL`, `OPENAI_BASE_URL`, and `OPENAI_MODEL`.
- There is an inconsistency between `common/config.py` defaults and `ConfigManager` env fallback defaults.
- Admin model configuration exists, but DeepSeek is not a first-class provider and the endpoint allowlist does not include `api.deepseek.com`.

## Existing Usage Pattern

Most text LLM call sites already use `LLMService()` or `get_llm_service()`, so they can consume the global default automatically.

Some call sites support explicit model selection:

- Business etiquette question draft generation supports `model_config_id`.
- Short answer AI scoring supports `model_config_id` and runtime overrides.
- AI Coach generation/scoring supports configured model names resolved against active DB LLM configs.
- Roleplay observation supports `model_config_id` or `model_name`.

Some model-related paths are outside the central LLM config flow:

- Deucate scoring uses `DEUCATE_*` environment variables directly.
- StepFun realtime voice uses `STEPFUN_*` environment variables and voice runtime policy.
- Some frontend forms allow manual model config IDs or JSON instead of selecting from configured model options.

## Product Judgment

A global LLM configuration is meaningful and needed.

The recommended direction is not "every AI point configures its own model". The default should be:

- Most business flows consume the global LLM default automatically.
- Only high-value or operationally sensitive scenarios expose a controlled override.
- Overrides should select from already configured active model configs, not free-text base URLs, keys, or model IDs.

## Candidate Approaches

### Option A: Global Default Only

Use the existing default LLM config everywhere and remove or hide most per-feature model fields.

Pros:

- Smallest governance surface.
- Easy for operations.
- Lower configuration mistakes.

Cons:

- Harder to tune generation vs scoring vs realtime workloads.
- Some existing override needs would be lost or pushed into code.

### Option B: Global Default Plus Scenario Binding

Keep `model_configs` as the central model registry, then introduce scenario bindings such as:

- `llm.default`
- `question_draft.generation`
- `short_answer.scoring`
- `ai_coach.generation`
- `ai_coach.scoring`
- `roleplay_observation.evaluator`

Each call site resolves its scenario binding first, then falls back to `llm.default`.

Pros:

- Keeps ordinary pages simple.
- Supports operational tuning by scenario.
- Avoids spreading base URL, key, and model text fields across business pages.
- Matches current code shape because many call sites already accept default or explicit `ModelConfig`.

Cons:

- Requires a small resolver layer and admin UI.
- Requires migration from manual ID/name inputs.

### Option C: Per-Feature Free Configuration

Each AI feature independently configures provider, base URL, key, model, temperature, and timeout.

Pros:

- Maximum local flexibility.

Cons:

- High security and governance risk.
- Repeats secrets and endpoint policy logic.
- Hard to audit, rotate, test, and roll back.
- Not recommended for this project.

## Confirmed MVP Scope

The MVP scope selected by the user is Option A: unify text LLM default consumption first.

Confirmed decisions:

- The global default text LLM should be managed primarily through the database-backed admin model configuration.
- Environment variables should remain only as fallback for local development, bootstrap, or DB configuration failure.
- DeepSeek should remain OpenAI-compatible for the MVP, using `provider=openai`.
- The MVP should add DeepSeek endpoint allowance and admin-facing preset/help text where needed, instead of introducing a new `deepseek` provider branch.
- Existing explicit model override fields should be preserved for backward compatibility in the MVP.
- The MVP should not hide, delete, or migrate those override fields; it should only ensure the default text LLM path is unified.

Initial scope:

- Define `llm.default` as the single global default.
- Ensure every text LLM call site that can use `LLMService()` or `get_llm_service()` consumes the same effective default.
- Reconcile DB default and environment fallback behavior.
- Avoid introducing scenario binding in the MVP.
- Avoid expanding MVP scope to Deucate scoring or StepFun realtime voice.
- Keep Deucate and StepFun out of the first MVP unless their governance becomes part of the explicit requirement.

Out of scope for MVP:

- Scenario-specific model binding.
- Per-feature model selection UI improvements.
- Deucate model governance.
- StepFun realtime voice model governance.
- Business-page model override redesign.

## Open Questions

No blocking product questions remain for the MVP.

## Acceptance Criteria

- There is one clear global default LLM configuration.
- Standard text LLM call sites can consume the global default without local model configuration.
- The global default is primarily managed by the database-backed admin model configuration.
- Environment variables remain available only as fallback for local development, bootstrap, or DB configuration failure.
- DeepSeek can be configured through the existing OpenAI-compatible provider path.
- Existing explicit override fields remain backward-compatible and are not migrated in this MVP.

## Risks

- Existing `.env` fallback and DB default behavior may diverge unless defaults are reconciled.
- Endpoint allowlist currently blocks some OpenAI-compatible providers through admin config.
- Manual frontend fields may create hidden configuration drift if not migrated.
- Deucate and StepFun have different runtime requirements and should not be folded into text LLM governance without a separate design pass.

## Implementation Notes

- Added shared LLM fallback defaults in `common.config` and made `ConfigManager.get_env_fallback(ModelType.LLM)` consume those defaults when `LLM_*` env fallback is used.
- Preserved legacy `OPENAI_API_KEY` fallback behavior for deployments that only configured `OPENAI_*`.
- Added `api.deepseek.com` to the OpenAI-compatible endpoint allowlist.
- Added DeepSeek/OpenAI-compatible presets to the admin model configuration form without changing API types or existing override fields.
- Added regression tests for LLM env fallback, DeepSeek endpoint allowlist, and the admin preset UI.
