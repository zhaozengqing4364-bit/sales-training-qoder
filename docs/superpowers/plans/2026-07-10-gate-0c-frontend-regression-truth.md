# Gate 0C Frontend Regression Truth Implementation Plan

日期：2026-07-10

状态：**Completed（2026-07-10）**

范围：全量 Vitest 失败真相、Dashboard 本地时间确定性、Business Etiquette Learning Topic
测试合同、Vitest 自然退出。

## 1. 目标与基线

从 `web/` 执行带完整 reporter 和 420 秒诊断保护的全量 `npx vitest run`，得到：

```text
209 files: 2 failed, 207 passed
1332 tests: 17 failed, 1309 passed, 6 skipped
Vitest duration: 366.45s
wall clock: 6:07.86
maximum RSS: 404036 KB
```

进程在 watchdog 前自行返回 exit 1，且 `hanging-process` 没有报告遗留句柄。因此原先
“超过 5 分钟未收敛”不是 open-handle 故障，而是把短于真实串行执行时间的观察窗口当成
runner timeout。本 Gate 要恢复断言真相并证明 exit 0，不通过扩大 timeout、skip 或排除制造绿色。

## 2. 失败分类

| 分类 | 数量 | 根因与处理 |
|---|---:|---|
| 时区 fixture 漂移 | 1 | offset-bearing instant 在 UTC runner 中变成 12:00；改用 runner-local 日期构造器 |
| Journey/API fixture 漂移 | 11 | 共享 Journey 缺 `learning_topics`，并 mock 了页面已不调用的 legacy article API |
| Fixture 漂移 + 旧治理语义 | 5 | 仍以 required module、active path、catalog unit 和 module next action 为权威；迁到 Learning Topic |

17 个失败中未发现生产缺陷。Business-skills 16 个用例统一在缺失专题门禁处 fail closed，
生产代码按当前治理合同工作正常。

## 3. 实施切片

### 3.1 Dashboard 本地时间确定性

- [x] morning/evening/streak 测试用 `new Date(year, month, day, hour, ...)` 表达 runner-local
  浏览器时间；
- [x] streak 的 session/report timestamps 也由同一本地日历构造后序列化为 ISO，避免 UTC
  临近午夜在美洲时区落到前一天；
- [x] 在 describe 级 `afterEach` 无条件恢复 real timers；
- [x] 不把生产问候逻辑硬编码为中国时区。

### 3.2 Business Etiquette 公开合同

- [x] Journey helper 显式返回 `TrainingJourneyResponse`；
- [x] required `modules` 不再伪造 `business_skills`，改为 non-blocking
  `learning_topics[].business_etiquette`；
- [x] 补齐 `retraining_requests`、AI coach availability、source 和所有 literal 治理字段；
- [x] mock 切换为 `getBusinessEtiquetteArticle` 和
  `completeBusinessEtiquetteArticleChapter(chapterId, options)`；
- [x] 删除对 legacy module article 参数的断言。

### 3.3 旧语义迁移和 fail-closed

- [x] 文章真相来自专题专属 endpoint，不从 module binding 回退；
- [x] URL 无 `unitId` 时仍可加载专题，并使用不带 query 的安全考试路由；
- [x] stale catalog unit 不参与专题解析；
- [x] AI coach 链接/禁用原因只由 topic `ai_coach` 决定；
- [x] 新增“学习专题未发布”明确回归，证明文章/学习单元 API 不被调用；
- [x] 保留 Journey 加载失败、文章缺失、训练包未发布和学习单元配置缺失分支。

## 4. Runner 与 CI 决策

`fileParallelism: false` 的历史提交没有记录可证明的取消条件。9 文件小样本显示 4 worker
可把 8.75 秒降为 3.02 秒，但不能证明 209 文件共享 mock/fake timer/jsdom 在并行下稳定。
本 Gate 保持串行配置，不把性能实验混进合同修复。

最终全量默认 runner 在 release-truth workflow 45 分钟 job timeout 内有约 7.8 倍余量。
完整自动发现接入唯一 `critical-quality-gate.sh` 属于 Gate 1B；Gate 0C 不创建第二套 runner。

## 5. 验证证据

```text
focused affected pages: 3 files, 50 passed
TypeScript strict check: pass
target ESLint: pass
timezone matrix (UTC / Asia-Shanghai / America-Los_Angeles): 24/24 each
full Vitest: 209 files passed; 1327 passed, 6 skipped (1333 total)
Vitest duration: 352.93s
wall clock: 5:54.32
maximum RSS: 437452 KB
natural exit: 0; no hanging-process report
```

最终测试总数比基线多 1，是新增“专题未发布”fail-closed 回归。6 个 skip 都是既有
`admin/test-bank` 条件测试；本 Gate 未新增 skip、only、exclude、弱断言或吞异常。

全量日志仍包含历史测试的 React `act(...)` / mock prop 警告和刻意错误分支日志；它们没有
造成失败或退出泄漏，也不来自本 Gate 改动。后续测试债务应独立治理，避免扩大本切片。

## 6. 规范、复核与证据

- `.trellis/spec/frontend/quality-guidelines.md` 增加七段式
  “Governance Projection Fixtures And Local Time” 合同；
- Trellis task 保存 17 项失败分类、runner/exit 诊断和七维设计审计；
- 独立 trellis-check 复核公开 API、DTO、timer cleanup、无测试隔离和用户并行文档保护；
- CodeGraph pre-impact/affected 选择两个改动测试文件，post-impact 复核不得扩大调用面。

## 7. 兼容性、风险与回滚

- 风险等级：P1（全量测试事实前置 Gate），实际生产改动为零；
- REST、WebSocket、权限、页面行为、Journey/AI coach 生产合同和 runner 配置均未改变；
- 无 migration、生产数据、真实 Provider、依赖或部署变更；
- 回滚只需撤销两个测试文件和对应规范/文档，不会影响运行时；
- 测试切片提交：`a1d852f1`；
- 用户并行修改的 Readiness 文档始终未暂存、未改写。

## 8. Trellis 证据

- 实施任务：`.trellis/tasks/07-10-modular-monolith-2-gate-0c`
- 完成后归档：`.trellis/tasks/archive/2026-07/07-10-modular-monolith-2-gate-0c`
- 任务内包含 PRD、逐项失败分类、Vitest 运行时诊断、设计审计、implement/check context
  和 implementation notes。
