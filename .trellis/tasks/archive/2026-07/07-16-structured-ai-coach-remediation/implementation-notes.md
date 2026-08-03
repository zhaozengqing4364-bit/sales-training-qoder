# 实施记录：结构化 AI Coach 与补练闭环

## 范围与成功标准

- 用户：新人销售学员；具备组织范围 Coach 复核 capability 的平台管理员。普通培训负责人尚无可信 Team scope，本切片保持 fail closed，Team 范围在后续切片建立。
- 主流程：进入 Coach 活动 → 冻结 Profile/Context/Prompt/模型修订 → 生成当前 checkpoint 的 3–5 张白名单训练卡 → 学员逐卡作答（先保存）→ 规则或受治理 AI 评估 → 反馈 → 达标进入下一 checkpoint，未达标最多两轮自动补练，随后转人工帮助。
- 唯一写权威：`ai_coach` 拥有 ProfileRevision、Session、Cycle、Turn、TrainingCard、CardResponse、Feedback/Assistance、CoachOutcome 与人工介入历史；`newcomer_training` 只拥有通用 Attempt/Outcome/Journey；`task_runtime` 只拥有任务状态；后续 `competency_readiness` 模块唯一写正式 CompetencyEvidence。
- 成功标准：当前 PRD 12 条 Acceptance Criteria 全部具有代码与针对性验证证据；首发路径不再暴露旧自由聊天 writer 或直接 Provider 调用。
- 最小验证：修改文件静态检查、Coach 领域单元/集成测试、统一 Activity API 与 Coach runner 针对性测试、Coach migration 结构/升级验证；不运行全量测试、构建或 E2E，最终浏览器/发布门禁留给切片 8。
- 回滚：关闭 `NEWCOMER_AI_COACH_ENABLED`，停止创建新的 Coach Session/AI 任务；在途记录保留为可恢复/人工处理，只读历史继续可查，不重新启用旧自由聊天 writer。生产不通过破坏性 downgrade 删除训练回答或 AI lineage。

## 已确认事实

- 旧 `sales_trainer` AI Coach 路由以任意消息驱动状态，持锁事务中直接调用 `LLMService.generate`，回答在 AI 返回后才保存，并把正式结果仅通过旧会话/SSE 投递。
- 当前统一 Activity Shell 只注册 lesson/quiz/audio/assignment；磁盘中不存在 CodeGraph 旧索引提到的 `ai-coach-runner.tsx`。
- `task_runtime`、`AIInvocationPort`、Prompt 编译/修订、schema registry、预算与 fenced Worker 已由前置切片提供，可复用短事务 → 外部 AI → 短事务模式。
- 标准训练包当前在录音讲解后直接进入三段异步场景录音；需发布新的 PathRevision，在二者之间加入结构化 Coach，既有 active Enrollment 继续冻结。
- 当前身份模型没有可信培训负责人 Team scope；平台管理员可获得组织范围 capability，跨组织必须 404 并记录 denied audit。
- CodeGraph 索引未包含前置切片新增的未跟踪模块；已用 CodeGraph 审查旧链路，再直接读取当前磁盘上的新模块，不重建用户索引。

## 保守实现决定

- `CoachProfileRevision` 本身就是掌握阈值、补练策略、卡片白名单和 AI 修订的发布/冻结业务配置；不额外创建第二套通用规则表。标准包默认阈值 80%，运行时只读取 Session 冻结快照，前端不写死。
- 使用三个显式耐久任务：卡片生成、语言答案评估、受限解释/示例。每次都在短事务中准备/落库，数据库事务不跨 Provider IO；可确定性卡由应用规则直接评分，不创建 AIInvocation。
- 卡片 public payload 使用 discriminated union 和固定 renderer；内部评估 spec 与 public payload 分离。未知类型、任意 HTML/组件名/脚本、非法数量或无来源一律 fail closed。
- 正式 CompetencyEvidence 属于切片 5。本切片只幂等写 CoachOutcome、通用 ActivityOutcome 和带 source refs 的 Outbox；验收中的 Evidence 可追溯在本切片落实为完整 lineage + 事件边界，不抢先建立第二个 Evidence writer。
- 管理人工介入 API 在本切片提供组织范围队列、追加指导和明确后续动作，且只追加历史、不改写回答/AI 结果。统一管理员 UI 与 Team scope 在切片 5/6 完成。
- Gold set 只覆盖 Coach Prompt/schema 的本地 Fake/contract 情形；正式 Provider 校准、shadow/canary、成本/延迟 readiness 属于切片 6/8 发布门禁。

## 页面契约

