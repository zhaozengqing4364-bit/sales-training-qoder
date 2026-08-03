# 验收矩阵

> 历史状态：2026-07-18 曾标记全部关闭。2026-07-20 复核确认该结论准确覆盖 Foundation 运行时与 Seed 闭环，但错误扩大为“管理员真实内容生产与 Legacy 迁移也已闭环”；原证据不删除，勘误和重新打开项见第 18 节。

## 1. Product Flow

| 场景 | 验收 | 证据 |
|---|---|---|
| 新人首次进入 | 只看到一个训练主入口和一个主操作 | [E-FLOW] |
| 已分配 Cohort | 自动定位冻结路径修订和当前任务 | [E-FLOW] [E-JOURNEY] |
| 无 Enrollment | 显示可理解状态；管理员可在当前流程分配 | [E-FLOW] [E-ADMIN] |
| 正常完成路径 | 学习、测验、录音、Coach、情景录音、复核完整通过 | [E-FLOW] |
| 未达标 | 显示薄弱能力、来源证据和明确补练 | [E-READINESS] |
| 复核完成 | 生成可追溯 `foundation_ready` 或未达标结论 | [E-READINESS] |
| Realtime | 首发学员路径、导航和配置中不可见 | [E-FLOW] [E-ARCH] |

## 2. Journey And Versioning

本节全部条目由 [E-JOURNEY] 验证。

- [x] PathRevision 发布后不可变。
- [x] Enrollment 不随新版自动迁移。
- [x] 显式迁移展示差异、受影响 Attempt 和审计原因。
- [x] Attempt 冻结 ActivityDefinition 和所有资源修订。
- [x] 技术重试不增加学习 Attempt。
- [x] 学习重试创建新 Attempt。
- [x] 同一幂等键只创建一个逻辑写入。
- [x] 并发开始同一活动不会生成重复 attempt_no。

## 3. Learning And Question Governance

本节全部条目由 [E-CONTENT] 验证。

- [x] 原始资料和精编内容可分别查看与版本化。
- [x] AI 不能直接修改原始资料。
- [x] 单章和多章出题都通过持久化任务。
- [x] 候选题保存来源片段、能力、Prompt、模型和批次。
- [x] 非法 AI 输出不写入候选表。
- [x] 未审核候选题不能进入试卷。
- [x] 重复题提示差异，不自动删除。
- [x] 来源更新使工作题 stale，阻止新发布。
- [x] 红线题和 AI 简答评分题有训练管理员复核。
- [x] 发布失败不产生部分题目生效。

## 4. Quiz

本节全部条目由 [E-QUIZ] 验证。

- [x] 客观题规则判分稳定可复现。
- [x] 简答题提交后立即保留答案并进入后台评分。
- [x] AI 评分失败不会丢失答案或生成固定分数。
- [x] 评分完成后 Attempt 通过事件自动 reconcile。
- [x] 总分和红线题规则均满足才通过。
- [x] 题目顺序、答案和评分合同冻结。
- [x] 三次尝试抽题重复率符合配置。

## 5. Audio

本节全部条目由 [E-AUDIO] 验证。

- [x] 浏览器使用单一麦克风流。
- [x] 录音支持试听、重录、文件上传和续传。
- [x] 服务端确认前本地草稿不会删除。
- [x] 100MB / 30 分钟边界有正向和拒绝测试。
- [x] 文件魔数、解码、静音、削波、时长和恶意文件校验存在。
- [x] 原始文件和标准化文件哈希可追溯。
- [x] 上传确认 2 秒目标不受 ASR/评分耗时影响。
- [x] 转写有分段时间、Provider、模型和置信度。
- [x] 低置信度不会直接正式评分。
- [x] AI 每个维度提供时间证据、理由和置信度。
- [x] 总分由领域规则计算。
- [x] 音频质量失败不算能力失败。
- [x] 转写校正和重评追加版本。
- [x] 重评影响已确认结论时重新打开复核。

