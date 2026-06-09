# 安全 / 鉴权 / 数据隐私 严苛审计报告

- **审计日期**：2026-06-03
- **审计范围**：`/Users/zhaozengqing/github/销售训练qoder/`
- **审计对象**：认证、授权 / RBAC、数据隐私（§VI）、敏感数据加密、日志脱敏、API 越权、WebSocket 鉴权、前端 XSS、CORS、Secrets 管理、销售训练新域权限
- **审计原则**：宪法原则 I（UX 不中断）、IV（容错与恢复）、V（成本）、VI（数据隐私：演练记录只能被本人和管理员访问）、VII（可观测性）
- **审计人**：严苛架构师
- **方法**：只读检索 + 静态阅读；未运行任何服务；未修改任何代码或现有文档

---

## 严苛评级

| 严重度 | 描述 | 数量 |
|--------|------|------|
| **P0 - 阻断** | 不可接受的高风险：越权、密钥兜底、不可控降级、不可逆数据泄露 | 4 |
| **P1 - 严苛** | 缺失或薄弱的鉴权 / 加密 / 脱敏；可能造成水平/垂直越权 | 9 |
| **P2 - 重要** | 已有兜底但偏离宪章；可观测性、合规、长期残留风险 | 7 |
| **P3 - 关注** | 设计 / 文档 / 工具链层面需跟进 | 4 |

> 报告内**未发现 P0** 致命级水平越权（学员之间的 audio_submission/quiz_attempt 访问均显式拒绝），但 **P1** 层级仍有 9 项可被精确利用的薄弱面。

---

## 1. 认证机制（Authentication）

### 1.1 实现概览

| 维度 | 现状 | 证据 |
|------|------|------|
| 协议 | **HS256 JWT**（`JWT_ALGORITHM=HS256`），24h 默认有效期 | `backend/src/common/auth/service.py:35-39` |
| 主密钥 | `JWT_SECRET` 环境变量，**默认值 `'your-super-secret-key-change-in-production-min-32-chars'`** 硬编码兜底 | `backend/src/common/auth/service.py:35-37` |
| 密码哈希 | `pbkdf2_sha256` / `bcrypt` 两种算法并存（`deprecated="auto"`） | `backend/src/common/auth/service.py:60` |
| 用户主表 | `users`（`hashed_password` 字段为可空；与登录兜底并存） | `backend/src/common/db/models.py:106-125` |
| 会话凭证 | **HttpOnly + Lax SameSite Cookie** `app_session`（dev 可关闭 Secure） | `backend/src/common/auth/service.py:287-323` |
| 二次校验 | CSRF Token Cookie（`app_csrf`，非 HttpOnly）+ Header `X-CSRF-Token`；仅在 cookie-auth + 写方法触发 | `backend/src/common/auth/service.py:367-393` |
| 失败模式 | 通用错误码 `[INVALID_CREDENTIALS]`（防枚举） | `backend/src/common/auth/api.py:160-166` |
| Token 撤销 | **无**（无 jti、无黑名单、无 refresh token） | `backend/src/common/auth/api.py:405-407`（注释明确"由客户端处理"） |
| 生产强校验 | `app_lifespan.py:33-39` 检测默认密钥则 `RuntimeError` | `backend/src/app_lifespan.py:33-39` |

### 1.2 `AUTH_SHARED_PASSWORD` 与 `AUTH_USER_PASSWORDS_JSON` 逻辑

| 流程 | 位置 | 行为 |
|------|------|------|
| 解析共享口令 | `common/auth/api.py:169-172` | `os.getenv("AUTH_SHARED_PASSWORD", "").strip()` |
| 解析用户覆盖 | `common/auth/api.py:175-195` | `os.getenv("AUTH_USER_PASSWORDS_JSON")` → JSON → `{email_lower: password}` |
| 凭据解析状态码 | `common/auth/api.py:198-219` | `get_auth_config_diagnostics()` 返回 `credentials_ready` / `user_overrides_valid` |
| 登录选择顺序 | `common/auth/api.py:312-332` | ① 优先 `User.hashed_password`（password reset 写库）→ 否则 ② 命中 `AUTH_USER_PASSWORDS_JSON[email]` → 否则 ③ 兜底 `AUTH_SHARED_PASSWORD` |
| 强度校验 | `common/auth/api.py:222-224` | `hmac.compare_digest` 恒定时比较 |
| 生产门禁 | `app_lifespan.py:57-66` | `env != "development"` 时若 `credentials_ready=False` 直接 `RuntimeError` 启动失败 |
| 兼容回退 | `common/auth/api.py:64-78`（注释中说明 `User.hashed_password` 是权威路径；env 密码是兜底） | 与 §VI 兼容：依赖此 fallback 的账号必须尽快 reset 到 db hash |

### 1.3 WeCom SSO（企业微信）

- **入口**：`GET /api/v1/auth/wecom/start` → 302 至 `https://open.weixin.qq.com/connect/oauth2/authorize`，携带 `state`、`redirect_uri`、`agentid`、`scope`（默认 `snsapi_base`）
  - `backend/src/common/auth/api.py:459-481`
- **回调**：`GET /api/v1/auth/wecom/callback`
  - 验证 state（HMAC constant-time）→ 交换 `access_token` → `/auth/getuserinfo` → `/user/get` 拉详情 → `upsert_wecom_user()` upsert
  - `backend/src/common/auth/api.py:483-551`、`common/auth/service.py:623-680`
- **State Cookie**：`app_wecom_oauth_state`（HttpOnly + Secure + SameSite=Lax），默认 600s 过期
  - `backend/src/common/auth/service.py:119-184`
- **Return-to 防开放重定向**：`/_sanitize_return_to` 拒绝非 `/` 开头或 `//` 开头（避免协议相对 URL）
  - `backend/src/common/auth/api.py:252-257`、`470`
- **开发登录**：`AUTH_ENABLE_DEV_LOGIN` 仅在 `ENVIRONMENT=development` 启用
  - `backend/src/common/auth/service.py:137-141`

### 1.4 Token 存储位置

| 客户端形态 | 证据 | 评级 |
|------------|------|------|
| **后端**：HttpOnly Cookie（`app_session` + `app_csrf`），`SameSite=Lax`，`Secure=True`（非 dev） | `common/auth/service.py:315-349` | 良好 |
| **前端**：浏览器原生 `credentials: "include"`（自动随 cookie） | `web/src/lib/api/client.ts:1720-1731` | 良好 |
| 前端**未持久化 JWT**；`localStorage` 唯一持久化项 = `qoder.login.rememberEmail.v1`（仅邮箱） | `web/src/app/(auth)/login/page.tsx:152-157`、`web/src/lib/auth/clear-client-auth-state.ts:1-2` | 良好 |
| 凭据流：登录响应体仍**返回 `token` JSON**（`LoginResponse.token`） | `common/auth/api.py:113-117`、`274-376` | **P2**（冗余泄露，前端 dev 工具可见） |

