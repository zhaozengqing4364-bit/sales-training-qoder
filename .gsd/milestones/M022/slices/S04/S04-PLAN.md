# S04: Organization / team / tenant target-state plan

**Goal:** 把 organization/team boundary 变成下一阶段可执行的 target-state migration plan。
**Demo:** After this: organization/team/tenant 的目标态、authz 影响、数据迁移、SSO/CRM/org-sync 插槽会有一份可执行路线，而不是继续停留在‘以后再说’。

## Must-Haves

- `organization/team/member/role/access scope` 的目标态模型与当前 `user/session/agent/persona` 模型映射清楚。
- authz、analytics、asset ownership、future integrations（SSO/CRM/org sync）有明确插槽，但不被提前实现进当前 MVP。
- modular monolith 下的迁移路径清楚，知道何时仍留在单体边界、何时才值得拆服务。

## Proof Level

- This slice proves: contract

## Integration Closure

S04 是 M022 的 final assembly/contract slice；完成后 org-boundary、SSO、CRM、org-sync 等未来工作可以直接转为新 milestone，而不重跑全仓扫描。

## Verification

- 后续 agent 可以直接引用 org target-state 文档判断某个新需求该挂在哪个 owner/entity/authz seam。

## Tasks

- [x] **T01: 建立 org/team target-state matrix** `est:1h`
  - 盘点当前 user/session/agent/persona/knowledge/report/admin ownership 模型，找出所有隐含的‘单组织/单租户’假设。
- 建一张 org/team/member/role/access scope target-state matrix，对齐 authz、analytics、asset ownership。
  - Files: `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`, `.gsd/plans/GSD_PLAN_post-M018-next-wave.md`, `backend/src/common/db/models.py`, `backend/src/common/auth`, `backend/src/admin/api`, `web/src/app/admin`
  - Verify: rg -n "user_id|role|owner|agent_id|persona_id|knowledge_base|organization|tenant|team" backend/src/common backend/src/admin web/src/app/admin .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md

- [ ] **T02: 设计保持单体边界的 org-boundary migration path** `est:1.5h`
  - 设计 modular monolith 下的迁移路径：哪些实体先加 organization/team ownership，哪些 authz/analytics/report surfaces 需要 compatibility readers。
- 为未来 SSO/CRM/org-sync/enterprise directory 预留 integration slots，但不把它们拉进当前实现范围。
  - Files: `.gsd/plans/GSD_PLAN_post-M018-next-wave.md`, `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`, `backend/src/common/db/models.py`, `backend/src/common/auth/service.py`
  - Verify: rg -n "migration path|organization|team|tenant|SSO|CRM|org sync|compatibility reader" .gsd/plans/GSD_PLAN_post-M018-next-wave.md .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md

- [ ] **T03: 把 org-boundary plan 写成下一轮企业化 roadmap 输入** `est:35m`
  - 把这份 org target-state plan 绑定到下一轮 roadmap 入口，明确什么情况下继续留在 modular monolith，什么情况下才值得拆服务。
- 记录 out-of-scope：当前不做多租户实现、不接 SSO/CRM、不改外部集成。
  - Files: `.gsd/plans/GSD_PLAN_post-M018-next-wave.md`, `.codex/roadmap/PROJECT_FUTURE.md`
  - Verify: rg -n "organization|team|tenant|monolith|service split|out-of-scope|SSO|CRM" .gsd/plans/GSD_PLAN_post-M018-next-wave.md .codex/roadmap/PROJECT_FUTURE.md

## Files Likely Touched

- .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
- .gsd/plans/GSD_PLAN_post-M018-next-wave.md
- backend/src/common/db/models.py
- backend/src/common/auth
- backend/src/admin/api
- web/src/app/admin
- backend/src/common/auth/service.py
- .codex/roadmap/PROJECT_FUTURE.md
