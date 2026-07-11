# ADR 2026-07-10：模块化单体 2.0 与 AI 原生架构治理

## Status

Accepted。目标设计已由用户批准；代码迁移按 Gate 逐步实施。Gate 0A–2 已完成，Gate 3–6
仍待实施。本文描述目标边界和迁移约束，不把尚未完成的物理迁移写成当前事实。

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

实施状态（2026-07-10）：Gate 0B 已使 backend unit + contract 达到 `2617 passed,
1 skipped`；Gate 0C 已使全量 Vitest 达到 209 files、1327 passed、6 个既有 skipped，
并在 5:54.32 自然 exit 0。该决策的“先恢复事实”前置已满足，Gate 1B 负责把完整自动
发现、影响选择和变更覆盖接入唯一主门禁。

Gate 1B 实现决定：unit+contract 与 Vitest 每次均按目录/配置自动发现，selector 只控制慢速
integration/backend E2E/Playwright。选择结果是有 schema 的 artifact，来源为 critical baseline、
直接测试改动、仓库 path policy 和健康 CodeGraph 加法；不可信 base、非法/空图结果、未知生产
路径、删除/重命名及横切配置变化必须扩大到 family/full fallback。CI 缺 CodeGraph 不得缩小
policy 选择。

changed coverage 使用 unit+contract 与 selected integration/E2E 合并后的 backend branch
artifact，以及 include 全生产 `src` 的 frontend Istanbul artifact。新增 executable line 门槛为
80%，关键状态机 branch ratio 不得低于 adoption floor。selection/coverage 两份 policy 的临时
anchor 具有相同 owner、退役条件和 2026-08-10 到期日，并由 guard 检查一致性；到期未退役
直接失败。

Gate 1B 完成证据（2026-07-10 UTC）：唯一 `critical-quality-gate.sh` 从 clean start 自然
exit 0；backend unit+contract branch coverage 为 `2665 passed, 1 skipped`，完整 Vitest 为
209 files / `1329 passed, 6 skipped`，全部本地 Playwright 关键族通过，selected backend
integration/E2E 为 `598 passed, 21 skipped`。changed executable lines 为 41/50（82%），
所有关键状态机 changed branch source line 已覆盖且 branch floor 无回退。独立 Trellis check
发现并修复跨 runner Presentation fixture fallback 后，selector/coverage guard 为 `48 passed`，
剩余阻塞 finding=0。

Gate 2 完成事实（2026-07-11 UTC）：Presentation 的 `stepfun_realtime` 生产入口默认选择
`PresentationRealtimeEngineHandler`，由 app root 用 immutable closed factory key 组合
`RealtimeSessionEngine` 和命名兼容 Adapter；`PRESENTATION_REALTIME_ENGINE_ENABLED=false`
在构造前原子回滚到 `LegacyPresentationStepFunRealtimeHandler`，每个 session 只构造一个
handler。Engine 显式拥有 versioned Connection/Turn/Grounding/Evidence 状态，兼容 Adapter
仍是 message、score、report 和 reconnect persistence 的唯一 writer；snapshot 仅 additive
新增 `runtime_state.realtime_engine` 并兼容 pre-Gate 恢复。Presentation 从第一次 base 初始化
即禁用 Sales capability construction，Sales 默认行为不变。真实 Golden differential 覆盖
connect/start/text/audio/transcript/response.done/reconnect/close、完整 legacy snapshot 投影、
epoch/grounding/evidence terminal state 和 mutation sensitivity。二进制音频只有在共享入口确认
upstream 与本地 audio flow 均 accepted 后才进入 Presentation 的 O(1) turn 累加器；本地 commit
成功后、response 调度前仅写一条 SHA-256 digest Evidence，拒绝帧、逐帧和重复 commit 均不写。

Gate 2 唯一 canonical gate 从 clean start 重跑并自然 exit 0：backend unit+contract
`2868 passed, 1 skipped`；Vitest 209 files / `1329 passed, 6 skipped`；Playwright generic/smoke/
newcomer/presentation/sales 分别为 `3/9/11/2/1 passed`（newcomer 保留 1 个既有真实收费
Provider 条件 skip）；selected backend integration/E2E `598 passed, 21 skipped`；changed
executable lines 770/847（90.91%），critical branch 无 changed missing line、无 adoption floor
回退，最终输出 `Critical quality gate passed`。

该完成事实不包含 Gate 3。兼容 Adapter 仍复用 `sales_bot` StepFun mixins，实际
`presentation_coach -> sales_bot` dependency policy 临时边仍保留；
`RealtimeProviderPort`、provider event codec 和 Grounding 单一状态/缓存权威仍待 Gate 3。

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
