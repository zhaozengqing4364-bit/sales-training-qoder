# M005: 后台治理与规模化运营

**Vision:** 在前面几个 milestone 已经证明训练本体可信之后，把系统从“可用产品”推进成“可运营平台”：主管能在系统内完成最关键的管理动作，训练资产有版本与健康治理，组织分析建立在统一 evidence 线上，对外导出与未来集成边界清晰可控。

## Success Criteria

- 主管或培训负责人可以在系统内完成**派发训练重点、提醒、跟踪完成与复盘 drill-in**，而不是只看静态报告。
- 知识库、PPT、Persona、voice runtime profile 等核心资产具备可检查的版本、健康状态、变更影响和必要的回滚/替换边界。
- 组织级分析和管理看板建立在统一 evidence / effectiveness 基线之上，不再混用历史 weighted formula 或 placeholder 数据。
- 系统对外导出、周报、入口参数和未来集成边界被明确收口，避免“每接一个系统就多一套逻辑”。

## Key Risks / Unknowns

- 现有 admin analytics 与 records surfaces 仍有历史口径、自算分数或占位 UI。— 若管理面继续漂移，组织运营会建立在错误信号上。
- manager-lite 目前更像名单和提醒日志，还不是完整任务闭环。— 若系统内没有最小可执行管理动作，M005 只会继续堆看板。
- 训练资产已经变多（知识库、PPT、Persona、runtime policy），但治理视角还分散。— 长期使用后会越来越难判断“哪些配置真的在生效、哪些版本可以回滚”。
- 若过早做真实外部集成，会把前几个 milestone 刚建立的内部边界再次打乱。— M005 必须先定义对外 contract，再决定是否接具体企业系统。

## Proof Strategy

- 管理分析还在漂移或占位 → retire in S01 by proving 组织级看板、用户 drill-in、records/export 都以统一 evidence/effectiveness 为基线。
- 主管动作不成闭环 → retire in S02 by proving 系统内能派发训练重点、提醒、记录完成状态并回看结果。
- 资产治理缺乏统一视角 → retire in S03 by proving 知识/PPT/Persona/runtime policy 至少具备健康、版本、影响范围与最近变更线。
- 运营节奏仍靠线下拼接 → retire in S04 by proving 团队/部门视角的周节奏包、风险名单和 drill-in 能在系统内跑通。
- 未来集成边界不清 → retire in S05 by proving 对外导出、深链入口、身份/任务/结果 contract 被收口为统一边界，而不是散落在页面里。

## Verification Classes

- Contract verification: analytics/admin/users/admin/interventions/admin records/export/deep-link 相关 API 与字段的 focused tests。
- Integration verification: admin analytics → user drill-in → task assignment/remind → session completion → review loop 的真实链路验证。
- Operational verification: 资产版本变更、active-session blocker、权限边界、导出/周报生成、支持运行态排障验证。
- UAT / human verification: 主管是否能在系统内完成一周最小训练管理动作，而不是回到线下表格和口头提醒。

## Milestone Definition of Done

This milestone is complete only when all are true:

- 管理端不再只是“看统计”，而是具备最小但完整的训练管理闭环。
- 组织级分析、用户 drill-in、提醒与任务跟踪共享统一 evidence / effectiveness 基线。
- 核心训练资产具备足够的版本/健康/影响面治理，长期运营不会越用越乱。
- 对外导出与未来集成 boundary 已经收口到统一 contract，后续接企业系统不需要重改核心训练链。
- 至少一个真实团队节奏完成“派发 → 跟进 → 复盘”的系统内 UAT。

## Requirement Coverage

- Covers: R012
- Partially covers: R017, R018, R019
- Leaves for later: vendor-specific live integrations beyond the agreed boundary
- Orphan risks: none

## Likely Work Surfaces