## 6. AI Coach

本节全部条目由 [E-COACH] 验证。

- [x] Coach 显示当前目标、薄弱点和卡片，而不是空白聊天。
- [x] 每次最多一张活动卡。
- [x] 学员回答在调用模型前已经保存。
- [x] 刷新或断网后可以恢复会话。
- [x] Prompt / Schema 缺失明确失败。
- [x] 不允许的卡片类型被后端拒绝。
- [x] 掌握度由冻结 Rubric 和领域规则计算。
- [x] 达到补练上限后进入人工复核。
- [x] AI 失败保留输入和重试位置。
- [x] 正式总结持久化到 Session / Outcome，不只在消息中。

## 7. Evidence And Readiness

本节全部条目由 [E-READINESS] 验证。

- [x] Evidence 追加式保存且有 source/lineage/confidence。
- [x] Dossier 使用最新有效证据、完整性和趋势。
- [x] 低置信度或 degraded 证据不能单独达标。
- [x] AI 初评与人工结论清晰区分。
- [x] 人工校准不覆盖 AI 历史。
- [x] 批量确认只对满足风险策略的学员开放。
- [x] 复核冲突使用 expected revision。
- [x] 重练任务绑定能力、来源证据和目标。
- [x] 重练前后对比可见。
- [x] 学员申诉有状态、处理人和结论。

## 8. Admin

本节全部条目由 [E-ADMIN] 验证。

- [x] `/admin/newcomer-training` 首页按待处理任务组织。
- [x] 路径编辑器三栏结构，主操作唯一。
- [x] 缺资源时当前页面快速创建和绑定。
- [x] 快建失败保留输入和上下文。
- [x] 发布页展示依赖、阻塞、影响和回滚。
- [x] 内容审核工作台支持来源、候选、质量三栏。
- [x] Cohort 可创建、分配、暂停、取消和查看进度。
- [x] 经理列表支持 URL 筛选、分页和批量处理。
- [x] 权限不足不加载敏感数据，也不伪装为空列表。

## 9. UI States

每个异步页面根据适用性覆盖以下状态；证据为 [E-UI]。

- [x] default / idle；
- [x] loading；
- [x] first-use empty；
- [x] filtered no-result；
- [x] submitting / executing；
- [x] partial success；
- [x] recoverable failure；
- [x] non-recoverable failure；
- [x] permission denied；
- [x] stale / conflict；
- [x] cancelled / interrupted；
- [x] offline / degraded；
- [x] background task pending；
- [x] success with persistent result。

## 10. Accessibility And Responsive

本节全部条目由 [E-A11Y] 的真实浏览器审计验证。

- [x] 核心流程全键盘可完成。
- [x] 焦点可见，Dialog/Drawer 进入与返回正确。
- [x] 表单 Label、错误和说明关联。
- [x] 图标按钮有 accessible name。
- [x] 状态不只依赖颜色。
- [x] 200% 缩放可完成任务。
- [x] 学员端 360px 宽度无横向关键内容丢失。
- [x] 长中英文、长文件名和大分值不破版。
- [x] 管理表格提供响应式布局或明确横向滚动。

## 11. Permission Matrix

| 角色 | 允许 | 禁止 |
|---|---|---|
| Learner | 自己的 Enrollment、Attempt、Dossier、Appeal | 他人数据、配置、发布 |
| Content Editor | 内容、候选题、工作修订 | 学员敏感记录、最终发布 |
| Training Admin | 路径、Cohort、Release、评分规则 | 系统密钥、越组织数据 |
| Training Manager | 负责团队档案、复核、重练 | 内容 Prompt、系统配置 |
| System Admin | 系统配置、Provider、任务诊断 | 无审计的高风险修改 |

所有角色的正向、越权、缺少 Team 关系和跨组织测试由 [E-PERMISSION] 验证。

## 12. Security