- 目标任务：学员在不离开训练活动页的情况下完成当前结构化训练卡并清楚知道下一步。
- 页面模型：稳定页头（checkpoint、进度、依据来源/薄弱点）+ 单一当前卡工作区 + 持久反馈区 + 底部唯一主操作；不是空白聊天界面。
- 数据来源：统一 `FoundationActivityWorkspace`/`FoundationActivityCommand`，经 DTO → typed workspace/runner → card renderer；不得展示 Prompt、traceId、原始枚举、内部 ID 或 raw JSON。
- 必须状态：preparing、awaiting_answer、evaluating、feedback_ready、checkpoint_mastered、remediation_required、failed_recoverable、offline、cancelled、needs_human_help、completed；恢复失败时保留已提交回答并给出刷新/重试/人工下一步。
- 可访问性：每类卡有语义 label/fieldset、键盘操作和可见焦点；颜色不是唯一结果信号；长内容在工作区内部滚动，底部主操作可达。

## 实施计划

1. 建立 `ai_coach` 领域契约、模型、状态机、AI schemas、上下文/Outcome 端口和 migration。
2. 实现保存优先的 Session Runtime、确定性评分、三类受治理持久任务、幂等/重试/取消/人工转接。
3. 在组合根注册 Profile 资源、Runtime、AI schemas 与 Worker handlers；把标准包的新 Profile/Coach Activity 插入冻结路径。
4. 扩展统一 learner/admin API 与 capability/audit；清理首发旧 Coach writer 和直接 Provider 调用。
5. 基于现有 Activity Shell 实现 typed Coach runner 和卡片 renderer，补齐恢复/失败/人工帮助状态。
6. 更新 API/ADR/Trellis Spec 与针对性测试，通过当前 PRD 验收后立即收口切片。

## 偏差

- PRD R11 写“写入 Competency Evidence”，但父任务冻结的唯一写权威要求正式 `CompetencyEvidence` 只能由切片 5 建立。为避免提前形成第二 writer，本切片实现完整 CoachOutcome/ActivityOutcome lineage 与事件边界，正式 Evidence 消费留给紧接的切片 5。
- 普通培训负责人目前没有可信 Team scope。本切片只给平台管理员 `newcomer.coach.review` 的 organization-scope 复核，并对普通培训负责人 fail closed；Team scope 与统一工作台按执行计划留给切片 5/6。
- 任务处理器联调发现 Pydantic v2 不能用 `TargetResult.model_validate(other_result_model)` 跨模型转换；改为先 `model_dump(mode="json")`，并为 Task result location 增加真实 handler 测试。这是本切片持久任务可执行性的必要修正，不扩大业务范围。
- Playwright 实际渲染尝试因运行环境缺少 Chromium 系统库 `libnspr4.so` 无法启动。未安装新系统依赖；本切片保留组件 DOM/语义/交互测试，实际浏览器、移动视口、截图和控制台门禁按父任务约束在切片 8 完成。

## 历史/无关问题

- 工作区开始前已有大量用户/前置切片未提交改动及历史 migration 归档；本切片不回滚、不清理。
- `.kiro/steering/backend-principles.md`、`frontend-principles.md` 在 task 引用中存在但磁盘缺失；已遵循仓库 AGENTS、Trellis specs 与 `DESING.md`，不在本切片补造缺失文件。
- CodeGraph 索引仍包含已删除旧 Coach 文件且不包含本轮新模块；遵循“不自行重建用户索引”，用索引做旧链路 impact，再以当前磁盘源码和针对性测试确认新链路。
- 旧 `sales_trainer` Journey 只读投影仍含 `start_ai_coach` 动作字符串；旧正式 Session/Turn/SSE writer 与路由已删除，新人首发只有统一 Activity Command 入口。该只读 Legacy 消费者清单留给切片 8，不在本切片顺手清理。
- 定向 pytest 首次按仓库默认覆盖率插件运行时，16 个目标测试全部通过，但因只运行目标文件导致全库覆盖率门槛 24% < 48% 而命令退出失败；随后按本任务“最小测试”约束使用 `--no-cov` 重跑。未伪装为产品失败，也未扩大为全量测试。

## 验收证据

