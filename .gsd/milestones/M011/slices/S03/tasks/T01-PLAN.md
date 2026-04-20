---
estimated_steps: 1
estimated_files: 2
skills_used: []
---

# T01: 实现 coverage-based answerability

实现 coverage-based answerability。按 profile required/optional slots 判 sufficient / partial / insufficient / blocked，不再只看命中条数。

## Inputs

- `backend/src/common/knowledge_engine/retrieval_planner.py`
- `backend/src/common/knowledge_engine/reranker.py`

## Expected Output

- `backend/src/common/knowledge_engine/answerability.py`
- `backend/tests/unit/common/test_knowledge_answerability.py`

## Verification

backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_answerability.py -q
