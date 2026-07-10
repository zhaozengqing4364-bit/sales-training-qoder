# ADR 2026-07-10：模块化单体 2.0 与 AI 原生架构治理

## Status

Accepted。目标设计已由用户批准；代码迁移按 Gate 逐步实施。本文描述目标边界和
迁移约束，不把尚未完成的物理迁移写成当前事实。

## 背景

系统当前采用 FastAPI + Next.js 模块化单体。现有架构文档要求场景隔离、共享逻辑
进入 `common`，并通过 contributor/port 处理跨域能力。近期审计确认：

- 系统具有稳定用户路径和较丰富测试资产；
- 第一轮 realtime Seam 已降低单文件复杂度；
- 13 个后端顶层包存在 49 条跨包依赖，12 个包位于同一 SCC；
- Realtime Mixin 仍通过数百个共享私有字段形成隐藏 Interface；
- Roleplay Contract、Configuration Governance、Evaluation 的所有权仍是过渡态；
- 发布门禁只执行部分测试，OpenAPI 和多组测试夹具已经漂移。

AI 辅助开发显著提高提交吞吐。继续按传统人周规划或依赖人工记忆维护边界，会让
结构债以更快速度增长。因此需要把目标架构和架构护栏同时纳入可执行合同。

## 决策

### 1. 保持模块化单体

继续使用单进程部署、单 PostgreSQL schema、Redis/Chroma 和现有 REST/WS 协议。
当前不拆微服务，不引入分布式事务或新的基础设施依赖。

### 2. 采用渐进式 Deep Module 迁移

目标 Module 为：

- Practice Session；
- Realtime Session Engine；
- Realtime Provider Adapters；
- Roleplay Contract & Situation Pack；
- Learning & Assessment Assets；
- Evaluation & Report；
- Configuration Governance；
- Training Journey；
- Identity/Access 和 Support/Observability Adapters。

迁移采用 Strangler/Branch by Abstraction。兼容层只转发，不新增规则。

### 3. Realtime 从继承改为组合

`RealtimeSessionEngine` 逐步成为 session runtime 的唯一决策权威。Sales、
Presentation、Examiner 通过 Scenario Hooks 和 Adapter 组合，不再通过 Sales Shared
Handler 继承后关闭能力。

StepFun 保持当前 Sales 默认 Provider，但作为 `RealtimeProviderPort` Adapter 接入。
引入 Port 不等于启用新的生产 Provider。

### 4. 完成中立领域所有权

- Roleplay Contract 从 curriculum-only 过渡所有权迁到中立 bounded context；
- ConfigBundle 的发布、版本、审批和影响预览迁到 Configuration Governance；
- Evaluation 只消费 Evidence、Roleplay Contract、Ruleset 和 Scenario Adapter；
- `admin`、HTTP、WebSocket、ORM、StepFun 都是 Adapter，不是领域所有者。

### 5. `common` 收缩但数据库暂不拆分

`common` 只保留稳定 Shared Kernel 和 port。跨域访问先迁到 repository/projection。
`common/db/models.py` 可物理拆文件，但继续使用同一个 `Base.metadata`，不在本轮改变
数据库部署、表名或 Alembic 历史。

### 6. 架构边界成为 CI 合同

建立 AST 架构 guard：

- 声明稳定允许依赖；
- 当前逆向边作为临时 exception，包含 owner、原因、退役条件、到期日；
- 禁止新增跨包边；
- 禁止扩大现有 SCC；
- exception 消失后要求同步删除政策条目；
- policy 过期直接失败。

CodeGraph 用于理解和 impact selection；CI guard 使用仓库内纯 Python AST 实现，避免
CI 依赖外部索引状态。

### 7. 先恢复测试事实，再扩大门禁

全量 unit/contract/Vitest 当前并非绿色。先按根因恢复测试、OpenAPI 和 contributor
隔离，再把自动发现测试加入主门禁。禁止通过 `xfail`、`|| true` 或永久排除列表把
未知失败伪装成绿色。

### 8. 使用可验证变更包衡量进度

计划单位为独立变更包和 Gate，不使用人周作为完成定义。每个变更包必须有：

- 明确行为或边界目标；
- 失败测试或当前失败证据；
- 最小 Implementation；
- 精确验证命令；
- 影响分析；
- 兼容和回滚点。

## 保持不变的合同

- 外部 REST/WS/binary audio shape；
- fail-fast auth、对象级权限和 RuntimeGate admission；
- frozen voice/curriculum/roleplay snapshot；
- KB fail-closed；
- request/response/connection epoch；
- REST/WS 同一 lifecycle；
- reconnect 不重复评分/报告；
- Roleplay observation record-only；
- Evidence 不足不伪分。

## 备选方案

### A. 只增加测试和依赖门禁

优点是风险低。缺点是只能阻止继续恶化，无法降低 Realtime、Roleplay 和 Evaluation
的实际变更半径。拒绝作为最终方案，保留为 Gate 0–1。

### B. 渐进式模块化单体 2.0

采用。它保留现有事务、部署和用户合同，通过 tracer bullet 和兼容 Adapter 逐步
替换内部结构。

### C. 重写或拆微服务

拒绝。当前问题是所有权和依赖方向，不是单体部署本身。重写会触发第二系统效应，
并在缺少可信全量门禁时放大行为丢失风险。

## 影响

### 代码

- 短期增加 architecture policy、测试 helper、兼容 Adapter 和 composition wiring；
- 中期减少跨域 import、Mixin 共享状态和字符串 service path；
- 长期删除旧 Handler 写入路径和过渡 contributor exception。

### 数据

- 本 ADR 不引入 migration；
- 历史 snapshot/hash/report 不重算；
- 后续表物理拆文件不改变表结构和 metadata authority。

### API 和权限

- 不改变外部 API、WS、close code、角色和对象权限；
- 新 Provider/Engine 路径必须继续执行相同 auth/admission/policy。

### 测试和 CI

- 先恢复现有红测和 OpenAPI parity；
- 再启用全量自动发现和 architecture guard；
- 真实 Provider 继续放在 schedule/manual gate。

### 运维

- 新旧 runtime 切换必须可观察、可关闭；
- 不同时双写评分和报告；
- 回滚切回旧 Adapter，不修改已冻结 session。

## 风险

- P1：Realtime、Roleplay、Evaluation 和核心状态机为高影响区域；
- 最大风险不是代码量，而是隐藏状态、时序和历史 snapshot 语义；
- 每个 Gate 未通过 Golden Conversation Contract 前不得删除旧路径。

## 回滚

1. 保留 architecture guard 和测试事实修复；
2. 通过 feature flag/runtime selection 把流量切回旧 Adapter；
3. 停止新 Engine 写入，保留已经冻结的 snapshot/evidence；
4. 回滚当前独立变更包，不跨 Gate 回滚无关改动；
5. 不恢复已退役的反向依赖作为长期方案；如紧急恢复，必须新增带到期日 exception。

## 参考

- `docs/architecture.md`
- `docs/adr/2026-06-20-backend-runtime-boundary-ownership.md`
- `docs/adr/2026-06-20-controlled-cross-domain-adapters.md`
- `docs/adr/2026-05-26-roleplay-contract-governance.md`
- `docs/adr/2026-07-03-roleplay-realtime-record-only.md`
- `docs/superpowers/specs/2026-07-10-modular-monolith-2-design.md`
