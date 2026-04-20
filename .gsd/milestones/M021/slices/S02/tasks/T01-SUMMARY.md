---
id: T01
parent: S02
milestone: M021
key_files:
  - backend/src/common/ai/llm_service.py
  - backend/src/prompt_templates/taxonomy.py
  - backend/tests/unit/prompt_templates/test_taxonomy.py
  - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
  - .gsd/KNOWLEDGE.md
  - .codex/loop/state.json
  - .codex/loop/log.md
key_decisions:
  - Recorded D233 to keep prompt-source taxonomy in code (`backend/src/prompt_templates/taxonomy.py`) and expose legacy template-bypass inventory in `common.ai.llm_service.LEGACY_PROMPT_ENTRYPOINTS` so downstream slices reuse one authority map.
  - Kept the change intentionally inventory-focused for T01: no runtime rewiring yet, only durable taxonomy/bypass proof that T02 can promote into a real compiled prompt consumer.
duration: 
verification_result: passed
completed_at: 2026-04-14T02:05:56.795Z
blocker_discovered: false
---

# T01: Codified prompt-source taxonomy and exposed the legacy template-bypass entrypoints that still ignore looked-up templates.

**Codified prompt-source taxonomy and exposed the legacy template-bypass entrypoints that still ignore looked-up templates.**

## What Happened

I turned the prompt-source inventory into code-owned artifacts instead of leaving it as grep-only research. First, I wrote a failing unit suite (`backend/tests/unit/prompt_templates/test_taxonomy.py`) that asserted the repository should expose a prompt taxonomy and explicitly mark legacy entrypoints that resolve templates without actually passing template text into model calls. Then I implemented `backend/src/prompt_templates/taxonomy.py`, which now classifies the current prompt surfaces across six buckets: `prompt_template_service`, `voice_instruction_compiler`, `persona_policy`, `presentation_prompt_resolver`, `runtime_guardrails`, and `legacy_llm_hardcoded_prompts`. The same module also names the two real fake-integration seams: `StagedEvaluationService.evaluate_stage -> LLMService.evaluate` and `ComprehensiveReportService._generate_detailed_feedback -> LLMService.generate_report`.

To make that inventory durable instead of duplicating strings in tests, I added `LEGACY_PROMPT_ENTRYPOINTS` to `backend/src/common/ai/llm_service.py`. That metadata states that `evaluate()` and `generate_report()` currently run in `hardcoded_builtin_prompt` mode and do not consume looked-up template text. I then wrote the same conclusion back into `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md` and `.gsd/KNOWLEDGE.md`, and saved decision D233 so downstream work can treat this taxonomy as the canonical prompt-control inventory for S02/T02 rather than re-auditing the same seams again.

## Verification

I reran the focused Python proof bundle after the new taxonomy landed: `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/prompt_templates/test_taxonomy.py backend/tests/unit/test_voice_instruction_compiler.py backend/tests/unit/evaluation/test_staged_evaluation_service.py backend/tests/unit/evaluation/test_comprehensive_report_service.py backend/tests/unit/test_report_generation_trigger.py -q`, which passed 86/86 tests. I then reran the exact slice grep gate from the task plan, and it now surfaces both the live compiled-instruction surfaces and the new taxonomy/bypass inventory under `backend/src/prompt_templates/taxonomy.py` and `backend/src/common/ai/llm_service.py`. Finally, LSP diagnostics were clean on `backend/src/common/ai/llm_service.py`, `backend/src/prompt_templates/taxonomy.py`, and `backend/tests/unit/prompt_templates/test_taxonomy.py`.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/prompt_templates/test_taxonomy.py backend/tests/unit/test_voice_instruction_compiler.py backend/tests/unit/evaluation/test_staged_evaluation_service.py backend/tests/unit/evaluation/test_comprehensive_report_service.py backend/tests/unit/test_report_generation_trigger.py -q` | 0 | ✅ pass | 4076ms |
| 2 | `rg -n "PromptTemplateService|render\(|generate_report|evaluate\(|instructions|persona_policy|strict=|SilentUndefined|base_url" backend/src/prompt_templates backend/src/common/ai backend/src/sales_bot/services backend/src/presentation_coach/services backend/src/evaluation/services` | 0 | ✅ pass | 39ms |

## Deviations

None.

## Known Issues

Focused backend pytest still emits the pre-existing pytest-cov `Module src was never imported` / `No data was collected` warnings for this repo-local unit bundle. They did not block the task and were not introduced by these changes.

## Files Created/Modified

- `backend/src/common/ai/llm_service.py`
- `backend/src/prompt_templates/taxonomy.py`
- `backend/tests/unit/prompt_templates/test_taxonomy.py`
- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`
- `.gsd/KNOWLEDGE.md`
- `.codex/loop/state.json`
- `.codex/loop/log.md`
