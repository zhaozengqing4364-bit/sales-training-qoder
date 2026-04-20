---
id: T03
parent: S02
milestone: M021
key_files:
  - docs/api-contract/prompt-templates.md
  - docs/api-contract/voice-runtime.md
  - docs/api-contract/personas.md
  - docs/api-contract/model-configs.md
  - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
key_decisions:
  - Kept PromptTemplateService documented as the legacy compiled-contract authority for evaluation/report instead of relabeling it as the live StepFun instruction surface.
  - Routed provider/base_url repair guidance to `/admin/model-configs` so admin operators have one explicit fix path for `PROMPT_CONTRACT_BASE_URL_REQUIRED` failures.
duration: 
verification_result: passed
completed_at: 2026-04-14T02:33:02.958Z
blocker_discovered: false
---

# T03: Documented the compiled prompt authority map so template, persona, runtime-profile, and base_url changes now point to the correct runtime path.

**Documented the compiled prompt authority map so template, persona, runtime-profile, and base_url changes now point to the correct runtime path.**

## What Happened

I wrote the post-T02 prompt authority line back into the long-lived admin-facing docs instead of leaving it implied in code. `docs/api-contract/prompt-templates.md` now explains that PromptTemplateService is still the governance surface but also compiles the concrete legacy evaluation/report prompt contract, names the fail-closed diagnostics for missing variables, empty renders, and base_url policy, and adds an operator-facing routing table for which admin surface changes which runtime path. `docs/api-contract/voice-runtime.md` and `docs/api-contract/personas.md` now explain that live StepFun/presentation instructions come from the compiled voice snapshot and instruction hash, with persona policy and runtime profile acting as upstream inputs while existing session snapshots stay frozen. `docs/api-contract/model-configs.md` now documents that provider/base_url settings gate whether the legacy compiled prompt contract can execute and that the fix path is model-configs rather than template editing. Finally, `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md` was updated to remove the stale fake-integration framing, mark PromptTemplateService as the legacy compiled-contract authority, mark LLMService as a compiled-contract consumer with compat fallback, and point S03 canonical evaluation kernel work at the `compile_runtime_prompt_contract(...) -> CompiledPromptContract -> LLMService` seam. No runtime code changed in this task; this was a documentation and operator-guidance sync against the T02 implementation.

## Verification

I reran the exact task-plan verification command after the doc sync: `rg -n "compiled prompt|template source|guardrail|missing var|base_url" docs/api-contract .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md backend/src/prompt_templates -S`, and it passed with the new compiled prompt, guardrail, missing-var, and base_url authority lines visible across the docs and existing prompt modules. I also ran a focused routing grep over the updated authority docs and architecture scan to confirm the admin guidance now distinguishes prompt-templates, personas, voice-runtime, and model-configs, and that the S03 canonical evaluation kernel entry plus `PROMPT_CONTRACT_BASE_URL_REQUIRED` repair path are explicitly documented. Because this task was doc-only and the written contract specified grep-based verification, no additional runtime or browser verification was required.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `rg -n "compiled prompt|template source|guardrail|missing var|base_url" docs/api-contract .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md backend/src/prompt_templates -S` | 0 | ✅ pass | 36ms |
| 2 | `rg -n "Admin 变更路由|Authority boundary|canonical evaluation kernel authority entry|instruction_contract_hash|PROMPT_CONTRACT_BASE_URL_REQUIRED" docs/api-contract/prompt-templates.md docs/api-contract/voice-runtime.md docs/api-contract/personas.md docs/api-contract/model-configs.md .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md -S` | 0 | ✅ pass | 11ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `docs/api-contract/prompt-templates.md`
- `docs/api-contract/voice-runtime.md`
- `docs/api-contract/personas.md`
- `docs/api-contract/model-configs.md`
- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`
