# Research: implementation scope

- Query: 审计报告 8 项整改全部闭环的可执行实施切片计划
- Scope: internal
- Date: 2026-07-06

## Findings

### 研究输入与约束

- Active task: 用户指定 `.trellis/tasks/07-03-2026-07-03`；`.trellis/scripts/task.py current --source` 返回当前未设置 active task，因此本研究按用户显式路径写入。
- CodeGraph: 仓库根目录未发现 `.codegraph/`，按项目 CodeGraph First 规则跳过 CodeGraph，改用只读 `rg` / `nl` 定位。若后续建立索引，改动前建议补跑 `codegraph explore` / `codegraph impact`。
- 审计来源：`docs/project-analysis/audit-2026-07-03-independent-architecture-review.md` 将 8 项列为 P0/P1 路线图，且 task brief 已给出部分建议测试命令。
- 相关 Trellis / 项目规范：
  - `.trellis/workflow.md`：研究成果必须持久化到 task research。
  - `.trellis/spec/backend/error-handling.md`：WebSocket 失败需 client-visible graceful state，不能静默吞错。
  - `.trellis/spec/backend/quality-guidelines.md`：测试优先、失败语义明确、不得 raw/静默错误。
  - `.trellis/spec/backend/realtime-roleplay-v1.md`：runtime 恢复、fail-closed、observability 是必测契约。
  - `.trellis/spec/backend/directory-structure.md`：`common/` 只放跨域通用能力，不放单域业务规则。
  - `backend/AGENTS.md`：backend 必须遵守 async DB、lifespan、structlog、路由注册约定。
  - `backend/src/sales_trainer/AGENTS.md`：`sales_trainer` 权限集中在 `permissions.py`，`tasks/*` 只能作为进程入口调用 service，且不得导入 realtime runtime。
  - `scripts/AGENTS.md`：`scripts/critical-quality-gate.sh` 是唯一质量门禁，禁止新增第二套 gate。

### 推荐最小闭环顺序

1. **先补 characterization / 权限 / 边界测试**：覆盖 `send_json` 当前吞错语义、Redis 启动失败语义、RBAC 角色矩阵、practice session 对象级权限缺口、Adapter 当前违规清单。这样后续改行为时能判断是有意收敛还是误伤。
2. **再接低耦合工程闭环**：Prometheus 核心指标接线和 `critical-quality-gate.sh` 纳入关键测试，二者相对独立，但 gate 更新必须在新增目标测试独立通过后进行。
3. **再做集中口径修复**：RBAC 角色常量 / capability 映射先统一，再处理 API 依赖和前端导航，避免权限测试与 UI 门禁相互踩踏。
4. **再改运行时失败语义**：`send_json` 和 Redis 启动期硬依赖都影响运行时可用性与错误语义，需在 characterization 后小步改，避免同时改变连接层和启动层导致故障归因困难。
5. **最后处理架构级持久化和跨域收敛**：Adapter 严格门禁要先消化既有违规；进程内异步任务持久化涉及 schema、worker、重试、审计、指标，必须先 ADR/方案，再选一个 job 做 pilot。

### 8 项实施切片

