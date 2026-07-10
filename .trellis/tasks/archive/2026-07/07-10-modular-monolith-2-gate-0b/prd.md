# 模块化单体 2.0 Gate 0B：后端回归真相

## Goal

逐簇诊断当前后端 unit + contract 的 15 个失败，依据已生效的领域、权限、配置和 API
合同判断生产缺陷还是测试夹具漂移，修复根因并恢复全量绿色，为 Gate 1B 自动测试发现
和后续 Realtime 架构迁移提供可信反馈环。

## What I already know

- 当前权威基线：`2613 collected, 2598 passed, 15 failed, 1 skipped, 74 warnings`
  （365.49 秒，使用 `tests/unit tests/contract -q --no-cov`）。
- Gate 0A/1A 已完成，OpenAPI parity 与 architecture dependency guard 已进入主门禁。
- 15 个失败分布：
  - audio/path/record lineage：6；
  - phase2 projection：1；
  - realtime roleplay enter permission：1；
  - legacy Sales Trainer services/path fixtures：5；
  - secret hygiene evidence：1；
  - PPT forbidden-word response serialization：1。
- 多个 audio/path 失败发生在发布校验阶段，fixture 没有满足现行 scenario/module contract；
  不能通过弱化生产发布校验来恢复旧测试。
- PPT ForbiddenWord 返回 500，堆栈为 Pydantic 无法序列化 ORM `ForbiddenWord`，属于真实
  生产 API 错误候选，必须以 API 合同和相邻实现确认。
- 只读诊断已完成最终分类：11 项 fixture 漂移、3 项断言语义漂移、1 项真实生产 bug。
  Sales Trainer 13 项没有生产 bug 证据；secret 是工作站 evidence 耦合；ForbiddenWord
  是 commit 后响应序列化 500。
- 当前工作区 Readiness 文档属于并行任务，不得修改、暂存或提交。

## Requirements

1. 每个失败先单独复现，使用 CodeGraph 调用链、领域 spec、相邻绿色测试和 Git 语义判断
   production bug 或 fixture/断言漂移；研究证据写入 `research/`。
2. Audio/path fixture 必须使用 canonical module key/type、受控 scenario config、已发布
   prompt/material/unit/path revision；不得放松生产 scenario、lineage 或 active-path 校验。
3. 权限断言必须遵循后端对象级权限和当前用户任务语义；不得仅为了旧断言隐藏管理员或
   训练经理已有合法读取能力。
4. Legacy Sales Trainer service tests 必须迁移到 canonical logical path/module/topic 合同，
   不在生产代码恢复只读 alias 或已退役模块语义。
5. Secret hygiene test 不得依赖未提交、一次性或工作站专属 evidence 文件；扫描器默认路径
   和跳过 report 的真实合同仍需被测试。
6. ForbiddenWord API 必须返回可序列化、稳定且权限正确的响应，禁止 ORM/内部字段直接
   泄漏或把 500 加入允许状态码。`admin` 与 `presentation_coach` 两个同形 POST 必须复用
   现有 `ForbiddenWordResponse`，在 commit 前完成 DTO 映射并保留各自权限语义。
7. 不使用 skip、xfail、删断言、`|| true`、吞异常或永久隔离清单制造绿色。
8. ForbiddenWord 响应 schema 变化必须通过 runtime generator 更新 OpenAPI，并通过 parity。
9. 聚焦集、相关领域回归、Ruff、architecture guard 和全量 backend unit+contract 必须通过。

## Acceptance Criteria

- [x] 15 个基线失败逐项有根因分类和代码证据。
- [x] Audio/path/record lineage 聚焦失败全部通过，生产发布校验未弱化。
- [x] Projection、permission 和 Sales Trainer service 聚焦失败全部通过。
- [x] Secret hygiene test 不再依赖缺失的工作站 evidence 文件。
- [x] ForbiddenWord API 不再返回 500，并有精确响应回归测试。
- [x] 两个 ForbiddenWord POST 返回同一稳定 DTO，OpenAPI parity 通过。
- [x] 修改文件 Ruff 通过，architecture guard 通过。
- [x] `tests/unit tests/contract -q --no-cov` 全量 0 failed。
- [x] 不新增 skip/xfail/永久排除，不修改外部无关行为。
- [x] Trellis check、update-spec、CodeGraph post-impact、逻辑提交和归档完成。

## Definition of Done

- 后端 unit + contract 全量绿色且自然退出；记录 collected/passed/skipped/warnings/duration。
- 每个真实生产 bug 有复现测试；fixture 漂移仅修改测试数据/断言并说明现行合同。
- API、权限、状态、path revision、scenario 和 lineage 兼容性有证据。
- 路线图 Gate 0B 状态、详细计划/研究、Trellis task 和提交事实一致。
- 不触碰 Gate 0C/1B 或 Readiness 并行工作。

## Technical Approach

- 并行只读诊断两组：Sales Trainer/lineage 与 secret/PPT；主代理汇总为逐簇小变更包。
- 优先修真实 500，再迁移 fixture；每簇 Red→Green 后运行相邻领域回归。
- 全量后端在所有聚焦簇绿色后重跑，若出现新失败则回到根因循环，不扩大排除范围。

## Decision (ADR-lite)

**Context**：现有失败混合了领域治理升级后的旧 fixture 和真实 API 序列化缺陷；批量改
断言会掩盖生产错误，直接改生产规则又会破坏已批准的发布/权限合同。

**Decision**：以当前领域 spec、对象权限、canonical path/module/scenario 和 API DTO 为
权威，逐失败分类。生产 bug 修生产并加回归；fixture 漂移只迁移 fixture。

**Consequences**：会修改多个历史测试文件，并可能产生一个小型生产 API 修复；换取后端
全量测试重新成为可进入 Gate 1B 的可信事实源。

## Out of Scope

- 不修前端 Vitest/Gate 0C。
- 不实施 Gate 1B 自动发现或 changed coverage。
- 不重构 Realtime Engine，不改变评分算法、path 业务规则或数据库 schema。
- 不调用真实外部 Provider，不操作生产数据。

## Technical Notes

- 路线图：`docs/superpowers/plans/2026-07-10-modular-monolith-2-roadmap.md`
- 相关 specs 将在根因研究后写入 implement/check context。
- 风险等级：P1；回滚按失败簇独立提交撤销，不涉及 migration。

## Research References

- `research/sales-trainer-failure-classification.md`
- `research/platform-api-failure-classification.md`
