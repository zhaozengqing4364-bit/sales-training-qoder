---
id: S02
parent: M021
milestone: M021
provides:
  - A real compiled prompt contract seam for legacy evaluation/report consumers.
  - One code-owned prompt taxonomy that distinguishes live StepFun instruction authority from legacy template/runtime helpers.
  - Explicit failure surfaces that S03/S04 can reuse instead of inferring prompt/runtime problems from silent fallback behavior.
requires:
  []
affects:
  - S03
  - S04
key_files:
  - backend/src/prompt_templates/compiled_contract.py
  - backend/src/prompt_templates/service.py
  - backend/src/prompt_templates/taxonomy.py
  - backend/src/common/ai/config_manager.py
  - backend/src/common/ai/llm_service.py
  - backend/src/evaluation/services/staged_evaluation.py
  - backend/src/evaluation/services/comprehensive_report.py
  - backend/src/sales_bot/services/voice_instruction_compiler.py
  - docs/api-contract/prompt-templates.md
  - docs/api-contract/voice-runtime.md
  - docs/api-contract/personas.md
  - docs/api-contract/model-configs.md
  - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
  - .gsd/KNOWLEDGE.md
key_decisions:
  - D233 — use code-owned prompt taxonomy plus explicit legacy prompt-entry inventory as the prompt control-plane authority map.
  - D234 — compile PromptTemplateService output into hashed CompiledPromptContract objects before legacy evaluation/report model calls, leaving raw dict prompts only as compatibility fallback.
  - D235 — document prompt authority so legacy compiled templates, live StepFun instructions, and model-config repair paths are routed to distinct admin surfaces.
patterns_established:
  - Compile admin-managed prompt templates into a hashed runtime artifact before model calls instead of looking them up and rebuilding prompts later.
  - Keep legacy raw-prompt builders as explicit compatibility fallback only, while compiled-contract consumers fail closed and emit diagnosable error tokens.
  - Document prompt authority by runtime surface (`prompt-templates`, `personas`, `voice-runtime`, `model-configs`) so operator changes map to one observable execution path.
observability_surfaces:
  - Compiled prompt diagnostics in `LLMService` logs: `PROMPT_TEMPLATE_RENDERED`, `LLM_BASE_URL_POLICY`, `runtime_consumer`, `contract_hash`, `base_url_policy`.
  - Explicit fail-closed tokens from prompt compilation/execution: `[PROMPT_CONTRACT_MISSING_VARIABLES:*]`, `[PROMPT_CONTRACT_EMPTY_RENDERED_PROMPT]`, `[PROMPT_CONTRACT_BASE_URL_REQUIRED]`, `[LLM_GENERATION_ERROR:*]`.
  - Authority routing documented in `docs/api-contract/prompt-templates.md`, `voice-runtime.md`, `personas.md`, and `model-configs.md`, with architecture scan alignment in `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`.
drill_down_paths:
  - .gsd/milestones/M021/slices/S02/tasks/T01-SUMMARY.md
  - .gsd/milestones/M021/slices/S02/tasks/T02-SUMMARY.md
  - .gsd/milestones/M021/slices/S02/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-14T02:39:16.694Z
blocker_discovered: false
---

# S02: Prompt control plane 统一

**Unified prompt control for legacy evaluation/report into a real compiled prompt contract, added explicit fail-closed diagnostics, and documented which admin surface owns which prompt/runtime path.**

## What Happened

