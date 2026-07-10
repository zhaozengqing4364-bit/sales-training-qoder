# Gate 0C Implementation Notes

## Baseline / Red

- 全量 209 files / 1332 tests：17 failed、1309 passed、6 skipped；
- Vitest 366.45 秒，wall 6:07.86，RSS 404036 KB；进程自然返回 exit 1；
- 1 项 Dashboard offset-time fixture 漂移；
- 16 项 Business Skills 先被缺 `learning_topics` 的共享 Journey fixture fail closed；
- 深挖后确认其中 11 项还缺公开 API mock 迁移，5 项断言本身仍是旧 module/active-path 语义。

## Implementation

- Dashboard：三个日期改为 runner-local 数字构造器；describe `afterEach` 恢复 real timers。
- Business Skills：Journey helper 类型化为 `TrainingJourneyResponse`，modules 为空，补齐
  non-blocking business-etiquette learning topic、retraining requests 和 AI coach availability。
- API mock/断言迁到 topic-specific article facade 与两参数 chapter completion。
- 5 个旧语义用例改为专题文章权威、无 unitId 安全路由、忽略 stale catalog、topic coach
  可用/不可用；新增专题未发布 fail-closed 用例。
- 生产代码、runner 配置、skip/exclude、依赖均未改变。

## Deviations

- 初始假设“只补共享 `learning_topics` 即可”不完整。按 research 继续追生产调用链后，发现
  测试还 mock legacy `getModuleArticle`/`completeModuleArticleChapter`，并有 5 个旧治理语义；
  采用当前公开 facade 和 Learning Topic authority 修复，已写入设计审计。
- 原先 5 分钟未结束被怀疑为 open handle。完整 420 秒诊断证明 6:07.86 自然结束，故不虚构
  生命周期生产修复，也不改 `fileParallelism`。
- 第一次最终命令误用 Vitest 4 不支持的 `--reporter=basic`，在启动阶段 exit 1；立即改为
  `--reporter=default --reporter=hanging-process`，最终权威运行成功。该 CLI 失误不涉及代码。

## Green / Verification

- 聚焦 3 files / 50 tests：pass；
- `npx tsc --noEmit --pretty false`：exit 0；
- 两个改动文件 ESLint：exit 0；
- 全量 209 files：1327 passed / 6 skipped / 1333 total；
- 最终全量 Vitest 352.93 秒，wall 5:54.32，RSS 437452 KB；自然 exit 0，无
  hanging-process report。
- 独立 check 发现 streak 的固定 UTC session timestamp 在 America/Los_Angeles 会跨本地日历；
  改为与 fake now 同源的 local Date→ISO 后，UTC、Asia/Shanghai、America/Los_Angeles
  三个时区均为 24/24 passed。

## Residual Observations

- 全量日志仍有既有 React `act(...)`、DOM mock prop 和刻意错误分支 stderr；它们不来自本
  Gate，也未造成失败或退出泄漏。作为独立测试债务治理，避免扩大 Gate 0C。
- 6 个 skip 均为既有 admin test-bank 条件用例，本 Gate 未新增。
- 用户并行 Readiness 文档始终未修改、未暂存。

## Commits

- `a1d852f1` `test(frontend): align governed learning topic fixtures`
- `dd5cf226` `docs: close modular monolith Gate 0C`
- `37b397f3` `chore(task): archive 07-10-modular-monolith-2-gate-0c`
