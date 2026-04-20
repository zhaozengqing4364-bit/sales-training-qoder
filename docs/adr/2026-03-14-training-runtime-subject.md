# ADR 2026-03-14: 训练运行时主语收敛为 `training_scenario_runtime`

## Context

系统同时存在 `Scenario`、`Agent`、`Presentation` 三套抽象：

- `Scenario` 更像训练模板/入口配置。
- `Agent` 更像销售场景的策略与能力配置载体。
- `Presentation` 是演讲训练的内容资源。

这些实体都可能参与一次训练，但它们不应该同时充当“运行时主语”。继续以实体名驱动接口、权限、观测和统计，会造成：

- 生命周期接口继续分叉，前端控制逻辑不断复制。
- 权限与审计口径按实体散落，难以形成统一控制面。
- 指标和链路追踪无法围绕一次真实训练会话建立单一事实来源。

## Options

### Option A: 保持现状，按实体类型分别建模

- 优点：短期改动最少，延续已有页面与数据结构。
- 缺点：运行时语义持续分裂，后续每增加一个场景都要复制 lifecycle、auth、telemetry、report 逻辑。

### Option B: 以 `PracticeSession` 作为主语，不显式暴露统一运行时描述

- 优点：数据库层已有会话聚合根，实现成本低。
- 缺点：会话 ID 只能说明“有一次训练”，不能说明其运行时语义，也无法明确区分配置面与运行时面。

### Option C: 对外统一为 `training_scenario_runtime`，并由 `PracticeSession` 承载事实

- 优点：把配置实体与运行时语义解耦，接口、权限、统计、观测都能围绕统一运行时主语演进。
- 缺点：需要补充契约字段、文档和前后端类型，短期有一次性收敛成本。

## Decision

选择 Option C。

- `PracticeSession` 继续作为事实锚点。
- 对外运行时主语统一为 `training_scenario_runtime`。
- `Scenario`、`Agent`、`Presentation` 保留在管理面/配置面，不再直接充当运行时主语。
- 会话契约对外暴露 `runtime_subject`，并补齐 `runtime_descriptor` 作为统一运行时描述。

这是一个偏“单向门”的语义决策，因为一旦前后端、指标和权限体系围绕统一主语建设，再回退到多主语会造成更大迁移成本。因此本次以 ADR 固化。

## Consequences

### Positive

- 生命周期控制可围绕单一运行时状态机治理，减少前端双写和后端分支。
- 权限、日志、trace 和指标更容易围绕单次训练建立统一观测链路。
- 后续新增场景时，可复用同一运行时契约，只替换配置来源。

### Negative

- 旧文档和部分历史命名仍会继续存在，需要分阶段清理。
- 管理面仍保留 `Agent` / `Scenario` / `Presentation`，团队需要明确“配置面”和“运行时面”的语言边界。

## Follow-up

- 会话、回放、报告、WebSocket 契约统一围绕运行时主语描述。
- 前端服务端边界、查询缓存和观测埋点继续围绕 `PracticeSession` + `training_scenario_runtime` 收口。
- 后端 OpenTelemetry 继续从“初始化入口”演进到“真实跨前后端链路贯通”。