## Delivered
- Promoted `PromptTemplateService` from lookup-only governance helper to a real runtime compiler via `compile_runtime_prompt_contract(...)`, which now produces a hashed `CompiledPromptContract` containing rendered prompt text, system message, runtime consumer, provider/base_url policy, and attached diagnostics.
- Rewired the legacy evaluation/report callers so `StagedEvaluationService.evaluate_stage()` and `ComprehensiveReportService._generate_detailed_feedback()` now compile the selected template before calling `LLMService.evaluate()` / `generate_report()`. Template changes now actually affect those legacy runtime paths instead of being looked up and then ignored.
- Kept raw dict prompt building inside `LLMService` only as a compatibility fallback for untouched callers, while compiled-contract consumers fail closed on missing variables, empty renders, missing `base_url`, and generation errors.
- Locked the prompt source taxonomy in code (`backend/src/prompt_templates/taxonomy.py`) so downstream slices now have one authoritative map for `prompt_template_service`, `voice_instruction_compiler`, `persona_policy`, `presentation_prompt_resolver`, `runtime_guardrails`, and legacy hardcoded prompt adapters.
- Wrote the authority split back into long-lived docs: `prompt-templates` is now documented as the legacy compiled-contract authority, `voice-runtime` + `personas` remain the live StepFun instruction authority, and `model-configs` is the repair surface for provider/base_url execution failures.

## What changed in practice
- Legacy evaluation/report prompt text is no longer reconstructed from hardcoded strings after template lookup; the compiled template artifact is now what the model receives.
- Missing-variable and provider/base_url failures now surface as explicit tokens such as `[PROMPT_CONTRACT_MISSING_VARIABLES:*]`, `[PROMPT_CONTRACT_EMPTY_RENDERED_PROMPT]`, `[PROMPT_CONTRACT_BASE_URL_REQUIRED]`, and compiled-path `[LLM_GENERATION_ERROR:*]` instead of silent fail-open filler responses.
- The prompt-control taxonomy now makes it explicit that live sales/presentation StepFun sessions still execute frozen `voice_policy_snapshot.instructions` / `instruction_contract_hash`, so template editing does not magically rewrite live StepFun instruction authority.

## Why this matters downstream
- S03 can now converge canonical evaluation work on one concrete seam: `PromptTemplateService.compile_runtime_prompt_contract(...) -> CompiledPromptContract -> LLMService.evaluate()/generate_report()`.
- S04 can surface AI quality/cost/failure events from explicit contract diagnostics instead of inferring failure from missing output or fallback copy.
- Future agents no longer need to rediscover whether a prompt change affects live StepFun runtime, legacy evaluation/report, or presentation interruption helper copy; the code taxonomy and docs now answer that directly.

## Operational Readiness (Q8)
- **Health signal:** compiled-contract paths emit `PROMPT_TEMPLATE_RENDERED` and `LLM_BASE_URL_POLICY` diagnostics with `runtime_consumer`, `contract_hash`, and `base_url_policy`; focused prompt-contract tests and slice gates pass against the new seam.
- **Failure signal:** contract compilation/execution now fails explicitly with `[PROMPT_CONTRACT_MISSING_VARIABLES:*]`, `[PROMPT_CONTRACT_EMPTY_RENDERED_PROMPT]`, `[PROMPT_CONTRACT_BASE_URL_REQUIRED]`, or `[LLM_GENERATION_ERROR:*]` instead of falling through to filler text.
- **Recovery procedure:** if diagnostics point to template variables or empty output, repair the relevant prompt template/scenario binding; if diagnostics point to `BASE_URL_REQUIRED`, fix `/admin/model-configs`; then rerun the focused prompt-contract gate and the broad `prompt or knowledge_answer or report` backend suite.
- **Monitoring gaps:** diagnostics are currently strongest in backend logs, focused tests, and docs; there is not yet a dedicated admin/support runtime page for compiled prompt failures or contract-hash drift. That visibility work belongs in S04.


## Verification

