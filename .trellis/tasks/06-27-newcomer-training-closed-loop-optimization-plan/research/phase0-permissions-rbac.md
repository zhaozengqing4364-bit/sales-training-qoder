# Phase 0 子代理 B：权限与对象级授权审计报告

> 日期：2026-06-27  
> 范围：新人训练路径 / 销售训练后台的材料文件访问、商务礼仪测验记录、operation logs/settings、article-progress、manager roles allowlist、历史重评 scope、JWT 默认密钥、配置资产导出审计。  
> 方法：已优先使用 CodeGraph CLI 查询 `sales_trainer.permissions`、material file access、operation logs/settings、article progress、business etiquette quiz attempts、regrade_api、manager roles；随后只读抽样源码、测试和契约。

## 2026-06-29 闭环复核附录

本文件保留 Phase 0 当时的只读审计结论；当前工作树已继续推进实现。以下是主 Agent 基于 CodeGraph 与最新 full gate 复核后的闭环状态，最终验收以 `audit-closure-matrix.md` 和 `final-verification-report.md` 为准。

| Phase 0 问题 | 当前状态 | 当前证据 |
|---|---|---|
| 材料文件访问只校验登录和 version published | 已闭环 | learner 文件访问已基于 active path projection 与历史训练记录回放授权；`audit-closure-matrix.md` P1 权限与安全、P1 内容资产与历史回放；2026-06-29 06:12 full gate passed |
| 商务礼仪测验记录 content_admin 可见、缺部门过滤 | 已闭环 | 训练记录与商务礼仪小测记录进入对象级 scope；content_admin 权限不足、manager 部门 scope 已由 RBAC/API 测试覆盖；`audit-closure-matrix.md` P1 权限与安全 |
| operation logs/settings 允许 support/training_manager 查看 | 已闭环 | logs/settings 收紧到治理角色；`audit-closure-matrix.md` P1 权限与安全；`backend/tests/unit/test_newcomer_training_path_permissions.py` 进入 full gate |
| article-progress 可传任意 published `learning_content_id` | 已闭环 | CodeGraph 复核 `backend/src/sales_trainer/article_api.py`：GET/POST `/article-progress` 均调用 `ArticleBindingService.resolve_module_article(..., require_active_binding=True)`；`ArticleBindingService._active_learning_content_id()` 无 active revision 时返回 `[NEWCOMER_PATH_ACTIVE_REVISION_MISSING]`，禁止 catalog fallback |
| `SALES_TRAINER_MANAGER_ROLES` 非法值未 allowlist | 已闭环 | manager roles allowlist、混入非法值诊断、全非法配置 fail-closed 已进入权限测试与 full gate；`audit-closure-matrix.md` P1 权限与安全 |
| 历史重评服务层缺对象级 scope | 已闭环 | CodeGraph 复核 `SalesTrainerRegradeService.preview_quiz_attempt()` 与 `SalesTrainerAudioRegradeService.preview_audio_submission()` 均先调用 `TrainingRecordService.get_record_for_viewer(..., team_department=...)`；regrade API 聚焦回归已记录于 `final-verification-report.md` |
| 配置资产导出审计默认关闭 / 模型配置缺审计 | 已闭环 | 配置资产导出、模型配置 CRUD/test/tts-preview 已补持久化审计；见 `audit-closure-matrix.md` P1 权限与安全和 full gate 证据 |

## 结论

**最高风险：P1。** 真实存在的 P1 权限问题主要是材料文件下载缺少 path/module/unit/learner-level 对象级授权，以及商务礼仪后台测验记录由 content 管理权限放行且缺部门 scope。`operation logs/settings` 也与契约冲突：代码和测试当前允许 training_manager/support 查看，但契约要求仅 admin/ops。

## 权限审计问题状态

