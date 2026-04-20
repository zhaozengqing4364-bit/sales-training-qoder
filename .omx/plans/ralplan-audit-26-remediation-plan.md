# RALPLAN 共识计划：26 项代码审计问题整改与增长迭代

## 0. 元数据
计划类型：RALPLAN-DR deliberate mode
任务目标：为审计发现的 26 个问题制定全面可靠的解决计划
执行范围：web/src、backend/src、backend/tests、web tests、前后端 API 合约、训练核心链路、用户增长闭环
排除范围：Docker、容器化、部署、运维、基础设施
上下文快照：.omx/context/audit-26-remediation-plan-20260420T025004Z.md
PRD：.omx/plans/prd-audit-26-remediation-plan.md
测试规格：.omx/plans/test-spec-audit-26-remediation-plan.md
计划状态：revised consensus draft after Architect ITERATE，规划阶段不实现业务源码

## 1. RALPLAN-DR 摘要

### 1.1 原则
1. 质量门禁先于功能扩张：先恢复测试、lint、类型和依赖基线，避免在不可信基线上叠加功能。
2. 核心训练可信链路优先：实时连接、麦克风、音频留痕、报告、回放、复练入口必须先稳定。
3. 用户可见状态必须真实：失败不能伪装成空数据，占位不能伪装成已保存，证据不足不能伪装成低分。
4. 安全与权限必须集中且可测：鉴权 helper、CSRF、统一 API client、错误 envelope 不允许多套权威。
5. 增长功能必须绑定现有证据链：首页推荐、历史聚合、报告再练、排行榜激励都必须基于现有 session evidence、retry_entry、focus_intent。

### 1.2 决策驱动
1. 风险面：阻断测试、安全误用、实时训练证据链优先级最高。
2. 用户价值：能提升训练完成率、复练率、报告可信度的事项优先。
3. 实施依赖：先做底座和可验证切片，再做复杂重构和增长功能。

### 1.3 可选方案
方案 A：全量一次性并行修复，不推荐。
优点：所有问题推进快。
缺点：26 项跨越安全、实时、前端体验、增长和重构，冲突和回归风险极高，现有后端门禁还不稳定。

方案 B：按“质量安全 -> 核心体验 -> 复练增长 -> 架构拆分 -> 可选增强”分期推进，推荐。
优点：每期有明确验收，先解决阻断和高风险问题，再放大用户价值。
缺点：全部 26 项完成周期更长，需要阶段管理。

方案 C：先做用户可见增长功能，不推荐作为首选。
优点：首页复练、历史复练、报告行动卡能快速可见。
缺点：如果音频证据、错误状态、测试门禁仍不可信，增长功能会包装不稳定体验。

最终决策：采用方案 B，但拆成“双层计划”。第一层是 26 项总路线 roadmap；第二层是首批可执行窄切片。首批只执行 Phase 0、问题 1、2、3、4、5、6、9；问题 7 仅做重构边界与测试清单；问题 8 仅做统一 response helper 与 touched endpoint 样例；问题 10 仅冻结复练数据契约，不实现完整增长闭环。中优 11-20 与低优 21-26 作为后续 backlog，不进入首批执行。

## 2. ADR
Decision：采用分阶段、质量门禁优先、核心训练可信链路优先的整改计划，并将 26 项总路线与首批可执行窄切片分离。
Drivers：后端测试收集被依赖缺失阻断；RoleChecker always-allow 存在权限误用风险；首页/训练/练习页仍存在用户可见真实性问题；retry_entry/focus_intent 已具备增长闭环基础。
Alternatives considered：一次性全量并行、增长功能优先、大文件重构优先。
Why chosen：当前项目最需要先恢复可验证性和可信体验，再把现有证据链转化为复练增长能力。
Consequences：短期先做底座和核心体验，低优游戏化/移动端增强排后；大文件重构必须拆小步，且首批禁止实际拆分 StepFun handler、practice.py、report/replay 等高风险核心文件。
Follow-ups：每个阶段结束后更新验证证据和剩余风险；若进入执行，优先 team 执行首批并行安全/体验/测试切片，ralph 负责收口验证。