| 项 | 风险 | 当前可直接落代码 | 应先补的方案 / 测试 | 关键验收命令 |
| --- | --- | --- | --- | --- |
| 1. `send_json` 失败语义修复 | P0 / 高调用面 | 不建议直接全局改为抛异常；可先新增 `SendResult` 类型和局部调用点适配测试 | 先补 `ConnectionManager.send_json` characterization tests，锁定缺连接、断连、发送异常、backpressure/error frame 的期望；再按调用点分批消费返回值 | `cd backend && python -m pytest -c pyproject.toml tests/unit/test_websocket_handler.py tests/unit/test_stepfun_transport.py tests/unit/test_stepfun_realtime_handler.py tests/unit/test_presentation_stepfun_realtime_handler.py tests/unit/test_main_presentation_ws_runtime.py --no-cov -q` |
| 2. Redis 启动期硬依赖治理 | P0 / 启动可用性 | 不建议在未定产品语义前吞掉 Redis 错误；可先补启动失败/健康状态测试 | 先写 ADR/方案：Redis 缺失到底是 fail-fast、只禁用 realtime snapshot，还是 degraded mode；再写 startup / health characterization tests | `cd backend && python -m pytest -c pyproject.toml tests/unit/test_session_runtime_authority.py tests/unit/test_app_factory.py tests/integration/test_support_runtime_api.py --no-cov -q` |
| 3. RBAC 角色口径统一 | P1 / 权限漂移 | 可以先集中角色常量、normalizer、capability mapper，并只替换局部调用点 | 先补角色矩阵 characterization tests，尤其是 `admin/super_admin/support/training_lead/training_manager/content_admin/newcomer_content_admin/operations/ops/operator/sre/readonly_auditor/user/learner` 的可见能力；若改 DB check constraint 或 admin role permission 表，需 migration 方案 | `cd backend && python -m pytest -c pyproject.toml tests/integration/test_rbac_access_control_api.py tests/integration/test_newcomer_training_path_rbac_api.py tests/integration/test_prompt_templates_api_rbac.py tests/unit/test_newcomer_training_path_permissions.py --no-cov -q`；`cd web && npx vitest run src/lib/sales-trainer/routes.test.ts src/components/admin/sales-trainer/module-nav.test.tsx src/components/layout/admin-sidebar.test.tsx` |
| 4. practice session 对象级权限测试 | P1 / IDOR | 可以当前迭代直接补测试，若测试暴露缺口再做最小权限修复 | 先补 outsider/admin/owner/missing-session 矩阵，重点补 `knowledge-check`、`enhanced-report`、report trends、audio segment 签名 URL 等缺口 | `cd backend && python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py tests/contract/test_audio_audit_contract.py tests/integration/test_session_lifecycle_api.py tests/integration/test_session_flow.py tests/unit/common/analytics/test_report_trends.py --no-cov -q` |
| 5. 关键测试纳入 `critical-quality-gate` | P1 / 发布门禁 | 可以当前迭代直接改 gate，但必须先单独跑新增目标确认耗时和稳定性 | 先确认新增目标不会让 gate 过慢/过脆；只扩展现有 `scripts/critical-quality-gate.sh`，不新增第二个 gate | 先跑：`cd backend && python -m pytest -c pyproject.toml tests/integration/test_supervisor_retraining_api.py tests/unit/test_presentation_stepfun_realtime_handler.py tests/unit/test_main_presentation_ws_runtime.py tests/integration/test_observability_surfaces.py tests/unit/test_session_runtime_authority.py --no-cov -q`；再跑：`bash scripts/critical-quality-gate.sh` |
| 6. Prometheus 核心业务指标接线 | P1 / 可观测性缺口 | 可以当前迭代直接接线，优先接入现有 helper，不改 metric names | 先补 `/metrics` contract tests，覆盖 practice session、LLM/ASR/TTS、WebSocket connection/message、error counter 至少一次真实调用或 service-level synthetic 调用 | `cd backend && python -m pytest -c pyproject.toml tests/integration/test_observability_surfaces.py tests/unit/test_websocket_handler.py tests/unit/test_stepfun_runtime_metrics_helpers.py tests/performance/test_nfr_metrics.py --no-cov -q` |
| 7. Adapter 跨域 import 扫描门禁 | P1 / 架构边界 | 可先新增扫描测试，但建议以“已知违规清单”模式落地，避免立刻红仓 | 先做 characterization：记录当前 `sales_trainer -> curriculum_practice` 直接 import；然后补 adapter facade 并逐项缩小 allowlist；最后启用严格 fail | `cd backend && python -m pytest -c pyproject.toml tests/unit/test_runtime_dependency_contract.py --no-cov -q` |
| 8. 进程内异步任务持久化方案 | P1 / 高架构影响 | 不建议当前迭代直接全量实现持久队列；可先补任务清单与现状 characterization tests | 必须先写 ADR/方案：统一 job/outbox 表、状态机、幂等键、重试/DLQ、worker 启停、审计和 metrics；再选 `sales_trainer` audio 或 report generation 做 pilot | 现状保护：`cd backend && python -m pytest -c pyproject.toml tests/integration/test_report_generation_trigger_fire_and_forget.py tests/integration/test_knowledge_upload_persistence.py tests/unit/test_audio_archival_job.py tests/integration/test_sales_trainer_api.py --no-cov -q`；pilot 后追加持久 job 单测/集成测试 |

### 1. `send_json` 失败语义修复

**关键文件**

