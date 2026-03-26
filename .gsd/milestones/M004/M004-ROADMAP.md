# M004: 复盘与学习闭环增强

## Vision
让用户与主管在现有 report / replay / history 业务入口上完成“训练 → 报告 → 回放 → 关键片段 → 针对性复练”的学习闭环。所有学习证据都必须来自统一 session evidence / replay / presentation review authority line，而不是再造一套生成式学习系统。

## Slice Overview
| ID | Slice | Risk | Depends | Done | After this |
|----|-------|------|---------|------|------------|
| S01 | 当前 report/replay/highlight 入口的学习证据 contract | high | — | ✅ | On the existing replay and highlight surfaces, a learner can see which turn mattered, why it mattered, which stage it belongs to, and what a better response looks like — without adding a new learning page. |
| S02 | report 直达 replay 关键片段 | high | S01 | ✅ | On the current report page, the learner can open the replay at the relevant turn/marker for the surfaced issue or goal. |
| S03 | 主问题驱动的再练入口 | high | S01, S02 | ✅ | From the current report or replay page, the learner can start a new practice session targeted at the previous issue family and see that focus carried into the new session. |
| S04 | PPT 页级学习证据 | medium | S01 | ⬜ | On the current PPT report/replay routes, a learner can see which page has which issue cluster and why it should be reworked. |
| S05 | sales + PPT 学习闭环终验 | medium | S03, S04 | ⬜ | At least one sales and one PPT route complete a live learning loop on the current entrypoints, and degraded states remain understandable. |