## 2.1 执行范围分层

### 2.1.1 26 项总路线范围
26 项全部保留为产品和工程 roadmap，用于解释依赖、阶段顺序、风险和后续 staffing。总路线不等于首批执行承诺。

### 2.1.2 首批可执行窄切片
首批只允许执行以下事项：
1. Phase 0：基线确认、未提交改动保护、可运行命令矩阵、文件所有权矩阵。
2. 问题 1：恢复后端 targeted pytest collection 所需依赖和最小 lint 基线。
3. 问题 2：删除或真实化 RoleChecker always-allow，并加防回归检查。
4. 问题 3：admin TTS preview 收敛到统一 API client。
5. 问题 4：首页失败不再伪装为空数据。
6. 问题 5：练习页结构化故障面板。
7. 问题 6：训练结束音频留痕 bounded flush 与降级解释。
8. 问题 9：训练入口 empty/failure/partial failure 状态区分和明确返回路径。
9. 问题 7：仅交付重构边界图、message/API contract snapshot、targeted regression list，不做实际拆分。
10. 问题 8：仅新增统一 response helper 与 touched endpoint 样例，旧接口保持兼容，不做全量 envelope 迁移。
11. 问题 10：仅冻结 recommendation/focus_intent 复练数据契约，完整今日复练任务卡进入下一批。

### 2.1.3 首批明确不执行
问题 11-26 不在首批实现；问题 10 不实现完整 UI 增长闭环；问题 7 不拆核心大文件；问题 8 不做全量 API 响应迁移。除非用户重新批准，不得把 roadmap backlog 混入首批代码改动。

## 3. 阶段路线

### Phase 0：执行前保护与基线确认
目标：不破坏当前未提交改动，确认可运行命令、依赖缺口、共享文件边界和首批执行范围。
任务：记录 git status；列出当前未提交改动；确认 web targeted vitest、web tsc、web eslint、backend targeted pytest、backend src ruff、backend tests ruff 的可运行状态；确认 backend pytest 当前因 rank_bm25、jwt 缺失阻断；确认 ruff 历史基线范围；建立首批 lane 文件所有权矩阵。
验收：形成执行上下文，所有后续 agent 明确不得回滚现有改动；每条 lane 有 owner、允许修改文件、禁止修改文件、必跑验证命令；列出允许失败与不允许失败的基线。

### Phase 1：质量、安全、API 一致性，高优 1-3，7-8 的低风险准备
目标：恢复关键质量门禁，消除权限误用和 API 调用分叉，同时避免在测试基线不稳时做高风险重构或全量 API 迁移。
覆盖问题：1、2、3；问题 7 只做边界与测试清单；问题 8 只做 response helper 与 touched endpoint 样例。
交付：后端测试依赖/收集恢复；RoleChecker 删除或真实化；TTS preview 统一 API client；新增 common.api.response helper；本轮 touched endpoint 使用统一 envelope；旧 endpoint 与前端 client 保持兼容；大文件只交付拆分边界图、message/API contract snapshot 和 regression list，不实际拆分。

### Phase 2：核心训练体验可信，高优 4-6、9
目标：首页、训练入口、练习页和音频证据链不再误导用户。
覆盖问题：4、5、6、9。
交付：首页模块化状态；练习页结构化故障面板；训练结束等待音频留痕完成/失败；训练入口区分 empty/failure/partial failure；返回路径明确。

### Phase 3：复练增长主闭环，高优 10，中优 11-13
目标：首页、历史页、训练页、报告页串成“下一次该练什么”。
前置：先冻结复练数据契约，再实现各页面入口，避免每个页面各自推导跳转参数。
覆盖问题：10、11、12、13。
交付：recommendation_kind、source_session_id、focus_intent、retry_entry fallback、缺 agent/persona/presentation 参数时的跳转规则、数据资格规则；随后实现今日复练任务卡、历史按问题聚合、销售 10 核心组合个性化排序、报告下一轮训练卡。

