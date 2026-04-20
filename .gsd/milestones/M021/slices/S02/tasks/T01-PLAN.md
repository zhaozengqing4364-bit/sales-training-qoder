---
estimated_steps: 2
estimated_files: 5
skills_used: []
---

# T01: 定义 prompt source taxonomy 与假接入点

- 沿 S01 inventory 明确 prompt source taxonomy：PromptTemplateService、voice_instruction_compiler、persona_policy、presentation prompt resolver、runtime guardrails、legacy hardcoded prompts。
- 找出当前‘取了 template 但最终没驱动模型调用’的真实代码点。

## Inputs

- `S01 live/compat inventory`
- `prompt-related modules`

## Expected Output

- `backend/src/prompt_templates/*`
- `backend/src/common/ai/llm_service.py`
- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`

## Verification

rg -n "PromptTemplateService|render\(|generate_report|evaluate\(|instructions|persona_policy|strict=|SilentUndefined|base_url" backend/src/prompt_templates backend/src/common/ai backend/src/sales_bot/services backend/src/presentation_coach/services backend/src/evaluation/services
