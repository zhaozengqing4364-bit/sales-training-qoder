# S02: Prompt control plane 统一 — UAT

**Milestone:** M021
**Written:** 2026-04-14T02:39:16.695Z

# S02 UAT — Prompt control plane unified compiled contract

## Preconditions
- Admin account available for `/api/v1/prompt-templates*`, `/api/v1/admin/personas`, `/api/v1/admin/voice-runtime`, and `/api/v1/admin/model-configs`.
- Backend is running with the M021/S02 code and migrations already applied.
- At least one sales prompt template bound for `prompt_type=stage` and one bound for `prompt_type=report`.
- At least one sales persona + voice runtime profile pair exists so a new StepFun session can be created for comparison against the legacy evaluation/report path.

## Test Case 1 — Legacy evaluation/report really consume the compiled template contract
1. In admin prompt templates, update the sales `report` template body to add a distinctive sentence such as `【M021-S02-COMPILED-CONTRACT】` in the rendered feedback instructions.
   - Expected: template update saves successfully; no persona/voice-runtime setting is required for this change.
2. Trigger the legacy comprehensive-report path on a sales session that has stage results (for example via the existing comprehensive-report/report-trigger flow used by the backend tests).
   - Expected: the resulting LLM prompt is built from `CompiledPromptContract`, not from the old hardcoded report text path.
3. Inspect backend logs or test instrumentation for the request.
   - Expected: log lines include compiled prompt diagnostics with `runtime_consumer=evaluation.services.comprehensive_report.ComprehensiveReportService._generate_detailed_feedback`, a `contract_hash`, and `LLM_BASE_URL_POLICY` / `PROMPT_TEMPLATE_RENDERED` diagnostics.
4. Repeat with a stage-evaluation template change on the legacy evaluation path.
   - Expected: `StagedEvaluationService.evaluate_stage()` also passes a compiled contract into `LLMService.evaluate()` and uses the updated template text.
5. Create a new StepFun sales session without changing persona or voice-runtime settings.
   - Expected: the live StepFun `instruction_contract_hash` / `voice_policy_snapshot.instructions` do **not** change just because the legacy evaluation/report template changed.

## Test Case 2 — Missing variables fail closed instead of silently falling back
1. Edit a sales `stage` or `report` template so it references a variable that the current caller does not provide (for example an extra placeholder absent from the render context).
   - Expected: template can be saved, but the next runtime compile should detect the missing variable.
2. Trigger the corresponding legacy evaluation/report path.
   - Expected: the path fails with an explicit token like `[PROMPT_CONTRACT_MISSING_VARIABLES:<name>]`; no generic conversational filler feedback is returned for the compiled-contract path.
3. Inspect logs for the same request.
   - Expected: a warning shows contract compilation failure for the named `runtime_consumer` and the missing variable list.
4. Restore the template by removing the invalid placeholder and rerun the same path.
   - Expected: compilation succeeds, diagnostics return to `PROMPT_TEMPLATE_RENDERED` / `LLM_BASE_URL_POLICY`, and the legacy evaluation/report flow runs normally again.

## Test Case 3 — Provider/base_url policy blocks execution on the right admin surface
1. In `/admin/model-configs`, pick the active LLM provider used by legacy evaluation/report and clear `base_url` when that provider requires one.
   - Expected: config save succeeds only if the admin surface allows it; this creates a known-bad runtime setup.
2. Trigger the legacy compiled prompt path again.
   - Expected: prompt compilation fails closed with `[PROMPT_CONTRACT_BASE_URL_REQUIRED]`; logs show `base_url_policy=required_missing` and the failure is attributed to model-configs/runtime policy, not to prompt-template content.
3. Without touching the prompt template or persona policy, repair the same model config by restoring a valid `base_url`.
   - Expected: the next compiled prompt contract succeeds and runs without the base_url failure token.
4. Verify a new StepFun session after this change.
   - Expected: StepFun instruction authority still comes from `voice_policy_snapshot` / `instruction_contract_hash`; changing model-configs repairs legacy compiled-contract execution but does not reclassify prompt ownership.

## Test Case 4 — Authority routing stays clear across prompt templates, personas, and voice runtime
1. Change `persona_policy.system_prompt` or customer-pressure fields on an admin Persona and preview the effective voice runtime policy.
   - Expected: the next StepFun/presentation session shows a different `instruction_contract_hash` / `voice_policy_snapshot.instructions`.
2. Revert the Persona and instead change only the `report` or `stage` prompt template.
   - Expected: legacy evaluation/report compiled prompt behavior changes, but the StepFun effective-policy preview and next-session instruction contract do not.
3. Change only the voice-runtime tool policy (for example `network_access_mode` or `require_kb_grounding`).
   - Expected: the next StepFun session guardrails/tool surface change, but legacy evaluation/report template text does not.
4. Cross-check the authority docs used by operators.
   - Expected: `prompt-templates.md`, `voice-runtime.md`, `personas.md`, and `model-configs.md` all describe the same routing rule you just observed in runtime behavior.

## Edge cases to record during UAT
- Compiled-contract diagnostics appear only on the legacy evaluation/report consumers today; absence of a dedicated admin/support page for these diagnostics is expected in S02 and should be logged as a follow-up, not a failure.
- Existing sessions keep their frozen `voice_policy_snapshot`; only newly created StepFun sessions should reflect persona or voice-runtime prompt changes.
- Presentation interruption helper copy may change from prompt-template edits, but that should still be treated as helper-copy scope, not as the live StepFun instruction authority.