### Phase 4：训练沉浸与团队互动，中优 14-20
目标：优化首屏速度、即时反馈、PPT 逐页、主管提醒、偏好记忆、文案一致性、高光清单。
覆盖问题：14、15、16、17、18、19、20。
交付：渐进式渲染；本轮动作完成状态；PPT 逐页补练一期；learner intervention open 接口；训练偏好本地记忆；中文 loading/error；高光复习清单。

### Phase 5：长期粘性与可选体验，低优 21-26
目标：增强排行榜激励、空态行动化、连续天数、能力地图、移动端快捷入口、上下文帮助卡。
覆盖问题：21、22、23、24、25、26。
交付：进步榜/附近排名；空态行动 CTA；连续练习展示；训练能力地图；移动快捷区；上下文帮助卡。

## 4. 26 个问题逐项解决计划

1. 后端测试质量门禁阻断
解决：补齐测试运行依赖，固定测试环境，先恢复 targeted pytest collection；ruff 分 src/tests 两层治理。
最小切片：让 test_dashboard_recommendation、test_audio_segment_api、test_main_presentation_ws_runtime 可收集。
验收：targeted pytest 不因 rank_bm25/jwt 缺失失败；backend/src ruff 有明确通过或 baseline。

2. RoleChecker always-allow
解决：删除 common/middleware/auth.py 中 RoleChecker，或改为 require_role 包装；新增 grep gate。
验收：rg RoleChecker 不存在，或测试证明非 admin 被拒绝。

3. 直接 fetch 绕过统一 API client
解决：admin settings/personas TTS preview 收敛到 api.admin.previewTTSBlob，复用 resolveApiBaseUrl、CSRF、错误处理。
验收：app/admin 页面无直接 NEXT_PUBLIC_API_URL 拼接；预览失败展示中文 ApiRequestError。

4. 首页失败伪装空数据
解决：首页 stats/recommendation/history 拆模块状态，失败不覆盖为 DEFAULT_STATS/空数组。
验收：单模块失败测试中页面显示失败模块和重试，不显示 0 数据伪空态。

5. 练习页错误互相遮蔽
解决：建立 PracticeFaultPanel，按连接、麦克风、留痕、会话状态并列展示。
验收：同时传入多个错误时全部可见，各自有恢复动作。

6. 训练结束音频留痕完成度不确定
解决：continuousUploader 暴露 pendingUploads/flushAndStop；生命周期结束进入 bounded flush 阶段，等待最后分片 register 完成、失败或达到明确超时，再跳报告；超时不无限阻塞用户。
验收：测试 stopUpload 等待最后分片 register；覆盖成功、失败、超时三种状态；失败或超时时报告页有证据缺失解释和影响范围说明。

7. 高复杂度文件维护风险
解决：首批只做测试锁定、边界图、message/API contract snapshot、targeted regression list；不得实际拆分 StepFun handler、practice.py、report/replay。后续每次只拆一个模块、一个 outward contract。
验收：首批产出边界和测试清单；后续实际拆分时每次不改变 outward contract，targeted tests 通过。

8. API envelope 重复
解决：新增 common.api.response 作为新接口和 touched endpoint 的唯一响应 helper；HTTPException handler 统一 detail 到顶层 envelope；前端 client 保持旧 envelope 兼容，禁止一次性全量迁移历史接口。
验收：新增接口只返回 success/data/error/message/trace_id 统一结构；旧接口未被无测试覆盖地批量修改；前端兼容旧结构和新结构。

9. 训练入口 empty/failure 混淆和返回路径不稳
解决：训练入口状态机化，主返回按钮改明确路由。
验收：failure 与 empty 文案不同；深链接进入返回训练大厅。

