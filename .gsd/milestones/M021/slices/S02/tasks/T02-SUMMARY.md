---
id: T02
parent: S02
milestone: M021
key_files:
  - backend/src/prompt_templates/compiled_contract.py
  - backend/src/prompt_templates/service.py
  - backend/src/common/ai/config_manager.py
  - backend/src/common/ai/llm_service.py
  - backend/src/evaluation/services/staged_evaluation.py
  - backend/src/evaluation/services/comprehensive_report.py
  - backend/src/common/services/practice_report_service.py
  - backend/src/prompt_templates/taxonomy.py
  - backend/src/sales_bot/services/voice_instruction_compiler.py
  - backend/tests/unit/prompt_templates/test_compiled_prompt_contract.py
  - backend/tests/unit/prompt_templates/test_taxonomy.py
  - backend/tests/unit/evaluation/test_staged_evaluation_service.py
  - backend/tests/unit/evaluation/test_comprehensive_report_service.py
key_decisions:
  - Compile PromptTemplateService output into a hashed runtime contract before evaluation/report model calls instead of forwarding lookup context and rebuilding prompts inside LLMService.
  - Keep raw dict-based hardcoded prompts inside LLMService only as compatibility fallback, while compiled-contract consumers fail closed on missing variables, missing config, and generation errors.
duration: 
verification_result: mixed
completed_at: 2026-04-14T02:25:54.821Z
blocker_discovered: false
---

# T02: Compiled prompt contracts now drive legacy evaluation/report runtime with explicit fail-closed diagnostics.

**Compiled prompt contracts now drive legacy evaluation/report runtime with explicit fail-closed diagnostics.**

## What Happened

I promoted PromptTemplateService from a lookup-only helper into a real runtime compiler for legacy evaluation/report flows. First, I added `backend/src/prompt_templates/compiled_contract.py` and `PromptTemplateService.compile_runtime_prompt_contract(...)` so a resolved template now becomes a hashed contract with version, runtime consumer, rendered prompt, system message, base_url policy, and attached diagnostics. Then I rewired `StagedEvaluationService.evaluate_stage()` and `ComprehensiveReportService._generate_detailed_feedback()` to compile that contract before calling the model layer, which means the template text is now the actual prompt artifact sent downstream instead of being looked up and ignored.

On the model side, I updated `LLMService` to consume `CompiledPromptContract` objects directly, log their diagnostics, and use fail-closed generation for contract-driven calls. Missing config and generation failures now return explicit error codes for these compiled paths instead of conversational filler fallbacks, while the old raw-dict hardcoded prompt behavior remains as compatibility-only fallback for untouched callers. I also added provider/base_url runtime policy description in `ConfigManager`, aligned the prompt taxonomy to the new truth (compiled-contract consumers instead of template-bypass seams), versioned the voice instruction contract hashing around the same shared contract utility, and fixed one pre-existing structured-logger formatting call in `practice_report_service` that the new fail-closed report path exposed during the broader slice gate.

## Verification

I followed a red/green cycle. I first wrote failing tests proving three things that were not true yet: PromptTemplateService should compile a runtime prompt contract, staged evaluation should pass that contract into `LLMService.evaluate`, and comprehensive report feedback should pass the compiled contract into `LLMService.generate_report`. After the implementation landed, the focused prompt-contract/taxonomy/evaluation/report/voice-instruction suite passed 80/80, LSP diagnostics were clean on every touched Python file, and the exact task-plan verification command `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests -k "prompt or knowledge_answer or report" -x -q` passed with 274 tests green and 6 skips. The first full-gate run surfaced one adjacent runtime issue — an old printf-style structured logger call in `practice_report_service` — which I fixed and then reran the gate successfully.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/prompt_templates/test_compiled_prompt_contract.py backend/tests/unit/prompt_templates/test_taxonomy.py backend/tests/unit/evaluation/test_staged_evaluation_service.py backend/tests/unit/evaluation/test_comprehensive_report_service.py backend/tests/unit/test_voice_instruction_compiler.py -q` | 0 | ✅ pass | 310ms |
| 2 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests -k "prompt or knowledge_answer or report" -x -q` | 1 | ❌ fail | 10700ms |
| 3 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests -k "prompt or knowledge_answer or report" -x -q` | 0 | ✅ pass | 17200ms |

## Deviations

None.

## Known Issues

The repository still emits pre-existing pytest-cov `Module src was never imported` / `No data was collected` warnings on these focused/backend gates, and the broad slice gate still reports pre-existing ResourceWarnings for unclosed sqlite connections plus unrelated deprecation/runtime warnings outside the touched prompt-control files.

## Files Created/Modified

- `backend/src/prompt_templates/compiled_contract.py`
- `backend/src/prompt_templates/service.py`
- `backend/src/common/ai/config_manager.py`
- `backend/src/common/ai/llm_service.py`
- `backend/src/evaluation/services/staged_evaluation.py`
- `backend/src/evaluation/services/comprehensive_report.py`
- `backend/src/common/services/practice_report_service.py`
- `backend/src/prompt_templates/taxonomy.py`
- `backend/src/sales_bot/services/voice_instruction_compiler.py`
- `backend/tests/unit/prompt_templates/test_compiled_prompt_contract.py`
- `backend/tests/unit/prompt_templates/test_taxonomy.py`
- `backend/tests/unit/evaluation/test_staged_evaluation_service.py`
- `backend/tests/unit/evaluation/test_comprehensive_report_service.py`
