# 切片 8 实施记录

## 用户、主流程与成功标准

- 学员：在唯一新人基础训练入口完成学习、测验、录音讲解、结构化 Coach、异步客户场景录音，并在故障后恢复到同一业务结果位置。
- 培训管理员/内容负责人：发布标准包、创建 Cohort/Enrollment、治理内容/题目/评分/Prompt，并通过 ReleasePlan 预览、确认和回滚。
- 培训经理/Reviewer：基于不可变 Evidence 与 Dossier 完成补练、申诉和人工复核；只有有权限的人工决定可授予 `foundation_ready`。
- 成功标准：旧写入口和 Realtime 首发依赖退出运行时；核心对象单写权威、持久任务和受治理 AI 合同有机器门禁；空库到首发闭环、故障恢复、权限、性能、发布与回滚均有可复现证据；父任务验收矩阵逐项关闭。

## 权威、数据、API、权限与状态影响

- Path/Cohort/Enrollment/Attempt/Journey 权威：`newcomer_training`；Enrollment 冻结 PathRevision，迁移只能显式预览并确认。
- 内容/题目/Quiz、Audio、Coach、Evidence、Readiness 分别由切片 2～5 建立的领域服务写入；跨域只通过稳定合同、身份、快照引用和版本化事件。
- Prompt/Provider/模型调用由 `ai_platform` 治理；长任务、Lease、重试、取消、死信和 Outbox 由 `task_runtime` 治理。
- 权限以后端 capability + organization/team/object scope 为准；前端可见性不是授权边界。高风险发布、复核、批量动作保留 preview/expected version/reason/audit/rollback。
- 本切片允许删除已证明无消费者的 Legacy 路由、Facade、注册和种子，但不得删除用户录音、答案、Outcome、Evidence、审计或历史版本。

## 实施计划

1. 用 CodeGraph、运行时 OpenAPI、路由/前端消费者扫描和架构 Guard 重新盘点唯一写权威及 Legacy/Realtime/Provider/进程内任务残余。
2. 先补失败测试和 Guard，再做最小 Clean Cut：移除已替代的路由/注册/Facade/种子/前端消费者，修复首发 bootstrap 幂等与契约漂移。
3. 收口 OpenAPI、类型、状态机、权限、安全、AI gold set、观测指标、Runbook、feature flag/rollout/rollback 和开发命令。
4. 在隔离环境执行空库 migration/reset/seed/start、确定性正常/补练/故障/权限/申诉 E2E、性能与 Worker/Provider 降级演练。
5. 运行切片 8 唯一获准的全量质量门禁和发布回滚演练；更新 Trellis Spec、父任务验收矩阵和最终证据后立即停止。

## 回滚方式

- 代码/路由清理通过恢复前一应用版本回滚；不会把 Legacy 写入口作为长期双写方案重新启用。
- 数据 migration 必须先 dry-run/影响统计并在隔离数据库演练 downgrade/upgrade；正式业务数据只追加版本或使用补偿，不做破坏性回写。
- 发布失败关闭新任务创建和入口，保留 Durable Task、业务数据与审计，回滚 ReleasePlan/应用版本并重建只读 Projection。

## 保守假设与工作区保护

- 当前仓库处于开发期且存在大量用户/前序切片未提交改动；不 reset、checkout、clean、commit、push 或创建 PR。
- 只清理新人基础训练首发范围内、已由 v2 权威替代且有消费者证据的代码；全仓其他产品的 Realtime、通用 Provider、BackgroundTask 或 Legacy 能力不因名字相似被顺带删除。
- 切片 8 按 PRD 明确执行全量门禁；历史失败先分类，只有本轮范围或阻塞首发门禁的问题才修复。

## 执行历史、偏差与未纳入事项