10. 首页今日复练任务卡
解决：/recommendations/latest 增加 due_reason/focus/suggested_duration/is_due_today，首页改为今日复练任务。
验收：sales_retry、presentation_page_retry、无记录三分支渲染正确。

11. 历史按问题复练聚合
解决：前端先聚合最近可评估记录 main_issue.issue_type，后端后续下沉。
验收：顶部展示最常卡住 3 类问题和再练入口。

12. 销售 10 组合个性化排序
解决：销售训练页读取 recommendation/history，匹配 CORE_COMBINATIONS 置顶。
验收：命中组合标注“基于上次报告推荐”。

13. 报告下一轮训练卡
解决：报告页汇总上次卡点、修正动作、判定条件、再练入口、回放锚点。
验收：retry_entry 完整时一键再练；缺配置时指向销售训练页。

14. 渐进式渲染
解决：首页/历史/训练页分区独立 loading，非关键数据 stale-while-revalidate。
验收：主 CTA 不被统计/历史接口阻塞。

15. 本轮动作完成状态
解决：RightPanelContent 基于 actionCard 和下一轮 scores/suggestions 推断完成状态。
验收：用户下一次发言后状态从等待变为已尝试或未命中。

16. PPT 逐页补练
解决：一期报告页问题页跳 replay page；二期 createSession 支持 presentation_focus_page。
验收：page 参数能定位回放页；二期练习页默认目标页。

17. 主管提醒 learner 承接
解决：新增 /users/me/interventions/open，只返回当前用户未解决提醒；首页展示重点。
验收：resolved 不展示；他人提醒不可见。

18. 训练偏好记忆
解决：一期 localStorage 保存 voiceMode/agent/persona/presentation；二期用户 settings 持久化。
验收：非推荐入口默认选中最近配置；推荐 focus_intent 优先。

19. 中文 loading/error
解决：替换 web/src/app/loading.tsx、admin/error.tsx 等英文文案。
验收：主错误/加载状态无英文按钮和标题。

20. 高光复习清单
解决：待改进高光支持加入本地清单，并可带 suggested_response 进入再练。
验收：报告页显示 1-3 个已选片段和带片段再练入口。

21. 进步榜/同目标榜
解决：先做我的附近排名，再扩 leaderboard_mode=improvement，最后 issue_type 同目标榜。
验收：样本不足有解释，证据不足不计入。

22. 空态行动化
解决：排行榜/图表/分析空态说明触发条件和去训练 CTA。
验收：空态不只显示“暂无数据”。

23. 连续天数与轻成就
解决：首页展示连续练习 N 天、本周目标 X/3，仅基于 completed/evaluable。
验收：证据不足训练不计入高质量成就。

24. 训练能力地图
解决：训练分类卡展示最近分数、完成次数、待复练目标、最弱能力。
验收：sales/presentation 卡展示不同能力标签。

25. 移动端快捷入口
解决：首页/训练页/练习页底部常驻继续训练、历史、帮助。
验收：移动视口无需打开抽屉即可看到主入口。

26. 上下文帮助卡
解决：LearnerHelpCard 接收 context，失败时给“仍可做什么”。
验收：dashboard/history/practice/report 文案不同且有行动按钮。

## 4.1 复练与增长数据资格规则

1. score_eligible：只包含 completed 且 evaluable 的训练，可计入分数、榜单、成就、趋势。
2. retry_eligible：可用于生成复练建议的训练，必须有足够 main_issue、next_goal、presentation_review 或 retry_entry 证据；PPT 页级问题可按 presentation_review 生成页面补练，不必强行等同 sales score eligibility。
3. explanation_only：证据不足、未完成或不满足复练条件的记录，只能用于解释“为什么不上榜/为什么建议完成一次可评估训练”，不得用于正向成就或排行榜。
4. 所有页面必须显式区分以上三类，避免把证据不足训练伪装成低分或激励。

## 4.2 首批 team 文件所有权矩阵