### 1.5 认证安全矩阵

| 控制 | 已实现 | 证据 |
|------|--------|------|
| 密码哈希（db 路径） | ✅ bcrypt/pbkdf2 | `common/auth/service.py:60` |
| 弱口令过滤（密码 reset） | ✅ `PasswordResetService` 强约束（用户自定义 schema 校验） | `common/auth/api.py:594-633` |
| 登录限流 | ❌ 未见 login 端点接 `rate_limit` 装饰器；`forgot-password` 有 IP 级限流 | `common/auth/api.py:557-591` |
| 登录失败计数 / 锁定 | ❌ 无（5 次失败锁定 / 滑窗） | — |
| 凭据防枚举 | ✅ 统一 401 `[INVALID_CREDENTIALS]` | `common/auth/api.py:160-166` |
| 设备指纹 / 会话清单 | ❌ 无；JWT 单点签发，无 `jti`、无活跃会话枚举 | — |
| 登录后强制 MFA | ❌ 无 | — |
| 密码 reset token | ✅ `PasswordResetToken` 表 + 单 token 约束 + 滑窗（1 req / 60s） | `common/db/models.py:701-753`、`common/auth/api.py:557-591` |
| 失败响应含 trace_id | ✅ | `common/auth/api.py:142-157` |
| **JWT 默认密钥兜底** | ❌ 存在（`service.py:35-37`），但 `app_lifespan.py:33-39` 已在生产环境 **强校验为启动失败** | 治理良好，**P3 残留**（生产侧必须 100% 设环境变量） |
| **生产 JWT 撤销** | ❌ 无（无黑名单，无 refresh token） | 学员离职/挂失无法远程吊销 → **P1** |
| **JWT 默认有效期 24h** | ⚠ 偏长 | `common/auth/service.py:39` |
| **响应体内 token 字段** | ⚠ 与 httpOnly cookie 同时下发 | `common/auth/api.py:113-117` → **P2** |

---

## 2. 授权 / RBAC

### 2.1 全局 RBAC 机制

| 控制 | 位置 | 行为 |
|------|------|------|
| 角色定义 | `User.role`（`String(20)`，check constraint 限定 13 个值，2026-06-03 迁移 `075_sales_trainer_rbac_roles` 扩展） | `common/db/models.py:115-125` |
| 通用依赖 | `get_current_user` / `get_current_admin_user` / `get_current_admin_user_for_app_routes` | `common/auth/service.py:505-597` |
| 工厂依赖 | `require_role(["admin"])` | `common/auth/service.py:600-620` |
| 细粒度权限 | `admin.api.permissions.require_admin_permission(perm)` + `AdminRolePermission` 表 | `admin/api/permissions.py:1-127` |
| 默认权限映射 | `DEFAULT_ADMIN_ROLE_PERMISSIONS`（admin / content_admin / operations / support / readonly_auditor 5 个角色 → 15 个权限维度） | `admin/api/permissions.py:32-81` |

### 2.2 销售训练新域权限矩阵（`sales_trainer/permissions.py`）

| 角色集 | 集合 | 行 |
|--------|------|-----|
| `SUPER_ADMIN_ROLES` | `admin`, `super_admin` | 8 |
| `CONTENT_ADMIN_ROLES` | `content_admin`, `newcomer_content_admin` | 9 |
| `TRAINING_LEAD_ROLES` | `support`, `training_lead`, `training_manager` | 10 |
| `OPS_ROLES` | `ops`, `operator`, `operations`, `sre` | 11 |
| 角色（迁移 075） | `user`, `admin`, `super_admin`, `support`, `training_lead`, `training_manager`, `content_admin`, `newcomer_content_admin`, `operations`, `ops`, `operator`, `sre`, `readonly_auditor` | 22 |

| 能力 | 函数 | 允许角色 |
|------|------|---------|
| 管理训练内容 | `is_sales_trainer_admin` / `is_sales_trainer_content_admin` / `can_manage_sales_trainer` | admin OR super_admin OR content_admin/newcomer_content_admin |
| 查看学员记录 | `can_view_sales_trainer_records` | admin OR (training_lead) OR (ops) |
| 查看全局记录（跨部门） | `can_view_sales_trainer_global_records` | admin OR ops |
| 重试 ASR / 评分任务 | `can_retry_sales_trainer_jobs` | admin OR ops |
| 查看运维日志 | `can_view_sales_trainer_logs` | admin OR ops |
| 查看设置健康 | `can_view_sales_trainer_settings` | admin OR ops |
| 团队作用域 | `team_scope_department(user)` | 管理员/ops → `None`（全局）；manager → user.department；其他人 → `"__NO_ACCESS__"` |

> 注：培训经理 `TRAINING_LEAD_ROLES` 既不在 admin，也不在 content_admin，**不可写**训练内容，仅可读本部门记录。

### 2.3 5 个 admin endpoint 抽查（销售训练新域）

| # | 端点 | 行 | 鉴权 | 越权风险 |
|---|------|-----|------|---------|
| 1 | `GET /admin/sales-trainer/units` | `sales_trainer/api.py:470-485` | `Depends(get_current_user)` + `_require_manager` → 任何已登录者先命中 `_require_manager` | ✅ 已校验 |
| 2 | `POST /admin/sales-trainer/units/{unit_id}/publish` | `sales_trainer/api.py:524-541` | `_require_manager` | ✅ |
| 3 | `GET /admin/sales-trainer/audio-submissions/{submission_id}/file` | `sales_trainer/api.py:954-980` | `_require_records_viewer` + `can_view_sales_trainer_global_records` + `team_department` | ✅ |
| 4 | `POST /admin/sales-trainer/audio-submissions/{submission_id}/retry-transcription` | `sales_trainer/api.py:983-1006` | `_require_job_retry`（admin/ops） | ✅ |
| 5 | `GET /admin/sales-trainer/operation-logs` | `sales_trainer/api.py:1258-1283` | `_require_ops_viewer`（admin/ops）+ `actor_department = _team_scope` 强制收窄到本部门 | ✅ |

> 抽查 5 个 admin endpoint 全部显式鉴权，**未发现垂直越权**。

### 2.4 学员端点（`@router`）

