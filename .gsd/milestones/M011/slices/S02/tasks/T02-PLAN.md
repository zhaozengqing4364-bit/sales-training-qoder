---
estimated_steps: 1
estimated_files: 4
skills_used: []
---

# T02: 实现意图分类与检索规划器

实现 DB-driven intent classifier 与 retrieval planner。支持 regex / keyword / entity+keyword 三种 rule，输出 profile_key 与 progressive retrieval plan。

## Inputs

- `backend/src/common/knowledge_engine/config_repo.py`
- `backend/src/common/knowledge_engine/entity_resolver.py`

## Expected Output

- `backend/src/common/knowledge_engine/intent_classifier.py`
- `backend/src/common/knowledge_engine/retrieval_planner.py`
- `backend/tests/unit/common/test_knowledge_intent_classifier.py`
- `backend/tests/unit/common/test_knowledge_retrieval_planner.py`

## Verification

backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_intent_classifier.py backend/tests/unit/common/test_knowledge_retrieval_planner.py -q
