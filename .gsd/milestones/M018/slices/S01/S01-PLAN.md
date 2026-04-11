# S01: 数据库性能基线 discovery

**Goal:** 对 N+1、索引、slow query 做第一轮基线审计，产出真实优化 backlog。
**Demo:** 有一份 query/index baseline，后续优化 backlog 基于真实证据而不是 audit 猜测。

## Must-Haves

- analytics/history/admin/leaderboard/projection 的热点查询路径被盘清。
- N+1、索引缺口、slow query 风险按证据级别分层记录。
- focused analytics proof 通过，且 discovery 结论明确哪些值得后续起 implementation slice。

## Proof Level

- This slice proves: contract

## Integration Closure

S01 为 M018 后续依赖治理和 runbook 工作提供当前数据面/运行面基线，也为未来性能实现 slice 提供事实入口。

## Verification

- future agents 可从 query/index baseline 判断哪些性能项已被证实、哪些仍需真实 Postgres/runtime 证据，不必再从 audit 文本重建背景。

## Tasks

- [x] **T01: 定位热点查询与索引候选路径** `est:40m`
  Why: 先定位最可能的热点查询和索引候选路径，后续基线才能围绕真实风险而不是全文猜测。

Do:
1. 梳理 analytics/history/admin/leaderboard/projection 的热点读路径。
2. 标出最可能的 N+1、索引缺口和 slow query 候选。
3. 记录哪些只是 ORM 结构猜测，哪些已经接近真实热点。

Done when: 已形成热点查询与索引候选清单，可直接指导后续 evidence gathering。
  - Files: `backend/src/common/analytics/*`, `backend/src/common/conversation/session_evidence.py`, `backend/src/admin/api/*`
  - Verify: rg -n "select|join|order_by|group_by|SessionEvidence|leaderboard|analytics" backend/src/common/analytics backend/src/common/conversation backend/src/admin/api

- [x] **T02: 形成 evidence-backed DB performance baseline** `est:1h`
  Why: baseline 的关键是把“已证实”和“猜测”分开，而不是直接把所有性能建议都推成待实现项。

Do:
1. 结合 focused tests、explain 或代码级查询审视形成第一轮 baseline。
2. 标明哪些问题已有足够证据，哪些仍需要真实 Postgres/runtime 证据。
3. 不抢跑加索引或改查询，只产出 evidence-backed 基线。

Done when: focused analytics proof 通过，且 baseline 已能支撑后续优化优先级。
  - Files: `backend/tests/contract/test_analytics.py`, `backend/tests/unit/common/test_admin_analytics_service.py`, `backend/tests/unit/common/test_leaderboard_service.py`
  - Verify: backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_analytics.py backend/tests/unit/common/test_admin_analytics_service.py backend/tests/unit/common/test_leaderboard_service.py -x -q

- [x] **T03: 输出 query/index discovery 结论** `est:20m`
  Why: 如果不把结论输出成可消费 backlog，后续 agent 仍会重新从零评估 query/index 风险。

Do:
1. 沉淀后续优化列表。
2. 显式区分“已证实的性能缺口”和“仍需真实 Postgres 证据的猜测项”。
3. 保持结论与 focused proof 对齐，不写空泛优化建议。

Done when: 后续是否起性能实现 slice 有一份明确、分层的 discovery 结论可复用。
  - Files: `backend/tests/contract/test_analytics.py`
  - Verify: backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_analytics.py backend/tests/unit/common/test_admin_analytics_service.py backend/tests/unit/common/test_leaderboard_service.py -x -q

## Files Likely Touched

- backend/src/common/analytics/*
- backend/src/common/conversation/session_evidence.py
- backend/src/admin/api/*
- backend/tests/contract/test_analytics.py
- backend/tests/unit/common/test_admin_analytics_service.py
- backend/tests/unit/common/test_leaderboard_service.py