| # | 端点 | 行 | 鉴权 | 风险 |
|---|------|-----|------|------|
| 1 | `GET /sales-trainer/units/{unit_id}` | `sales_trainer/api.py:249-264` | `Depends(get_current_user)` + 仅返回 `status == "published"` | ✅ |
| 2 | `POST /sales-trainer/audio-submissions/upload` | `sales_trainer/api.py:374-404` | `current_user` 强绑 `actor.user_id`（line 387） | ✅ |
| 3 | `GET /sales-trainer/audio-submissions/{submission_id}` | `sales_trainer/api.py:425-442` | `get_submission(id, actor=current_user)` 内部断言 `submission.user_id != str(actor.user_id)` → `[ACCESS_DENIED]` 403 | ✅ |
| 4 | `GET /sales-trainer/quiz-attempts/{attempt_id}` | `sales_trainer/api.py:335-352` | `service.get_attempt()` 同样断言（line 176） | ✅ |
| 5 | `GET /sales-trainer/materials/versions/{version_id}/file` | `sales_trainer/api.py:295-314` | 已登录即可下载（**未校验 unit_id 是否 published / 是否对该用户可见**） | **P1**（已发布 unit 的 material 资源可被任意登录用户拉取，文件路径走 `resolve_file_access` 内部校验，但是否在 unit 关联图内未显式断言） |

### 2.5 跨域 admin RBAC 残留风险（来自 `security_inventory.py` 自报清单）

| route_family | 现状 | 风险 |
|--------------|------|------|
| `admin.api.admin`（presentation 管理） | `Depends(get_current_admin_user)` | `security_inventory.py:55-66` 标记 baseline+watch |
| `admin.api.analytics` | 同上 | `security_inventory.py:67-80` 同级 |
| `admin.api.release_verification` | `require_admin_permission(release_verification.manage)` | 已收口 |
| `admin.api.system_logs` | `require_admin_permission(config_audit.read)` | 已收口；allowed_roles 含 `content_admin/operations/support/readonly_auditor` |
| `admin.api.training_records` | `Depends(get_current_admin_user)` | 枚举/删除其他用户 session |
| `admin.api.users` | `Depends(get_current_admin_user)` | 标杆（positive control） |
| `admin.api.interventions` | 同上 | 自由 note 字段仍需脱敏 |
| `admin.api.governance` | 同上 | OK |
| `admin.api.knowledge_answer_config` | router 级别 | OK |
| `admin.api.model_configs` | router 级别 | OK |
| `admin.api.presentation_ai` | router 级别 | OK |
| `admin.api.rag_profiles + voice_runtime` | router 级别 | OK |

> 与 sales_trainer 域 `Depends(get_current_user) + _require_*()` 不同：销售训练 admin 使用"非 admin 依赖 + 业务级 helper"组合，**审计可读性低于传统 admin 域**（需对照 `permissions.py`），但**实际拦截一致**。

### 2.6 RBAC 不足 / 待办

| 项 | 严重度 |
|----|--------|
| `is_sales_trainer_content_admin` 与 `team_scope_department` 联动缺失：content_admin 没有 `_team_scope()` 收窄，看到的 records 是**全局**（因为 `_require_records_viewer` 即允许），存在跨部门数据窥视可能 | **P1** |
| `sales_trainer_admin_paper_router` 与 `sales_trainer/paper_api.py` 的 `_require_manager` 复用 `can_manage_sales_trainer`，与 `/admin/sales-trainer/...` 主路由策略一致，**已对齐** | OK |
| 没有 `require_role(["content_admin"])` 装饰器包装式断言；统一通过 helper 函数 | P3（架构风格） |
| 没有"开发者登录"开关：dev login 仍由 `is_dev_login_enabled()` 收口，仅在 `ENVIRONMENT=development` 启用 | OK |

---

## 3. 数据隐私（宪法原则 VI）

> **宪法原则 VI**：演练记录只能被本人和管理员访问。

### 3.1 audio_submission 访问控制

| 调用 | 行 | 行为 |
|------|-----|------|
| `AudioSubmissionService.get_submission(id, actor, allow_admin, team_department)` | `sales_trainer/services/audio_submission_service.py:333-353` | `allow_admin=True` → 任意通过；`team_department` 命中 `User.department == department` → 通过；否则 `submission.user_id != str(actor.user_id)` 抛 `[ACCESS_DENIED]` 403 |
| `_submission_in_department` | `sales_trainer/services/audio_submission_service.py:773-781` | JOIN `User.department == team_department` |
| `list_submissions(user_id, team_department)` | `sales_trainer/services/audio_submission_service.py:435-462` | 支持按 user_id 和 team_department 收窄；admin 端 `@admin_router.get("/audio-submissions")` 传入 `_team_scope(current_user)` |
| `resolve_audio_file_access` | `sales_trainer/services/audio_submission_service.py:355-433` | 内部调 `get_submission` → 复用上述检查；外加本地存储路径防穿越（`storage_root not in (resolved_path, *resolved_path.parents)`） |
| `list_score_results` | `sales_trainer/services/audio_submission_service.py:464-508` | 同样支持 `team_department` 收窄 |
| `serialize_submission` | `sales_trainer/services/audio_submission_service.py:510-545` | 返回 `user_id/user_name/user_email/user_department` → **admin 端列表会显示其他学员的邮箱** → **P1**（与 `_mask_email` 标杆不一致） |

### 3.2 quiz_attempt 访问控制

| 调用 | 行 | 行为 |
|------|-----|------|
| `QuizService.get_attempt(id, actor, allow_admin=False)` | `sales_trainer/services/quiz_service.py:166-178` | 学员本人 OK；否则 `[ACCESS_DENIED]` 403 |
| `QuizService.get_admin_attempt(id, actor, allow_admin, team_department)` | `sales_trainer/services/quiz_service.py:180-200` | admin/部门命中 → 通过；否则按学员本人校验 |
| `list_attempts(user_id, unit_id, team_department)` | `sales_trainer/services/quiz_service.py:202-233` | admin 端传入 `_team_scope(current_user)` 强制收窄 |
| `serialize_attempt` | `sales_trainer/services/quiz_service.py:235+` | 返回 `user_id/user_name/user_email/user_department` → **同 audio_submission，admin 端列表裸露邮箱** → **P1** |

### 3.3 水平越权漏洞扫描

