# 新人训练 P0/P1 阻断修复总计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 关闭新人训练受控试点前最关键的三个阻断：复核决策完整性、路径前置闸门、学习专题可信证据。

**Architecture:** 三个子计划按可独立评审、独立回滚的 Module 切分。执行顺序为复核决策完整性 → 路径前置闸门 → 学习专题 Attempt；每个子计划必须单独通过测试和提交，不允许把当前客户问答 WIP 混成一个大提交。

**Tech Stack:** FastAPI、Pydantic v2、SQLAlchemy AsyncSession、Alembic、PostgreSQL/SQLite 测试、Next.js/React/TypeScript、Vitest、Pytest。

## Global Constraints

- 只修改新人训练闭环直接依赖的文件，不顺手重构无关模块。
- 继续使用 active asset revision 作为训练配置唯一生效源。
- 学习专题保持 `required=false`、`blocks_next=false`，不得重新进入主路径完成率。
- 所有关键写入必须有后端权限、对象范围、幂等、并发冲突和审计。
- 历史证据不得被新 revision 重写或冒充为当前 revision 证据。
- 普通用户界面不得展示内部 key、traceId、raw JSON 或数据库主键。
- 不新增第三方依赖。
- 每个子计划从独立 worktree/branch 执行，避免污染当前 39 项未提交工作区。

---

## 子计划及依赖顺序

1. [Readiness 复核决策完整性](./2026-07-10-readiness-decision-integrity.md)
   - 独立 `review_readiness` 写权限。
   - 独立决策状态表、幂等键和乐观并发。
   - OperationLog 只保留为审计 Adapter。

2. [新人路径前置闸门](./2026-07-10-newcomer-path-prerequisite-gates.md)
   - 发布时校验依赖引用。
   - Journey、旧 Path Projection、直接单元访问共用一个 prerequisite policy。
   - 训练未完成时后续入口后端 fail-closed。

3. [学习专题可信 Attempt 证据](./2026-07-10-learning-topic-attempt-evidence.md)
   - 建立通用、revision-bound 的 Learning Topic Attempt Module。
   - 商务礼仪和客户问答统一投影契约。
   - AI 失败也保留提交证据，历史 revision 不污染当前进度。

## 总体验收闸门

- [ ] `operations` 可以查看全局记录，但不能创建 readiness review action。
- [ ] 培训负责人只能复核本部门新人，平台管理员可以全局复核。
- [ ] 相同幂等键重复提交只产生一个复核动作；陈旧版本提交返回 409。
- [ ] 未满足 `unlock_after_unit_ids` 时，Journey 显示锁定且直接 API 访问失败。
- [ ] 前置任务达标后，相同 Journey 请求立即解锁后续任务。
- [ ] 学习专题 Attempt 包含 actor、topic revision、path revision、题目/答案/评分快照和 client token。
- [ ] 新专题 revision 不继承旧 revision 的通过状态和次数限制。
- [ ] FAQ AI 评分失败时仍可在管理端追溯失败 Attempt。
- [ ] Readiness Dossier 只把 lineage 完整且属于当前 revision 的 Attempt 作为当前证据。
- [ ] 三个子计划的测试均进入 `scripts/critical-quality-gate.sh`。

## 发布与回滚顺序

1. 先发布兼容性数据库 migration。
2. 再发布后端读写逻辑和权限；此时前端旧请求必须得到明确契约错误，不能静默降级。
3. 同一发布窗口部署前端新的幂等/版本字段和锁定交互。
4. 观察 review-action 冲突率、Attempt 失败率、Journey 锁定诊断至少一个受控试点周期。
5. 回滚时先回滚应用并保留 additive 新表；只有尚未产生新业务数据的环境才执行 migration downgrade。旧 OperationLog 和旧商务礼仪 Attempt 表在整个灰度期保留，避免历史丢失。
