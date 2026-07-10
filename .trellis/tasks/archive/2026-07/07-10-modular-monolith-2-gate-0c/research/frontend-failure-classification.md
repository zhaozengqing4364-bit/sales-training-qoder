# Gate 0C 前端失败分类

## 结论

本轮聚焦的 17 个失败中，没有发现需要修改生产代码的缺陷：

- 1 个首页问候语失败属于测试时区漂移；
- 11 个商务礼仪页面失败属于共享 Journey/API mock 落后于现行公开合同；
- 5 个商务礼仪页面失败除共享 mock 问题外，断言本身仍在验证已经废弃的旧路径语义。

商务礼仪的 16 个失败当前都在同一个前置门禁处短路：测试的 `journeyResponse()` 没有 `learning_topics`，而生产 hook 会在专题缺失时按设计 fail closed。因此当前 DOM 统一显示“商务礼仪规范学习专题尚未发布”，并不能证明 16 个下游分支各自存在生产缺陷。

## 复现证据

在 `web/` 下执行：

```bash
npx vitest run \
  'src/app/(dashboard)/page.test.tsx' \
  'src/app/(dashboard)/sales-trainer/business-skills/page.test.tsx' \
  'src/app/(dashboard)/sales-trainer/business-skills/exam/page.test.tsx' \
  --reporter=verbose
```

结果稳定为：

- Test Files：2 failed，1 passed；
- Tests：17 failed，32 passed，共 49；
- `business-skills/exam/page.test.tsx`：7/7 通过；
- `business-skills/page.test.tsx`：16 失败、2 通过；
- `dashboard/page.test.tsx`：仅晚间问候用例失败；
- 进程约 22 秒自然退出，聚焦命令本身没有挂住。

另执行：

```bash
npx vitest run \
  'src/app/(dashboard)/sales-trainer/business-skills/page.test.tsx' \
  -t 'does not duplicate section labels|fails closed when active path loading fails' \
  --reporter=verbose
```

结果 2/2 通过，证明纯函数用例正常，且 Journey 加载失败时的 fail-closed 页面也是当前受保护行为。

## 失败分类

| 分类 | 数量 | 用例 |
| --- | ---: | --- |
| 时区/环境漂移 | 1 | `falls back to the email prefix and switches to an evening greeting when no name is present` |
| 共享 fixture/API mock 漂移 | 11 | 配置单元渲染、陈旧文章进度隔离、加载/提交小测、独立小测工作区、AI 评分依据、历史作答、待评分状态、提交失败保留答案、训练包发布阻塞、文章绑定缺失、学习单元配置缺失 |
| 共享 fixture 漂移 + 旧语义断言 | 5 | 模块文章绑定回退、从 active path 解析 unitId、不从 catalog 推导 unitId、从 Journey module next action 读取 AI 教练、忽略 catalog AI 教练入口 |

### 1. 首页问候语：测试时区漂移，不是生产缺陷

生产函数 `web/src/app/(dashboard)/page.tsx:88` 使用 `new Date().getHours()`，即浏览器/运行进程的本地小时。失败用例在 `web/src/app/(dashboard)/page.test.tsx:371` 冻结为：

```ts
new Date("2026-04-09T20:00:00+08:00")
```

当前测试环境是 UTC。这个绝对时间在 UTC 中是 12:00，所以 `getHours()` 返回 12，生产页面按现有合同正确渲染“午安”，而测试错误期待“晚安”。早安用例偶然通过，是因为 `09:00+08:00` 转换后为 UTC 01:00，仍落在早晨区间。

建议仅修改测试：

- 用 runner 本地日期构造器冻结小时，例如 `new Date(2026, 3, 9, 20, 0, 0)`；
- 增加 `afterEach(() => vi.useRealTimers())`，显式恢复计时器；
- 不要为了让 CI 通过而把生产问候强制改成中国时区；现有文档没有这项产品合同。

### 2. 商务礼仪：共享 Journey fixture 缺少现行学习专题合同

生产调用链位于 `use-business-skills-workbench.ts:99-153`：

1. 调用 `api.salesTrainer.getJourney()`；
2. 从 `journeyResponse.learning_topics` 查找 `business_etiquette` 或来源模块 `business_skills`；
3. 专题不存在时抛出“商务礼仪规范学习专题尚未发布”，保持 fail closed；
4. 专题存在后并行调用专题专属文章、学习单元 API，并从 `learningTopic.ai_coach` 解析 AI 教练入口。