本节全部条目由 [E-SECURITY] 验证。

- [x] 音频、转写、评分访问有对象级权限。
- [x] 签名 URL 短时有效且不暴露长期公开地址。
- [x] 文件上传验证真实内容，不只看 MIME。
- [x] Prompt Injection 内容隔离并经过 Schema 验证。
- [x] Provider 输入遵守允许清单。
- [x] 日志不含密钥、完整音频、完整转写和敏感个人数据。
- [x] 下载、导出、重评、人工结论和批量操作留审计。
- [x] 高风险操作有预览、原因和确认。

## 13. Performance

本节全部条目由 [E-PERFORMANCE] 的固定数据集和真实浏览器基线验证。

- [x] Journey 首屏 p75 ≤ 2s。
- [x] 普通 API p95 ≤ 500ms。
- [x] Journey 列表 Query 数不随行数线性增长。
- [x] AI Coach ≤ 1.5s 显示运行反馈。
- [x] Audio Finalize ≤ 2s 返回。
- [x] Audio pipeline p95 ≤ 90s。
- [x] Dossier base projection ≤ 2s。
- [x] 100 人在线、20 上传、20 AI Job 压测无状态丢失。
- [x] 管理端 10,000 Attempt 分页、筛选和排序由服务端执行。

## 14. Observability

本节全部条目由 [E-OBSERVABILITY] 验证。

- [x] Request/Task/Event trace 可串联。
- [x] Task queue depth、lease timeout、retry、dead letter 有指标。
- [x] ASR 低置信度、AI invalid schema、Provider timeout 有指标。
- [x] Review backlog、remediation count 和 stale content 有业务指标。
- [x] capability health 能区分未配置、降级和不可用。
- [x] 重要失败有用户结果位置和管理员诊断位置。

## 15. Architecture

本节全部条目由 [E-ARCH] 验证。

- [x] 无跨模块 ORM 查询。
- [x] 无新增未声明跨包依赖。
- [x] SCC 不扩大。
- [x] 无字符串动态 Handler 导入。
- [x] 无业务模块直接 Provider SDK 调用。
- [x] 无 Controller 混合权限、事务、数据库和外部调用。
- [x] 无重复状态机和重复业务权威。
- [x] 新共享抽象有至少两个真实消费者或明确平台合同。

## 16. Automated Verification

Backend（全部见 [E-AUTOMATION]）：

- [x] Ruff。
- [x] Mypy。
- [x] Unit。
- [x] PostgreSQL integration。
- [x] API contract。
- [x] Alembic head / check。
- [x] Architecture dependency guard。
- [x] OpenAPI parity。

Frontend（全部见 [E-AUTOMATION] [E-A11Y]）：

- [x] TypeScript。
- [x] ESLint。
- [x] Vitest。
- [x] Production build。
- [x] Playwright learner core。
- [x] Playwright admin publish。
- [x] Playwright manager review。
- [x] A11y checks。

Provider（全部见 [E-AI]）：

- [x] Fake scenarios。
- [x] ASR gold set。
- [x] Scoring gold set。
- [x] Prompt/model shadow。
- [x] Provider staging smoke。

初始首发没有“已发布旧模型 vs 候选升级模型”，因此实际双版本 shadow 对比为不适用项而非缺口；升级合同、同 manifest 对比、阈值和阻断规则已冻结并测试，未来出现候选版本时必须先 shadow/canary。ASR 使用版本化确定性 ASR contract 与音频流水线故障/置信度集合；真实生成式能力由 12 次受治理 Provider 调用单独校准。

## 17. Final Release Evidence

本节全部条目由 [E-RELEASE] 验证。

- [x] 一键 reset/seed/start/verify 可在干净环境运行。
- [x] 一个新学员从分配到 `foundation_ready` 的真实或 deterministic E2E 证据。
- [x] 一个未达标、补练、重试、人工复核的 E2E 证据。
- [x] 一个上传中断、续传、ASR 失败、评分重试的 E2E 证据。
- [x] 一个 Prompt/题目/路径发布失败且旧版本仍有效的证据。
- [x] 一个跨组织越权被拒绝的证据。
- [x] Rollback runbook 实际演练记录。

