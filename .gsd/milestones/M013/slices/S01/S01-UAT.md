# S01: SYSTEM_AUDIT_REPORT 条目归一化 — UAT

**Milestone:** M013
**Written:** 2026-04-09T16:45:08.785Z

# S01 UAT — SYSTEM_AUDIT_REPORT 条目归一化

## Preconditions
- 仓库中存在最新的 `SYSTEM_AUDIT_REPORT.md` 与 `.gsd/plans/GSD_PLAN_system-audit-repair.md`。
- 评审者可读取 `.gsd/PROJECT.md`、`.gsd/DECISIONS.md`、`.gsd/KNOWLEDGE.md`。
- 允许从仓库根目录运行 `rg` 与一次 scoped parser check。

## Case 1 — 归一化矩阵必须覆盖全部 51 条 audit finding
1. 打开 `.gsd/plans/GSD_PLAN_system-audit-repair.md`，定位到 `1.5.3` 到 `1.5.11` 的原始归一化矩阵区块。
2. 运行 `rg -n "already-fixed|actionable-now|needs-discovery|deferred-by-product|contradicted-by-project-knowledge" .gsd/plans/GSD_PLAN_system-audit-repair.md`。
3. 预期：文档中能看到五类 disposition 图例、rollup counts，以及每个 audit section 的逐条矩阵行。
4. 运行 scoped parser check（只统计 `1.5.3` 到 `1.5.11`，不包含 `1.5.12+` appendix）。
5. 预期：输出 `matrix_rows=51`，并得到 `{actionable-now: 15, deferred-by-product: 8, needs-discovery: 26, already-fixed: 1, contradicted-by-project-knowledge: 1}`。

## Case 2 — 每个 deferred / contradicted / discovery finding 都要有 closeout appendix 支撑
1. 在 `.gsd/plans/GSD_PLAN_system-audit-repair.md` 中定位到 `1.5.13 T02 disposition 复核补遗`。
2. 运行 `rg -n "deferred-by-product|contradicted-by-project-knowledge|needs-discovery" .gsd/plans/GSD_PLAN_system-audit-repair.md`。
3. 预期：文档中存在三类 appendix 内容：
   - 已修项 retirement seam（当前为 JWT secret 风险）。
   - deferred / contradicted 条目的 conflict source 与 why it stays out。
   - needs-discovery 条目的 owning slice 与 implementation 前必须补出的 proof。
4. 随机抽查至少三个 finding（例如 `4.1.1`、`5.1.1`、`3.2.1`）。
5. 预期：每个 finding 都能在原矩阵与 appendix 之间对上 audit ID、disposition、证据路径和后续归属，不存在“只写了 disposition 名称但没有支撑说明”的条目。

## Case 3 — T03 crosswalk 必须把逻辑 owner 映射到真实 roadmap slices
1. 在 `.gsd/plans/GSD_PLAN_system-audit-repair.md` 中定位到 `T03 backlog crosswalk`。
2. 运行 `rg -n "M014|M015|M016|M017|M018" .gsd/plans/GSD_PLAN_system-audit-repair.md`。
3. 预期：文档中存在 `Legacy logical slice -> Actual milestone/slice` 对照表，并出现 `M013-S02`、`M014`、`M015`、`M016`、`M017`、`M018` 的真实 slice 编号。
4. 抽查一条 actionable-now finding（例如 `1.1.2` 或 `14.3`）与一条 needs-discovery finding（例如 `3.2.1` 或 `15.3`）。
5. 预期：能从原矩阵 owner 标签找到对应 legacy logical slice，再从 crosswalk 找到真实执行 slice；后续执行者不需要重读原 audit 文档也能知道应该去哪一个 roadmap slice 落地。

## Case 4 — 项目元信息必须同步到新的审计归一化事实
1. 打开 `.gsd/DECISIONS.md`，查找 `M013/S01/T01`、`M013/S01/T02`、`M013/S01/T03`。
2. 预期：至少存在一条 T01 归一化决策和两条 T02/T03 决策，能解释为什么采用五类 disposition、为什么保留原矩阵、为什么用 crosswalk 而不是重写 owner 标签。
3. 打开 `.gsd/KNOWLEDGE.md`。
4. 预期：存在关于 `.gsd/plans/GSD_PLAN_system-audit-repair.md` 的非显然使用约束，至少包括 row-count 校验要避开 appendix，以及逻辑 owner 标签必须通过 T03 crosswalk 解码为真实 slice。
5. 打开 `.gsd/PROJECT.md`。
6. 预期：Current State / Milestone Sequence 已反映 M013/S01 完成，并明确后续 repair/discovery slices 应基于这份归一化计划推进。

## Edge Checks
- **Appendix double-counting guard:** 若有人直接对整份 `GSD_PLAN_system-audit-repair.md` 做表格计数，应识别为错误验证方式；正确方式必须只统计 `1.5.3` 到 `1.5.11`。
- **Stable audit traceability:** 若下游尝试把原矩阵中的 `M1`-`M6` owner 标签直接改写成 `M013`-`M018`，应视为破坏 traceability；正确做法是保留矩阵 owner 并使用 T03 crosswalk。
- **No unclassified items:** 任意抽查一个 audit ID，都应能同时回答四件事：它属于哪类 disposition、证据在哪、为什么是这个 disposition、后续由哪个 slice 消费或为什么当前不进入 backlog。
