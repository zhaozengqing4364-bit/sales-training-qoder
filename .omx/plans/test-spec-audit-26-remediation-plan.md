# 测试规格：26 项代码审计问题整改与增长迭代

## 测试原则
1. 高风险重构先补行为测试，再拆分职责。
2. 用户可见状态必须区分 loading、success、empty、failed、partial failed。
3. 核心训练链路必须覆盖开始、录音、留痕、结束、报告、回放。
4. 安全鉴权必须有正反例：允许路径与拒绝路径都要测。
5. 增长功能必须验证不会在证据不足时制造虚假激励。
6. 测试按阶段启用，首批只要求与 Phase 0-2 窄切片相关的必跑集合，后续 backlog 测试在对应阶段启用。


## 按阶段必跑测试矩阵

### Phase 0 必跑
1. git status 和未提交改动记录。
2. web targeted vitest、web tsc、web eslint 的当前状态记录。
3. backend targeted pytest collection、backend src ruff、backend tests ruff 的当前状态记录。
4. 允许失败与不允许失败 baseline 记录。

### Phase 1 必跑
1. dashboard recommendation、audio segment API、main presentation WS runtime targeted pytest 至少可收集，不因 rank_bm25/jwt 缺失失败。
2. RoleChecker grep/单测证明不存在 always-allow 权限 helper。
3. admin TTS preview 统一 API client 单测或组件测试，覆盖 base URL、CSRF、错误 envelope。
4. common.api.response touched endpoint contract test；旧 envelope 兼容测试保持通过。
5. 问题 7 只验收边界图、contract snapshot、regression list，不要求实际拆分测试。

### Phase 2 必跑
1. 首页模块失败态测试：失败模块不显示 0 数据伪空态。
2. 练习页多故障并列展示测试：连接、麦克风、音频留痕、会话状态均可见。
3. continuous audio uploader bounded flush：成功、失败、超时三种状态。
4. 训练入口 empty、failure、partial failure 文案与按钮区分，主返回按钮指向明确路由。

### Phase 3 必跑
1. recommendation/focus_intent contract tests：sales_retry、presentation_page_retry、无记录、缺参数 fallback。
2. history issue aggregation 排除 explanation_only，保留 retry_eligible。
3. report next-action card 跳转参数完整。
4. sales core combination personalized ordering。

### Phase 4-5 对应阶段启用
PPT 逐页补练、learner intervention、leaderboard improvement、连续天数、能力地图、移动端快捷区、上下文帮助卡只在对应阶段进入实现时成为必跑项。

## 单元测试
1. 后端依赖与导入基线：dashboard recommendation、audio segment API、main presentation WS runtime 可被 pytest 收集。
2. RoleChecker 删除或替换后，新增 grep/单测证明不存在 always-allow 权限 helper。
3. dashboard recommendation：sales_retry、presentation_page_retry、无可评估记录三种分支。
4. history issue aggregation：main_issue.issue_type 聚合、证据不足记录排除、无记录兜底。
5. leaderboard improvement mode：两次可评估训练差值、样本不足处理、证据不足排除。
6. focus_intent 个性化排序：命中核心组合置顶、无推荐保留默认排序。
7. continuous audio uploader：stopUpload/flushAndStop 等待 pending uploads、返回失败状态或在明确超时后降级。
8. API client：TTS preview 使用统一 base、CSRF、错误 envelope。

## 前端组件/页面测试
1. 首页：stats 失败但 recommendation/history 成功时，只 stats 模块显示失败；不显示 0 数据伪空态。
2. 首页：recommendation 返回 sales_retry 时渲染今日复练任务卡；presentation_page_retry 时渲染页级补练任务。
3. 练习页：同时存在 wsError、audioError、lifecycleError、audioUploadError 时四类状态均可见。
4. 练习页：终止会话时显示“正在保存音频证据/生成报告”阶段；成功、失败、超时均有可见状态，不提前隐藏失败原因。
5. 训练入口：empty 与 failure 文案不同，failure 有重试按钮，返回按钮指向明确路由。
6. 报告页：下一轮训练卡展示上次卡点、修正动作、判定条件、按目标再练。
7. 历史页：按问题复练卡展示出现次数、最近报告、再练入口。
8. 排行榜/图表：空态说明触发条件和下一步训练入口。
9. loading/error：全局和 admin error/loading 文案为中文。
10. 移动端快捷区：首页、训练页、练习页关键入口可见。

## 集成测试
1. cookie session unsafe request 缺少 CSRF header 仍返回 403，Bearer unsafe request 不被误拦截。
2. 管理端 TTS preview 通过统一 client 调用，后端失败时前端展示 ApiRequestError 中文文案。
3. createSession 携带 focus_intent 后，练习页 preflight 和报告 retry_entry 可串联。
4. report -> replay anchor -> retry training 的跳转参数完整保留。
5. learner open intervention 接口只返回当前用户未解决 intervention，不泄漏他人数据。
6. PPT page retry 从报告页到 replay page，再到后续 presentation_focus_page 创建会话分阶段验证。

## E2E/关键路径测试
1. 新用户：进入首页 -> 训练大厅 -> 销售训练 -> 选择角色 -> 开始练习 -> 结束 -> 报告 -> 按目标再练。
2. 老用户：首页今日复练任务 -> 带 focus_intent 进入训练 -> 报告显示目标延续。
3. 失败恢复：模拟 dashboard stats 失败，用户仍可从 recommendation 进入训练；模拟练习页音频留痕失败，实时训练可继续且报告解释证据缺失。
4. PPT 用户：报告页定位问题页 -> 回放页页级定位 -> 逐页补练入口。

## 静态检查与质量门禁
1. web targeted vitest、web tsc、web eslint。
2. backend src ruff 优先通过；tests ruff 分阶段清理。
3. backend targeted pytest 收集不失败。
4. 大文件拆分阶段每个切片必须保留 targeted unit/integration tests。
5. 禁止直接 fetch 新增规则：对 web/src/app 与 web/src/components 中新增 fetch 进行 grep 检查，允许名单仅限上传到第三方预签名 URL 等特殊路径。

## 观测与验收证据
1. 每个阶段记录命令、结果、失败原因和剩余风险。
2. 用户可见失败态保留 trace_id 或可定位错误码。
3. 音频留痕失败需能在练习页或报告页说明影响范围。
4. 增长功能指标至少包括：今日复练任务点击、按问题复练点击、报告再练点击、训练启动完成率。


## 首批不要求通过的后续测试
1. 问题 11-26 的完整 UI/E2E 测试不属于首批阻断项。
2. StepFun handler 实际拆分后的回归测试不属于首批阻断项；首批只要求 contract snapshot 和 regression list。
3. 全量 API envelope 迁移测试不属于首批阻断项；首批只测 touched endpoint 和兼容层。