Lane A backend-quality-security：拥有 backend requirements/pyproject、backend tests targeted files、backend/src/common/middleware/auth.py；不得修改练习页前端。
Lane B frontend-api-admin：拥有 web/src/lib/api/client.ts 中 admin TTS preview 相关方法、web/src/app/admin/settings/page.tsx、web/src/app/admin/personas/[id]/page.tsx；修改 client shared 区域前需与 Lane D/E 对齐类型。
Lane C practice-core-ux：拥有 web/src/app/(user)/practice/[sessionId]/page.tsx、use-practice-session-lifecycle、use-continuous-audio-uploader、PracticeFaultPanel 新组件；不得修改 dashboard recommendation 契约。
Lane D learner-entry-states：拥有 web/src/app/(dashboard)/page.tsx、training sales/presentation entry state、ScenarioList、learner route error/empty components；不得修改 admin TTS。
Lane E backend-api-contract：拥有 backend/src/common/api/response.py 或等价 helper、backend/src/common/api/dashboard.py 中 touched response 样例和 recommendation contract 草案；不得全量迁移历史 endpoint。
Leader/verifier：唯一负责合并 web/src/lib/api/client.ts、backend/src/common/api/dashboard.py、backend/src/common/api/practice.py 等共享文件冲突。

## 4.3 首批启动约束

推荐首批不超过 4 条 lane 并行。若必须引入 Lane E，应只做契约/helper，不做大范围 endpoint 修改。任何 lane 发现需要触碰未拥有共享文件，先上报 leader，不得自行扩大范围。

## 5. 依赖关系
1 -> 2/3/8/7：质量门禁恢复是后续安全和重构前置。
2 -> 17：learner intervention 接口必须建立在真实权限边界上。
3 -> 8：统一 API client 与统一 envelope 相互支撑。
8 -> 10/11/12/13/17：统一 envelope 与 API client 错误处理影响 recommendation/history/report/intervention 调用。
4/9 -> 10/11/12/13：状态真实性先于增长入口。
10 契约 -> 11/12/13：recommendation/focus_intent 契约先于历史、销售页、报告页复练入口。
6 -> 13/16/20：证据链可靠先于报告行动卡、PPT 逐页补练和高光清单。
7 贯穿所有阶段，但不得先于测试锁定，且首批只做边界与测试准备。

## 6. 风险与预案
风险 1：后端依赖修复牵出 Python 环境混乱。
预案：只固定测试运行所需最小依赖和命令，不做全量环境迁移；区分 runtime dependency、test extra、test stub；rank_bm25 与 PyJWT 必须记录为何属于恢复既有代码所需。

风险 2：StepFun handler 拆分破坏实时协议。
预案：先冻结 outward WebSocket message contract，按内部服务抽取，不改消息结构。

风险 3：首页/历史/报告新增复练入口造成重复推荐或错误跳转。
预案：统一 recommendation_kind、source_session_id、focus_intent 规则，所有入口缺参数时回退训练大厅；首批只冻结契约，不同时铺开所有增长 UI。

风险 4：增长功能误用证据不足训练。
预案：所有榜单、成就、推荐默认只使用 evaluable completed session，证据不足只能作为解释，不作为正向成就。

风险 5：并行 team 修改同一前端页面冲突。
预案：按文件分 lane，首页/历史/报告/练习页分离，leader 统一整合 shared api types；web/src/lib/api/client.ts、backend/src/common/api/dashboard.py、backend/src/common/api/practice.py、response helper 由指定 owner 或 leader 合并。

风险 6：音频留痕等待过久损害结束体验。
预案：采用 bounded flush，设置明确等待上限；超时后进入报告页但显示“音频证据仍在保存/部分失败”与影响范围，后台或用户可重试。

风险 7：API envelope 全量迁移造成大范围前后端回归。
预案：compatibility-first，新增和 touched endpoint 先统一，旧 endpoint 保持兼容，前端 client 继续兼容旧结构。

