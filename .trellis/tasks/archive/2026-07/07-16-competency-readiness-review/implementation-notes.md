# 切片 5 实施记录

## 页面与业务契约

- 目标用户：新人学员、具有明确 Team 范围的培训负责人、平台管理员。
- 主流程：活动 Outcome → 不可变能力证据 → 达标档案/冻结快照 → 人工决定 → `foundation_ready`；未满足时在档案内安排补练，学员完成后重新评估；学员可对事实、评分或决定提出申诉。
- 工作对象：Canonical Competency Revision、Competency Mapping、Competency Evidence、Readiness Dossier/Snapshot、Review Decision、Retraining Assignment、Appeal、Calibration Session。
- 页面模型：学员使用只读档案与申诉入口；培训负责人使用风险/等待时间排序的队列和档案审批工作区。
- 主操作：学员“继续训练/提交申诉”；培训负责人“记录复核决定”或“安排补练”。正式决定和补练结果必须持久化，不以 Toast 作为唯一记录。
- 状态：loading、empty、partial、permission denied、stale/conflict、submitting、retrying、success/error 均由稳定 API 状态或错误码驱动。

## 唯一写权威

- `competency_evidence`：唯一写 Canonical Competency、Mapping、Evidence 与 Evidence validity history。
- `readiness`：唯一写 Dossier、Snapshot、ReviewDecision、RetrainingAssignment、Appeal、CalibrationSession 与 AI Summary draft。
- `readiness` 同时唯一写例外批准影响预览；预览绑定 Reviewer、Dossier/Snapshot/version、能力/证据引用、理由和 15 分钟有效期，confirm 只能消费完全相同的 impact hash。
- `newcomer_training`：继续唯一写 Enrollment、Attempt、ActivityOutcome；不导入 Evidence/Readiness ORM。
- 应用组合根仅通过稳定 Port/Event 把 Outcome 投影到 Evidence，再通知 Readiness；活动域不跨模块写表。
- 旧 `sales_trainer.services.readiness_dossier_service` 不是目标权威；本切片切换为 readiness 适配 API，兼容 URL 仅保留到切片 6 的管理 UI 切换。

## 数据、API、权限与状态影响

- 数据：新增修订化能力目录、追加式证据/有效性历史、版本化档案快照、不可变人工决定、补练、申诉、校准和审计表；迁移向下只删除本切片新增表。
- API：实现学员 `/newcomer-training/dossier`、`/dossier/appeals`；管理 `/admin/newcomer-training/reviews*`，正式写入使用冻结合同中的 `/commands/record-decision` 和 `/commands/assign-retraining`。旧 readiness URL 仅保留同一写权威的有界只读别名，待清理切片删除。
- 例外批准使用 `/commands/preview-exception` 先持久化影响预览，再由 `/commands/record-decision` 携带 preview token、impact hash 和明确确认；版本、快照、理由或引用变化均拒绝并审计。
- 权限：学员仅本人；培训负责人仅显式 Team membership 范围；平台管理员组织内不受 Team 限制。内容管理员不因内容权限获得复核权。所有跨组织/越权决定、导出与申诉处理拒绝并审计。
- 状态：Dossier 遵循 `projecting → incomplete|ready_for_review → under_review → decided`，新有效 Evidence 使受影响快照 `stale` 并重新开放；Decision 追加并 supersede，不覆盖旧记录。

## 成功标准

- 七项首发标准能力采用标准包已冻结键：`product_knowledge`、`customer_understanding`、`needs_discovery`、`value_expression`、`objection_handling`、`process_compliance`、`communication_structure`。
- 每个终态 ActivityOutcome 幂等投影 Evidence；技术失败、无法评分、低质量、处理中或非法结果不参与正式 Gate。
- Regrade 追加新 Outcome/Evidence 并 supersede 旧证据；Dossier 增量与 rebuild 收敛。
- 有效 Snapshot 上只有受权人工 Reviewer 可授予 `foundation_ready`。
- 正常达标与例外批准是不同决定；例外必须在当前档案内完成影响预览和二次确认，不能只提交确认布尔值。
- 补练可在档案内选择当前发布活动或创建待治理的最小草稿；完成已发布活动补练后自动更新档案。
- 申诉与重评保留原决定并显式 stale/reopen。
- AI Summary 无引用、Schema 非法或调用失败不阻塞确定性复核。

## 最小验证范围

- 后端：新增 Evidence/Readiness policy、服务、API、权限、并发/幂等/重建/重评针对性单元与集成测试；修改文件 Ruff/Mypy。
- 前端：新增 dossier ViewModel/页面、API domain 和既有 readiness 兼容页面相关 Vitest；修改文件 ESLint 与目标 TypeScript 检查。
- 数据：迁移静态/升级-降级结构检查；若本地缺少 Alembic CLI 或真实 PostgreSQL，仅记录未验证项，留切片 8 做全量门禁。
- 不运行全量 pytest、全量 Vitest、全量构建或全项目格式化；切片 8 才执行完整发布门禁。

## 回滚

- 功能降级：暂停新复核命令和 Evidence consumer；保留旧 Decision/Evidence，不删除历史。
- 数据回滚：降级本切片 Alembic revision 删除新增表；若已有正式决定，优先部署前一版本并禁写，不直接降级删除业务历史。
- UI/API：切片 6 完成前兼容 URL 可切回只读；不得恢复 legacy OperationLog 作为正式决定写权威。

## 假设与已确认偏差