| 问题 | 状态 | 风险 | 证据 |
|---|---|---:|---|
| 材料文件访问只校验登录和 version published，缺少 path/module/unit/learner-level 对象级授权 | **未闭环** | P1 | `backend/src/sales_trainer/api.py:343` learner 文件接口仅注入 `current_user`，随后调用 `SalesTrainerMaterialService.resolve_file_access(version_id)`；`backend/src/sales_trainer/services/material_service.py:445` 只校验 version 存在且 `status == "published"` 和存储路径边界。 |
| 商务礼仪测验记录 content_admin 可见，且 admin 列表缺部门过滤 | **未闭环** | P1 | `backend/src/sales_trainer/business_etiquette_api.py:682` admin `/quiz-attempts` 使用 `_require_manager`；`_require_manager` 在同文件 `91` 调 `can_manage_sales_trainer`，而 `permissions.py:58` 允许 content_admin；`BusinessEtiquetteQuizService.list_attempts` 在 `backend/src/sales_trainer/services/business_etiquette_quiz_service.py:257` 无 `team_department` 参数。 |
| operation logs/settings 允许 support/training_manager 查看 | **未闭环** | P1 | 契约 `docs/api-contract/sales-trainer.md` 概览说明培训负责人不能查看系统日志；权限实现 `backend/src/sales_trainer/permissions.py:96` `can_view_sales_trainer_logs` 包含 manager，`104` settings 复用 logs；测试 `backend/tests/unit/test_newcomer_training_path_permissions.py:37/65/79` 也固化 manager/logs 许可。 |
| 普通 sales_trainer article-progress 可传任意 published `learning_content_id` | **部分闭环 / 需人工决策** | P2 | `backend/src/sales_trainer/article_api.py:140` POST 已在 `163-177` 校验 payload 与当前模块绑定一致；GET `article-progress` 仍接受 query `learning_content_id` 并委托 `ArticleBindingService.resolve_module_article`。是否允许旧客户端按 id 读进度，需要产品决定；若废弃 fallback，应移除 query override。 |
| `SALES_TRAINER_MANAGER_ROLES` 非法值未 allowlist/fail-closed | **未闭环** | P1 | `backend/src/sales_trainer/permissions.py:36-43` 直接把 env 拆成 role set，非空即覆盖默认；未校验是否属于安全 allowlist，误配为 `content_admin,user` 会扩大 manager 能力。 |
| 历史重评服务层缺对象级 scope，仅依赖 admin/ops 角色 | **需人工决策 / 当前角色门槛已闭环** | P2 当前，未来 P1 | `backend/src/sales_trainer/regrade_api.py:54` 只允许 `can_regrade_sales_trainer_history`，即 `permissions.py:92` admin/ops；当前无 manager 重评能力，跨部门风险被角色门槛挡住。若未来给培训负责人重评，必须在 regrade service/API 增加 target user department scope。 |
| JWT 默认密钥风险 | **已生产闭环，但代码仍有治理债** | P3 | `backend/src/common/auth/service.py:35` 仍有默认 `JWT_SECRET`；`backend/src/app_lifespan.py:24-39` 在非 development 环境检测默认值并 fail-fast。 |
| 配置资产导出审计默认关闭 | **未闭环** | P1 | `backend/src/admin/api/config_assets.py:35-42` `record_export_audit: bool = False`；`export_config_assets` 仅在 `body.record_export_audit` 为真时提交审计；`backend/src/admin/config_assets/export_service.py:29/70` 也默认不记录。 |
| 模型配置变更缺持久化审计 | **本子任务未充分展开，需后续专项** | 待定 | 本轮聚焦新人训练权限面；只确认 audit-synthesis 提到该项，但未完整审阅 `backend/src/admin/api/model_configs.py` CRUD/test/tts-preview 全路径。建议单独派 admin/config reviewer。 |

## 具体修复任务

### T1. 材料文件下载增加对象级授权

