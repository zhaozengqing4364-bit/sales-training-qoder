# S02: Query understanding、planner 与 Haystack 检索执行

**Goal:** 把 query normalization / entity resolution / intent classification / retrieval planning 与 Haystack execution adapter 接起来，解决命中与排序前的根问题。
**Demo:** After this: 给定“请介绍一下世袭科技”这类 query，引擎能输出实体解析、intent、retrieval plan、执行查询列表和排序结果。

## Tasks
- [x] **T01: Added a deterministic entity resolver that rewrites configured aliases to canonical entities and returns auditable match traces for downstream query planning.** — 实现 entity resolver。先做 deterministic alias → canonical entity mapping，不上复杂 NLP。测试覆盖 alias、canonical passthrough、no-match 三条基本路径。
  - Estimate: 20-30m
  - Files: backend/src/common/knowledge_engine/entity_resolver.py, backend/tests/unit/common/test_knowledge_entity_resolver.py
  - Verify: backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_entity_resolver.py -q
- [x] **T02: Added DB-backed intent classification and progressive retrieval planning for normalized knowledge queries.** — 实现 DB-driven intent classifier 与 retrieval planner。支持 regex / keyword / entity+keyword 三种 rule，输出 profile_key 与 progressive retrieval plan。
  - Estimate: 35-45m
  - Files: backend/src/common/knowledge_engine/intent_classifier.py, backend/src/common/knowledge_engine/retrieval_planner.py, backend/tests/unit/common/test_knowledge_intent_classifier.py, backend/tests/unit/common/test_knowledge_retrieval_planner.py
  - Verify: backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_intent_classifier.py backend/tests/unit/common/test_knowledge_retrieval_planner.py -q
- [ ] **T03: 接 Haystack 检索执行与业务排序** — 实现 Haystack execution adapter 与项目自有 reranker。先保证 adapter 能跑 retrieval steps，reranker 能按 title/entity/doc_type/section/diversity 给出可解释分数。产品介绍类 query 命中后必须 early-stop。
  - Estimate: 45-60m
  - Files: backend/src/common/knowledge_engine/haystack_adapter.py, backend/src/common/knowledge_engine/reranker.py, backend/tests/unit/common/test_haystack_adapter.py, backend/tests/unit/common/test_knowledge_reranker.py, backend/tests/unit/test_stepfun_internal_knowledge_searcher.py
  - Verify: backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_haystack_adapter.py backend/tests/unit/common/test_knowledge_reranker.py backend/tests/unit/test_stepfun_internal_knowledge_searcher.py -q
