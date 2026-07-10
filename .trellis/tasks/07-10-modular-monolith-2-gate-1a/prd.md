# 模块化单体 2.0 Gate 1A：架构适应度

## Goal

先同步 Gate 0A 的完成证据，再把当前后端跨包依赖、强连通分量和临时迁移边转换为
离线、确定性、可由 CI 执行的架构合同。该 Gate 只建立护栏，不搬迁业务代码，不改变
REST、WebSocket、权限、状态机、Provider、数据或用户行为。

## What I already know

- Gate 0A 已通过 5 个工作提交完成并归档，聚焦回归为 `53 passed, 1 warning`；后端
  unit + contract 为 `2579 passed, 15 failed, 1 skipped`，15 项属于 Gate 0B。
- Gate 0A 原实施计划仍有 35 个未勾选项，总体路线图没有可执行进度表，文档事实落后于
  已归档 Trellis 任务和 CI。
- 13 个目标后端包当前基线为 49 条跨包边，其中 12 个包处于同一 SCC；`supervisor`
  不在该 SCC。
- 仓库没有 `architecture_dependency_guard.py`、对应单测或
  `module-dependency-policy.yaml`；现有门禁只有若干局部 boundary tests。
- CI guard 必须使用仓库内 Python AST，不依赖 `.codegraph/` 或外部服务。
- 当前工作区的 readiness 文档改动属于其他任务，本 Gate 不得暂存、覆盖或提交。

## Requirements

1. Gate 0A 计划、总体路线图和目标设计必须同步完成状态、提交/测试证据和下一 Gate。
2. 新增纯 Python AST scanner，统计 static import、`TYPE_CHECKING`、函数内 import 和
   字面量 `import_module`/`__import__`；非字面量 plugin path 明确不推断。
3. 新增 YAML policy，声明 13 个包、stable edges、temporary edges 和 baseline SCC。
4. 每个 temporary edge group 必须包含 owner、reason、retire_when、expires_on；缺失、
   格式错误、过期、已经消失却未删除的 exception 都必须失败。
5. 当前 12 包 SCC 可以通过且允许缩小；新增跨包边、扩大 SCC 或把 `supervisor` 并入
   SCC 必须失败。
6. scanner、policy、单测、架构文档和现有 `critical-quality-gate.sh` 形成一套权威，
   不新增第二套发布门禁。
7. 保留现有 runtime/newcomer/knowledge boundary tests，并把 architecture guard test 加入
   backend gate targets。
8. 通过临时 probe 验证 `sales_bot -> supervisor` 会同时触发 unexpected edge/SCC 失败；
   probe 必须删除且不得提交。
9. 不新增第三方依赖，不修改生产模块依赖或运行时行为。

## Acceptance Criteria

- [x] Gate 0A 文档状态与归档任务、提交和验证证据一致。
- [x] `collect_edges` 覆盖 static、typing、local 和 literal dynamic import。
- [x] Tarjan SCC 单测通过，结果确定性。
- [x] 当前仓库 49 条边全部由 stable 或 temporary policy 解释。
- [x] policy 缺字段、过期、陈旧 exception 会失败。
- [x] 当前 12 包 SCC 通过，新增边和扩大的 SCC 会失败。
- [x] 故障 probe 产生预期双重失败，删除后恢复绿色。
- [x] architecture guard、现有 boundary tests、Ruff 和 CLI 全部通过。
- [x] architecture guard 与单测进入 canonical critical gate。
- [x] `git diff --check`、Trellis check 和 CodeGraph post-impact 通过。

## Definition of Done

- 严格按 Red → Green 实施，不通过弱化政策、永久 allowlist 或跳过伪造绿色。
- 没有生产行为、API、权限、数据库或 Provider 变化。
- 新架构政策具备 owner、原因、退役条件、到期日和失败消息。
- `.trellis/spec/` 记录可执行架构政策的长期合同。
- 本 Gate 逻辑提交完成，Trellis 任务归档并记录 journal。

## Technical Approach

- 以批准的 `2026-07-10-gate-1a-architecture-fitness.md` 为实施权威；实现时以实际 AST
  扫描结果校验 49 条边，不盲目信任手写基线。
- `validate_repository()` 返回稳定排序的 violations，CLI 只读并用退出码表达结果。
- policy 把目标稳定方向和历史迁移例外分开；稳定边可以暂时未出现，临时边一旦消失
  必须同步删除。
- scanner 位于 `backend/scripts/`，测试位于 `backend/tests/unit/`，policy 位于
  `docs/architecture/`；门禁接入现有 Backend Ruff 后的无服务阶段。

## Decision (ADR-lite)

**Context**：CodeGraph 适合理解和影响分析，但 CI 不能依赖外部索引；当前 allowlist
测试只能保护局部边界，不能阻止全局 SCC 扩张。

**Decision**：采用仓库内 AST + YAML policy + Tarjan SCC guard。当前历史债作为带期限
exception，而不是宣称架构已经无环。

**Consequences**：短期增加政策维护成本；换取每次 AI 变更都能在 CI 中证明没有新增
跨包边或扩大循环，并为后续 Gate 2–6 提供可收缩基线。

## Out of Scope

- 不修 Gate 0B/0C 测试失败。
- 不实施自动测试选择、changed coverage 或 Gate 1B。
- 不创建 RealtimeSessionEngine，不迁移 Presentation，不删除任何现有跨包边。
- 不修改数据库、前端、生产权限和外部协议。

## Technical Notes

- 详细计划：`docs/superpowers/plans/2026-07-10-gate-1a-architecture-fitness.md`
- 目标设计：`docs/superpowers/specs/2026-07-10-modular-monolith-2-design.md`
- ADR：`docs/adr/2026-07-10-modular-monolith-2-ai-native-governance.md`
- 根因/基线：`research/architecture-guard-baseline.md`
- 风险等级：P1；回滚为撤销 guard/policy/CI 独立提交，不涉及生产数据。

## Research References

- [`research/architecture-guard-baseline.md`](research/architecture-guard-baseline.md) —
  当前缺失项、动态 import、局部边界测试与算法风险。