| 类型 | 风险 | 证据 |
|------|------|------|
| 学员 A 通过修改 `{submission_id}` 路径访问学员 B 的 audio_submission | ❌ **不存在**（`get_submission` 强校验 owner） | `audio_submission_service.py:351` |
| 学员 A 通过 `{attempt_id}` 访问学员 B 的 quiz_attempt | ❌ **不存在**（`get_attempt` 强校验 owner） | `quiz_service.py:176` |
| 学员 A 伪造 `user_id` 查询 admin 列表端点 | ❌ **不存在**（admin 端由 `_require_records_viewer` 拦截） | `sales_trainer/api.py:909` |
| 学员 A 通过 unit_id 跨发布状态读未发布 unit | ❌ **不存在**（`get_published_unit` 强制 `status == "published"`） | `sales_trainer/api.py:258-263` |
| 学员 A 通过 unit_id 拉取未发布 material | ❌（`resolve_file_access` 内部默认要求 unit status） | `material_service.py:459`（`[MATERIAL_FILE_ACCESS_DENIED]`） |
| 学员 A 通过 `material_id` 直查 | ⚠（未发布 material 文件是否仍可下载取决于 material 服务的版本过滤） | **P2**（建议读取路径再加 status 断言） |
| 学员 A 通过 `team_department` 路径参数探测其他部门 | N/A：team_department 不接受用户输入，由 `_team_scope(current_user)` 从 token 计算 | `sales_trainer/api.py:131-134` |
| 学员 A 调 admin 端 `audio-submissions` 不带 user_id | OK：默认返回本部门（或全局） | `sales_trainer/api.py:901-924` |
| 学员 A 调 admin 端 `audio-submissions?user_id=other` | OK：受到 `team_department` 收窄限制 | 同上 |

### 3.4 隐私残留项

| 编号 | 描述 | 严重度 |
|------|------|--------|
| PRIV-1 | `audio_submissions` admin 端列表 `serialize_submission` 返回 `user_email`（明文），与 §VI 原则和 `admin/api/users.py:218-239` 的 `_mask_email` 标杆不一致 | **P1** |
| PRIV-2 | `quiz_attempts` admin 端列表 `serialize_attempt` 同样返回 `user_email` | **P1** |
| PRIV-3 | `operation_log` `list_logs` 仅按 `actor_department` 收窄，不区分目标 target 的归属 → ops/admin 可看跨部门操作日志（含 ip/ua/trace） | **P2** |
| PRIV-4 | `serialize_submission` 中 `transcript_text` / `raw_payload` 完整返回 admin | OK（admin 范围合理） |
| PRIV-5 | `SalesTrainerAudioScoreResult.transcript_snapshot` 同样持久化在 db，admin 端可见 | OK（评估必要） |
| PRIV-6 | `audio_submission.user_id` 持久化前已被 `str(actor.user_id)` 规范化（line 229），避免 UUID 漂移 | OK |
| PRIV-7 | WebSocket `realtime_handler.handle_connection`（`sales_bot/websocket/stepfun_realtime_handler.py:805-848`）不绑定 `actor` → 学员**可能跨账号接入别人的 session**（`session_id` 不与 `user_id` 在 handler 内强绑定） | **P1**（需补 `payload["sub"] == str(session.user_id)` 校验） |
| PRIV-8 | `BaseWebSocketHandler.handle_connection` 同样不校验 token sub 与 session 拥有者 | **P1**（`common/websocket/base_handler.py:219-275`） |

---

## 4. 敏感数据加密

### 4.1 Fernet 加密机制

| 项 | 值 | 证据 |
|----|----|------|
| 算法 | AES-128-CBC + HMAC-SHA256（Fernet） | `common/ai/encryption.py:15` |
| 主密钥 | `MODEL_CONFIG_ENCRYPTION_KEY` 环境变量；缺失抛 `ValueError` | `common/ai/encryption.py:43-50` |
| 单例 | `get_encryption()` (lru_cache) | `common/ai/encryption.py:140-151` |
| 掩码 | `mask_key()`（`sk-...xxxx` 模式） | `common/ai/encryption.py:101-123` |
| 加/解密结果 | `Result[T]`（不抛异常） | `common/ai/encryption.py:58-99` |
| 启动门禁 | `validate_production_config` 中是否校验 `MODEL_CONFIG_ENCRYPTION_KEY` **未确认**（无显式 hint） | `common/analytics/release_readiness.py:23` 仅校验 JWT 默认密钥 |

### 4.2 加密字段字典

| 表.列 | 加密算法 | 加密入口 | 解密入口 | 备注 |
|-------|---------|---------|---------|------|
| `model_configs.api_key_encrypted` (Text) | Fernet | `common/ai/encryption.py::encrypt_api_key` → `admin/api/model_configs.py:301, 543` | `decrypt_api_key` → `admin/api/model_configs.py:451, 723` | UI 通过 `api_key_masked` 展示 |
| `rag_profiles.*.api_key_encrypted` (推测) | Fernet | `common/knowledge/rag_profile_service.py:144-148` | 同上 | 调用 `encrypt_api_key` / `decrypt_api_key` |
| `users.hashed_password` | bcrypt / pbkdf2_sha256 | `passlib.CryptContext.hash` | `pwd_context.verify` | 双向（写+验） |
| `password_reset_tokens.token_hash`（隐式） | n/a（一次性 token） | n/a | n/a | `common/db/models.py:701-745` 单 token 约束 |
| **Sales trainer** 数据库字段 | — | — | — | **无加密字段**（录音文件本地存储，OSS/COS URL 签名） |
| `sales_trainer_audio_submissions.storage_key` | n/a（仅路径） | n/a | n/a | 本地 / 远程对象存储 |
| 配置文件 `extra_config` JSON | ❌ 未加密（`ModelConfig.extra_config`） | — | — | 可能含 provider 元数据；不强敏感，但 `base_url` 已直接明文存库 |

### 4.3 加密覆盖率

- **覆盖范围**：仅 `ModelConfig.api_key_encrypted`、`RagProfile.api_key_encrypted`（`admin/api/rag_profiles.py:124`）以及 `users.hashed_password`
- **未覆盖**：
  - `MODEL_CONFIG_ENCRYPTION_KEY` 之外的密钥（如 OSS/COS secret、StepFun key、WeCom secret）→ 走环境变量，**不入库**（OK）
  - `extra_config`（JSON）如含次级密钥，**未强制加密** → **P2**
  - 录音文件本身 → 通过对象存储 / 本地文件系统，不二次加密（合理）
  - 转写文本 / 评分原文 → 持久化在 db 明文 Text 字段（OK：admin 范围）

---

## 5. 日志脱敏（CLAUDE.md §VI + L1 编程规则 §6）

### 5.1 工具栈