## Evidence Index

### E-FLOW

- `backend/tests/e2e/test_foundation_closed_loop.py`：管理员安装标准包、Cohort/Enrollment、五类 Activity、Evidence/Dossier 与人工 `foundation_ready` 的确定性跨域闭环。
- `web/tests/e2e/newcomer-training-closed-loop.spec.ts`、`newcomer-training-learner.spec.ts`、`newcomer-training-admin.spec.ts`：唯一入口、冻结修订、单一下一步、统一管理端和 Realtime 缺席；最终 Playwright 证据见 `.sisyphus/evidence/task-9-playwright-report.html`。

### E-JOURNEY

- `backend/tests/unit/newcomer_training/test_path_contracts.py`、`test_enrollment_freeze.py`、`test_activity_attempts.py`、`test_activity_application.py`、`test_journey_projection.py`、`test_release_plan.py`。
- `.sisyphus/evidence/changed-coverage-report.json`：上述五个 Foundation 核心权威模块的关键分支 floor 全部 100%，无 violation。

### E-CONTENT

- `backend/tests/unit/learning/test_source_question_governance.py`、`test_task_definitions.py`、`test_quiz_runtime.py`、`backend/tests/unit/newcomer_training/test_foundation_question_generation.py`。
- `web/src/components/admin/newcomer-training/content-workspace.test.tsx` 与 `question-review-workspace.test.tsx`。

### E-QUIZ

- `backend/tests/unit/learning/test_quiz_runtime.py`、`backend/tests/unit/newcomer_training/test_activity_application.py` 与 `backend/tests/e2e/test_foundation_closed_loop.py`。
- `web/src/components/newcomer-training/activity-runners/quiz-runner.test.tsx`。

### E-AUDIO

- `backend/tests/unit/audio_assessment/test_durable_pipeline.py`、`test_media.py`、`test_audio_clean_cut.py`、`backend/tests/migrations/test_audio_assessment_migration.py`。
- `web/src/components/newcomer-training/activity-runners/audio-assessment-runner.test.tsx`、`browser-audio-uploader.test.ts`、`use-browser-audio-recorder.test.ts`。
- `.sisyphus/evidence/foundation-capacity-baseline.json`：20 并发 finalize p95 `307.36ms`，确定性完整 pipeline p95 `1323.84ms`，无状态丢失。

### E-COACH

- `backend/tests/unit/ai_coach/test_contracts_and_registration.py`、`test_runtime_pipeline.py`、`test_clean_cut.py`。
- `web/src/components/newcomer-training/activity-runners/coach-runner.test.tsx`。

### E-READINESS

- `backend/tests/unit/readiness/test_competency_readiness.py`、`backend/tests/integration/test_foundation_readiness_api.py`、`backend/tests/migrations/test_competency_readiness_migration.py`。
- `web/src/app/admin/newcomer-training/reviews/**.test.tsx` 与 `web/src/components/newcomer-training/readiness-dossier-view.test.tsx`。

### E-ADMIN

- `backend/tests/unit/newcomer_training/test_admin_api.py`、`test_admin_permissions.py`、`test_release_plan.py`。
- `web/src/components/admin/newcomer-training/{v2-path-editor,activity-resource-drawer,content-workspace,question-review-workspace,cohort-detail-workspace,assessment-operations-workspace,release-workspace}.test.tsx`。
- `web/tests/e2e/newcomer-training-admin.spec.ts`。

### E-UI

- `web/src/lib/newcomer-training/view-models.test.ts`、`errors.test.ts`、Journey/Activity/Task/Notification/Dossier 和管理工作台组件测试。
- 全量 Vitest：`201 files / 1148 passed / 6 skipped`；Playwright Foundation 页面全部通过。

