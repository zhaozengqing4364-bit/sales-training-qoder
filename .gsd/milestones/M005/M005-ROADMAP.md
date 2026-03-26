# M005: 后台治理与规模化运营

## Vision
基于已经证明可信的训练与学习闭环，把现有 admin 业务代码入口做成真正可运营的管理链路：主管能在系统内看对数据、指定重点、提醒、复查结果；运营能看清 Persona / knowledge / presentation / runtime 配置的影响与健康。

## Slice Overview
| ID | Slice | Risk | Depends | Done | After this |
|----|-------|------|---------|------|------------|
| S01 | admin analytics / user drill-in 语义收口 | high | — | ⬜ | The current admin analytics and user drill-in routes no longer disagree with learner/supervisor evidence about scores, issue families, or evaluability. |
| S02 | 系统内主管重点与提醒闭环 | high | S01 | ⬜ | A supervisor can set a training focus, send a reminder, and later see whether a resulting session improved that issue family — all on current admin surfaces. |
| S03 | 资产影响面与健康治理 | medium | S01 | ⬜ | On the current knowledge/persona/presentation/runtime admin pages, operators can see recent changes, health anomalies, and likely impact range. |
| S04 | 团队周节奏包与 cohort 问题面 | medium | S02, S03 | ⬜ | A team lead can look at the current admin entrypoints and see issue buckets, risk lists, improving lists, and a one-week operating summary. |
| S05 | 现有 admin 链路的组织化 UAT | medium | S04 | ⬜ | One real team workflow completes analytics → user drill-in → focus/reminder → report/replay review → weekly pack using the current admin surfaces. |