## 7. 可用 agent 类型与建议分工
可用角色：planner、architect、critic、executor、test-engineer、debugger、build-fixer、code-reviewer、security-reviewer、designer、verifier、writer、explore。

ralph 顺序执行建议：
1. build-fixer/debugger：恢复 backend targeted pytest collection 和 src ruff baseline。
2. security-reviewer/executor：RoleChecker、direct fetch、API envelope 首批。
3. executor/designer：练习页状态面板、首页状态真实性、训练入口状态机。
4. executor/product lane：今日复练、历史聚合、报告行动卡。
5. verifier：跑 targeted web/backend tests，汇总证据。

team 并行执行建议：
Lane A backend-quality-security：问题 1、2、8。
Lane B frontend-api-admin：问题 3、19，协助 8 的前端兼容。
Lane C practice-core-ux：问题 5、6、15。
Lane D learner-entry-states：问题 4、9、14、22、26。
Lane E retention-loop：问题 10、11、12、13、18、20。
Lane F analytics-growth：问题 17、21、23、24、25。

建议首批 team 只执行 Lane A-D 和问题 10 的后端/首页基础，不一次性做低优项。

## 8. 启动提示
推荐首批执行：$team "按 .omx/plans/ralplan-audit-26-remediation-plan.md 只执行首批可执行窄切片：Phase 0、问题 1/2/3/4/5/6/9；问题 7 仅边界与测试清单；问题 8 仅 helper 与 touched endpoint 样例；问题 10 仅复练契约设计。严格排除 Docker/部署/运维，保护现有未提交改动，每个 lane 提交验证证据。"
保守执行：$ralph "按 .omx/plans/ralplan-audit-26-remediation-plan.md 顺序执行首批窄切片：Phase 0、问题 1、2、3，随后问题 4、5、6、9；问题 7/8/10 只做计划限定的低风险准备，不实现后续 backlog。"

## 9. 完成定义
1. 对应阶段问题全部有代码、测试和验证证据。
2. 未解决问题有明确剩余风险和下一阶段归属。
3. 用户可见失败、空态、证据不足状态不再互相混淆。
4. 不涉及 Docker、部署、运维。
5. 不回滚或覆盖现有未提交改动。

## 10. 架构审查与批判收口

### 10.1 最强反方观点
反方认为：26 项问题横跨工程治理、安全、实时训练、前端体验、增长和移动端，如果计划仍保留全量路线，执行团队可能误以为可以一次性并行推进，造成冲突、验证成本膨胀和主链路回归。尤其 StepFun handler、practice.py、report/replay 页面和首页/历史/报告增长闭环都触及核心用户路径，一旦同时改动，失败定位会困难。

### 10.2 真实取舍张力
张力一：质量门禁优先会推迟用户可见增长收益，但如果跳过门禁，增长功能会建立在不可信证据链上。
张力二：首页/报告/历史复练闭环可以快速提升粘性，但必须依赖 evaluable session、retry_entry、focus_intent 的真实数据，不能先做静态推荐。
张力三：大文件拆分长期收益高，但短期最容易制造回归，因此只能作为被测试保护的分步工程，而不是首批大改。

### 10.3 综合裁决
裁决：APPROVE WITH EXECUTION GATES。
通过条件：本计划可作为全量路线图，但执行时不得一次性启动 26 项；首批只建议执行 Phase 1-2 和问题 10 的最小首页推荐切片。Phase 3 以后必须在 Phase 1-2 验证证据齐全后再启动。低优可选项不得阻塞高优修复。

### 10.4 Critic 质量门槛
1. 每个执行 tranche 必须列出文件范围和测试命令。
2. 任何重构必须先有现有行为测试。
3. 任何用户可见增长入口必须声明数据来源、证据不足兜底和缺参数回退路径。
4. 所有失败态必须与真实空态分离。
5. 不得包含 Docker、部署、运维建议。