| 工具 | 位置 | 行为 |
|------|------|------|
| `StructuredLogger` 包装层 | `common/monitoring/logger.py:237-253` | `info/warning/error/debug` 入口对 `kwargs` 调 `sanitize_log_kwargs` |
| `sanitize_log_kwargs` → `sanitize_log_value` | `common/monitoring/logger.py:147-177` | 递归脱敏，字段名命中 `SENSITIVE_LOG_FIELD_MARKERS=("token","password","cookie","email")` 即 `[REDACTED]`；email 走 `mask_email_for_logs`（保留前 2 位 + 域名） |
| `is_sensitive_log_key` | `common/monitoring/logger.py:78-84` | 字段名包含 marker 即命中（substring 匹配） |
| `mask_email_for_logs` | `common/monitoring/logger.py:87-101` | `xxx***@domain`（local-part 保留 2 位） |
| `mask_ip_address_for_admin` | `common/monitoring/logger.py:123-144` | IPv4: `1.2.*.*`；IPv6: `::1:***` |
| `mask_user_identifier_for_admin` | `common/monitoring/logger.py:104-120` | email → mask_email；其他 → 前 2 位 + `***` |
| `log_safety_inventory.py` | `common/monitoring/log_safety_inventory.py` | 6 个 sinks 的代码自有清单 + 状态矩阵 |
| 早期 `common/logging/sanitizer.py` | 含 `password` / `token` 正则匹配 | 旧版，仍存在但未在新代码使用 |

### 5.2 脱敏覆盖率

| 字段类型 | 是否被识别 | 证据 |
|----------|-----------|------|
| `token` | ✅ substring 命中 | `logger.py:78-84` |
| `password` | ✅ | 同上 |
| `cookie` | ✅ | 同上 |
| `email` | ✅（mask 保留 domain） | `logger.py:87-101` |
| `api_key` / `secret` / `apikey` | ❌ **未识别**（不含 `token/password/cookie/email` 子串） | **P1**（encryption.py 中 `encrypt_api_key` 仍可能输出 raw bytes 字符串到日志时漏脱敏） |
| `ip_address` / `client_host` | ⚠ 仅 `mask_ip_address_for_admin` 提供，**未接入 logger** | **P2** |
| `user_identifier` | ⚠ 同上，仅 admin log 上下文使用 | **P2** |
| `wechat_user_id` / `wecom_user_id` | ❌ | P3 |
| `trace_id` | ✅ allowlist（admin support 上下文） | OK |
| 路径中的 `storage_key`（含 user_id） | ❌（`audio_submission_service.py:602` 等位置 logger 使用 `error_code` 不带 storage_key） | OK by happenstance |
| StepFun realtime transcript 内容 | ⚠（`raw_response`/`raw_payload` 进入 logger 走 `error_code` 字段；不命中 marker → 不过滤） | **P2**（`sales_trainer/services/paraformer_file_asr.py:98-100` 显式 `_redact_url_query` / `_redact_transcription_result`，但若其他模块漏写会被 StructuredLogger 兜底"全留"） |

### 5.3 log_safety_inventory 自报状态

| surface | state | priority |
|---------|-------|----------|
| `common.monitoring.logger.StructuredLogger` | present | watch |
| `common.monitoring.latency_tracker.record_stage` | present | watch |
| `common.auth.api.logout` | present | watch |
| `common.auth.api.login/forgot/reset failure branches` | present | watch |
| `common.auth.service.verify_token` | present | watch |
| `admin.api.users._queue_user_audit_log` | present | baseline（positive control） |

> 整体"present"，**但 marker 集合太小**，api_key / secret 漏识别（见上）。

### 5.4 关键日志中**未脱敏**的具体风险点

| 文件:行 | 内容 | 风险 |
|---------|------|------|
| `common/analytics/verification_runner.py:1494-1495` | `r'password\s*=\s*...'` / `r'api[_-]?key\s*=\s*...'` 出现在代码（用于扫描 secret 残留） | 风险低（regex 本身），但若真实扫描命中会以原始 token 形式入库 |
| `common/analytics/verification_runner.py:1495` 注释 | `api_key="..."` 形式示例字符串 | OK（仅示例） |
| `paraformer_file_asr.py:98-100` | 已显式 redact URL query，**应当作为模式** | OK（标杆） |
| `admin/api/system_logs.py:50` `redaction_summary` 字段 | 字符串定义 | OK |
| `admin/api/governance.py:301` `support_log_redaction` | 描述性字段 | OK |

---

## 6. API 越权审计（`api-audit-anomaly-report.md` 摘要 + 新发现）

### 6.1 已记录异常（节选 2026-05-18 报告，未含越权专项）

| 类别 | 数量 | 是否含越权 |
|------|------|------------|
| 后端定义但前端未调用（孤立端点） | 25 | 否（功能缺失） |
| 前端定义但无页面调用的孤立 API 方法 | 35 | 否 |
| 知识库别名路由冗余 | ~18 | 否 |
| HTTP 方法不一致 | 0（已修复） | — |
| 绕过 API client | 0（已修复） | — |

> 报告**未做越权审计**，但本次审计**未发现**额外的水平/垂直越权（与 §3.3 一致）。

### 6.2 本次审计新发现的越权 / 信息泄露点

| 编号 | 位置 | 描述 | 严重度 |
|------|------|------|--------|
| OV-1 | `sales_trainer/services/audio_submission_service.py:520-521` `serialize_submission` | admin 端 list 返回 `user_email` 明文 | **P1**（见 §3.4 PRIV-1） |
| OV-2 | `sales_trainer/services/quiz_service.py:248-251` `serialize_attempt` | 同 OV-1 | **P1** |
| OV-3 | `sales_bot/websocket/stepfun_realtime_handler.py:805-848` | token 验证后未将 `payload["sub"]` 与 session 拥有者绑定 | **P1**（学员可接入别人 session） |
| OV-4 | `common/websocket/base_handler.py:219-275` | 同 OV-3 | **P1** |
| OV-5 | `sales_trainer/api.py:295-314` `get_sales_trainer_material_version_file` | 不显式校验 material 是否与已发布 unit 关联 | **P1**（间接） |
| OV-6 | `sales_trainer/api.py:1258-1283` `admin_list_operation_logs` | `actor_department = _team_scope` 收窄目标 actor，但**不收窄** `target_type/target_id` 任意过滤 → 可扫描其他部门操作痕迹 | **P2** |
| OV-7 | `common/auth/service.py:493-502` `verify_token` | `jwt.decode` 不指定 `audience` / `issuer` → 无法拒绝跨服务 token 误用 | **P2** |
| OV-8 | `common/auth/api.py:113-117` | 登录响应同时下发 JWT body + httpOnly cookie；body 可被 XSS（虽然 §8 未发现 XSS）读取 | **P2** |
| OV-9 | `common/auth/service.py:36-39` | JWT 默认 secret 兜底；**生产已阻断**（`app_lifespan.py:33-39`）→ P3 |
| OV-10 | `common/rate_limit/api_limiter.py:222-238` `_get_client_ip` | 无条件信任 `X-Forwarded-For`，**未校验反代** → 后端置于直连环境可伪造 IP 触发/绕开 rate limit | **P1** |
| OV-11 | `backend/src/common/auth/service.py:277-284` `_websocket_query_token_enabled` | dev/test 自动启用 query token；**生产默认关闭**，但若 `WEBSOCKET_QUERY_TOKEN_ENABLED=true` 被误设则 token 走 URL（**会进入反向代理访问日志**） | **P2** |
| OV-12 | `sales_trainer/api.py:1010-1032` retry-scoring 路径在 `get_submission` 之后**未再校验** `actor` 是否仍能操作 | OK（前置校验足够） | — |
| OV-13 | `sales_trainer/api.py:470-1283` 所有 admin endpoint 仅 `get_current_user`，未走 `get_current_admin_user` | 形式不一致，但 `_require_*` helper 已补 | P3（风格） |
| OV-14 | `sales_trainer/api.py:295-314` material 文件下载 | 文件名直接来自 `submission.original_filename` → 反射型 XSS 风险（如果文件名未净化） | **P2**（需要前端不将 `original_filename` 直接插入 HTML，已知前端无 `dangerouslySetInnerHTML`，但若文件名为 `<script>...</script>` 可能被部分浏览器下载提示界面 XSS） |
| OV-15 | `app_factory.py:138-145` CORS `allow_methods=["*"]` + `allow_headers=["*"]` + `allow_credentials=True` | 通配方法+通配头+凭据 → 配合 `allow_origin_regex`（DEV 默认放行 10/192.168/172 内网段）→ **生产环境如果保留 DEV 正则将形成大面积开放** | **P1**（如果生产误用 `_is_dev_or_test_environment`） |