## Fresh verification
1. `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/prompt_templates/test_compiled_prompt_contract.py -x -q` → **2 passed**. This re-proved the explicit diagnostics/fail-closed seam for compiled prompt contracts, including missing-variable handling and base_url policy wiring.
2. `rg -n "PromptTemplateService|render\(|generate_report|evaluate\(|instructions|persona_policy|strict=|SilentUndefined|base_url" backend/src/prompt_templates backend/src/common/ai backend/src/sales_bot/services backend/src/presentation_coach/services backend/src/evaluation/services` → **pass**. This re-proved the slice taxonomy/integration inventory across prompt templates, runtime guardrails, persona policy, and legacy evaluation/report consumers.
3. `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests -k "prompt or knowledge_answer or report" -x -q` → **274 passed, 6 skipped**. This re-ran the slice’s main backend integration gate after assembly of all three tasks.
4. `rg -n "compiled prompt|template source|guardrail|missing var|base_url" docs/api-contract .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md backend/src/prompt_templates -S` → **pass**. This re-proved the authority map and operator guidance across docs and code-owned prompt modules.
5. LSP diagnostics were clean on the touched Python authority files: `prompt_templates/service.py`, `prompt_templates/taxonomy.py`, `common/ai/config_manager.py`, `common/ai/llm_service.py`, `evaluation/services/staged_evaluation.py`, `evaluation/services/comprehensive_report.py`, `sales_bot/services/voice_instruction_compiler.py`, and `common/services/practice_report_service.py`.

## Verification notes
- The repo still emits pre-existing pytest-cov `Module src was never imported` / `No data was collected` warnings on focused repo-root backend gates.
- The broad backend suite still emits pre-existing ResourceWarnings for unclosed sqlite connections and unrelated deprecation/runtime warnings outside the S02 prompt-control files.
- These warnings were visible during the fresh runs above but did not block slice acceptance.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

None.

## Known Limitations

Compiled prompt contracts currently govern the legacy evaluation/report path and presentation helper rendering only. Live StepFun sales/presentation sessions still run on the separate compiled `voice_policy_snapshot` instruction contract, and compiled-prompt diagnostics are not yet surfaced on a dedicated admin/support observability page.

## Follow-ups

S03 should migrate canonical evaluation kernel work onto the new `CompiledPromptContract` seam. S04 should promote contract diagnostics and fail-closed outcomes into explicit quality/cost/failure events on support/runtime surfaces.

## Files Created/Modified

- `backend/src/prompt_templates/compiled_contract.py` — Introduced the compiled prompt contract data model and stable contract hash helper shared by legacy prompt consumers and voice instruction hashing.
- `backend/src/prompt_templates/service.py` — Added `compile_runtime_prompt_contract(...)`, strict render/fail-closed behavior, runtime-policy diagnostics, and base_url policy enforcement.
- `backend/src/prompt_templates/taxonomy.py` — Locked the prompt source taxonomy and current live/compat authority split into a code-owned inventory.
- `backend/src/common/ai/llm_service.py` — Made legacy evaluation/report accept `CompiledPromptContract`, log contract diagnostics, and disable filler fallback on compiled paths while preserving raw-dict compatibility mode.
- `backend/src/common/ai/config_manager.py` — Exposed provider/base_url runtime policy description used by compiled prompt diagnostics and fail-closed execution.
- `backend/src/evaluation/services/staged_evaluation.py` — Compiled stage-evaluation templates into runtime contracts before calling `LLMService.evaluate()`.
- `backend/src/evaluation/services/comprehensive_report.py` — Compiled report templates into runtime contracts before calling `LLMService.generate_report()`.
- `backend/src/sales_bot/services/voice_instruction_compiler.py` — Aligned voice instruction hashing with the shared prompt-contract hash utility so live and legacy compiled artifacts share one hash vocabulary.
- `docs/api-contract/prompt-templates.md` — Documented PromptTemplateService as the legacy compiled-contract authority and added admin routing guidance for prompt-related changes.
- `docs/api-contract/voice-runtime.md` — Clarified that live StepFun/presentation instruction authority remains the compiled voice runtime contract, not prompt templates.
- `docs/api-contract/personas.md` — Clarified persona_policy as an upstream input to live compiled StepFun instructions rather than a legacy template surface.
- `docs/api-contract/model-configs.md` — Documented provider/base_url repair as the execution gate for legacy compiled prompt contracts.
- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md` — Updated the prompt authority map and S03/S04 entry seams to reflect the shipped compiled-contract path.
- `.gsd/KNOWLEDGE.md` — Added follow-up guidance about fail-closed compiled-contract behavior and the model-config repair path.
