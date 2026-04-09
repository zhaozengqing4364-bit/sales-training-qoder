# S01: 数据库性能基线 discovery

**Goal:** 对 N+1、索引、slow query 做第一轮基线审计，产出真实优化 backlog
**Demo:** After this: 有一份 query/index baseline，后续优化 backlog 基于真实证据而不是 audit 猜测

## Tasks
- [ ] **T01: 定位热点查询与索引候选路径** — 梳理 analytics/history/admin/leaderboard/projection 的热点读路径，标出最可能的 N+1 / 索引缺口 / slow query 候选。
  - Estimate: 40m
  - Files: backend/src/common/analytics/*, backend/src/common/conversation/session_evidence.py, backend/src/admin/api/*
  - Verify: rg -n "select|join|order_by|group_by|SessionEvidence|leaderboard|analytics" backend/src/common/analytics backend/src/common/conversation backend/src/admin/api
- [ ] **T02: 形成 evidence-backed DB performance baseline** — 用 focused tests、explain 或代码级查询审视形成第一轮 baseline，明确哪些只是猜测、哪些值得后续起 implementation slice。
  - Estimate: 1h
  - Files: backend/tests/contract/test_analytics.py, backend/tests/unit/common/test_admin_analytics_service.py, backend/tests/unit/common/test_leaderboard_service.py
  - Verify: backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_analytics.py backend/tests/unit/common/test_admin_analytics_service.py backend/tests/unit/common/test_leaderboard_service.py -x -q
- [ ] **T03: 输出 query/index discovery 结论** — 沉淀后续优化列表，显式区分“已证实的性能缺口”和“尚需真实 Postgres 证据的猜测项”。
  - Estimate: 20m
  - Files: backend/tests/contract/test_analytics.py
  - Verify: backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_analytics.py backend/tests/unit/common/test_admin_analytics_service.py backend/tests/unit/common/test_leaderboard_service.py -x -q