- 父任务早期决策日志使用“表达清晰度”等用户语言，切片 2 已冻结的标准包和本切片 PRD 使用“产品知识”等七项正式键；按更具体且已进入 PathRevision 的标准包身份实施，并为展示保留用户语言说明，不额外建立第二套全局能力。
- Realtime 客户语音对练明确不在本切片。
- 快速创建的补练对象先保存为与档案绑定的最小待治理草稿；只有已发布 ActivityDefinition 可由学员执行。此约束避免 Reviewer 绕过发布治理。
- AI Summary 是可选辅助；确定性档案始终可用。
- 学员安全投影在后端移除内部风险、Reviewer 私密备注、原始 AI 草稿、Evidence source refs/lineage；不能只依赖前端“不渲染”来保护敏感字段。

## 历史问题与未纳入范围

- CodeGraph 尚未索引切片 1～4 的新模块；本切片不重建索引，先用 CodeGraph 分析已索引 legacy 影响，再读取当前磁盘源码核对新链路。
- 本地 Playwright Chromium 在切片 4 因缺少 `libnspr4.so` 无法启动；不安装系统依赖，实际渲染总门禁留切片 8。
- 旧 Phase/Module DTO、Realtime 类型和统一管理工作区清理分别属于切片 6～8，不在本切片顺手处理。
- SQLite 针对性测试覆盖 expected version、重复决定和两个 Reviewer 的冲突顺序，但不冒充真实 PostgreSQL 并发事务证据；PostgreSQL 竞争写、完整浏览器 E2E、性能和发布回滚演练留切片 8 最终门禁。

## 偏差日志

- 初始管理 API 草案曾使用 `/decisions`、`/retraining` 子资源路径；核对冻结 `newcomer-training-v2` 合同后，在产生外部消费者前改回 `/commands/record-decision`、`/commands/assign-retraining`，没有保留第二套写路由。
- 初始例外决定只带 `exception_confirmed` 布尔值，不能证明 Reviewer 看过同一份影响。核对父任务冻结状态机后，改为持久化短期 preview token + impact hash，并在当前档案页以内联方式完成预览和二次确认。
- Outcome 写入在同一事务内立即投影 Evidence/Dossier，以保证当前主流程读到一致结果；同时保留幂等 Outcome 事件处理入口和全量 rebuild 作为恢复/对账路径，不引入第二个写权威。

## 已执行验证

- `ruff`：Slice 5 Evidence/Readiness、应用组合根、Activity 变更、API、迁移与目标测试文件通过。
- `mypy`：20 个 Slice 5 后端源/测试文件通过，无类型错误。
- `pytest`：最终目标集合 `31 passed`，覆盖七项能力、Outcome→Evidence/Dossier 生产写入、幂等/supersede/invalidate/rebuild、Snapshot stale、两 Reviewer 版本冲突及拒绝审计、人工决定、持久例外预览/impact 绑定/消费、补练完成、申诉重评重开、AI 摘要失败/引用、校准不覆盖历史、角色 API、迁移 upgrade/downgrade、新人 Attempt/标准包/路由/领域边界。标准包 verify-only 首轮暴露跨域错误未翻译，修正为公开 `NewcomerTrainingError` 后复验通过。
- CodeGraph `affected` 选出的 AppFactory/OpenAPI/Domain contributor 目标集合 `16 passed`；新增 Slice 5 symbol 尚未进入现有索引，`impact` 明确返回 not found，未重建用户索引。
- Web `eslint`：档案组件、管理队列/详情、API domain/types 与目标测试通过。
- Web `vitest`：4 个目标文件、`10 passed`，覆盖七项能力、学员脱敏、失败保留申诉输入、风险队列、人工决定、就地补练、持久例外预览/二次确认和 API 命令路径。
- Web `tsc --noEmit`：清除被 `.gitignore` 覆盖、仍引用已退役 Module route 的生成类型缓存，并补齐 Readiness 错误卡合同后通过；未运行 Next 全量构建。
- OpenAPI：运行时合同初次检查识别 stale，按生成器更新 `specs/001-ai-practice-system/contracts/openapi.yaml` 后 `--check` 通过。
- Architecture/Alembic：依赖 guard 通过；`alembic heads` 唯一 head 为 `20260717_1230_005`。
- Migration：`20260717_1230_005` 在临时 SQLite 执行 upgrade、约束/索引检查和 downgrade 通过；真实 PostgreSQL 迁移、竞争写与锁影响留切片 8 最终发布门禁。
- Trellis：任务 `implement.jsonl` 8 项、`check.jsonl` 4 项校验通过；新增 `backend/competency-evidence-readiness.md` 可执行规范并同步前端 ViewModel/所有权索引。

## Acceptance Evidence

- 稳定七项能力、Outcome 幂等 Evidence、增量/rebuild 收敛、质量排除：`backend/tests/unit/readiness/test_competency_readiness.py` 的 catalog、writer、policy、invalidation 用例。
- Regrade/supersede、冻结 Snapshot stale、申诉重评重开：同文件 `test_regrade_supersedes_history_and_marks_frozen_snapshot_stale`。
- 人工身份、Team/organization、导出/决定拒绝审计、expected version 竞争：同文件 human/denial/conflict 用例及 `backend/tests/integration/test_foundation_readiness_api.py`。
- AI 摘要失败/引用、校准历史隔离：同文件 AI summary 与 calibration 用例。
- 就地补练及完成后重投影：同文件 retraining loop 与 `web/src/app/admin/sales-trainer/readiness/[learnerId]/page.test.tsx`。
- 例外批准：持久 preview token/impact hash 后端用例、管理页预览/明确确认组件用例，以及生成 OpenAPI 路由合同。
- 迁移与模型注册：`backend/tests/migrations/test_competency_readiness_migration.py`、Domain contributor/AppFactory/OpenAPI 目标测试。