- `backend/src/common/websocket/base_handler.py:106`：`ConnectionManager.send_json` 当前返回 `None`；缺连接直接 return，发送异常只记录 `"Failed to send message"`，不抛、不返回失败。
- `backend/src/common/websocket/base_handler.py:192`：接收队列 overflow 时通过 `manager.send_json` 发送 backpressure 错误帧。
- `backend/src/common/websocket/base_handler.py:359`：`send_message` 只 await `manager.send_json`，没有判断发送结果。
- `backend/src/common/websocket/base_handler.py:413`：`send_error` 同样忽略发送结果。
- `backend/src/common/websocket/base_handler.py:473`：reconnection success 也忽略发送失败。
- `backend/src/training_runtime/stepfun_transport.py:56`：已有 `StepFunSendStatus.SENT/FAILED`。
- `backend/src/training_runtime/stepfun_transport.py:61`：已有 `StepFunSendResult`。
- `backend/src/training_runtime/stepfun_transport.py:228`：`StepFunTransport.send_json` 已返回结构化 `StepFunSendResult`，异常映射为 `FAILED`，可作为模式参考，但它是 upstream transport，不应直接混同 client WebSocket。

**现有测试**

- `backend/tests/unit/test_websocket_handler.py:79`：`test_send_json_success`。
- `backend/tests/unit/test_websocket_handler.py:87`：`test_send_json_failure_logged_not_raised` 明确锁定“发送失败不抛，只记录”的旧语义。
- `backend/tests/unit/test_stepfun_transport.py:184`：`test_should_return_failed_send_result_when_websocket_send_errors` 已覆盖 StepFun transport 结构化失败。

**切片建议**

- 第一刀：补 `ConnectionManagerSendResult` characterization，明确 `missing_connection / send_exception / sent` 三种结果，不急于改变所有调用点。
- 第二刀：`ConnectionManager.send_json` 返回结构化结果，并让 `send_message/send_error/backpressure/reconnect_ack` 至少记录 structured log + metric；不要默认抛异常给 message loop。
- 第三刀：对必须用户可见的关键帧（error/backpressure/reconnect_ack）补调用方处理，例如失败后标记连接不可用或关闭连接，避免“业务以为已通知用户”。

### 2. Redis 启动期硬依赖治理

**关键文件**

- `backend/src/common/websocket/session_state_service.py:76`：Redis URL 从 `SESSION_STATE_REDIS_URL` 或 `REDIS_URL` 读取。
- `backend/src/common/websocket/session_state_service.py:146`：`_require_redis` 在 client 不存在时抛 `RuntimeError`。
- `backend/src/common/websocket/session_state_service.py:151`：`describe_authority` 已区分 `session_snapshot=redis_snapshot` 与 `runtime_connections=process_memory`。
- `backend/src/common/websocket/session_state_service.py:170`：`start` 中 `redis.from_url` + `client.ping()`。
- `backend/src/common/websocket/session_state_service.py:198`：Redis 连接失败后 `raise RuntimeError("Failed to connect Redis...")`，导致 lifespan 启动失败。
- `backend/src/common/websocket/session_state_service.py:204`：成功后用 `asyncio.create_task` 启动 cleanup loop。
- `backend/src/common/websocket/session_state_service.py:248`：`save` 依赖 `_require_redis`，失败返回 `Result.fail` 并记录 metrics。
- `backend/src/common/websocket/session_state_service.py:404`：`get_stats` 暴露 `redis_connected/running/authority/metrics/last_error`。
- `backend/src/app_lifespan.py:120`：startup 依次初始化 session manager、session state service、audio archival scheduler；未捕获 Redis startup RuntimeError。
- `backend/src/common/config.py:81`：Redis/session state TTL/cleanup 配置。
- `docs/api-contract/support-runtime.md:60`：支持运行时契约把 Redis snapshot 作为多进程/重启恢复权威。

**现有测试**

- `backend/tests/unit/test_session_runtime_authority.py:32`：验证 SessionManager 是 process-local runtime connection authority。
- `backend/tests/unit/test_session_runtime_authority.py:67`：用 fake redis 验证 SessionStateService snapshot authority 和 metrics。
- 未发现明确覆盖 `app_lifespan` 在 Redis 不可用时 fail-fast/degrade 的测试。

**切片建议**