- `backend/src/admin/api/interventions.py`
- `backend/src/common/analytics/admin_analytics_service.py`
- `backend/src/common/analytics/history_service.py`
- `backend/src/common/analytics/release_verification_service.py`
- `backend/src/common/api/users.py`
- `backend/src/common/api/analytics.py`
- `web/src/app/admin/analytics/page.tsx`
- `web/src/components/admin/manager-lite-panel.tsx`
- `web/src/app/admin/records/page.tsx`
- `web/src/app/admin/users/[id]/page.tsx`
- `web/src/app/admin/knowledge/page.tsx`
- `web/src/app/admin/personas/[id]/page.tsx`
- `web/src/app/admin/presentations/[id]/page.tsx`
- `web/src/app/admin/voice-runtime/page.tsx`
- `docs/api-contract/analytics.md`
- `docs/api-contract/sessions.md`
- `docs/business-usage-growth-analysis-2026-02.md`
- `docs/business-usage-growth-execution-playbook-2026-02.md`

## Slices

- [ ] **S01: 管理分析与 drill-in 口径统一** `risk:high` `depends:[]`
  > After this: admin analytics、user detail、records 列表和 manager-lite 都站到统一 evidence / effectiveness 基线上，不再混用旧 weighted formula 或 placeholder 数据。

- [ ] **S02: 系统内主管任务与提醒闭环** `risk:high` `depends:[S01]`
  > After this: 主管可以在系统内指定训练重点、发起提醒、查看完成情况，并把结果回连到具体 session/report drill-in。

- [ ] **S03: 训练资产版本与健康治理面** `risk:medium` `depends:[S01]`
  > After this: 知识库、PPT、Persona、runtime profile 至少具备最近变更、版本状态、健康异常和影响范围视图。

- [ ] **S04: 团队 / 部门周节奏运营面板** `risk:medium` `depends:[S02,S03]`
  > After this: 团队负责人可以按周查看任务完成、风险名单、提升名单、重点 drill-in 和可导出的周节奏包。

- [ ] **S05: 对外导出与未来入口边界收口** `risk:medium` `depends:[S02,S04]`
  > After this: 系统能够生成稳定的导出数据包、周报、深链入口参数和后续集成 contract，为未来 SSO / CRM / 企业微信接入留下统一边界。

- [ ] **S06: 组织化运营验收** `risk:medium` `depends:[S05]`
  > After this: 至少一个真实团队完成系统内“派发 → 跟进 → 复盘”UAT，并验证权限、导出和资产治理都可持续使用。

## Boundary Map

### S01 → S02

Produces:
- admin analytics / user drill-in / records / manager-lite 共享的 score/evaluable/effectiveness baseline。
- 主管查看个人与团队数据时可依赖的统一 session summary。
- focused tests 防止旧 0.4/0.3/0.3 口径重新回流到管理面。

Consumes:
- nothing (first slice)

### S01 → S03

Produces:
- 资产治理面后续可引用的使用/影响统计基线。
- “哪些训练资产被哪些 session / 人群使用” 的统一统计前提。

Consumes:
- nothing (first slice)

### S02 → S04

Produces:
- 任务派发、提醒、完成状态、结果 drill-in 的最小管理 contract。
- 从主管动作到 session/report 的闭环关系。
- 可被周节奏面板复用的 manager action 数据结构。

Consumes from S01:
- 统一的管理分析口径。

### S03 → S04

Produces:
- 知识/PPT/Persona/runtime profile 的版本、健康、变更和影响范围视图。
- 周节奏里可引用的“本周材料/配置发生了什么变化”治理信息。

Consumes from S01:
- 资产影响统计基线。

### S02 + S04 → S05

Produces:
- 任务、提醒、结果、周报、导出的一致 contract。
- 稳定的 deep-link / export payload / future integration envelope。
- 不依赖某个具体企业系统也能验证的对外边界。

Consumes from S02:
- 系统内主管任务闭环。

Consumes from S04:
- 团队/部门周节奏运营面板。

### S05 → S06

Produces:
- 一条真实组织化运营验收路径。
- 系统内 manager workflow、资产治理、导出 boundary 和权限验证的最终 proof。

Consumes from S05:
- 已收口的对外导出与入口 contract。