---

## 7. WebSocket 鉴权

### 7.1 解析链

| 顺序 | 传输 | 行为 | 位置 |
|------|------|------|------|
| 1 | `authorization: Bearer <token>` | 标准 | `common/auth/service.py:434-439` |
| 2 | `Cookie: app_session=...` | 解析 SimpleCookie | `common/auth/service.py:441-447`、`416-425` |
| 3 | `?token=...`（query） | **仅当 `WEBSOCKET_QUERY_TOKEN_ENABLED=true` 或 dev/test/local** | `common/auth/service.py:277-284`、`449-455` |

### 7.2 验证位置

| Handler | 行 | 验证 |
|---------|-----|------|
| `BaseWebSocketHandler.handle_connection` | `common/websocket/base_handler.py:230-254` | `verify_token(resolved_token)` → 失败仅 `logger.warning`，**不关闭 socket**，将 `self.user_id = None` → **OV-4** |
| `StepFunRealtimeHandler.handle_connection` | `sales_bot/websocket/stepfun_realtime_handler.py:805-848` | 同上模式；`self.user_id` 为 None 时仍可启动处理消息（**OV-3**） |
| `StepFunRealtimeConnection.handle_connection` | `sales_bot/websocket/stepfun_realtime_connection.py:824+` | 同样模式 |
| `SalesBot Router` (`sales_bot/websocket/router.py:471-486` `_extract_user_id_from_token`) | 仅作为辅助函数返回 `user_id` 或 None，**调用方未强制 None → close** | **OV-3** |
| `curriculum_practice/websocket/router.py:184` | 同样模式 | — |

### 7.3 重连与重验证

- 现有实现：每次 `handle_connection` 重新解析 token → 重新 `verify_token`，**重连等同于重新鉴权**（这是正确的）
- 但**不重新比对** `payload["sub"]` 与 `session.user_id` → 学员 token 可挂在任意 `session_id` 上 → **P1**（OV-3/OV-4）

### 7.4 缺失控制

| 项 | 缺失位置 | 评级 |
|----|----------|------|
| Token 验证失败应主动 `websocket.close(code=4401)` | `BaseWebSocketHandler.handle_connection:253-255`、`StepFunRealtimeHandler.handle_connection:832-834` | **P1** |
| `session_id` ↔ `user_id` 强校验 | 同上 | **P1** |
| CSRF 不强制（`should_enforce_csrf` 不适用于 WS） | 协议限制 | OK |
| WS 心跳超时（30s） | `BaseWebSocketHandler:285-300` | OK |
| Backpressure / 队列溢出 | `BaseWebSocketHandler:184-217` | OK |

---

## 8. 前端 XSS 防御

### 8.1 静态扫描

```
grep -rn "dangerouslySetInnerHTML" /Users/zhaozengqing/github/销售训练qoder/web/src/
# 0 命中
```

- **零使用** `dangerouslySetInnerHTML` → XSS 静态面安全。

### 8.2 用户输入展示方式（抽查 sales-trainer 前端）

| 页面 | 文件 | 渲染方式 | 风险 |
|------|------|---------|------|
| 学员音频提交页 | `web/src/app/(dashboard)/sales-trainer/audio/[unitId]/page.tsx` | React `{value}` 文本插值 | OK（自动转义） |
| 管理员录音提交 | `web/src/app/admin/sales-trainer/audio-submissions/[submissionId]/page.tsx` | 同上 | OK |
| 管理员训练记录 | `web/src/app/admin/sales-trainer/training-records/page.tsx` | 同上 | OK |
| 学员/管理员 `next-step-panel.tsx` | — | 同上 | OK |
| 复习报告页 | `web/src/app/(dashboard)/sales-trainer/audio/result/[submissionId]/page.tsx` | 同上 | OK |

### 8.3 风险残留

- `transcript_text`、`raw_payload`、`raw_response` 等 JSON 字段若被误接 React `dangerouslySetInnerHTML` 渲染会 XSS；当前未发现。
- `submission.original_filename` 通过 `Content-Disposition: attachment; filename=...` 传递 → 由浏览器下载界面处理；不直接 HTML 注入。

---

## 9. CORS 配置

### 9.1 配置

| 项 | 值 | 行 |
|----|-----|-----|
| 源 | `CORS_ORIGINS` 环境变量优先；dev/test 兜底 `DEV_CORS_ORIGINS`（localhost / 127.0.0.1 / 内网正则） | `app_factory.py:79-99` |
| `allow_origin_regex` | dev 兜底为内网 IP 段；生产未配置则 `None` | `app_factory.py:102-110` |
| `allow_methods` | `["*"]` | `app_factory.py:143` |
| `allow_headers` | `["*"]` | `app_factory.py:144` |
| `allow_credentials` | `True` | `app_factory.py:142` |
| 显式拒绝 `*` 在 credentials=True 时 | `_validate_cors_origins` raise RuntimeError | `app_factory.py:121-133` |

### 9.2 风险

| 项 | 描述 | 评级 |
|----|------|------|
| **生产环境若环境变量 `CORS_ORIGINS` 未设**且 `ENVIRONMENT` 不在 dev/test → `allow_origins=[]` 即拒绝全部，**OK** | `app_factory.py:91-93` | OK |
| 若生产误置 `ENVIRONMENT=development` | `DEV_CORS_ALLOW_ORIGIN_REGEX` 放行 10/172/192.168 内网 + `.local` 域 | **P1**（防御纵深） |
| `allow_methods=["*"]` + `allow_credentials=True` | 符合 CORS 规范（不能 `*` origins），但允许 PUT/DELETE/TRACE 等所有方法 | **P2** |
| `allow_headers=["*"]` | OK，浏览器还会做 CORS preflight 自定义头协商 | OK |