- 第一刀：先 ADR/方案定产品语义。若 Redis 是 realtime snapshot 必需，应 fail-fast 但返回清晰健康检查和启动诊断；若允许 degraded mode，应显式禁用 reconnect snapshot 并在 `/health` / support runtime surface 暴露。
- 第二刀：补 startup characterization tests，覆盖缺 redis package、ping 失败、env 未配置、运行中 cleanup ping 失败。
- 第三刀：实现策略开关，例如 `SESSION_STATE_REDIS_REQUIRED=true` 默认 fail-fast；若业务确认允许降级，再引入 `degraded` 状态而非静默跳过。

### 3. RBAC 角色口径统一

**关键文件**

- `backend/src/common/db/models.py:116`：`User.role` 字段。
- `backend/src/common/db/models.py:121`：`ck_user_role` 允许 `user/admin/super_admin/support/training_lead/training_manager/content_admin/newcomer_content_admin/operations/ops/operator/sre/readonly_auditor`。
- `backend/src/common/db/models.py:174`：`AdminRolePermission`。
- `backend/src/common/db/models.py:185`：`ck_admin_role_permissions_role` 只允许 `admin/support/content_admin/operations/readonly_auditor`，与 `User.role` 口径不一致。
- `backend/alembic/versions/20260603_1000_075_sales_trainer_rbac_roles.py:19`：migration 中维护了一份 `USER_ROLE_CHECK`。
- `backend/src/common/auth/service.py:564`：`get_current_admin_user` 只允许 `role == "admin"`。
- `backend/src/common/auth/service.py:580`：`get_current_admin_user_for_app_routes` 也只允许 `admin`。
- `backend/src/common/auth/service.py:600`：`require_role` 是较通用角色校验入口。
- `backend/src/admin/api/permissions.py:32`：`DEFAULT_ADMIN_ROLE_PERMISSIONS` 又维护一份 admin permission 角色矩阵。
- `backend/src/sales_trainer/permissions.py:10`：`SUPER_ADMIN_ROLES = {"admin", "super_admin"}`。
- `backend/src/sales_trainer/permissions.py:14`：`CONTENT_ADMIN_ROLES`。
- `backend/src/sales_trainer/permissions.py:17`：`TRAINING_LEAD_ROLES`。
- `backend/src/sales_trainer/permissions.py:21`：`OPS_ROLES`。
- `backend/src/sales_trainer/permissions.py:26`：`SALES_TRAINER_LEARNER_ROLES = {"user", "learner"}`，其中 `learner` 不在 `User.role` check constraint。
- `backend/src/sales_trainer/permissions.py:84`：capability projection。
- `backend/src/prompt_templates/permissions.py:7`：prompt template admin roles 另有一份 `{"admin", "super_admin"}`。
- `web/src/lib/sales-trainer/routes.ts:45`：前端 sales trainer route/capability 列表。
- `web/src/lib/sales-trainer/routes.ts:215`：基于 capability 过滤 admin items。

**现有测试**

- `backend/tests/integration/test_rbac_access_control_api.py`
- `backend/tests/integration/test_newcomer_training_path_rbac_api.py`
- `backend/tests/integration/test_prompt_templates_api_rbac.py`
- `backend/tests/unit/test_newcomer_training_path_permissions.py`
- `web/src/lib/sales-trainer/routes.test.ts`
- `web/src/components/admin/sales-trainer/module-nav.test.tsx`
- `web/src/components/layout/admin-sidebar.test.tsx`

**切片建议**

- 第一刀：写角色矩阵 characterization，锁定每个 role 的 API 权限、sales trainer capability、前端导航可见性。
- 第二刀：新增单一角色定义/normalizer，至少让 `sales_trainer`、prompt templates、admin permissions 引用同一稳定口径。
- 第三刀：处理 `learner`：若它是产品概念而非 DB role，应映射到 `user` + capability；若是 DB role，必须 migration/契约更新。
- 第四刀：只有在矩阵测试通过后再调整 `get_current_admin_user*` 语义，避免误把 `support/content_admin/operations` 变成全局 admin。

### 4. practice session 对象级权限测试

**关键文件**

