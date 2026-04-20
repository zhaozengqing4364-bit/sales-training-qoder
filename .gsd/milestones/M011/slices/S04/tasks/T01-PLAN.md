---
estimated_steps: 1
estimated_files: 3
skills_used: []
---

# T01: 增加知识问答评测 harness

实现 evaluation harness 与初始 fixture case 集。先覆盖产品介绍、价格、版本比较、辅导类、blocked/timeout 降级等样例。

## Inputs

- `backend/src/common/knowledge_engine/engine.py`
- `backend/src/common/knowledge_engine/assembler.py`

## Expected Output

- `backend/src/common/knowledge_engine/evaluation.py`
- `backend/tests/evaluation/test_knowledge_answer_engine_eval.py`
- `backend/tests/fixtures/knowledge_answer_eval_cases.json`

## Verification

backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/evaluation/test_knowledge_answer_engine_eval.py -q