---

## 10. Secrets 管理

### 10.1 数量

- `backend/.env.example`：**78** 个环境变量（已确认）
- `backend/.env`（实际部署）：**62** 个

### 10.2 硬编码残留扫描

```
grep -rni "api[_-]?key.*=.*['\"]" /Users/zhaozengqing/github/销售训练qoder/backend/src/ | grep -v ".env"
# 命中均为空字符串 / 占位 ""，无真实密钥残留
```

```
grep -rnE "(secret|token)\s*=\s*['\"][^'\"]{8,}" backend/src/ | grep -v "test|conftest|.env|access_token|refresh_token|..."
# 0 命中
```

### 10.3 风险项

| 项 | 描述 | 评级 |
|----|------|------|
| **JWT_SECRET 默认值 `'your-super-secret-key-change-in-production-min-32-chars'`** | `common/auth/service.py:35-37`；`common/analytics/release_readiness.py:23` 已在生产启动时强校验为 `RuntimeError` → 实际是 P3 | P3 |
| **MODEL_CONFIG_ENCRYPTION_KEY** | 缺失时 `KeyEncryption.__init__` 抛 `ValueError`，但**未在生产启动时 fail-fast**（`app_lifespan.py` 仅校验 JWT secret 和 auth credentials） | **P2** |
| **AUTH_SHARED_PASSWORD 默认值** | 若未设：登录端点返回 `[AUTH_SERVICE_UNAVAILABLE]` 503；生产启动 fail-fast（`app_lifespan.py:62-66`） | OK |
| **WECOM_SECRET / WECHAT_SECRET** | 未配置时 SSO 端点返回 `[WECOM_SSO_UNAVAILABLE]` 503；生产启动 fail-fast（`app_lifespan.py:67-71`） | OK |
| **ASR / TTS / LLM 提供商 key** | 走 `MODEL_CONFIG_ENCRYPTION_KEY` 加密 + 运行时解密；不走明文 | OK |
| **`users.hashed_password` 落库 bcrypt** | OK | OK |
| **password_reset_tokens 单 token 约束** | `uq_password_reset_tokens_single_active_user` | OK |

### 10.4 加密字段字典（精简）

| Key | 用途 | 存储 | 备注 |
|-----|------|------|------|
| `JWT_SECRET` | JWT 签名 | env | 生产必填 |
| `MODEL_CONFIG_ENCRYPTION_KEY` | Fernet 加密 model config api_key | env | 启动未 fail-fast |
| `AUTH_SHARED_PASSWORD` | 共享登录口令 | env | 兼容路径 |
| `AUTH_USER_PASSWORDS_JSON` | per-user 覆盖 | env JSON | 兼容路径 |
| `WECOM_CORP_ID/SECRET/AGENT_ID` | 企业微信 SSO | env | 生产必填 |
| `DASHSCOPE_API_KEY` | TTS/ASR | env（直读） | 落入 ModelConfig 时 Fernet 加密 |
| `STEPFUN_API_KEY` | 实时语音 | env | 直读 |
| `OPENAI_API_KEY` / `LLM_API_KEY` / `EMBEDDING_API_KEY` | LLM 兼容 | env | 直读或 ModelConfig |
| `TENCENT_COS_*` / `ALI_OSS_*` | 对象存储 | env | 直读 |

---

## 11. 销售训练新域权限矩阵（总结）

| 角色 | 数量 | 学员记录 | 全局记录 | 任务重试 | 训练内容 | 运维日志 | 设置健康 |
|------|------|---------|---------|---------|---------|---------|---------|
| `user`（学员） | 默认 | 自己 | ❌ | ❌ | ❌（仅看 published） | ❌ | ❌ |
| `training_lead` / `training_manager` | 中层管理 | 本部门 | ❌ | ❌ | ❌ | ❌ | ❌ |
| `content_admin` / `newcomer_content_admin` | 内容 | ❌（缺收窄！） | ⚠ | ❌ | ✅ | ❌ | ❌ |
| `ops` / `operator` / `operations` / `sre` | 运维 | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ |
| `admin` / `super_admin` | 超级 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `support` | 业务支持 | ❌（实际在 `TRAINING_LEAD_ROLES` 中） | ❌ | ❌ | ❌ | ❌ | ❌ |
| `readonly_auditor` | 只读审计 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

> **注 1**：`is_sales_trainer_content_admin` 定义但**`content_admin` 既不在 `can_view_sales_trainer_records` 也不在 `can_view_sales_trainer_logs`** → content_admin 可管理训练内容，**但看不到任何学员记录**（合理），但 admin 列表查询时没有 `_team_scope` 收窄（**OV-1/OV-2** 仍由 content_admin 触发？实际 content_admin 不通 `_require_records_viewer`）。
>
> **注 2**：`is_sales_trainer_content_admin` 不会因 `_team_scope` 收窄 → 一旦 `_require_records_viewer` 通过（admin/ops），即可看全局。**当前 content_admin 永远不通过 `_require_records_viewer`，因此未实际触发越权**。

---

## 12. 严苛分级

### P0 - 阻断（无）

### P1 - 严苛（9 项）

| 编号 | 位置 | 问题 |
|------|------|------|
| P1-1 | `sales_trainer/services/audio_submission_service.py:520-521` | admin 端 audio_submission 列表裸露 `user_email` |
| P1-2 | `sales_trainer/services/quiz_service.py:248-251` | admin 端 quiz_attempt 列表裸露 `user_email` |
| P1-3 | `sales_bot/websocket/stepfun_realtime_handler.py:805-848` | token 验证失败不 close，sub 与 session 拥有者不绑定 |
| P1-4 | `common/websocket/base_handler.py:219-275` | 同 P1-3，影响 PPT / 销售对练所有 WS |
| P1-5 | `common/rate_limit/api_limiter.py:222-238` | 无条件信任 `X-Forwarded-For`，可伪造 IP 绕开限流 |
| P1-6 | `sales_trainer/api.py:295-314` | material 文件下载未与 published unit 关联校验 |
| P1-7 | `common/auth/service.py:493-502` | JWT 无 `audience` / `issuer` 校验，跨服务 token 误用风险 |
| P1-8 | `app_factory.py:42-50, 94-99` | 生产若 `ENVIRONMENT=development` 误置 → 内网段 CORS 全部放行 |
| P1-9 | `common/ai/encryption.py:78-99` + `common/monitoring/logger.py:21` | log marker 集合不含 `api_key`/`secret`/`apikey` → 模型 API key 落库/落栈可能裸入日志 |