- `backend/src/common/api/practice.py:160`：`_is_admin_user` 仅判断 `admin`。
- `backend/src/common/api/practice.py:164`：`_can_read_session` 为 admin 或 owner。
- `backend/src/common/api/practice.py:360`：GET session 先查对象再 `_can_read_session`。
- `backend/src/common/api/practice.py:400`：runtime preflight 权限检查。
- `backend/src/common/api/practice.py:447`：lifecycle 权限检查。
- `backend/src/common/api/practice.py:511`：update session 权限检查。
- `backend/src/common/api/practice.py:681`：report 权限检查。
- `backend/src/common/api/practice.py:737`：knowledge-check 权限检查；`backend/src/common/api/practice.py:762` 还读取进程内 live handler。
- `backend/src/common/api/practice.py:1161`：enhanced-report 权限检查。
- `backend/src/common/api/practice.py:1223`：conversation highlights 权限检查。
- `backend/src/common/api/practice.py:1277`：score snapshot fallback 权限检查。
- `backend/src/common/api/practice.py:1391`：comprehensive report 权限检查。
- `backend/src/common/api/practice.py:1523`：audio upload URLs 权限检查。
- `backend/src/common/api/practice.py:1590`：audio segment register/list/failure 权限检查。
- `backend/src/common/analytics/report_trends.py:27`：重复定义 `_can_read_session`。
- `backend/src/common/analytics/report_trends.py:117`：report trends 先查目标 session 再鉴权。

**现有测试**

- `backend/tests/contract/test_audio_audit_contract.py:282`：outsider audio upload/register/list 返回 403。
- `backend/tests/contract/test_audio_audit_contract.py:435`：missing session 返回 404。
- `backend/tests/contract/test_practice_evidence_contract.py:1190`：outsider report/replay 返回 403。
- `backend/tests/contract/test_practice_evidence_contract.py:1772`：outsider audio segment signed URL 返回 403。
- `backend/tests/integration/test_session_lifecycle_api.py:550`：outsider lifecycle 403，admin allowed。
- `backend/tests/integration/test_session_flow.py:600`：enhanced report owner path；未看到 outsider enhanced-report 覆盖。
- `backend/tests/unit/common/analytics/test_report_trends.py:9`：趋势点限制为当前用户同场景；未看到 unauthorized target session 覆盖。

**切片建议**

- 第一刀：测试优先，不必先改业务代码。新增矩阵：owner 200、outsider 403、admin 200、missing 404。
- 第二刀：补缺口 endpoint：knowledge-check、enhanced-report、report trends、score snapshot / highlights、audio signed URL。
- 第三刀：若发现重复 `_can_read_session` 漂移，把权限判断收敛到共享 helper，但不要扩大到全局 RBAC 重构。

### 5. 关键测试纳入 `critical-quality-gate`

**关键文件**

- `scripts/critical-quality-gate.sh:169`：`VITEST_GATE_TARGETS` 列表。
- `scripts/critical-quality-gate.sh:201`：`BACKEND_GATE_TARGETS` 列表。
- `scripts/critical-quality-gate.sh:242`：backend smoke regression 列表。
- `scripts/critical-quality-gate.sh:717`：执行 backend gate targets。
- `scripts/critical-quality-gate.sh:725`：执行 backend smoke regression。
- `scripts/AGENTS.md:14`：确认 `critical-quality-gate.sh` 是规范门禁。

**现有可纳入但当前未在 gate 的关键测试**

- `backend/tests/integration/test_supervisor_retraining_api.py`
- `backend/tests/unit/test_presentation_stepfun_realtime_handler.py`
- `backend/tests/unit/test_main_presentation_ws_runtime.py`
- `backend/tests/integration/test_observability_surfaces.py`
- `backend/tests/unit/test_session_runtime_authority.py`
- 可按整改进展考虑追加：`backend/tests/unit/test_websocket_handler.py`、`backend/tests/contract/test_audio_audit_contract.py`、`backend/tests/unit/test_runtime_dependency_contract.py`。

**切片建议**

- 第一刀：新增目标测试先独立跑，记录耗时。
- 第二刀：加入现有 gate 数组，不新增脚本、不改执行入口。
- 第三刀：如果某些测试太慢或需要外部依赖，放 smoke list 或保留在 nightly，不要硬塞导致本地 gate 不可用。

### 6. Prometheus 核心业务指标接线

**关键文件**

