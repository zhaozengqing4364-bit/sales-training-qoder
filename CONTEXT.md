# CONTEXT.md — 领域术语表

> 本文件是项目的共享领域语言源头。所有模块、ADR、spec 和代码中的术语以此为准。
> 与代码矛盾时，先更新本文件，再修代码。

---

## 场景 (Scenario)

**定义**：训练类型的高层分类，决定了 WebSocket 运行时、评估逻辑和报告模板的选型。

| 取值 | 说明 |
|------|------|
| `sales` | 销售对练场景，走 `sales_bot/` 运行时 |
| `presentation` | PPT 演练场景，走 `presentation_coach/` 运行时 |

**文件**：`PracticeSession.scenario_type` 字段。

**禁止**：
- 不得将 Practice Mode / Practice Pattern 与 Scenario 混淆。
- Scenario 只取 `sales | presentation` 两个值，不扩展。

---

## 练习模式 (Practice Mode)

**定义**：某个 Scenario 下的具体练习形态。例如在 `sales` 场景下，可以有 `customer_roleplay`（客户对练）、`product_pitch`（产品介绍）等模式。

**状态**：待定 — 当前系统尚未统一定义 Practice Mode 枚举。一旦落地，此处更新。

**与 Scenario 的关系**：N:1。一个 Scenario 可以有多个 Practice Mode。

---
