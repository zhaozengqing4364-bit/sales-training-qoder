# Implementation Notes

## Assumptions

- 当前 `codex/newcomer-training-v0-9-closure` 是本 Goal 的功能分支。
- 当前普通 checkout 不是 linked worktree；由于 Goal 指定当前工作树为权威且存在必须保留的用户修改，选择原地执行，不创建第二工作树。
- 普通 CI 使用 Fake/local Provider；真实 StepAudio 仅走已有受控门禁。

## Protected Existing Changes

- `docs/superpowers/plans/2026-07-10-readiness-decision-integrity.md`：用户既有修改，禁止纳入本任务提交。

## Deviations

- Task 2：默认 SQLite 开发库从空库执行完整 Alembic 历史链时，既有 `001` 迁移因
  `practice_sessions` 不存在而失败，尚未运行到本次 `092`。本次以 ORM 元数据真实建表、
  SQLite schema 反射、迁移脚本静态契约和专项测试验证 `092`；完整迁移链问题保留到
  Task 15 reset/seed 闭环，不静默忽略。

## Verification Evidence

- Baseline：旧路径配置专项 `22 passed`。
- Task 1 RED：新测试因 `sales_trainer.orchestration` 不存在而 collection error，符合功能缺失预期。
- Task 1 GREEN：`14 passed`。
- Task 1 Ruff：`All checks passed!`。
- Task 1 Mypy：`Success: no issues found in 4 source files`。
- CodeGraph 尚未索引新文件，`impact` 无法识别；新包当前只有新增测试调用，无既有共享调用者。
- Task 2 RED：repository 模块不存在，collection error，符合功能缺失预期。
- Task 2 GREEN：repository + schema 反射 `4 passed`。
- Task 2 Ruff：`All checks passed!`。
- Task 2 Mypy：`Success: no issues found in 1 source file`。
- Task 2 Alembic：默认空 SQLite 的既有历史链在 `001` 失败，未触达 `092`；错误为
  `no such table: practice_sessions`，已纳入最终 reset/seed 验证项。
- Task 3 RED：revision service 模块不存在，collection error，符合功能缺失预期。
- Task 3 GREEN：修订服务与管理 API `4 passed`；assignment-only 路径完成草稿、校验、发布闭环。
- Task 3 资源校验：按资源类型批量读取 LearningContent、ExamPaper、Material、
  PracticeTemplate、VoiceRuntimeProfile 与通用发布 revision；无逐活动查询。
- Task 3 权限与审计：内容管理员可编辑、平台管理员可发布；草稿、发布、恢复、删除均写操作日志。
- Task 3 Ruff：`All checks passed!`；Mypy：`Success: no issues found in 8 source files`。
- Task 4 RED：registry、activities 包缺失导致两个 collection error。
- Task 4 GREEN：封闭六类型注册表、统一执行上下文/投影协议、模块/阶段/路径纯函数聚合，`4 passed`。
- Task 4 Ruff 与 Mypy 均通过；配置不能触发动态 import，未知类型使用稳定错误码拒绝。
- Task 5：Lesson 复用 LearningProgress，发布内容不可用时显式失败；完成章节后写统一 attempt 并关联学习证据。
- Task 5：Quiz 在 pinned ActivityExecutionContext 下校验 paper/learner 范围，绕开旧新人路径先修条件，冻结路径 revision/module/activity 快照并关联 quiz attempt。
- Task 5 受影响回归：lesson、quiz 与旧通用 paper 测试共 `15 passed`；Ruff、Mypy 通过。
- Task 6：录音活动直接冻结 rubric 发布 revision、确认材料版本、路径 revision、enrollment 与 activity 快照，不构造 SalesTrainerUnit。
- Task 6：作业附件采用 MIME 白名单、大小限制、安全文件名、SHA-256 元数据；支持 local/COS，业务记录不保存文件字节。
- Task 6 偏差：保留无 unit/context 的通用音频工具上传，但它不携带训练快照、不能推进新人活动；新人训练只有 execution_context 可形成证据。
- Task 6 状态契约补充 `needs_review`，与 manual_review 作业语义一致；专项及通用 audio 回归 `33 passed`，Ruff、Mypy 通过。
- Task 7：AI Coach 新会话从发布的 coach profile revision 与 pinned activity 创建，冻结 profile revision 和完整 activity context。
- Task 7：StepAudio start 公共服务已直接要求 ActivityExecutionContext/client_token，校验 learner、已发布 PracticeTemplate、启用 VoiceRuntimeProfile 与 provider readiness，external binding owner 为 `newcomer_training`。
- Task 7：旧 AI Coach 路由内部仍有待 Task 14 删除的 module-key 代码，但新 activity handler/runtime 不读取它；最终 legacy authority 搜索必须归零后才可闭环。
- Task 7 focused/realtime 回归 `7 passed`；Ruff、Mypy 通过。旧 realtime 测试已按批准的新 activity contract 改写，保留类型、范围、模板和 runtime 失败断言。
- Task 8 RED：canonical journey service 不存在导致 collection error。
- Task 8：首次读取固定 active revision 到 enrollment；后续发布不改变历史路径。服务端统一投影阶段/模块/活动状态，只标记一个主下一步，required 完成后可推荐 optional。
- Task 8：新增 canonical learner journey/detail/action API；所有写入重新解析 pinned context 并由六类 handler 执行。
- Task 8：统一 attempt 快照补齐 enrollment/path revision/phase/module 上下文；TrainingRecordService 支持 activity_id/type/phase/module 过滤和冻结标题投影。
- Task 8 focused + readiness regression + activity records 共 `15 passed`；Ruff、Mypy 通过。
- Task 8 未关闭项：ReadinessDossier 与旧 admin journey 仍引用将在 Task 9 删除的 TrainingJourneyService；Step 5 保持未勾选，必须在固定后端权威删除时改为 orchestration projection 后再关闭。
- Task 9：seed 直接生成三阶段、产品 A/B/标准 Demo 与六类代表活动，默认执行幂等 seed，`--verify-only` 只读验证；专项 `3 passed`。
- Task 9：reset 仅作用于新人编排 enrollment/attempt 与三种新人路径 revision resource type，支持 dry-run、确认词与异常回滚；专项 `2 passed`。
- Task 9：Readiness 与 TrainingRecord 统一使用冻结的 `activity_id/activity_type/phase/module` 身份；能力项从 attempt result snapshot 投影，复核决定追加审计记录且不覆盖 attempt。
- Task 9：录音与考试重评通过统一 activity attempt 的 evidence 反查对象范围，历史重评继续追加 evidence，不恢复旧 record authority；受影响集成测试 `2 passed`。
- Task 9：删除固定路径、专题、商务礼仪、旧 AI Coach chat 与旧 dashboard/journey authority 及其过期测试；保留 LearningContent、ExamPaper、材料、评分、revision、StepAudio 与统一 AI Coach session 引擎。
- Task 9 结构检查：`CANONICAL_NEWCOMER_MODULE_KEYS|business_etiquette|customer_faq|company_product_demo|business_skills` 在 `backend/src/sales_trainer` 运行时代码中零命中；应用 composition root 可导入。
- Task 9 后端新人回归：`84 passed`；Ruff 全通过；Mypy `Success: no issues found in 116 source files`。