- Session 冻结 Profile/Activity/Path/Context：`CoachSession`、`CoachProfileRevision`、migration 约束及 `test_profile_freezes_exactly_three_checkpoints_and_bounded_remediation`、Outcome lineage 测试。
- 后端控制三个 checkpoint：`StructuredCoachRuntime.continue_training()` 与三检查点 Outcome 测试；标准包顺序测试确认录音讲解 → Coach → 三段异步场景录音。
- 每轮 3～5 张白名单卡：严格 discriminated union、Profile whitelist、数量策略、八类 contract 测试、未知类型/额外字段/空输出/越界来源/HTML fail-closed 测试。
- 保存后调用 AI：`submit_answer()` 的显式 flush boundary、client-token/hash 唯一约束、保存/重放/Provider timeout/retry 测试。
- 确定性卡不调用模型：选择/排序规则评分与任务数断言。
- 非法 AI 输出不完成评分：卡片生成和答案评估非法 Schema 均进入 `failed_recoverable`，已提交答案保留；无 Context 时启动 fail closed。
- 阈值来自快照：Profile 标准包默认 80，测试使用 82 证明 runtime/UI 读取快照而非前端常量；模型报告 mastered 不作为状态真源。
- 自动补练最多两轮：两轮后任务数不再增加并进入人工帮助；高不确定性完成轮次后同样进入人工队列。
- 人工帮助：organization/capability scope、跨组织 404、追加式指导/指派、版本/幂等与 denied audit API 边界。
- 正式反馈/Outcome 持久化：CardResponse、Assistance、CoachOutcome 与 normalized ActivityOutcome；受限讲解不改变正式 Session 状态。
- Evidence lineage：回答、卡片、Context source、generation/evaluation Invocation、Prompt template/revision/hash、模型路由 profile/revision 进入持久结果；正式 CompetencyEvidence 单写由切片 5 消费。
- Clean cut：旧自由聊天 handler/service/routes/SSE 与直接 Provider scoring 删除；统一 `/activities/{activity_id}/commands` 是唯一正式 Coach 写入口，clean-cut 测试锁定。

## 验证记录

- `python3 ./.trellis/scripts/task.py validate .trellis/tasks/07-16-structured-ai-coach-remediation`：通过，`implement.jsonl` 7 项、`check.jsonl` 4 项有效。
- `backend/.venv/bin/ruff check src/ai_coach ...`：通过，Coach 源码与新增/修改目标测试无 lint 问题。
- `backend/.venv/bin/mypy src/ai_coach ...`：通过，Coach 源码和新测试无类型错误；未修复旧测试文件已有的 untyped-def 历史问题。
- `backend/.venv/bin/pytest -q --no-cov tests/unit/ai_coach tests/migrations/test_structured_ai_coach_migration.py ...`：安全内容修正前 43 项通过；最终收口会再运行相同目标集合。
- `backend/.venv/bin/pytest -q --no-cov tests/unit/ai_coach/test_runtime_pipeline.py`：15 项通过，覆盖真实 handler result location、恢复/取消、无 Context、保存优先、非法输出、受限讲解、高不确定性、两轮补练和 Outcome。
- CodeGraph `impact AiCoachSessionService/AiCoachActivityHandler/ActivityShell` 与 `affected ...`：选出旧 Journey/Readiness/registry 及活动页/ActivityShell 回归；后端影响集 13 项、前端影响集 8 项均通过。
- `web npx eslint`（Coach runner/test、ActivityShell/page/types 目标文件）：通过。
- `web npx vitest run coach-runner.test.tsx activity-shell.test.tsx`：15 项通过；最终 Coach runner + ActivityShell + Activity page 目标集合 18 项通过；CodeGraph 影响集 `page.test.tsx + activity-shell.test.tsx` 8 项通过。
- 临时目标 `tsconfig.coach-slice.json` + `npx tsc --project ... --noEmit`：通过；临时配置已删除。
- Playwright 最小渲染：未执行成功；Chromium 启动报 `libnspr4.so: cannot open shared object file`。临时 QA route/script/dev server 均已删除/停止，未向仓库引入测试脚手架或依赖。
- `$trellis-check` 最终目标门禁：Ruff 通过；Mypy 21 个目标源文件通过；Backend 61 项目标/影响测试全部通过（2 个依赖弃用 warning）；Frontend ESLint、目标 TypeScript 与 18 项 Vitest 全部通过；相关 `git diff --check` 和临时文件/进程清理通过。

## 未验证与后续门禁

- 当前切片不运行全量 pytest、全量 Next build、全量 E2E 或全库格式化；父目标明确仅切片 8 执行这些发布门禁。
- 真实 Provider、Gold Set 人工校准、shadow/canary、成本/延迟阈值与 Provider readiness 留给切片 6/8；本切片使用确定性 AI fake/contract 验证正常、空/非法、幻觉来源、prompt injection、timeout、重复和高不确定性。
- 实际浏览器桌面/390px、200% zoom、键盘焦点、长文本、console/screenshot 因本环境浏览器系统库缺失未验证，必须在切片 8 门禁关闭。

## 风险、发布与回滚

- 风险等级：P1（AI 结构化输出、训练状态机、敏感员工训练回答、跨模块 Outcome 回流）。
- 发布顺序：migration → API → Coach Worker/Prompt/model/provider readiness → 新 PathRevision 标准包 → feature flag 分范围启用。
- 降级/回滚：关闭 Coach feature flag 和 enqueue，保留 Session/Response/Invocation/Outcome/审计；在途任务完成、重试或协作取消，禁止恢复旧自由聊天 writer。
