---
estimated_steps: 3
estimated_files: 5
skills_used: []
---

# T02: 落地 unified quality/cost/failure events 与 knowledge path mode

- 设计并落地 quality/cost/failure event schema，让 runtime、report/read-side、knowledge-answer runs 共用同一条可检查的事件线。
- 收敛 knowledge-answer dual-run/shadow 路径到明确的 live+compat mode，并把 event 写入 diagnostics/run history。
- 保持不泄露 secret/base_url/token 等敏感信息。

## Inputs

- `T01 event list`
- `S03 canonical kernel`

## Expected Output

- `backend/src/common/knowledge_engine/*`
- `backend/src/common/ai/llm_service.py`
- `backend/src/sales_bot/websocket/components/*`
- `backend/src/support/api/runtime_status.py`

## Verification

backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_conclusion_evidence_parity.py backend/tests/integration/test_knowledge_flow.py backend/tests/integration/test_websocket_status_contract.py -x -q
