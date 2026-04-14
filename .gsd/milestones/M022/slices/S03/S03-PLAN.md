# S03: Manager calibration 与 admin truth surfaces 收口

**Goal:** 把 manager calibration、team coaching、admin truth surfaces 建立在真实 evidence 和真实统计上。
**Demo:** After this: manager/admin 的关键决策面会使用真实 canonical evidence 和真实统计，不再混用 demo 数字、漂移口径或不可解释总分。

## Must-Haves

- admin 首页/关键管理面移除或替换 fake stats/dummy cards，不再伪装实时运营数字。
- manager calibration/team coaching 至少有一组建立在 canonical evidence 上的 focused surfaces。
- learner/manager/admin 对同一训练事实的口径一致。

## Proof Level

- This slice proves: integration

## Integration Closure

S03 结束后，组织侧看到的关键训练面会与 learner report/replay 使用同一事实线；S04 org target-state 不再建立在 demo 面之上。

## Verification

- 主管看到的 not passed / trend / calibration / team summary 都能回到 canonical evidence，而不是本地凑数。

## Tasks

- [x] **T01: 识别 manager/admin 的 fake stats 与漂移 summary** `est:45m`
  - 盘点 admin 首页、manager-lite、analytics/user detail 当前哪些数字或 summary 是 demo/placeholder/漂移口径。
- 定义 truth surface 优先级：哪些必须接真实 evidence/stats，哪些应降级为说明文案或移除。
  - Files: `web/src/app/admin/page.tsx`, `web/src/components/admin`, `backend/src/common/analytics`, `backend/src/admin/api`
  - Verify: rg -n "2543|84|placeholder|demo|mock|dummy|manager-lite|analytics" web/src/app/admin web/src/components/admin backend/src/common/analytics backend/src/admin/api

- [x] **T02: 让 manager/admin 决策面只显示真实 evidence 与真实 stats** `est:2h`
  - 用 canonical evidence/stats 替换关键管理面上的 fake numbers/dummy cards；没有真实数据的项显式降级，不再硬造‘正在运行中’假象。
- 优先锁主管最常用 surfaces：admin home、user detail、manager-lite、not passed / trend / calibration cards。
  - Files: `web/src/app/admin/page.tsx`, `web/src/components/admin`, `backend/src/common/analytics`, `backend/src/admin/api/users.py`
  - Verify: npm --prefix web test -- --run "src/app/admin/page.test.tsx" "src/components/admin/manager-lite-panel.test.tsx" && backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_admin_analytics_service.py -x -q

- [ ] **T03: 固定 manager/admin truth surface 的产品边界** `est:35m`
  - 把 manager calibration/team coaching 入口、truth surface 说明写回 architecture scan 和 product plan。
- 明确哪些管理能力已可产品化，哪些仍是后续工作，避免商业话术超过真实实现。
  - Files: `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`, `.gsd/plans/GSD_PLAN_post-M018-next-wave.md`
  - Verify: rg -n "manager|calibration|truth surface|fake stats|placeholder|canonical evidence" .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md .gsd/plans/GSD_PLAN_post-M018-next-wave.md

## Files Likely Touched

- web/src/app/admin/page.tsx
- web/src/components/admin
- backend/src/common/analytics
- backend/src/admin/api
- backend/src/admin/api/users.py
- .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
- .gsd/plans/GSD_PLAN_post-M018-next-wave.md