### E-A11Y

- `web/tests/e2e/newcomer-training-audit-helpers.ts`、`newcomer-training-learner.spec.ts`、`newcomer-training-admin.spec.ts` 覆盖桌面、360px、200% zoom、键盘、焦点、长文本、accessible name 与横向溢出。
- 报告：`.sisyphus/evidence/task-9-playwright-report.html`。

### E-PERMISSION

- `backend/tests/unit/newcomer_training/test_admin_permissions.py`、`backend/tests/integration/test_newcomer_training_path_rbac_api.py`、`backend/tests/integration/test_foundation_readiness_api.py`、`backend/tests/integration/test_practice_session_object_permissions.py`。

### E-SECURITY

- `backend/tests/unit/audio_assessment/test_media.py`、`backend/tests/unit/ai_platform/test_provider_contracts.py`、`backend/tests/unit/readiness/test_competency_readiness.py` 与对象权限测试。
- `.sisyphus/evidence/secret-scan-report.json`：723 文件扫描通过；最终门禁同时验证安全错误信封、审计和跨组织拒绝。

### E-PERFORMANCE

- `.sisyphus/evidence/foundation-capacity-baseline.json`：1,000 学员/Enrollment、10,000 Attempt、100 并发 Journey、20 上传、20 AI Job；Journey p75 `1514.17ms`、管理页 p95 `496.14ms`、AI 入队 p95 `130.84ms`、Dossier `46.76ms`，全部通过。
- `web/tests/e2e/newcomer-training-performance.spec.ts`：真实浏览器首屏与 API SLO。

### E-OBSERVABILITY

- `backend/tests/unit/ai_platform/test_observability.py`、`backend/tests/unit/test_observability_metrics.py`、`backend/tests/integration/test_observability_surfaces.py`。
- `docs/setup/foundation-operations-runbook.md` 与 `backend/tests/contract/test_foundation_operations_runbook.py`：指标、阈值、责任、处置卡和恢复验证合同。

### E-ARCH

- `backend/scripts/architecture_dependency_guard.py --check` 在最终门禁通过；机器政策见 `docs/architecture/newcomer-foundation-guard-policy.yaml`。
- `backend/tests/unit/test_release_readiness.py`、运行时 OpenAPI parity、Legacy import/route clean-cut tests 与 `.sisyphus/evidence/changed-coverage-report.json`。

### E-AUTOMATION

- `.sisyphus/evidence/task-9-quality-gate.txt`：Ruff、Architecture Guard、OpenAPI、Gold Set、Mypy 769 文件、Backend Unit+Contract `3432 passed / 1 skipped`、Web typecheck/lint、Vitest、production build、21 条 Playwright、Integration+E2E `530 passed / 56 skipped`、容量和 changed coverage 全部通过。

### E-AI

- `.sisyphus/evidence/foundation-ai-gold-set.json`：8 个用例，Schema/拒绝/依据/降级/稳定性均 `1.0`，事实错误与越界引用均 `0.0`。
- `.sisyphus/evidence/foundation-ai-real-provider-staging.json`：6 个接受用例各重复 2 次，共 12 次受治理真实调用全部成功；报告整体 `status=passed`。
- `backend/tests/unit/ai_platform/test_asr_contract.py`、`test_foundation_ai_quality_gate.py`、`test_foundation_ai_provider_staging.py` 与 `docs/ai-governance.md`。

### E-RELEASE

- `.sisyphus/evidence/foundation-reset-rehearsal.json`：随机 disposable PostgreSQL 数据库双循环 reset/seed/verify，`status=passed`、`database_removed=true`。
- `backend/tests/integration/newcomer_training/test_foundation_release_migration.py`：空库、指定旧基线 downgrade/upgrade、重复 upgrade/seed 与保留基线权限。
- `backend/tests/e2e/test_foundation_closed_loop.py` 及 Audio/Coach/Readiness/ReleasePlan 故障、补练、申诉、跨组织场景测试。
- `backend/tests/unit/newcomer_training/test_release_plan.py`、`docs/setup/foundation-release-runbook.md`、`docs/setup/foundation-operations-runbook.md`：旧版本保活、显式 rollback、Projection rebuild 与不删除用户证据。

