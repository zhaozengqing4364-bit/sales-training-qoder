# S02: Prompt control plane 统一

**Goal:** 统一 prompt control plane，让 PromptTemplateService/voice instruction/persona policy 形成真实编译产物。
**Demo:** After this: prompt template、voice instruction、persona policy、runtime guardrail 不再各走各路，至少有一条 compiled prompt contract 真正驱动 live/legacy 路径。

## Must-Haves

- PromptTemplateService 真正驱动 live 或 legacy 仍保留的路径，不再只是看起来被调用。
- prompt 来源碎片化被收敛成清晰 taxonomy：template、persona policy、runtime guardrail、compiled instruction。
- missing-variable/base-url/fail-open policy 有明确默认值与 failure surface。

## Proof Level

- This slice proves: integration

## Integration Closure

S02 结束后，S03 canonical evaluation kernel 与 S04 quality events 都建立在同一 compiled prompt contract 上。

## Verification

- missing vars、template drift、provider/base_url policy 会有显式 diagnostics，而不是 silent fail-open。

## Tasks

- [x] **T01: 定义 prompt source taxonomy 与假接入点** `est:50m`
  - 沿 S01 inventory 明确 prompt source taxonomy：PromptTemplateService、voice_instruction_compiler、persona_policy、presentation prompt resolver、runtime guardrails、legacy hardcoded prompts。
- 找出当前‘取了 template 但最终没驱动模型调用’的真实代码点。
  - Files: `backend/src/prompt_templates`, `backend/src/common/ai/llm_service.py`, `backend/src/sales_bot/services/voice_instruction_compiler.py`, `backend/src/presentation_coach/services/prompt_role_resolver.py`, `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`
  - Verify: rg -n "PromptTemplateService|render\(|generate_report|evaluate\(|instructions|persona_policy|strict=|SilentUndefined|base_url" backend/src/prompt_templates backend/src/common/ai backend/src/sales_bot/services backend/src/presentation_coach/services backend/src/evaluation/services

- [ ] **T02: 让 compiled prompt contract 真正驱动 runtime** `est:2.5h`
  - 设计并实现一个 compiled prompt contract：明确输入来源、编译结果、hash/version、runtime consumer。
- 让 live/legacy 仍保留的路径实际消费这个 compiled contract，而不是分别硬编码。
- 对 missing vars/fail-open/base_url policy 增加显式 diagnostics 或 guardrails。
  - Files: `backend/src/prompt_templates`, `backend/src/common/ai/config_manager.py`, `backend/src/common/ai/llm_service.py`, `backend/src/sales_bot/services/voice_instruction_compiler.py`, `backend/src/presentation_coach/services/prompt_role_resolver.py`, `backend/src/evaluation/services`
  - Verify: backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests -k "prompt or knowledge_answer or report" -x -q

- [ ] **T03: 把 prompt authority 写回文档与管理面说明** `est:40m`
  - 更新 prompt docs、architecture scan 与 admin-facing guidance，说明哪个 surface 改模板会影响哪些 live path。
- 为后续 S03 canonical evaluation kernel 标明 compiled prompt 的 authority entry。
  - Files: `docs/api-contract`, `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`, `backend/src/prompt_templates`
  - Verify: rg -n "compiled prompt|template source|guardrail|missing var|base_url" docs/api-contract .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md backend/src/prompt_templates

## Files Likely Touched

- backend/src/prompt_templates
- backend/src/common/ai/llm_service.py
- backend/src/sales_bot/services/voice_instruction_compiler.py
- backend/src/presentation_coach/services/prompt_role_resolver.py
- .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
- backend/src/common/ai/config_manager.py
- backend/src/evaluation/services
- docs/api-contract
