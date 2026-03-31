---
estimated_steps: 1
estimated_files: 5
skills_used: []
---

# T01: 创建 KnowledgeAnswerEngine seam 与基础契约

先写 engine seam 的失败测试，再创建 `common/knowledge_engine` 包、基础 request/result contract 和 Haystack dependency 接入点。保持只有最小构造能力，不提前引入复杂逻辑。

## Inputs

- `docs/plans/2026-03-31-haystack-knowledge-answering-engine.md`

## Expected Output

- `backend/src/common/knowledge_engine/__init__.py`
- `backend/src/common/knowledge_engine/engine.py`
- `backend/src/common/knowledge_engine/schemas.py`
- `backend/tests/unit/common/test_knowledge_answer_engine.py`
- `backend/pyproject.toml`

## Verification

backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_answer_engine.py -q

## Observability Impact

定义 engine result contract 中的 audit_run_id / retrieval_summary / unsupported_claims 字段。
