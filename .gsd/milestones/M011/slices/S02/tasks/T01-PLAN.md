---
estimated_steps: 1
estimated_files: 2
skills_used: []
---

# T01: 实现实体解析层

实现 entity resolver。先做 deterministic alias → canonical entity mapping，不上复杂 NLP。测试覆盖 alias、canonical passthrough、no-match 三条基本路径。

## Inputs

- `backend/src/common/knowledge_engine/config_repo.py`
- `docs/plans/2026-03-31-haystack-knowledge-answering-engine.md`

## Expected Output

- `backend/src/common/knowledge_engine/entity_resolver.py`
- `backend/tests/unit/common/test_knowledge_entity_resolver.py`

## Verification

backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_entity_resolver.py -q
