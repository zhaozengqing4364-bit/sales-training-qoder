---
estimated_steps: 1
estimated_files: 2
skills_used: []
---

# T02: 实现基于证据的回答组装器

实现 evidence-driven answer assembler。先从 deterministic structured assembly 开始，输出 final_text、blocked_text、citations、unsupported_claims。

## Inputs

- `backend/src/common/knowledge_engine/answerability.py`
- `backend/src/common/knowledge_engine/schemas.py`

## Expected Output

- `backend/src/common/knowledge_engine/assembler.py`
- `backend/tests/unit/common/test_knowledge_answer_assembler.py`

## Verification

backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_answer_assembler.py -q
