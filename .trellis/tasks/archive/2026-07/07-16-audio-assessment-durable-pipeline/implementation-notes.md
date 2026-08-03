# 实施记录：录音评测持久流水线

## 范围与成功标准

- 用户：新人销售学员、具备相应 capability 的培训管理员/复核人。
- 主流程：开始录音活动 → 分块本地草稿与直传 → 服务端校验 → 标准化 → 受治理 ASR → 质量判定 → 结构化评分 → Outcome 对账；`assignment` 固定复用 discovery/objection/commitment 三段异步录音。
- 唯一写权威：`audio_assessment` 模块拥有 Submission、UploadSession、Artifact、TranscriptRevision、QualityReport、ScoreOutcomeVersion 和重评记录；`newcomer_training` 只拥有通用 Attempt/Outcome/Journey；`task_runtime` 只拥有任务状态。
- 成功标准：当前 PRD 12 条 Acceptance Criteria 全部有代码与针对性测试证据；旧同步/进程内临时后台写入口不再可写。
- 最小验证：修改文件静态检查、音频领域单元/集成测试、Activity API 与浏览器草稿/runner 针对性测试、Alembic 单头和空库 upgrade；不运行全量测试/构建。
- 回滚：关闭音频 Activity feature flag、停止新任务 Worker；保留已上传 artifact/任务/结果为只读。数据库迁移 downgrade 仅用于尚未承载业务数据的开发环境，生产回滚不删除录音。

## 已确认事实

- 现有 `AudioSubmissionService.save_uploaded_file` 会 `await file.read()`，`create_submission(auto_process=True)` 会在请求内同步转写和评分。
- 旧 Sales Trainer API 使用 FastAPI `BackgroundTasks`，不具备进程重启恢复能力；旧 Transcript 会原地覆盖。
- 现有对象存储仅提供短期签名 PUT/GET 和 HEAD 大小；没有云厂商原生 multipart 抽象。
- 现有 `task_runtime`、`AIInvocationPort`、ASR workload contract、Provider 故障分类和 fenced worker 已可复用。
- 现有浏览器录音 hook 把所有 Blob 保存在数组中，刷新即丢失；当前 Activity Shell 只注册 lesson/quiz。
- 实时 WebSocket 录音链路属于延期能力，不能成为本模块业务权威。

## 保守实现决定

- 在不引入新外部服务/依赖的前提下，multipart 采用“一个 UploadSession 对应多个不可变 part object”的应用级协议；每个 part 独立签名 PUT、登记 hash/size，服务端 HEAD 复核，标准化阶段按清单合并。这样可中断、续传、取消、过期，也不把大文件经过 API 内存。
- PRD 的 `normalizing` 与切片 0 已接受状态机并不冲突：作为 `uploaded → validating → normalizing → transcribing` 的显式持久阶段加入领域状态；其余失败态继续使用已接受的 recoverable/terminal/needs_review 投影语义。
- 正式 Competency Evidence 的唯一写权威属于后续切片 5。本切片只幂等写 Outcome、发布 `ActivityOutcomeRecorded`/音频结果事件并保留 competency mapping；不得抢先创建正式 Evidence 行。验收中的“不重复 Evidence”以重复 reconcile 不重复发布同一 outbox 事件为本切片边界，后续消费者依事件幂等键落证据。
- 标准化生产适配器复用已配置对象存储和受控工具；若运行环境没有可用标准化工具，保留原始 artifact 并进入可恢复失败，不伪造成功。

## 实施计划

1. 扩展冻结 Activity 配置与通用 Attempt 状态，新增 `audio_assessment` 领域模型、状态机、上传/存储端口和 Alembic 迁移。
2. 实现 audio/assignment 共用 Runtime、应用级 multipart、对象完整性校验、短签名试听和对象级权限/审计。
3. 注册 validation/normalization/transcription/scoring/reconcile 持久任务；ASR/评分统一经 AIInvocationPort，外部 IO 与数据库短事务分离。
4. 实现不可变 TranscriptRevision、质量报告、ScoreOutcomeVersion、幂等 reconcile、人工修订/重转写、重评 preview/confirm/invalidate。
5. 在根组合层路由 learning/audio Runtime 与资源校验；封存旧写 API，移除请求内同步和 BackgroundTask 正式写链路。
6. 重做浏览器录音草稿为 IndexedDB 分块、暂停/继续/恢复；新增分块直传与两类活动 runner，复用当前 Activity Shell 视觉基础。
7. 增加针对性故障、权限、幂等、版本与大文件边界测试；逐项关闭 PRD AC。