- 文件：`backend/src/sales_trainer/api.py`、`backend/src/sales_trainer/services/material_service.py`，必要时新增 `sales_trainer/services/material_access_policy.py`。
- 函数：`get_sales_trainer_material_version_file`、`SalesTrainerMaterialService.resolve_file_access`。
- 期望行为：
  - learner 下载必须证明 `version_id` 属于当前 active path projection 中该学员可访问的 module/unit/material binding，或属于本人历史 submission 的 frozen `material_snapshot`。
  - admin 下载走 admin endpoint 或同一 policy，content_admin 仅下载内容资产；manager 只下载本部门学员历史记录引用的材料；ops/admin 全局。
  - archived 但被历史 submission snapshot 引用的 version 可只读下载，避免历史回放断链；未绑定/不可见返回 404 或 403，建议对 learner 使用 404 防枚举。
- 测试建议：
  - learner A 可下载自己 active module 绑定材料。
  - learner A 不能下载未绑定但 published 的材料 version。
  - learner A 可下载自己历史 submission 冻结的 archived version。
  - content_admin 可下载后台内容材料但不能借 learner 接口绕过对象 scope。
  - manager 只能下载本部门学员历史记录引用材料。

### T2. 商务礼仪 quiz attempts 改用 records 权限并增加部门 scope

- 文件：`backend/src/sales_trainer/business_etiquette_api.py`、`backend/src/sales_trainer/services/business_etiquette_quiz_service.py`。
- 函数：`list_business_etiquette_quiz_attempts`、`BusinessEtiquetteQuizService.list_attempts`。
- 期望行为：
  - admin list 使用 `can_view_sales_trainer_records`，不是 `can_manage_sales_trainer`。
  - content_admin/newcomer_content_admin 返回 403。
  - training_manager/support 仅可看本人 `department` 范围；无部门时 fail-closed。
  - ops/admin 可全局。
- 测试建议：
  - content_admin 403。
  - training_manager 只能看到同部门 attempt，指定其他部门 `user_id` 返回空或 404。
  - ops/admin 可看全局。

### T3. 收紧 operation logs/settings 到 admin/ops

- 文件：`backend/src/sales_trainer/permissions.py`、`backend/tests/unit/test_newcomer_training_path_permissions.py`、`backend/tests/integration/test_newcomer_training_path_rbac_api.py`。
- 函数：`can_view_sales_trainer_logs`、`can_view_sales_trainer_settings`、`sales_trainer_admin_capability_projection`。
- 期望行为：
  - `support/training_lead/training_manager` 的 `view_logs=false`、`view_settings=false`。
  - `/api/v1/admin/sales-trainer/settings` 和 `/operation-logs` 对 manager 返回 403。
  - records/manager-dashboard 仍保留 manager 部门 scope 访问。
- 测试建议：
  - 更新当前固化 manager logs 许可的单测。
  - 集成测试新增 `training_lead` 请求 settings/logs 均 403。

### T4. Manager roles env allowlist

- 文件：`backend/src/sales_trainer/permissions.py`。
- 函数：`sales_trainer_manager_roles`、`sales_trainer_admin_role_label`。
- 期望行为：
  - 只允许默认安全集合或显式 allowlist，例如 `support,training_lead,training_manager` 及项目批准的别名。
  - env 含非法 role 时只保留合法项并记录结构化诊断；显式配置全非法时 fail-closed 为空集合，不扩大也不保留默认 manager 权限。
  - 空值仍使用默认。
- 测试建议：
  - unset/env 空：默认三角色。
  - env=`training_manager,evil,user`：仅保留合法项，不能让 `user` 获得 manager capability；全非法 env 返回空集合。
  - role label 与 capability projection 同步。

### T5. Article progress 移除任意 learning_content_id override（需产品确认兼容期）

- 文件：`backend/src/sales_trainer/article_api.py`、`sales_trainer/services/article_binding_service.py`。
- 函数：`get_newcomer_module_article_progress`、`complete_newcomer_module_article_chapter`。
- 期望行为：
  - learner 进度读写只使用 active module binding 解析出的 `learning_content_id`。
  - 若保留兼容 query/payload id，只能作为 stale-client guard：必须等于当前绑定，否则 409。
  - 管理端绑定态不要通过 learner 接口侧推。
