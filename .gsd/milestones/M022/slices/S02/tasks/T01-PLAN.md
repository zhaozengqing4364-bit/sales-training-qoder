---
estimated_steps: 2
estimated_files: 5
skills_used: []
---

# T01: 定义 industry pack / customer-pressure 资产合同

- 盘点现有 admin agents/personas/knowledge/scenarios surfaces 与 runtime snapshot 之间的映射。
- 定义首轮 industry pack contract：哪些字段属于 persona、哪些属于 scenario、哪些属于 knowledge bundle/customer pressure。

## Inputs

- `current admin/runtime surfaces`
- `M022 S01 rubric contract`

## Expected Output

- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`
- `backend/src/agent/api/*`
- `backend/src/sales_bot/api/scenarios.py`

## Verification

rg -n "persona_policy|customer_pressure|scenario|knowledge_base|agent|industry" backend/src/agent backend/src/sales_bot backend/src/common/knowledge