## 偏差

- 原计划把 `prompt_contract_hash` 作为 Scorecard 冻结值；实现真实 Prompt 编译后确认合同 hash 包含本次场景、Transcript 和 rubric 的渲染结果，静态值会让所有正式评分发生合同不匹配。已改为 Scorecard 只冻结 exact PromptTemplate/Revision 与模型路由，Worker 在每次评分前使用同一 `StrictPromptCompiler` 对真实动态变量编译并把 `sha256:` hash 写入 Invocation。
- 标准训练包为录音讲解和三段异步客户场景新增四个 immutable published resource，并发布新的 PathRevision label `2026.07-foundation-audio-v2`；既有 active Enrollment 仍冻结在原 PathRevision，不自动迁移。旧 label 相同但内容漂移时 fail closed，不自动覆盖。
- 云厂商 Provider/model 取决于部署环境。标准包只冻结 exact Prompt/route revision 引用，不臆造或自动发布 Provider 配置；Slice 6 ReleasePlan 必须把 Prompt、模型路由、Schema、Provider readiness 和校准纳入发布依赖闭包。
- 未完成上传清理采用部署级 Cron/CronJob 调用有界脚本，不在 API 进程内启动隐式 scheduler。清理使用行锁、stale claim 和 token fencing，数据库 claim 事务与对象删除 IO 分离；正式 Artifact 不进入该清理器。
- R14 的统一管理员录音工作台按父任务执行计划属于切片 6。本切片已交付组织范围队列和修复/更正/重评/失效 preview-confirm API 权威，不提前制作重复管理 UI。
- 正式 CompetencyEvidence 行仍由切片 5 唯一拥有。本切片以幂等 Outcome + `ActivityOutcomeRecorded`/音频结果 Outbox 作为跨域边界，不抢先建立第二个证据 writer。

## 历史/无关问题

- 工作区在本切片开始前已有大量未提交改动和旧迁移删除，属于此前切片/用户工作；不回滚、不清理。
- CodeGraph 索引不包含前两切片新增的未跟踪模块；已先使用 CodeGraph 理解旧链路，再直接读取当前磁盘源码。
- 全量空库 `alembic upgrade head` 会被本任务开始前已删除的历史 migration revision 和 SQLite 历史外键行为阻塞；本切片不恢复旧迁移，改用 `test_audio_assessment_migration.py` 验证当前录音 migration 的目标表、约束与 downgrade。
- 全量 TypeScript 检查会读取工作区遗留的 `.next*` 生成声明，其中仍导入已经按 Slice 2 删除的 `/newcomer-training/modules/[moduleId]` 页面；这是生成缓存/历史问题，不恢复被退役页面。本切片只运行修改文件 ESLint 和直接相关 Vitest。
- 旧录音 writer/BackgroundTask 文件及其测试在建立新单写后按 R15 删除；不保留为了让旧测试继续通过的兼容写入口。
- 仓库其他产品域仍有实时语音/ASR 和进程内任务代码；实时客户对练明确不在首发，且这些独立产品域不是本切片的顺手清理范围。Slice 8 仅对新人基础训练消费者做最终 dead-code/authority gate。

## 验收证据