- 测试建议：
  - 传当前绑定 id 成功。
  - 传其他 published content id 返回 409/404。
  - module disabled/missing 返回 typed error，不写 progress。

### T6. 历史重评预留对象级 scope

- 文件：`backend/src/sales_trainer/regrade_api.py`、`backend/src/sales_trainer/services/regrade_service.py`、`backend/src/sales_trainer/services/audio_regrade_service.py`。
- 函数：`preview_*_regrade`、`run_*_regrade`。
- 期望行为：
  - 当前 admin/ops 全局行为保持。
  - 若引入 manager 重评 capability，必须在 preview/run 前校验 target attempt/submission 的 user.department 与 actor.department。
  - impact_scope 写入 scope_basis，例如 `global_admin` / `ops_global` / `department:销售一部`。
- 测试建议：
  - content_admin 继续 403。
  - manager 当前 403。
  - 若启用 manager 重评，跨部门 preview/run 均 404/403，同部门成功且 audit 写 scope。

### T7. JWT 默认密钥治理债

- 文件：`backend/src/common/auth/service.py`、`backend/src/app_lifespan.py`、`backend/tests/unit/common/test_auth_transport_matrix.py` 或新增 auth security test。
- 期望行为：
  - 生产已 fail-fast 保持不变。
  - 可考虑将默认值限制为 development/test，非 dev 导入或启动必须显式 env，避免脚本/测试绕过 lifespan 时误用默认签名。
- 测试建议：
  - `ENVIRONMENT=production` + 默认 `JWT_SECRET` 启动失败。
  - development 允许默认但 release readiness 报告标记非生产限定。

### T8. 配置资产导出强制审计

- 文件：`backend/src/admin/api/config_assets.py`、`backend/src/admin/config_assets/export_service.py`、`backend/tests/integration/test_config_asset_import_export_api.py`、`backend/tests/unit/test_config_asset_import_export_service.py`。
- 函数：`ConfigAssetExportRequest`、`export_config_assets`、`ConfigAssetExportService.export_bundle`。
- 期望行为：
  - 导出默认 `record_export_audit=true` 或移除请求开关并强制写 `SystemLog(action="config_asset_export")`。
  - 响应 `export_meta.export_audit_recorded=true`。
  - dry-run 概念不适用于导出；若需要无审计预览，必须另设低风险 metadata preview endpoint。
- 测试建议：
  - 未传 `record_export_audit` 也写 SystemLog。
  - 显式 false 被拒绝或忽略为 true。
  - 失败导出不写 success audit，但应有 failure audit 或结构化日志。

## RBAC 测试矩阵

| 场景 | learner | content_admin | training_manager/support | ops | admin/super_admin |
|---|---|---|---|---|---|
| learner active 材料文件下载 | 仅本人可访问 path/module 绑定材料 | 不走 learner 接口 | 不走 learner 接口 | 不走 learner 接口 | 不走 learner 接口 |
| admin/content 材料下载 | 403 | 允许内容资产下载 | 仅本部门历史记录引用材料 | 全局 | 全局 |
| 商务礼仪 quiz attempts admin list | 403 | 403 | 同部门 only | 全局 | 全局 |
| `/admin/sales-trainer/settings` | 403 | 403 | 403 | 200 | 200 |
| `/admin/sales-trainer/operation-logs` | 403 | 403 | 403 | 200 | 200 |
| 普通训练记录 / audio submissions | 403 | 403 | 同部门 only；无部门空范围 | 全局 | 全局 |
| 历史重评 preview/run | 403 | 403 | 当前 403；未来启用则同部门 only | 全局 | 全局 |
| manager role env 误配为 `user` | 不得获得能力 | 不受影响 | 默认安全集合 | 不受影响 | 不受影响 |
| 配置资产导出 | 403 | 取决于 admin permission，不应默认允许 | 403 | 取决于平台权限 | 允许且强制审计 |

## 安全检查摘要

