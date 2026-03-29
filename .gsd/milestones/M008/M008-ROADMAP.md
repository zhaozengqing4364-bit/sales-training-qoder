# M008: 

## Vision
在现有训练、knowledge-check 与 canonical report 路由族上，给每条 knowledge-backed session 建立一条小而稳定、可审计、可对照的 retrieval truth：是否触发检索、何时检索、命中了什么、为什么 miss 或失败，以及这些事实如何同时解释 knowledge-check 与 report 的结论。

## Slice Overview
| ID | Slice | Risk | Depends | Done | After this |
|----|-------|------|---------|------|------------|
| S01 | 会话检索账本落库 | high | — | ✅ | 查看同一条 knowledge-backed session 的 persisted `voice_policy_snapshot`，可以回答是否发生检索、查了什么、返回了多少结果、为什么 miss 或失败。 |
| S02 | knowledge-check 与 report 共用检索真相 | high | S01 | ✅ | 对同一条 completed session 连续请求 `/api/v1/practice/sessions/{id}/knowledge-check` 和 `/api/v1/practice/sessions/{id}/report`，两边返回一致的 retrieval 事实与分层解释。 |
| S03 | 报告页检索事实可见化 | medium | S02 | ✅ | 打开现有 report 页即可看到该 session 的 KB 绑定、最近检索事实与对应的 hit/miss/failure/weak-evidence 说明。 |
