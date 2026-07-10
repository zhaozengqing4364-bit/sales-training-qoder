# 模块化单体 2.0 Gate 0A：平台合同真相

## Goal

在不改变生产 REST/WS、权限、状态机、Provider 或数据语义的前提下，恢复 FastAPI
路由/OpenAPI、domain contributor、Realtime 鉴权与异步采集测试的可信基线，并把
这些合同纳入现有主质量门禁，为后续架构重构提供可靠反馈环。

## What I already know

- 用户已批准“渐进式模块化单体 2.0 + AI 原生变更包”方案。
- 本任务只实施总体路线图的 Gate 0A；Gate 0B、0C、1A 及 Realtime 重构不在本任务。
- 后端 unit + contract 当前基线为 2,592 collected、2,556 passed、36 failed、1 skipped。
- `test_route_integrity.py` 的 4 个失败来自 FastAPI `_IncludedRouter` 表示变化；OpenAPI
  parity 是真实漂移：committed 330 paths、runtime 491 paths、runtime-only 161。
- Realtime reconnect 测试继续使用 fake token，但生产 Handler 已 fail-fast 关闭 4401。
- Transcript capture 测试在非阻塞异步 task 获得调度前立即读取列表，存在测试竞态。
- `test_sales_trainer_phase2_contract.py` 清空全局 contributor registry 后未恢复，导致
  后续 `test_sessions.py` 出现 `[RUNTIME_POLICY_RESOLVER_NOT_REGISTERED]`。
- `register_domain_contributors()` 可重复调用，是生产 composition root 的权威清单。
- 当前工作区有用户未提交的 readiness/design-system 任务改动，本任务不得纳入或覆盖。

## Requirements

1. Reconnect 测试必须注入合法身份 payload，不得弱化生产 JWT 校验或 4401 行为。
2. Transcript capture 测试必须用条件等待证明 sink 已启动，同时证明主事件处理未等待
   sink 完成；禁止固定 sleep。
3. 测试默认 contributor 必须复用 `domain_contributor_bootstrap`，不能维护第二份 domain
   注册清单；每个测试前后恢复默认 registry，避免顺序依赖。
4. 路由测试必须同时盘点 direct route 和 FastAPI included route effective context，继续
   检查 method/path 重复、关键路由、WebSocket 双路由和静态路由优先级。
5. OpenAPI 以 `create_app().openapi()` 为权威，提供稳定生成命令和只读 `--check`；
   committed contract 必须与 runtime schema 语义相等。
6. 只扩展现有 `scripts/critical-quality-gate.sh`，不得新增第二套发布门禁。
7. Gate 0A 负责的失败必须全部消失；全量测试中剩余 Gate 0B 失败必须显式记录，不得
   通过 skip/xfail/排除伪造全绿。

## Acceptance Criteria

- [x] Realtime reconnect 和 transcript-capture 聚焦测试稳定通过。
- [x] Contributor 污染顺序复现通过，`test_sessions.py` 不再因未注册 port 失败。
- [x] Route integrity 和 app factory route surface 测试通过。
- [x] OpenAPI 生成后 `--check` 返回 0，runtime-only/committed-only paths 均为 0。
- [x] OpenAPI 生成器具备稳定渲染和语义 drift 单测。
- [x] Gate 0A 测试目标和 OpenAPI check 进入现有 critical quality gate。
- [x] 修改文件通过 Ruff；聚焦回归集全部通过。
- [x] 全量 unit+contract 重跑后，Gate 0A 失败簇为 0，其他失败按 Gate 0B 归档。

## Definition of Done

- 测试按 Red → Green 验证，修复根因而非删除断言。
- 不改变生产 API、WS、权限、lifecycle、snapshot 或 Provider 行为。
- OpenAPI 合同和脚本用法有文档。
- `trellis-check` 完成 spec、lint、测试和跨层一致性复核。
- 发现的长期规范经 `trellis-update-spec` 判断并记录。
- 只提交本任务文件，用户未提交改动保持原样。

## Technical Approach

- FastAPI route inventory 在测试层引入局部兼容 iterator，读取 direct route 或
  `_IncludedRouter.effective_route_contexts()`，不把框架测试 helper 放进生产 common。
- Contributor 隔离通过 autouse fixture 在每个测试前后调用生产 bootstrap；测试需要
  空 registry 时在自身 Arrange 显式 clear。
- OpenAPI generator 位于 `backend/scripts/`，显式把 `backend/src` 加入 import path，
  支持写入默认 committed contract 和 `--check` 语义比较。
- 实施严格按
  `docs/superpowers/plans/2026-07-10-gate-0a-platform-contract-truth.md` 五个 Task 执行。

## Decision (ADR-lite)

**Context**：当前测试资产丰富，但部分关键测试未进入主门禁且已发生 fixture/框架/API
合同漂移；直接启动 Realtime 架构重构会缺少可信反馈环。

**Decision**：先完成 Gate 0A 平台合同真相，不改变生产行为；路由适配留在测试层，
contributor 复用生产 composition root，OpenAPI 由 runtime schema 生成。

**Consequences**：会产生一份较大的 generated OpenAPI diff，并短期增加测试 fixture 和
生成脚本；换取后续每个架构切片都有可重复、可进入 CI 的行为合同。

## Out of Scope

- 不修 Gate 0B 的 Sales Trainer、PPT forbidden word、secret scan 失败。
- 不修 Gate 0C 的 dashboard/business-skills Vitest 失败和全量退出性能。
- 不实施 Gate 1A dependency/SCC guard。
- 不创建 RealtimeSessionEngine、Provider Port 或新的生产 Adapter。
- 不修改数据库、migration、权限、业务阈值和用户界面。
- 不运行真实 StepFun/LLM/TTS Provider。

## Technical Notes

- 总设计：`docs/superpowers/specs/2026-07-10-modular-monolith-2-design.md`
- ADR：`docs/adr/2026-07-10-modular-monolith-2-ai-native-governance.md`
- 路线图：`docs/superpowers/plans/2026-07-10-modular-monolith-2-roadmap.md`
- 详细计划：`docs/superpowers/plans/2026-07-10-gate-0a-platform-contract-truth.md`
- 根因证据：`research/platform-contract-root-causes.md`
- 风险等级：P1；本任务不写生产数据，回滚为逐个独立变更包回退。

## Research References

- [`research/platform-contract-root-causes.md`](research/platform-contract-root-causes.md) —
  记录四个失败簇的可重复反馈环、根因证据和不应采用的伪修复。