- OWASP A01 Broken Access Control：**存在 P1**，材料文件和商务礼仪 attempts 需要对象级授权修复。
- OWASP A02 Cryptographic Failures：JWT 默认密钥生产启动已 fail-fast，残留为 P3 治理债；未读取任何生产密钥。
- OWASP A03 Injection：本轮未发现相关 SQL 字符串拼接；主要查询使用 SQLAlchemy 参数化表达式。
- OWASP A04 Insecure Design：manager roles env 非法值直接生效，属于权限配置设计缺陷。
- OWASP A05 Security Misconfiguration：配置资产导出审计默认关闭；settings/logs 能力与契约不一致。
- OWASP A07 Identification/Auth Failures：JWT 默认值已生产保护，但建议收紧导入/脚本绕过 lifespan 的风险。
- OWASP A09 Logging/Monitoring Failures：导出审计默认关闭；operation logs 暴露给 manager 也增加敏感元数据泄露面。

## 验证命令

已执行：

```bash
codegraph explore "sales_trainer.permissions manager roles object level authorization learner admin capabilities"
codegraph explore "sales trainer material file access learner admin file endpoint authorization"
codegraph explore "sales trainer operation logs settings article progress business etiquette quiz attempts regrade_api"
codegraph node backend/src/sales_trainer/permissions.py
codegraph node backend/src/sales_trainer/services/material_service.py
codegraph node backend/src/sales_trainer/regrade_api.py
codegraph node backend/src/sales_trainer/article_api.py
codegraph node backend/src/sales_trainer/business_etiquette_api.py
codegraph node backend/src/sales_trainer/api.py
npm audit --omit=dev
rg -n "(SECRET_KEY|JWT|jwt|AUTH_SECRET|secret_key|change-me|default.*secret|HS256|ACCESS_TOKEN|token)" backend/src backend/.env.example .env.example pyproject.toml backend/requirements*.txt
rg -n "record_export_audit|audit.*false|AUDIT|operation_log|OperationLogService|record_audit|export_audit" backend/src docs .trellis/tasks/06-27-newcomer-training-closed-loop-optimization-plan/research/audit-synthesis.md
```

结果：

- `npm audit --omit=dev`：0 vulnerabilities。
- `pip-audit`：未执行成功，当前环境未安装 `pip-audit`，`python` 命令也不存在；重试 `python3 -m pip_audit` 后仍显示 `PIP_AUDIT_UNAVAILABLE`。
- secrets scan：未发现生产密钥读取或真实密钥泄露证据；发现 `.env.example`/文档占位符和 `JWT_SECRET` 默认值，已在上文归类。

建议修复后执行：

```bash
cd backend
pytest tests/unit/test_newcomer_training_path_permissions.py -q
pytest tests/integration/test_newcomer_training_path_rbac_api.py -q
pytest tests/integration/test_business_etiquette_quiz_api.py -q
pytest tests/integration/test_newcomer_training_path_material_api.py -q
pytest tests/integration/test_newcomer_training_path_regrade_api.py tests/integration/test_newcomer_training_path_audio_regrade_api.py -q
ruff check src/sales_trainer src/admin/api/config_assets.py src/admin/config_assets
```

## 回滚策略

- 权限收紧类改动优先通过单一权限函数回滚：`permissions.py` 能力函数是主开关。
- 材料文件对象级授权如误伤，可短期只允许 admin/ops/content_admin 后台下载，learner 接口保持 fail-closed，并通过 active path/material binding 修复数据后恢复。
- 商务礼仪 attempts 加部门 scope 后若运营报表缺数据，先临时给 ops/admin 使用全局查询，不把 content_admin 或 manager 放大全局。
- 配置资产导出强制审计若引发事务失败，可回滚为“导出成功 + audit failure typed warning”，但不建议恢复默认不审计。

## 停止条件

本轮已完成指定权限审计问题核验、拆分修复任务、RBAC 测试矩阵、风险等级、回滚策略和验证命令。未修改业务代码或权限策略文件；仅写入本报告。