| Acceptance Criteria | 实现与针对性证据 |
|---|---|
| 30 分钟/100MB 配置边界 | `AudioCapturePolicySnapshot`/标准包冻结规则；`test_server_enforces_frozen_limits_and_part_layout` 验证后端权威；runner 测试验证前端真实提示 |
| 浏览器内存与刷新恢复 | MediaRecorder 每秒 chunk 串行写 IndexedDB；manifest 以 32 个 chunk 有界批次读取、单 part hash/持久化；hook 测试覆盖暂停/恢复/刷新草稿，完整 Blob 仅显式试听时创建 |
| multipart 中断/续传/取消/清理 | uploader 测试覆盖缺失 part 续传、Abort 保留草稿和 cloud credential；runtime/maintenance 测试覆盖 session 过期、取消、删除失败释放 claim 与重试 |
| 服务端对象完整性 | confirm 与 Worker 两次 HEAD；pipeline 测试覆盖伪造 hash、part layout、完整 size/hash 与受控 key/组织关系 |
| Worker 重启恢复 | 首次执行后用新 `AudioPipelineTaskHandler` 实例从 PostgreSQL 状态重放；同 Invocation/reconcile 只产生一份 Transcript/Score/Outcome |
| Transcript 不可变修订 | governance 测试断言 `automatic → manual_correction → retranscription` 三个 revision，均保留 supersede/Artifact/Invocation lineage |
| 无法评分 ≠ 能力未达标 | 低置信度测试断言 `needs_review`、零 ScoreOutcome/Outcome；UI 显示“不会按零分记录” |
| AI/ASR/存储故障真实失败 | ASR timeout、invalid scoring schema、storage failure 分别落精确 recoverable stage，保留已完成 artifact/Transcript，不伪造分数 |
| Reconcile 幂等 | 相同 task/业务键重放后 Transcript/Score/通用 Outcome 与 Outbox effect 各一份；业务成功只在 reconcile 后投影 |
| Regrade/失效历史 | 人工更正、重转写、重评追加 ScoreOutcomeVersion；preview token/impact hash/idempotency/audit 生效，旧版本不覆盖 |
| 权限与审计 | 实际 playback/regrade route 的跨组织请求返回 404 并在请求组织留下 denied audit；capability projection 测试锁定内容编辑与管理员边界 |
| 旧写链路移除 | 旧同步 service 方法、FastAPI BackgroundTasks、三份进程内 audio task、subtype/重评 writer 路由及前端 client writer 由 clean-cut contract 测试证明不存在 |

## 验证记录

- `python3 ./.trellis/scripts/task.py validate .trellis/tasks/07-16-audio-assessment-durable-pipeline`：通过，`implement.jsonl` 9 项、`check.jsonl` 3 项有效。
- Backend Ruff check + format check（仅 audio 模块、组合根、migration/script 和直接测试）：通过，30 个目标文件已格式化。
- Backend Mypy（`audio_assessment`、AI/audio 组合根、标准包、admin delivery）：通过，20 个 source file 无问题。
- Backend Pytest：31 passed；覆盖 audio clean cut、9 个 durable pipeline/故障/权限/版本测试、2 个媒体测试、标准包、路由、admin capability、AI composition 和 migration。
- Frontend ESLint（audio runner/store/uploader/recorder、auth cleanup、clean-cut test）：通过。
- Frontend Vitest：6 files / 25 tests passed；覆盖录制草稿、续传、runner 状态、accessible cancel、terminal/missing-draft recovery、logout cleanup 和旧 client writer 退役。
- Targeted strict TypeScript：使用临时范围 `tsconfig.audio-check.json`（已删除）检查上述 audio/auth 入口及测试，通过；没有读取历史 `.next*` 生成声明。
- CodeGraph：`AudioAssessmentRunner` 影响 Activity Shell 与本地测试，`useBrowserAudioRecorder` 影响 runner/shell/测试，均已纳入 Vitest；未跟踪的新 backend 模块未进入现有 CodeGraph 索引，未自行重建用户索引。

## 未验证与后续门禁

- 未在目标云环境调用真实 OSS/COS、DashScope ASR 或正式 LLM；Gold Set、shadow/canary、Provider 成本/延迟与正式路由 readiness 是 Slice 6 ReleasePlan + Slice 8 发布门禁，当前 Fake/contract 测试不能冒充。
- 未在本切片运行完整 Playwright、真实 30 分钟/100MB 浏览器负载、p95 90 秒 SLO、全量构建或发布回滚演练；按父任务测试约束统一留给 Slice 8。
- 统一管理员录音工作台和 Team 范围培训负责人 UI/权限投影由 Slice 5/6 完成；当前平台管理员只在组织范围内使用本切片的队列/治理 API，普通 `training_manager` 在缺少 Team scope 权威时保持 fail closed。
- 全库空库 Alembic 与全量 TypeScript 的历史阻塞见上文；本切片不恢复已删除 migration，也不恢复退役 Module 页面。

## 风险、发布与回滚

- 风险等级：P1（大文件、敏感员工训练数据、AI/ASR、跨模块 Outcome 回流）。
- 发布：migration → API → 独立 audio Worker → 未完成上传 Cron → Prompt/model/provider readiness → 按两个 Activity flag 分范围启用。
- 降级/回滚：关闭 `NEWCOMER_AUDIO_ASSESSMENT_ENABLED` / `NEWCOMER_ASYNC_ASSIGNMENT_ENABLED` 和新 enqueue；让在途任务完成或协作取消；保留数据库、Artifact、Transcript、Score/Outcome 和审计，只读历史继续可用；禁止重新开启旧同步/BackgroundTask writer，生产不执行破坏性 downgrade。
