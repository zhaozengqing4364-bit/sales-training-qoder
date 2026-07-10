# Gate 0C 设计产物七维审计

## 总体结论

按设计产物审计指南逐项追到当前源码、公开 API、DTO、测试与 CI 后，Gate 0C 的方向成立：
这是一次测试合同迁移和确定性 cleanup，不需要修改生产 UI 或恢复旧 active-path 语义。

初审发现 3 个必须修正的设计盲区，均已回写 PRD/实施上下文：

1. 不是只补 `learning_topics`；测试还 mock 了废弃的 module article API；
2. 16 个 business-skills 用例中有 5 个断言仍以旧 module/active-path/next-action 为权威；
3. 5 分钟未完成不等于挂住；真实串行基线在 6:07.86 自然退出。

修正后无待解决的设计级硬错误。

## 七维核实

### 1. 参照对象真实性

- 生产 hook 真实调用 `api.salesTrainer.getJourney()`、
  `api.newcomerTraining.getBusinessEtiquetteArticle()`、
  `getBusinessEtiquetteLearningUnits()` 和
  `completeBusinessEtiquetteArticleChapter(chapterId, options)`。
- 测试当前拦截的 `getModuleArticle`/`completeModuleArticleChapter` 是仍存在但不再由该页面使用的
  legacy facade；因此不能把它们当现行参照。
- 首页生产问候真实使用浏览器/runner 本地 `new Date().getHours()`，没有“中国时区”产品合同。

### 2. 依赖方向

- 改动限于两个 co-located page test 和 Trellis/docs；页面继续只 import `@/lib/api/client`。
- 不新增 frontend domain import、backend package edge 或跨包例外。

### 3. 类型字段完整性

- `TrainingJourneyResponse` 必填 `learning_topics`、`retraining_requests`；共享 fixture 将补齐。
- `TrainingJourneyLearningTopicProgress` 的 `required`/`blocks_next` 必须为 literal `false`，
  `score_display_policy` 为 `quiz_attempt_score`，并包含 `units`、`ai_coach`、`source`。
- `SalesTrainerAiCoachAvailability` 必填 enabled/configured/available/coach_path/
  disabled_reason/allowed_interaction_types；测试将让 coachPath 直接决定该专题投影，而不再写
  `journey.modules[].next_action`。

### 4. 事务与 IO 边界

- 本 Gate 无数据库写、外部网络或生产事务变更。
- 页面测试 mock 公开 facade；不会调用真实 Provider 或真实后端。

### 5. 调用方语义一致性

- 学习专题是非 required/non-blocking 投影；缺专题时页面按现有合同 fail closed。
- 文章 endpoint 是专题专属真相源，不再从 Journey module 的 learning content 绑定回退。
- 无 URL `unitId` 仍可阅读/小测；考试链接以不带 unitId 的安全路由降级，不应恢复 catalog 推导。
- AI 教练入口只来自 `learning_topics[].ai_coach`，不可继续用 module `next_action`。

### 6. 测试即时影响

- 公共 API mock 改名后必须同步两参数 complete 断言，并删除对 article legacy 参数的断言。
- 需保留/新增明确的专题缺失 fail-closed 用例，防止共享 happy-path fixture 掩盖治理门禁。
- Dashboard 增加 `afterEach` 需要同步 import；runner-local date constructor 避免 UTC 偶然性。
- CodeGraph affected 只返回两个目标测试文件；聚焦回归先跑它们，再跑全量 209 文件。

### 7. 产物内部一致性

- PRD、两份 research 与 context 都以 17 个失败和 6:07.86 自然退出为同一基线。
- Gate 0C 只建立全量绿色事实；把完整自动发现接入 `critical-quality-gate.sh` 是 Gate 1B，
  不在本 Gate 偷跑或新建第二套 runner。
- 不修改 `fileParallelism`：小样本并行探针不是全量稳定性证明。

## 修复稳定性确认

- 不回退 learning-topic fail-closed；
- 不恢复 module article/active path/catalog 兼容路径；
- 不删除断言，不新增 skip/only/exclude；
- 不用扩大 timeout 代替根因修复；
- 用户并行 Readiness 文档保持排除。

## 实施清单

1. 修 Dashboard 本地小时 fixture 和对称 timer cleanup；
2. 把 business-skills API mock 切到专题专属 facade；
3. 用完整 Journey learning topic fixture 恢复 11 个现行语义用例；
4. 把 5 个旧语义用例改成专题专属文章、无 unitId 降级、topic AI coach 的现行合同；
5. 保留专题/Journey/文章/训练包缺失的 fail-closed 分支；
6. 聚焦 Green 后执行类型、lint、全量 Vitest 自然退出和架构门禁。
