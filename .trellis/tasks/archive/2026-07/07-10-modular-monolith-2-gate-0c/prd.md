# 模块化单体 2.0 Gate 0C：前端回归真相

## Goal

逐文件复现、分类并修复当前全量 Vitest 的失败与不能在 CI timeout 内自然退出的问题，
建立可重复、可观测、无永久隔离的前端测试事实，为 Gate 1B 自动发现与变更覆盖提供可信基线。

## What I already know

- Dashboard greeting 已冻结绝对时间，但 `+08:00` instant 在 UTC runner 中被 `getHours()`
  解释为中午；这是测试时区漂移，不是生产问候逻辑缺陷。
- Business-skills 的 16 个失败都先落入“学习专题未发布”：共享 Journey mock 缺少
  `learning_topics`，且公开文章 API mock/断言仍使用已废弃的 module 绑定签名。其中 5 个用例
  还在验证已由 learning-topic governance 取代的旧 active-path/module-action 语义。
- 2026-07-10 可观测全量基线自然退出：209 个文件中 2 失败/207 通过，1332 个测试中
  17 失败/1309 通过/6 跳过；Vitest 366.45 秒，shell wall-clock 6:07.86，最大 RSS
  404036 KB。退出码 1 仅由断言失败引起，没有超过 420 秒外部诊断上限。
- `web/vitest.config.ts` 当前使用 jsdom、`fileParallelism: false`、10 秒 test timeout，未配置
  全量 run timeout、per-file reporter 或 open-handle 诊断。
- 权威命令是从 `web/` 执行 `npm test` / `npx vitest run`；Playwright E2E 不属于本 Gate。
- Gate 0B 已完成，后端 unit + contract `2617 passed`；Gate 1B 只剩 Gate 0C 前置阻塞。
- Readiness 文档属于并行任务，必须保持未触碰、未暂存。

## Assumptions

- 保持生产 UI、API 合同、权限和用户路径不变；优先修确定性测试时钟、共享 mock 与资源清理。
- “自然退出”指 Vitest 进程无需外部 kill，在明确的 CI wall-clock timeout 内返回 exit 0。
- 不通过降低断言、删除测试、永久 skip/only、关闭资源检测或扩大 timeout 掩盖泄漏。
- 若失败揭示真实生产缺陷，则先按 public behavior 增加/保留复现，再修生产根因。

## Requirements

1. 保留可限时且记录退出码、Vitest/墙钟耗时、内存和文件级进度的全量基线证据。
2. 每个失败按生产缺陷、fixture 漂移、时间/随机性、共享状态、异步未收敛或环境依赖分类，
   证据写入 `research/`。
3. Dashboard 时间测试必须用 runner-local 日期构造器表达本地小时，并在每个测试后恢复
   Vitest fake timers。
4. Business-skills 测试必须模拟当前 learning-topic governance Journey DTO 和专题专属公开 API
   facade；AI 教练入口只由 topic `ai_coach` 决定，禁止为旧 fixture 放松生产 fail-closed 行为。
5. 对不能退出的问题使用 per-file 二分、handle/timer/network 诊断定位资源所有者，并在测试或
   生产生命周期边界显式 cleanup。
6. 全量 Vitest 必须自然 exit 0，命令由单一 runner 执行并有 CI timeout；不得新增永久隔离。
7. TypeScript、ESLint、相关前端合同测试和 architecture guard 必须通过。

## Acceptance Criteria

- [x] 基线包含总文件数、总测试数、失败清单、耗时、内存和退出行为。
- [x] Dashboard greeting 测试不依赖执行机器的当前时间。
- [x] Business-skills 失败逐项分类，shared governance mock 与当前合同一致。
- [x] 没有新增 `skip`、`only`、永久 exclude、弱断言或吞异常。
- [x] 所有新增 timer/listener/server/observer 在测试后可证明清理。
- [x] 全量 `npx vitest run` 绿色并在规定 timeout 内自然退出。
- [x] `npx tsc --noEmit`、ESLint、architecture guard 与 `git diff --check` 通过。
- [x] Trellis check、update-spec、CodeGraph post-impact、逻辑提交和归档完成。

## Definition of Done

- 全量前端测试结果与路线图、详细计划、Trellis evidence 一致。
- 真实 UI 行为和 API 契约保持兼容；测试 fixture 只表达当前可生产状态。
- 慢测试和生命周期问题有 owner/root cause，不依赖外部 kill 或偶然 GC。
- Gate 1B 前置从“0B/0C”收敛为已满足，可安全加入全量自动发现。
- Git 工作区只剩明确属于其他任务的 Readiness 文档。

## Technical Approach

- 先用 shell wall-clock timeout 包住 `npx vitest run`，保存完整日志和真实 exit code；再用
  Vitest file listing / per-file execution定位失败与尾部停顿。
- 时间类测试采用 `vi.useFakeTimers()` + runner-local `vi.setSystemTime()` + `afterEach` 恢复。
- Governance fixture 使用完整 `TrainingJourneyResponse`/`TrainingJourneyLearningTopicProgress`
  字段，并只 mock `getBusinessEtiquetteArticle`、`completeBusinessEtiquetteArticleChapter` 等公开 facade。
- Open-handle 诊断优先检查 fake timers、未关闭的 query retry、MutationObserver、event listener、
  media/WebSocket mock 和动态 import；修复资源所有者，不只增加 timeout。

## Decision (ADR-lite)

**Context**：现有信号混合断言失败与进程不退出；直接逐条改 UI 断言会掩盖共享 fixture 或
生命周期根因，单纯扩大 timeout 也无法建立测试真相。

**Decision**：采用“可观测全量基线 → 失败簇分类 → 聚焦 Red/Green → 资源所有者 cleanup →
全量自然退出”的顺序。生产合同为权威，测试 fixture 随合同迁移。

**Consequences**：可能需要修改共享 test setup、页面测试 fixture 或少量真实生命周期代码；
换取 Gate 1B 可依赖的确定性前端反馈环。

## Out of Scope

- 不做 UI 重设计、不修改业务文案或权限语义。
- 不运行真实后端/Provider，不把 Playwright E2E 混入 Vitest。
- 不实施 Gate 1B changed coverage 或 Gate 2 Realtime Engine。
- 不修与当前失败/退出根因无关的历史 lint 美化。

## Technical Notes

- 路线图：`docs/superpowers/plans/2026-07-10-modular-monolith-2-roadmap.md`
- Runner：`web/package.json`、`web/vitest.config.ts`
- 相关 spec：`.trellis/spec/frontend/quality-guidelines.md`
- 风险等级：P1；无 migration、无生产数据、可按失败簇独立回滚。

## Verification Snapshot

- 聚焦 affected pages：3 files / 50 tests passed；
- TypeScript strict check 与改动文件 ESLint：通过；
- Dashboard 在 UTC、Asia/Shanghai、America/Los_Angeles 三时区各 24/24 通过；
- 全量 Vitest：209 files passed，1327 passed / 6 skipped，352.93 秒；
- wall clock 5:54.32，RSS 437452 KB，自然 exit 0，无 hanging-process report；
- 最终架构、全量 lint、独立 check、提交和归档在收尾阶段记录。