### P2 - 重要（7 项）

| 编号 | 位置 | 问题 |
|------|------|------|
| P2-1 | `sales_trainer/api.py:1258-1283` | admin op-logs 不收窄 `target_type/target_id` |
| P2-2 | `common/auth/api.py:113-117` | 登录响应同时下发 token body + httpOnly cookie（冗余） |
| P2-3 | `common/auth/service.py:277-284` | `WEBSOCKET_QUERY_TOKEN_ENABLED` 误设 → token 进入 URL → 进入反代日志 |
| P2-4 | `common/ai/models.py:81` | `ModelConfig.extra_config` 未加密字段可能含次级密钥 |
| P2-5 | `app_factory.py:143-144` | `allow_methods=["*"]` + `allow_headers=["*"]` + `allow_credentials=True` |
| P2-6 | `app_lifespan.py` | 未对 `MODEL_CONFIG_ENCRYPTION_KEY` 进行 fail-fast 校验 |
| P2-7 | `sales_trainer/api.py:295-314` + `audio_submission_service.py:430-467` | `original_filename` 反射到 `Content-Disposition`，潜在浏览器下载提示 XSS |

### P3 - 关注（4 项）

| 编号 | 位置 | 问题 |
|------|------|------|
| P3-1 | `common/auth/service.py:35-37` | JWT 默认密钥硬编码兜底（已生产 fail-fast） |
| P3-2 | `sales_trainer/api.py:470-1283` | admin 端使用 `Depends(get_current_user) + _require_*` 而非 `get_current_admin_user` |
| P3-3 | `log_safety_inventory.py` | 6 个 surface 全部 `priority=watch`/`baseline`，无 `fix-first` 项 |
| P3-4 | `sales_trainer/permissions.py` | 缺 `require_*` 装饰器风格断言（统一走 helper 函数） |

---

## 13. 推荐修复优先级（提案）

| 优先级 | 修复项 | 估时 |
|--------|-------|------|
| **本周** | P1-1, P1-2（admin 列表邮箱脱敏，对齐 `_mask_email` 标杆） | 0.5d |
| **本周** | P1-3, P1-4（WS `payload["sub"] == session.user_id` 强校验 + 失败 `close(4401)`） | 1.5d |
| **本周** | P1-5（IP 信任链：增加 `TRUSTED_PROXIES` 配置或仅在 env 启用 `X-Forwarded-For`） | 0.5d |
| **本周** | P1-9（log marker 加入 `api_key`、`secret`、`apikey`、`apikey`） | 0.25d |
| **下周** | P1-7（JWT `aud` / `iss` claim 校验） | 1d |
| **下周** | P1-6（material 文件下载关联 published unit） | 0.5d |
| **下周** | P1-8（生产环境 `_is_dev_or_test_environment` 强校验） | 0.25d |
| **下下周** | P2-1 ~ P2-7 全部 | 3d |

---

## 14. 不在本审计范围

- 前端 React 组件 props 透传、组件间状态共享
- Webpack/构建产物完整性
- CI/CD 流程密钥分发
- 第三方依赖 CVE（需 `pip-audit` / `npm audit` 单独跑）
- 数据库备份加密 / 静态加密（TDE）
- 移动端原生壳
- 服务器操作系统 / 容器镜像扫描
- 业务逻辑漏洞（如评分规则被绕过、文件上传变形绕过）

---

## 附录 A：证据索引（关键 file:line）

| 主题 | 位置 |
|------|------|
| JWT 签发/验证 | `backend/src/common/auth/service.py:479-502` |
| 登录鉴权 4 种入口 | `backend/src/common/auth/api.py:272-376` |
| 销售训练权限模型 | `backend/src/sales_trainer/permissions.py:1-82` |
| 5 个 admin endpoint 抽查 | `backend/src/sales_trainer/api.py:470, 524, 954, 983, 1258` |
| audio_submission 水平越权检查 | `backend/src/sales_trainer/services/audio_submission_service.py:333-353` |
| quiz_attempt 水平越权检查 | `backend/src/sales_trainer/services/quiz_service.py:166-200` |
| Fernet 加密 | `backend/src/common/ai/encryption.py:1-198` |
| 日志脱敏 | `backend/src/common/monitoring/logger.py:78-177` |
| log 脱敏清单 | `backend/src/common/monitoring/log_safety_inventory.py:1-184` |
| CORS 配置 | `backend/src/app_factory.py:31-145` |
| WS token 解析 | `backend/src/common/auth/service.py:277-475` |
| 销售训练 admin RBAC 模板 | `backend/src/sales_trainer/api.py:101-134` |
| 75 号 RBAC 角色扩展迁移 | `backend/alembic/versions/20260603_1000_075_sales_trainer_rbac_roles.py:19-23` |
| Admin API 异常清单 | `docs/api-contract/api-audit-anomaly-report.md` |
| Admin RBAC 矩阵 | `backend/src/admin/api/security_inventory.py:32-277` |
| Admin 细粒度权限装饰器 | `backend/src/admin/api/permissions.py:1-127` |
| 默认凭据检查 | `backend/src/app_lifespan.py:33-39, 57-66` |
| 密码 reset 模型 | `backend/src/common/db/models.py:701-745` |
| User 模型 | `backend/src/common/db/models.py:106-125` |
| ModelConfig 加密列 | `backend/src/common/ai/models.py:75` |

---

**结论**：
- **水平越权（学员 A → 学员 B）**：已通过 service 层 owner 校验 + 团队范围收窄显式阻止。✅
- **垂直越权（学员 → admin）**：admin 域使用 `get_current_admin_user` / `require_admin_permission`；销售训练新域使用 helper 函数 + 业务断言，**拦截有效但风格不一致**。✅
- **凭证管理**：JWT/SSO/密码 重置链路完整；生产 fail-fast 覆盖核心 secret。✅
- **加密**：仅 ModelConfig + RagProfile API Key 走 Fernet；其他密钥依赖 env。✅（小幅扩展覆盖到 `extra_config`）
- **日志脱敏**：marker 集合偏小（缺 `api_key`/`secret`/`apikey`），需扩展。⚠
- **WebSocket 鉴权**：token 验证但**不 close 失败、不绑定 sub↔session**。❌（P1-3/4）
- **CORS**：默认 dev 内网放行，生产误置 ENV 风险。⚠
- **XSS**：静态零命中 ✅
- **限流 / IP 信任**：未做反代可信链校验 ⚠

> 整体**未发现 P0 致命问题**；P1 集中在 WebSocket 鉴权完整性、admin 列表邮箱脱敏、IP 信任链三处，需在 1-2 周内收敛。
