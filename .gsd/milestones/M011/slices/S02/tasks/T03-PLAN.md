---
estimated_steps: 1
estimated_files: 5
skills_used: []
---

# T03: 接 Haystack 检索执行与业务排序

实现 Haystack execution adapter 与项目自有 reranker。先保证 adapter 能跑 retrieval steps，reranker 能按 title/entity/doc_type/section/diversity 给出可解释分数。产品介绍类 query 命中后必须 early-stop。

## Inputs

- `backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py`
- `backend/src/common/knowledge_engine/retrieval_planner.py`

## Expected Output

- `backend/src/common/knowledge_engine/haystack_adapter.py`
- `backend/src/common/knowledge_engine/reranker.py`
- `backend/tests/unit/common/test_haystack_adapter.py`
- `backend/tests/unit/common/test_knowledge_reranker.py`
- `backend/tests/unit/test_stepfun_internal_knowledge_searcher.py`

## Verification

backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_haystack_adapter.py backend/tests/unit/common/test_knowledge_reranker.py backend/tests/unit/test_stepfun_internal_knowledge_searcher.py -q

## Observability Impact

输出每个候选文档的 score breakdown 和执行过的 query steps。