- 2026-07-18：完成任务激活/校验、Trellis 规范注入和第一轮 CodeGraph 探索。首个门禁阻塞是旧 smoke bootstrap 对 `voice_runtime_profiles_name_key` 的非幂等写入；已通过迁移到 Foundation 标准包 bootstrap、移除 v1 seed/reset 编排和幂等测试收口，不保留第二写权威。
- 2026-07-18：以运行时装配、OpenAPI、前后端消费者和架构 Guard 为证据完成第一批 Clean Cut：移除旧资源发布 tombstone、旧 readiness/regrade API、旧管理员读取入口、旧 ConfigBundle 路径权威及其前端消费者；保留其他产品独立的销售/演示 Realtime，Foundation 首发不再注册、导航、seed 或依赖 Realtime。
- 2026-07-18：新人复核入口统一到 `/admin/newcomer-training/reviews`，后端 `primary_action_href` 同步切换到该权威入口。队列与档案页补齐权限、空结果、陈旧数据、失败恢复、能力门禁、证据/规则/AI 推断/人工决定分层和用户语言映射；审批仍只能由具备 `readiness.review` 能力的人工 Reviewer 发起。
- 2026-07-18：删除已无消费者的录音“评分结果”旧入口，管理录音首页只保留当前三个有效任务。相关前端 Vitest 5 个文件 10 条用例、定向 ESLint、TypeScript 全量类型检查、后端 readiness 单测与 Ruff 均通过。
- 2026-07-18：质量门禁在 TypeScript 前清理 `.next` 与 `.next-smoke` 的生产/开发生成类型根，避免已删除路由因陈旧 Next 类型缓存造成假失败；脚本单测扩展为 4 条、Ruff 和 `bash -n` 均通过。移除已经没有对应用例的旧 Coach Playwright 真实 Provider 调用后，当前 5 个 Playwright 调用点仍全部经本地运行库 seam。
- 2026-07-18：删除运行时已不装配的 `sales_trainer/orchestration/admin_api.py`、`learner_api.py` 及其陈旧测试，Clean Cut 测试改为断言文件不存在；架构 Guard 同步移除已经无违规支撑的 `admin -> sales_trainer` 白名单。OpenAPI 已从运行时重新生成，Guard、OpenAPI parity、Clean Cut/路由契约和 Foundation 错误信封针对性测试均通过。
- 2026-07-18：建立版本化 Foundation AI Gold Set，覆盖题目生成、短答评分、录音评分、Coach 卡片/回答评估、Dossier 摘要，以及非法 Schema 拒绝和 Provider 超时降级；确定性门禁验证 Schema、依据、事实、越界引用、降级、稳定性与成本并已生成通过证据。质量门禁已将其设为完整验证必跑项，并以单独的 `foundation-ai-real-provider` 模式通过受治理调用服务运行真实 Provider staging；该模式要求显式确认，只保留安全血缘、用量、延迟、失败码和输出哈希。
- 2026-07-18：新增隔离 PostgreSQL schema 的 Foundation migration 发布门禁，实际完成空库到唯一 head、当前 head 降到指定 baseline 后再升级、重复 upgrade、标准包重复 seed/verify-only、基线用户与自定义权限保留、无未验证外键等验证；用例 1 条通过，耗时 26.10 秒，并已加入关键集成测试选择策略。
- 2026-07-18：新增受保护 reset 双循环演练器及其静态/单元门禁。演练器只允许本机 PostgreSQL、随机 disposable database、随机 Redis prefix、临时文件目录和禁用 COS，并要求显式确认；应用角色不需要建库权限，单独的本机管理员连接只负责创建/删除 disposable database。真实演练先把空库升级到唯一 head `20260717_1500_006`，再连续执行两轮 reset/seed/verify；两轮均得到 1 个管理员、业务表为空、标准包 `Path=1 / Questions=7 / Quizzes=7` 且 verify-only 幂等，所有外部前缀/临时目录清洁，最后数据库删除成功。通过证据为 `.sisyphus/evidence/foundation-reset-rehearsal.json`。
- 2026-07-18：建立隔离 PostgreSQL schema 的 Foundation 容量门禁，实际覆盖 1,000 学员、1,000 Enrollment、10,000 Attempt、每路径 100 活动、100 并发 Journey、20 并发 Durable AI Task 和 20 并发录音上传/处理，并生成通过证据。门禁发现并修复了仅在 PostgreSQL FK 生效时暴露的 UploadSession→Part、TranscriptRevision→QualityReport 插入顺序问题，以及管理列表对同一 PathRevision 重复解析冻结快照的问题；录音单测 9 条和容量用例 1 条通过。完整质量门禁同时新增生产 Web build 与该容量基线，防止开发模式性能或 SQLite 顺序测试冒充发布证据。
- 2026-07-18：跨域 deterministic Foundation E2E 已覆盖管理员安装标准包、Cohort/Enrollment、Lesson、Quiz、Audio、Coach、三段异步场景录音、Evidence/Dossier 和人工 Reviewer 授予 `foundation_ready`，`backend/tests/e2e/test_foundation_closed_loop.py` 为 `1 passed`。补练、申诉、跨组织拒绝、发布失败保旧、录音故障恢复、任务/Outbox 重放和复核并发由同一发布门禁中的领域/集成场景覆盖；聚焦场景集合 `60 passed`，真实 PostgreSQL Task Runtime 集合 `20 passed`，Foundation migration `1 passed`。
- 2026-07-18：新增 Foundation 运营事故 Runbook 及合同测试，覆盖 API/Task/上传/AI/Dossier/Release/安全 9 类告警和 Worker、Provider、对象存储、orphan、reconcile、Dossier、发布、Prompt/模型、权限、Activity 快速关闭 10 张处置卡。发布失败旧计划保持 active 与显式 rollback 已由 `test_release_plan.py` 的原子失败/回滚场景验证。
- 2026-07-18 偏差记录：在加入 `FOUNDATION_AI_REAL_PROVIDER_CONFIRM=1` 强制开关前，一次原本用于验证“缺少凭据”分支的本地命令因项目导入自动加载 `.env`，意外向已配置 endpoint 发起 6 次调用；全部返回受治理的 `AI_PROVIDER_HTTP_503`，没有生成业务输出或费用，也未打印密钥。随后立即增加双重显式确认并验证未确认命令只生成 `configuration_error`、不发起网络调用。后续真实 Provider 只允许通过受控质量门禁执行；当前 503 结果不能作为 staging 通过证据。
- 2026-07-18：真实 Provider staging 首轮受治理执行暴露两个门禁缺陷：Endpoint 校验结果对象被错误转成 repr 而不是规范化 URL，且“稳定性”错误要求生成式 JSON 字节完全一致。已把 Provider 配置修为规范化 `endpoint.base_url`；稳定性改为每次重复都独立通过 Schema/依据/事实/引用边界，并比较会影响业务的结构、得分和不确定性，允许无害措辞差异。Coach `evidence_from_answer` 现在由 Schema 强制非空，金标输入补齐实际来源、Rubric、转写和学员回答，避免要求模型猜测缺失上下文。
- 2026-07-18：最终受控真实 Provider staging 使用 `deepseek-v4-flash`、6 个接受用例各重复 2 次，共 12 次受治理调用，全部 `succeeded`；Schema、非法输出拒绝、依据覆盖、降级合同、稳定性均为 `1.0`，事实错误和越界引用均为 `0.0`，成本为 `0` 个最小货币单位，证据只保留安全血缘、用量、延迟和输出哈希。通过证据为 `.sisyphus/evidence/foundation-ai-real-provider-staging.json` 与 `task-9-foundation-ai-real-provider-gate.txt`。
- 2026-07-18：第一次完整质量门禁已通过 secret scan、测试选择、Backend Ruff/Architecture Guard/OpenAPI/确定性 Gold Set、全量 Mypy，以及 `3374 passed / 1 skipped` 的 Backend Unit+Contract；随后在 Vitest 暴露 4 处陈旧/脆弱前端测试与一个未纳入覆盖的 `server-api`。已只修复对应契约测试、补 `server-only` 测试 alias 和 `server-api` 单测；独立全量 Vitest 复跑为 `201 files / 1148 passed / 6 skipped`，Statements/Branches/Functions/Lines 为 `56.63% / 53.91% / 51.72% / 59.02%`。该第一次门禁因中途失败不算发布通过，必须在最终代码冻结后完整重跑并覆盖证据。
- 2026-07-18：第二次完整质量门禁已通过 secret scan、Backend Ruff/Architecture Guard/OpenAPI/确定性 Gold Set、全量 Mypy、`3379 passed / 1 skipped` 的 Backend Unit+Contract、Web typecheck/lint、`201 files / 1148 passed / 6 skipped` 的全量 Vitest 和生产构建，随后在 smoke bootstrap 暴露评分规则集幂等性缺陷：数据库已存在相同 `(scenario_key, ruleset_version)` 自然键但不同历史 ID 时，脚本只按固定 ID 查询并尝试重复插入。已将 bootstrap 收口为“固定 ID 一致则复用、自然键存在则复用、固定 ID 被冲突身份占用则显式失败、否则创建”，并先用回归测试复现后修复；单测 `3 passed`、Ruff 通过，原始 smoke 启动成功，且对真实开发库连续执行 bootstrap 两次均成功。针对脚本/测试执行的 Mypy 报告 66 个既有 SQLAlchemy Column/未注解测试错误；完整门禁只对 `src` 执行 Mypy 且已经通过，因此未顺带修复该范围外历史类型债务。第二次门禁同样因中途失败不算发布通过，最终必须从头完整重跑。
- 2026-07-18：第三次完整质量门禁的 Backend 全量测试实际完成 `3380 passed / 1 skipped`，Pytest 报告耗时 1182.89 秒，但覆盖率汇总仍在进行时触发了 1200 秒 watchdog，退出码 124；这是门禁预算未给覆盖率收尾留出余量，不是测试失败。默认 Backend watchdog 已最小调整为 1500 秒并保留环境变量覆盖，新增脚本合同测试锁定该发布余量；定向 `6 passed`、Ruff 和 `bash -n` 均通过。第三次门禁因 watchdog 中止仍不算发布通过。
- 2026-07-18：第四次完整质量门禁已通过前述后端门禁，Backend 全量结果为 `3381 passed / 1 skipped`，随后 Vitest 在学习内容 Markdown 预览用例稳定复现 1 秒等待上限不足：产品代码先延迟 600ms 再动态载入富文本预览，覆盖率模式下导入与渲染总耗时约 1.05 秒。未改变产品延迟策略，只把该异步行为测试的局部等待上限调整为 5 秒；同一目标用例复跑 `1 passed / 22 skipped`，定向 ESLint 通过。第四次门禁因 Vitest 中止仍不算发布通过。
- 2026-07-18：第五次完整质量门禁已通过 Backend `3381 passed / 1 skipped`、Web typecheck/lint、Vitest `201 files / 1148 passed / 6 skipped` 和生产构建，随后 newcomer smoke bootstrap 遇到同一测试学员已在切片 7 班次中拥有 active Enrollment。原脚本虽标注幂等，却只对自己的固定班次幂等；已补失败回归并收口为：若同组织学员已有 active Enrollment 且冻结到当前标准包 PathRevision，则直接复用；若冻结到不同修订则显式失败，绝不自动迁移。定向测试 `2 passed`、Ruff 通过，对真实开发库连续运行两次均返回同一 Enrollment。第五次门禁因 smoke 中止仍不算发布通过。
- 2026-07-18：在最终浏览器门禁前置复核中，学员页面出现跨源前端遥测 `403`。根因是跨源 `sendBeacon` 会携带同站 Cookie，却无法附加 CSRF Header；现改为仅同源且不存在 CSRF Cookie 时使用 Beacon，跨源遥测使用 `credentials: same-origin` 的 keepalive fetch，避免把登录 Cookie 发送到跨源 API。回归测试 4 条、ESLint、全量 TypeScript 通过；学员入口 3 条、smoke+新人闭环 11 条、演示 2 条、销售 1 条 Playwright 前置验证均通过。
- 2026-07-18：发布慢测试选择器暴露长期陈旧的静态目标：策略仍引用 7 个不存在的集成测试。选择器现在在生成 Manifest 前验证所有 critical/path-rule 目标真实存在，并将基线切换到当前 Learning/Journey/Unit Revision 测试；单测 29 条和 Ruff 通过。全量慢测试前置复跑随后准确暴露 7 条仍调用已退役 newcomer paper/unit/旧录音管理路由的测试；已移除 `paper_api`/`unit_api` 中未注册的 newcomer Router 与死 CRUD Facade，测试改为验证仍受支持的 `/sales-trainer` 资源路由及 Foundation Audio Queue。相关路由/权限/回滚定向场景 `9 passed`、Ruff 通过。此次手工 coverage append 因复用了不同 coverage mode 的本地 `.coverage`，在汇总时报告 branch/statement 数据不可合并；正式门禁会像脚本合同规定的那样先清空 coverage 数据并从同一 branch 配置开始，因此该手工预检不作为发布证据。
- 2026-07-18：第六次完整质量门禁在 Secret Scan、测试选择、Ruff、Architecture Guard 通过后，被 OpenAPI parity 正确阻断；原因是刚完成的 dead Router 清理改变了运行时契约，而快照尚未刷新。已从 `create_app().openapi()` 重新生成契约并立即以独立 `--check` 进程验证一致；该次门禁仍不算发布通过，必须从头完整重跑。
- 2026-07-18：第七次完整质量门禁已通过 Backend `3384 passed / 1 skipped`、Web typecheck/lint、Vitest `201 files / 1148 passed / 6 skipped`、生产构建、全部 Playwright、Backend 慢测试 `530 passed / 56 skipped` 和容量基线，最后被 changed-coverage 策略中仍指向 5 个已删除 Legacy Path/Journey 文件的陈旧关键分支基线阻断。策略现迁移到 5 个唯一 `newcomer_training` 权威模块，并以新增边界测试覆盖权限、幂等、非法状态、并发版本、预览过期、影响哈希、对象范围、配置阻塞和所有投影恢复分支；87 条聚焦测试与 Ruff 通过，旧完整覆盖报告和新增聚焦分支证据的并集为 `activity 82/82`、`activity_application 34/34`、`application 150/150`、`contracts 22/22`、`journey 54/54`。该次门禁在策略修复前已中止，仍不算发布通过；最终必须从头完整重跑并以同一份新鲜覆盖报告证明 100% 关键分支基线。
- 2026-07-18：第八次完整质量门禁通过 Secret Scan、选择策略、Backend Ruff/Architecture/OpenAPI/AI Gold Set/Mypy、`3432 passed / 1 skipped` 的 Backend Unit+Contract，以及 Web typecheck/lint，随后被评分标准编辑页的 Vitest 阻断。目标测试单独运行时曾通过、按完整文件顺序运行时失败；根因是测试版 `useToast` 每次渲染都返回新对象，使依赖 `toast` 的 `loadPrompt` 回调和 Effect 反复重建，形成与真实稳定 Context 不符的加载竞态。测试现复用同一 hoisted Toast API 对象，目标文件连续三轮均为 `4 passed`，组件表单测试 `1 passed`，定向 ESLint 无错误；产品运行时逻辑未为测试妥协。第八次门禁仍不算发布通过，必须在此修复后从头完整重跑。
- 2026-07-18：第九次完整质量门禁从头运行并最终通过：Secret Scan 扫描 723 文件；Backend Ruff、Architecture Guard、OpenAPI、确定性 AI Gold Set、Mypy 769 文件通过；Backend Unit+Contract `3432 passed / 1 skipped`；Web typecheck、lint（0 errors）、Vitest `201 files / 1148 passed / 6 skipped`、生产构建通过；Playwright 通用/学员/管理/闭环/Presentation/Sales 合计 21 条全部通过；Backend Integration+E2E `530 passed / 56 skipped`；容量基线通过；changed coverage 无违规，Foundation 五个关键权威模块分支 floor 均为 100%。最终证据为 `.sisyphus/evidence/task-9-quality-gate.txt`，结束时间 `2026-07-18 12:12:11`。此前记录的全仓 lint warning、第三方弃用和非 Foundation 异步资源 warning 未升级为错误，均未在本任务顺带清理。
- 未纳入：通用 Knowledge API 的 `BackgroundTasks`、未装配的通用音频归档调度器和其他产品的 Realtime 属于 Foundation 首发边界外；只有在后续证据表明它们被 Foundation 运行时调用时才进入本切片清理。