- `backend/src/common/monitoring/metrics.py:25`：Prometheus metric definitions。
- `backend/src/common/monitoring/metrics.py:35`：WebSocket active/message/duration metrics。
- `backend/src/common/monitoring/metrics.py:52`：practice session metrics。
- `backend/src/common/monitoring/metrics.py:71`：LLM/ASR/TTS metrics。
- `backend/src/common/monitoring/metrics.py:118`：error counter。
- `backend/src/common/monitoring/metrics.py:180`：`track_practice_session` helper。
- `backend/src/common/monitoring/metrics.py:201`：`track_llm_request` helper。
- `backend/src/common/monitoring/metrics.py:213`：`track_asr_request` helper。
- `backend/src/common/monitoring/metrics.py:219`：`track_tts_request` helper。
- `backend/src/common/monitoring/metrics.py:225`：`track_websocket_connection` helper。
- `backend/src/common/monitoring/metrics.py:230`：`track_websocket_message` helper。
- `backend/src/common/monitoring/metrics.py:243`：`track_error` helper。
- `backend/src/http_routes.py:136`：注册 `/metrics`。
- `backend/src/common/api/analytics.py:170`：frontend analytics 已接入 metrics。
- `backend/src/curriculum_practice/services/roleplay/dual_read_observability.py:32`：situation pack dual-read 已接入 metrics。

**现有测试**

- `backend/tests/integration/test_observability_surfaces.py:8`：验证 frontend analytics metrics 可出现在 `/metrics`。
- `backend/tests/integration/test_observability_surfaces.py:87`：验证 `/metrics` endpoint。
- `backend/tests/performance/test_nfr_metrics.py:128`：WebSocket latency performance，但不是 Prometheus 接线断言。
- `backend/tests/unit/test_stepfun_runtime_metrics_helpers.py`：测试 runtime metrics helper，不是 Prometheus helper。

**切片建议**

- 第一刀：不改 metric 名称，优先在已有业务完成点接 helper：session 创建/完成、LLM/ASR/TTS 请求、WebSocket connect/disconnect/message、业务错误。
- 第二刀：补 `/metrics` integration tests，验证至少一次真实 API 或 service 调用能产生核心业务指标。
- 第三刀：接线时避免在高频路径同步做重计算；只做 counter/histogram observe。

### 7. Adapter 跨域 import 扫描门禁

**关键文件**

- `docs/adr/2026-06-20-controlled-cross-domain-adapters.md:5`：说明当前有两个受控桥。
- `docs/adr/2026-06-20-controlled-cross-domain-adapters.md:14`：决策为 Adapter 是唯一允许跨边界位置。
- `docs/adr/2026-06-20-controlled-cross-domain-adapters.md:22`：现有测试仅锁 `__all__`。
- `backend/tests/unit/test_runtime_dependency_contract.py:52`：已有 AST import 扫描 helper。
- `backend/tests/unit/test_runtime_dependency_contract.py:126`：`common` reverse dependency guard。
- `backend/tests/unit/test_runtime_dependency_contract.py:154`：`sales_trainer` 不得依赖 realtime runtime。
- `backend/tests/unit/test_runtime_dependency_contract.py:199`：Adapter export guard 只检查导出，不扫描全仓 import。

**当前已发现直接跨域 import**

- `backend/src/sales_trainer/article_api.py:14` 直接导入 `curriculum_practice.services.learning_progress_service`。
- `backend/src/sales_trainer/services/article_exam_prerequisite_service.py:9` 直接导入 `curriculum_practice.models.LearningChapter`。
- `backend/src/sales_trainer/services/article_exam_prerequisite_service.py:10` 直接导入 `curriculum_practice.services.learning_progress_service`。
- `backend/src/sales_trainer/services/business_etiquette_question_draft_service.py:19` 直接导入 `curriculum_practice.models.LearningChapter`。
- `backend/src/sales_trainer/services/business_etiquette_quiz_service.py:13` 直接导入 `curriculum_practice.models.QuestionItem`。
- `backend/src/sales_trainer/services/exam_paper_revision_payloads.py:7` 直接导入 `curriculum_practice.models.QuestionItem`。
- `backend/src/sales_trainer/services/business_etiquette_learning_service.py:7` 直接导入 `curriculum_practice.services.learning_progress_service`。
- `backend/src/sales_trainer/services/business_etiquette_import_service.py:15` 直接导入 `curriculum_practice.models.LearningChapter/LearningContent`。

**切片建议**

- 第一刀：在 `test_runtime_dependency_contract.py` 中新增扫描，但以 known violations 清单锁住当前违规，避免立刻红仓。
- 第二刀：把上述调用逐步迁到 `curriculum_practice_adapter.py` 或新 facade，不让业务 service 直接碰 foreign ORM。
- 第三刀：清空 allowlist 后改为严格 fail，作为最终门禁。

