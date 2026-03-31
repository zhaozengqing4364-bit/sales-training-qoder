---
estimated_steps: 1
estimated_files: 3
skills_used: []
---

# T02: 增加知识问答 debug API

实现 read-only debug API。支持列出 answer runs、查看单次 run、查看 step breakdown，让后续可以按 run_id 调试。

## Inputs

- `backend/src/common/knowledge_engine/audit_repo.py`
- `backend/src/common/knowledge_engine/schemas.py`

## Expected Output

- `backend/src/common/api/knowledge_debug.py`
- `backend/tests/integration/test_knowledge_debug_api.py`

## Verification

backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_knowledge_debug_api.py -q

## Observability Impact

形成面向后续排障和运营调优的统一 debug surface。
