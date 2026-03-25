# M005: 后台治理与规模化运营

**Vision:** 基于已经证明可信的训练与学习闭环，把现有 admin 业务代码入口做成真正可运营的管理链路：主管能在系统内看对数据、指定重点、提醒、复查结果；运营能看清 Persona / knowledge / presentation / runtime 配置的影响与健康。

## Success Criteria

- 现有管理入口 `web/src/app/admin/analytics/page.tsx`、`web/src/app/admin/users/page.tsx`、`web/src/app/admin/users/[id]/page.tsx`、`backend/src/admin/api/interventions.py` 不再各讲各的话，全部站到当前 unified evidence / sales semantics 基线上。
- 主管可以在现有 admin surfaces 内完成最小闭环：看见问题 → 指定训练重点 / 提醒 → 查看完成情况 → drill into report/replay 复查结果。
- 知识库、Persona、PPT、voice runtime 这些已经存在的运营资产具备版本、健康、影响范围与最近变更的统一治理视角。
- 组织级看板与导出基于真实业务代码与训练事实，而不是旧 weighted formulas、placeholder 数据或环境/工具链杂项。

## Slices

- [ ] **S01: admin analytics / user drill-in 语义收口** `risk:high` `depends:[]`
  > After this: The current admin analytics and user drill-in routes no longer disagree with learner/supervisor evidence about scores, issue families, or evaluability.

- [ ] **S02: 系统内主管重点与提醒闭环** `risk:high` `depends:[S01]`
  > After this: A supervisor can set a training focus, send a reminder, and later see whether a resulting session improved that issue family — all on current admin surfaces.

- [ ] **S03: 资产影响面与健康治理** `risk:medium` `depends:[S01]`
  > After this: On the current knowledge/persona/presentation/runtime admin pages, operators can see recent changes, health anomalies, and likely impact range.

- [ ] **S04: 团队周节奏包与 cohort 问题面** `risk:medium` `depends:[S02,S03]`
  > After this: A team lead can look at the current admin entrypoints and see issue buckets, risk lists, improving lists, and a one-week operating summary.

- [ ] **S05: 现有 admin 链路的组织化 UAT** `risk:medium` `depends:[S04]`
  > After this: One real team workflow completes analytics → user drill-in → focus/reminder → report/replay review → weekly pack using the current admin surfaces.

## Boundary Map

### S01 → S02

Produces:
- A unified admin analytics / user-drill-in semantic baseline on the current evidence line.
- Shared issue-family, evaluability, degradation, and score semantics reused by intervention workflows.

Consumes:
- nothing (first slice)

### S01 → S03

Produces:
- A trustworthy usage / impact baseline that asset-governance screens can reuse.
- Alignment between admin analytics and learner/supervisor evidence surfaces.

Consumes:
- nothing (first slice)

### S02 → S04

Produces:
- Focus assignment / reminder / status / result-linkage contracts on the current admin routes.
- Manager actions that can be aggregated into a weekly operating view.

Consumes from S01:
- Unified admin semantics.

### S03 → S04

Produces:
- Asset health / impact / recent-change context that can be shown in weekly operating packs.
- A governance line for knowledge/persona/presentation/runtime assets.

Consumes from S01:
- Usage / impact baseline.

### S04 → S05

Produces:
- A real team workflow on the current admin entrypoints: analytics → drill-in → action → review.
- Operating-pack outputs and acceptance surfaces.

Consumes from S02:
- Manager workflow contract.

Consumes from S03:
- Asset-governance surfaces.
