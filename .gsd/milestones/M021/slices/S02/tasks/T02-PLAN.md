---
estimated_steps: 3
estimated_files: 6
skills_used: []
---

# T02: 让 compiled prompt contract 真正驱动 runtime

- 设计并实现一个 compiled prompt contract：明确输入来源、编译结果、hash/version、runtime consumer。
- 让 live/legacy 仍保留的路径实际消费这个 compiled contract，而不是分别硬编码。
- 对 missing vars/fail-open/base_url policy 增加显式 diagnostics 或 guardrails。

## Inputs

- `T01 taxonomy`
- `S01 keep/compat matrix`

## Expected Output

- `backend/src/prompt_templates/*`
- `backend/src/common/ai/config_manager.py`
- `backend/src/common/ai/llm_service.py`
- `backend/src/sales_bot/services/voice_instruction_compiler.py`

## Verification

backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests -k "prompt or knowledge_answer or report" -x -q