### 8. 进程内异步任务持久化方案

**关键文件**

- `backend/src/sales_trainer/api.py:295`：`_schedule_audio_processing` 使用 FastAPI `BackgroundTasks.add_task`。
- `backend/src/sales_trainer/api.py:631`：audio upload auto process 时调度后台任务。
- `backend/src/sales_trainer/api.py:671`：audio register auto process 时调度后台任务。
- `backend/src/sales_trainer/tasks/process_audio.py:14`：audio processing task 入口。
- `backend/src/sales_trainer/tasks/process_audio.py:21`：task 自建 DB session。
- `backend/src/sales_trainer/tasks/process_audio.py:23`：调用 `AudioSubmissionService.process_submission`。
- `backend/src/sales_trainer/tasks/process_audio.py:28`：异常只记录日志，无持久 job/retry/DLQ。
- `backend/src/common/knowledge/api.py:234`：`process_document_background` 是 BackgroundTasks 入口。
- `backend/src/common/knowledge/api.py:720`：document upload 后 `background_tasks.add_task`。
- `backend/src/common/knowledge/api.py:1015`：document reprocess 后 `background_tasks.add_task`。
- `backend/src/common/db/session_lifecycle.py:504`：report generation trigger。
- `backend/src/common/db/session_lifecycle.py:537`：`asyncio.create_task(trigger_report_generation(...))`。
- `backend/src/evaluation/services/report_generation_trigger.py:829`：报告生成触发器明确 fire-and-forget。
- `backend/src/common/jobs/audio_archival.py:297`：audio archival scheduler 明确是 process-local。
- `backend/src/common/jobs/audio_archival.py:325`：scheduler 使用 `asyncio.create_task`。
- `backend/src/app_lifespan.py:135`：lifespan 初始化 audio archival scheduler。
- `backend/src/curriculum_practice/models.py` / `backend/src/curriculum_practice/services/test_bank.py`：已有 `test_bank_import_jobs` 持久 job 模式，可作为最小范式参考。

**现有测试**

- `backend/tests/integration/test_report_generation_trigger_fire_and_forget.py:1`：验证 report trigger fire-and-forget 自持 session。
- `backend/tests/integration/test_report_generation_trigger_fire_and_forget.py:160`：成功路径持久化。
- `backend/tests/integration/test_report_generation_trigger_fire_and_forget.py:198`：失败路径持久化。
- `backend/tests/integration/test_knowledge_upload_persistence.py:106`：monkeypatch `process_document_background`。
- `backend/tests/unit/test_audio_archival_job.py:96`：scheduler session / idempotent start-stop。
- `backend/tests/integration/test_sales_trainer_api.py`：覆盖 audio processing 被调度，但不是 durable queue。

**切片建议**

- 第一刀：先 ADR/方案，不直接上队列。方案至少包含 job schema、状态机、幂等键、retry/backoff、dead-letter、worker ownership、shutdown semantics、observability、权限/审计。
- 第二刀：做 inventory characterization，区分“业务必须持久化任务”和“连接/进程生命周期临时 task”。不要把 WebSocket handler 内部处理队列误纳入 durable job。
- 第三刀：选一个 pilot。建议优先 `sales_trainer` audio processing 或 report generation：二者有明确业务结果、失败可见，且现有测试已覆盖调度/持久结果。
- 第四刀：pilot 稳定后再迁移 knowledge processing 和 scheduler 类任务。

## Caveats / Not Found

- 未使用外部资料；本轮为仓库内部研究，没有外部版本/文档引用。
- 因 `.codegraph/` 不存在，本轮无法使用 CodeGraph MCP/CLI 做影响面分析；以上调用面基于只读文本检索和文件阅读。
- 本文件未执行测试，只提供整改切片和验收命令。实际落代码前应先运行对应 characterization tests，避免把既有失败误判为本次引入。
- `Redis 启动期硬依赖治理` 和 `进程内异步任务持久化方案` 涉及产品运行语义与架构决策，不建议在没有 ADR/方案的情况下直接实现。
- `Adapter 跨域 import 扫描门禁` 当前存在已知跨域 import；若直接启用严格扫描会红仓，应先用 allowlist/known violations 方式闭环再逐步清零。