测试的共享 `journeyResponse()`（`page.test.tsx:177-259`）仍只构造旧的 `modules: [{ module_key: "business_skills", ... }]`，完全没有 `learning_topics`。因此 16 个需要进入页面主流程的用例都在第 3 步短路。此处应修 fixture，不能删除或放宽生产门禁。

建议让共享 Journey mock 至少包含一个已发布专题，字段与当前 `TrainingJourneyLearningTopicProgress` 一致：

- `topic_key: "business_etiquette"`；
- `source_module_key: "business_skills"`；
- `required: false`、`blocks_next: false`；
- `status`、`learning_content_id`、`units`、`source`；
- `ai_coach` 使用当前 availability 合同；
- 补齐 `retraining_requests` 等当前 Journey 响应字段。

同时保留一个明确的“专题不存在”用例，继续证明 fail closed。

### 3. 商务礼仪：公开 API mock 名称和参数形状已经过期

测试在 `page.test.tsx:62-70` 仍拦截：

- `getModuleArticle`；
- `completeModuleArticleChapter`。

生产 hook 当前调用：

- `getBusinessEtiquetteArticle()`（`use-business-skills-workbench.ts:111`）；
- `completeBusinessEtiquetteArticleChapter(chapterId, { learning_content_id })`（`use-business-skills-workbench.ts:236`）。

公开 API 实现在 `web/src/lib/api/domains/newcomer-training.ts:141`。即使只补上 `learning_topics`，测试仍会落到未拦截的真实 API facade，并且完成章节的 mock/断言仍是旧三参数形式：当前测试在 `page.test.tsx:384` 把第二个参数当作 `chapterId`，在 `page.test.tsx:450-454` 期待 `(moduleKey, chapterId, options)`；现行合同是 `(chapterId, options)`。

建议测试只 mock 当前公开 facade：

- `getBusinessEtiquetteArticle: getArticleMock`；
- `completeBusinessEtiquetteArticleChapter: completeChapterMock`；
- 把 mock implementation 和调用断言改为两参数合同；
- 文章读取不再断言旧模块参数。

### 4. 五个用例还需要按新治理语义重写

提交 `5e1428ea` 已把商务礼仪从 Journey 必修模块/active path 推导迁移到独立学习专题治理。下列用例不是简单补 fixture 就能得到有意义覆盖：

1. `falls back to module article binding when selected unit has no article binding`
   - 旧语义：从模块/单元配置回退文章绑定。
   - 当前语义：专题专属文章 endpoint 是文章真相源，不再接收模块绑定参数。

2. `resolves missing unitId from the active path projection instead of catalog config`
   - 旧语义：从 `journey.modules` 解析 active unit。
   - 当前语义：页面可独立加载专题文章和训练包；`unitId` 不再是加载前置条件。

3. `does not infer the business skills unit from stale unit path config when unitId is missing`
   - 旧断言期待页面不可用。
   - 当前 hook 刻意不调用 `listUnits`，无 `unitId` 仍可进入专题学习；应改测当前路由/考试链接的降级行为，而不是恢复旧门禁。

4. `shows the AI coach entry from the Journey next action`
   - 入口来源已从 `journey.modules[].next_action` 迁移为 `learning_topics[].ai_coach`。

5. `does not render an AI coach entry from path catalog availability without a Journey action`
   - 不应再比较 path catalog 与 module action；应改为比较专题 `ai_coach.available/coach_path/disabled_reason` 的可用与不可用状态。

## 建议实施顺序与回归边界

1. 先修首页 fake time 与计时器清理；
2. 更新商务礼仪共享 Journey fixture 和两项公开 API mock；
3. 让 11 个仍符合现行产品语义的用例恢复执行，并逐个处理真实下游断言；
4. 重写上述 5 个旧语义用例，验证学习专题治理合同；
5. 保留专题缺失、Journey 加载失败、文章/训练包缺失等 fail-closed 用例；
6. 依次运行三个聚焦文件，再运行 Gate 0C 指定的全量 Vitest 自然退出检查。

禁止采用的“修复”：

- 删除 `if (!learningTopic)` 门禁；
- 在生产代码中恢复 `listUnits`、旧 module 绑定回退或旧 API 别名；
- `skip/only` 失败用例；
- 用更宽泛的文本断言掩盖页面落入不可用态；
- 把首页生产时区硬编码为 `+08:00` 来迎合当前 fixture。

## 风险判断

风险等级：P2（测试合同迁移）。建议改动范围限于测试 fixture、mock 和断言。生产 fail-closed、专题真相源和公开 API 合同目前彼此一致，不应因本批失败而回退。