[E-FLOW]: #e-flow
[E-JOURNEY]: #e-journey
[E-CONTENT]: #e-content
[E-QUIZ]: #e-quiz
[E-AUDIO]: #e-audio
[E-COACH]: #e-coach
[E-READINESS]: #e-readiness
[E-ADMIN]: #e-admin
[E-UI]: #e-ui
[E-A11Y]: #e-a11y
[E-PERMISSION]: #e-permission
[E-SECURITY]: #e-security
[E-PERFORMANCE]: #e-performance
[E-OBSERVABILITY]: #e-observability
[E-ARCH]: #e-arch
[E-AUTOMATION]: #e-automation
[E-AI]: #e-ai
[E-RELEASE]: #e-release

## 18. 2026-07-20 Authoring 验收勘误

本节是对历史结论的补充审计，不撤销已经通过的运行时、版本冻结、ReleasePlan、权限和学员执行证据。以下项目必须改为“运行时已具备、Authoring 未闭环”并由新父任务重新验收：

| 原结论 | 2026-07-20 真值 | 状态/后续任务 |
|---|---|---|
| “缺资源时当前页面快速创建和绑定” | 前端完整快建主要覆盖 LearningUnit/Quiz；AudioMaterial、ScoringScheme、CoachProfile、Scenario 没有全部形成可恢复快建闭环 | 重新打开：`07-19-foundation-path-inflow-binding-preview` |
| “内容审核工作台支持来源、候选、质量三栏”及 Learning 全部关闭 | 现有文字 Source/Unit 与 AI Candidate 运行可用；PPT/PPTX、Demo 视频/链接、讲解稿、示范音频、完整手工/导入题库和 Quiz 编排尚未形成管理员全生命周期 | 重新打开：`07-19-foundation-multimedia-content-assets`、`07-19-foundation-question-bank-quiz-authoring` |
| “统一管理端完成配置、审核、运营、发布和回滚” | 单一入口与 ReleasePlan 已实现；录音材料/评分、Coach Profile、异步场景主要来自 Seed，Training Admin 缺少完整 CRUD；角色过滤还会让功能看起来消失 | 重新打开：`07-19-foundation-audio-scoring-authoring`、`07-19-foundation-ai-coach-authoring`、`07-19-foundation-async-scenario-authoring`、`07-19-foundation-admin-ia-capabilities` |
| “旧权威清理完成” | v2 运行时不再以 Legacy 为新人写权威；但用户真实 `石犀ppt讲解`、`demo讲解` 和 PPT 仍在 Legacy，尚未迁入新学员路径 | 重新打开：`07-19-foundation-legacy-migration-cutover` |
| “最终 E2E 已证明管理员可从零配置真实训练内容” | E2E 证明标准包与运行时闭环，未证明管理员无需 Seed/Legacy/数据库即可创建 PPT/Demo、题库、评分、Coach 和场景 | 重新打开：`07-19-foundation-authoring-e2e-closure` |

新的权威边界见 [`docs/adr/2026-07-20-foundation-authoring-and-legacy-migration-authority.md`](../../../../../docs/adr/2026-07-20-foundation-authoring-and-legacy-migration-authority.md)，父任务见 [`07-19-newcomer-training-content-authoring-closure`](../../../07-19-newcomer-training-content-authoring-closure/prd.md)。后续验收必须提供真实管理员 CRUD、浏览器流程、失败恢复、组织/权限和 ReleasePlan 证据；路由存在、Seed 成功、资源 option 可列出或组件静态渲染均不足以重新勾选。
