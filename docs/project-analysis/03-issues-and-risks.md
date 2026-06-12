# 项目问题诊断报告 —— 架构、设计与潜在缺陷

> 生成时间：2026-06-09
> 分析范围：backend/src + web/src 全量代码（只读分析）
> 说明：本文档基于代码静态分析识别的问题，未运行动态测试验证。问题按严重程度分为 P0（阻断）、P1（高危）、P2（中危）、P3（低危/技术债）。

---

## 目录

1. [P0 级问题（阻断性）](#一p0-级问题阻断性)
2. [P1 级问题（高危）](#二p1-级问题高危)
3. [P2 级问题（中危）](#三p2-级问题中危)
4. [P3 级问题（低危/技术债）](#四p3-级问题低危技术债)
5. [架构层面的系统性问题](#五架构层面的系统性问题)
6. [前端特定问题](#六前端特定问题)
7. [数据库与持久化问题](#七数据库与持久化问题)
8. [安全与合规问题](#八安全与合规问题)
9. [性能与扩展性问题](#九性能与扩展性问题)
10. [改进路线图建议](#十改进路线图建议)

---

## 一、P0 级问题（阻断性）

### P0-001: Presentation PPT 替换操作的并发写竞争

**问题描述**：`presentation_coach/api/presentations.py` 中的 `replace` 端点存在已确认的并发写竞争（`confirmed_concurrent_writer_race`）。当多个管理员同时替换同一个 PPT 时，可能导致文件元数据和页数据的不一致。

**影响范围**：`POST /api/v1/presentations/:id/replace`，管理后台 PPT 管理页面。

**根因分析**：
- 替换操作涉及多步骤：更新 `presentations` 表、删除旧 `pages`、插入新 `pages`、更新 `forbidden_words`。
- 无数据库级乐观锁（version_number 虽存在但未在替换流程中做 CAS 校验）。
- 无分布式锁或行级锁保护。

**修复建议**：
1. 在替换流程开始时对 `presentations` 行加 `SELECT FOR UPDATE` 锁。
2. 使用 `version_number` 做乐观锁校验，不匹配则返回 `409 CONCURRENT_MODIFICATION`。
3. 将替换操作封装为原子性数据库事务。

---

### P0-002: Presentation PPT 删除缺少活跃会话拦截

**问题描述**：`DELETE /api/v1/presentations/:id` 缺少对活跃 `practice_sessions` 的引用检查（`confirmed_route_guard_gap`）。删除正在被练习引用的 PPT 会导致运行时错误。

**影响范围**：管理后台 PPT 删除操作。

**根因分析**：删除前未检查 `practice_sessions.presentation_id` 外键引用，也未检查 session 状态是否为 `in_progress`。

**修复建议**：
1. 删除前查询 `SELECT COUNT(*) FROM practice_sessions WHERE presentation_id = :id AND status IN ('preparing', 'in_progress')`。
2. 若存在活跃会话，返回 `409 ACTIVE_SESSIONS_EXIST`。
3. 或改为软删除（`status = 'archived'`）而非物理删除。

---

### P0-003: AI Coach 功能前后端对齐风险

**问题描述**：Git 工作区存在未提交的 Alembic 迁移文件 `20260609_1000_078_sales_trainer_ai_coach.py` 和 `20260609_1100_078b_sales_trainer_ai_coach_interaction_fields.py`，表明 AI Coach 功能正在开发中。前端已存在完整的 AI Coach 页面和 API 调用，但后端数据库模型可能尚未完全对齐。

**影响范围**：`/sales-trainer/business-skills/coach` 页面，`/newcomer-training/ai-coach/*` API。

**根因分析**：功能开发中的中间状态，前后端交付节奏不同步。

**修复建议**：
1. 立即验证 `sales_trainer_ai_coach_sessions` 和 `sales_trainer_ai_coach_turns` 表是否与后端模型完全一致。
2. 确认 `POST /newcomer-training/ai-coach/sessions` 和 `POST /turns` 的后端实现完整性。
3. 在功能完全落地前，前端页面应添加功能开关或降级提示。

---

### P0-004: WebSocket 所有权校验与 session 状态竞态条件

**问题描述**：`websocket_routes.py` 中的所有权校验（`_resolve_presentation_session_owner_id`）在并发场景下可能与 `RuntimeGate.admit_session()` 的校验存在时间窗口差。一个 session 在被连接的同时可能被另一个请求修改 `user_id` 或 `status`。

**影响范围**：所有 WebSocket 端点（`/ws/presentation`, `/ws/sales`, `/ws/curriculum/examiner`）。

**根因分析**：
- `resolve_owner_id` 和 `admit_session` 分别执行两次独立的数据库查询。
- 两次查询之间没有事务隔离。
- 如果管理员在两次查询之间转移了 session 所有权，可能导致非所有者成功连接。

**修复建议**：
1. 将 `admit_session` 和所有权校验合并为单次数据库查询。
2. 使用 `SELECT FOR UPDATE` 在准入时对 `practice_sessions` 行加锁。
3. 在 `RuntimeAdmissionDecision` 中直接包含 `owner_id`，避免二次查询。

---

## 二、P1 级问题（高危）

### P1-001: `common/db/models.py` 单文件 2600+ 行，维护成本极高

**问题描述**：所有核心 ORM 模型（约 65 张表）集中在单个文件中，违反了关注点分离原则。任何表的修改都需要加载整个文件，增加了代码冲突概率和认知负担。

**影响范围**：全部后端开发、数据库 schema 演进、Code Review 效率。

**根因分析**：
- 历史遗留的单文件组织方式。
- 缺乏按领域拆分模型的架构决策。
- 存在跨表外键时，拆分需要处理循环导入问题。

**修复建议**：
1. 按领域拆分为多个模型文件：`user_models.py`, `session_models.py`, `content_models.py`, `config_models.py` 等。
2. 使用 SQLAlchemy 的 `__tablename__` 和 `ForeignKey` 字符串引用（而非类引用）避免循环导入。
3. 保留 `common/db/models.py` 作为向后兼容的聚合导入点（re-export）。

---

### P1-002: `practice_session_service.py` 的循环导入风险

**问题描述**：`common/services/practice_session_service.py` 同时导入了 `websocket/base_handler.py`、`session_manager.py`、`presentation_coach.services`、`sales_bot.services` 和 `training_runtime.service`。这种高层服务向低层基础设施的辐射式导入形成了潜在的循环依赖网。

**影响范围**：会话创建、生命周期管理、运行时启动。

**根因分析**：
- `PracticeSessionCreateService` 试图在一次调用中完成所有编排（验证、策略解析、curriculum 应用、DB 写入）。
- 将 WebSocket 连接管理器的引用带入了 HTTP 层服务。

**修复建议**：
1. 引入事件总线（Event Bus）或消息队列，将 "session 创建完成" 事件发布出去，由 WebSocket 层订阅处理。
2. 将 `PracticeSessionCreateService` 拆分为更小的领域服务：`SessionValidationService`、`VoicePolicyResolver`、`CurriculumSnapshotBuilder`。
3. 使用依赖倒置原则，让高层服务依赖抽象接口而非具体实现。

---

### P1-003: WebSocket query token 在生产环境的兼容风险

**问题描述**：`websocket_routes.py` 和 `common/auth/service.py` 中，`resolve_websocket_token` 支持从 query param 解析 token（开发兼容路径）。虽然 `AUTH_TRANSPORT_MATRIX` 明确标记为 `compatibility = [query_token]`，但路由层没有基于环境变量的硬阻断。

**影响范围**：所有 WebSocket 端点，生产环境安全。

**根因分析**：
- 开发便利性优先，未在生产环境强制禁用 query token。
- token 可能出现在 URL 中，被日志、代理服务器、浏览器历史记录留存。

**修复建议**：
1. 在 `websocket_routes.py` 的 `_handle_presentation_websocket` 中，当 `ENVIRONMENT == "production"` 时，若 token 仅来自 query param 而无 Authorization Header 或 Cookie，直接拒绝连接（code 4001）。
2. 添加明确的运行时断言：`assert not (is_production and token_source == "query_only")`。
3. 在健康检查端点暴露 "auth_transport_strictness" 指标。

---

### P1-004: CSRF 豁免列表硬编码且可能遗漏

**问题描述**：`http_routes.py` 中的 `CSRF_EXEMPT_PATHS` 是硬编码集合。新增公共端点（如 OAuth callback、第三方 webhook）时，开发者可能忘记加入豁免列表，导致合法请求被 CSRF 中间件拦截。

**影响范围**：所有新增公共 HTTP 端点。

**根因分析**：
- 豁免列表是命令式维护的（imperative），而非声明式。
- FastAPI router 注册时无法自动感知 CSRF 策略。

**修复建议**：
1. 在 `register_routers` 时，要求每个 public router 显式声明 `csrf_exempt=True` 元数据。
2. 添加启动时校验：扫描所有路由，检查 public 路由是否在豁免列表中，不一致则抛异常拒绝启动。
3. 或将 CSRF 策略内嵌到路由装饰器中：`@router.post("/webhook", csrf_exempt=True)`。

---

### P1-005: `common/db/models.py` 中 CheckConstraint 在 SQLite 下的兼容性

**问题描述**：项目大量使用数据库级 `CheckConstraint` 进行枚举值校验（如 `role IN (...)`、`status IN (...)`）。SQLite 对 `CheckConstraint` 的支持存在限制，特别是在 `JSON` 类型字段的子属性校验上可能无效。

**影响范围**：数据完整性，特别是开发环境（SQLite）。

**根因分析**：
- `_jsonb_compatible_type()` 在 SQLite 下回退到 `JSON`，而 SQLite 的 JSON 支持是扩展性质的。
- `CheckConstraint` 中引用 JSON 路径的表达式在 SQLite 中可能不生效。
- 开发环境使用 SQLite，可能引入在 PostgreSQL 下不会出现的脏数据。

**修复建议**：
1. 在应用层（Pydantic Schema / SQLAlchemy Validators）增加与数据库约束等价的校验。
2. 在 CI 中使用 PostgreSQL 容器跑集成测试，确保约束一致性。
3. 在 `init_db()` 中添加 SQLite 约束兼容性检查，发现不支持的数据库构造时抛警告。

---

### P1-006: 单例模式在进程级共享状态的隐患

**问题描述**：`SessionManager`、`SessionStateService`、`ConnectionManager`、`LatencyTracker` 均以模块级全局变量实现进程内单例。在多进程部署（Uvicorn workers > 1）时，这些单例不再共享状态，导致：
- 同一 session 的 WebSocket 连接可能被不同 worker 处理。
- 断线重连时无法从其他 worker 的内存中恢复状态。
- 连接踢除（kick old connection）在跨 worker 场景下失效。

**影响范围**：生产环境多进程部署。

**根因分析**：
- 单例设计假设了整个应用是单进程模型。
- 未在架构文档中明确标注 "仅适用于单进程部署"。

**修复建议**：
1. 将所有进程级单例迁移到 Redis 或共享内存。
2. 在 `SessionManager` 的文档字符串中明确标注 "进程内单例，多进程部署需使用 Redis 后端"。
3. 启动时检测 `uvicorn.workers` 配置，若 >1 且未配置 Redis，抛警告或拒绝启动。

---

### P1-007: 密码重置的 Partial UNIQUE 约束在迁移中的兼容性

**问题描述**：`password_reset_tokens` 表使用了 `Partial UNIQUE` 约束（`WHERE used_at IS NULL AND invalidated_at IS NULL`）。这在 SQLite 中通过 `sqlite_where` 实现，在 PostgreSQL 中通过 `postgresql_where` 实现。Alembic 自动迁移可能无法正确识别这种条件唯一约束。

**影响范围**：密码重置功能，schema 迁移。

**根因分析**：
- SQLAlchemy 的部分索引在不同数据库后端中的语法差异较大。
- Alembic 的自动迁移生成器（`autogenerate`）对 `postgresql_where`/`sqlite_where` 的支持有限。

**修复建议**：
1. 在 Alembic 迁移中手写该索引的创建/删除语句，不依赖 autogenerate。
2. 添加数据库无关的替代方案：在应用层查询 `SELECT ... WHERE user_id = :uid AND used_at IS NULL AND invalidated_at IS NULL`，若已存在则先作废旧令牌。
3. 在 `PasswordResetService` 中增加幂等性保护。

---

### P1-008: StepFun Realtime 上游连接异常断开时的资源泄漏

**问题描述**：`StepFunRealtimeHandler` 在 `finally` 块中关闭上游连接，但如果上游连接在 `asyncio.gather` 中异常取消，`_close_upstream()` 可能未完全释放 `websockets` 客户端协议的资源。

**影响范围**：销售实时对话 WebSocket，长时间运行的会话。

**根因分析**：
- `websockets` 库在异常关闭时需要显式调用 `close()` 并等待关闭握手完成。
- `finally` 块中的关闭逻辑可能未处理 `asyncio.CancelledError` 的特殊情况。

**修复建议**：
1. 使用 `asyncio.timeout` 包装 `_close_upstream()`，确保关闭操作不会无限挂起。
2. 添加连接泄漏检测：定期检查 `gc.get_objects()` 中的 WebSocketClientProtocol 实例数量。
3. 在 `session_manager.unregister_session` 中强制关闭所有关联的上游连接。

---

## 三、P2 级问题（中危）

### P2-001: 音频流背压控制仅客户端侧，服务端不同步

**问题描述**：前端 `usePracticeWebSocket` 实现了本地缓冲（最大 200 帧 ~4 秒）和背压控制（`slow_down`/`resume`）。但服务端 `StepFunRealtimeHandler` 的背压水位线是 512KB，两者的阈值和策略不一致。客户端可能还在发送音频，但服务端已丢弃。

**影响范围**：实时语音对话的音频质量。

**修复建议**：
1. 将服务端背压阈值通过 WebSocket 消息同步给客户端（如 `backpressure_config` 初始化消息）。
2. 统一背压单位：以时间（毫秒）而非字节数作为阈值。
3. 在 `session.init` 消息中包含服务端的音频缓冲区容量。

---

### P2-002: `RuntimeGate` 的 `is_kb_lock_unbound_for_session_id` 超时策略僵化

**问题描述**：`STEPFUN_KB_LOCK_DECISION_TIMEOUT_MS` 默认 2200ms。在知识库查询慢或 ChromaDB 负载高时，这个超时可能导致本可以运行的 session 被错误拒绝。

**影响范围**：需要知识库绑定的练习会话。

**修复建议**：
1. 将超时配置为可动态调整（从 `business_rule_configs` 读取）。
2. 实现渐进式 KB Lock 检查：先快速检查（500ms），若超时则标记为 "degraded" 而非直接拒绝，允许会话以降级模式启动。
3. 将 KB Lock 检查结果缓存（TTL = 60s），避免对同一 session 重复查询。

---

### P2-003: 评分规则集双轨制导致的数据不一致

**问题描述**：`evaluation_runs` → `training_report_snapshots` 构成版本化评分报告，同时 `comprehensive_reports` 和 `staged_evaluation_results` 提供传统单 session 报告。两种评分系统使用不同的 ruleset 来源和计算逻辑，可能产生不一致的分数。

**影响范围**：报告展示、督导评审、学员成长追踪。

**修复建议**：
1. 在 `comprehensive_reports` 中显式记录使用的 ruleset ID 和版本。
2. 添加评分差异检测：比较同一 session 在两种系统中的分数，若差异 >5 分则告警。
3. 逐步将 `comprehensive_reports` 迁移到 `evaluation_runs` 体系，废弃旧路径。

---

### P2-004: `PromptTemplate` SQLAlchemy 模型与 Pydantic 模型同名

**问题描述**：`common/db/models.py` 中的 `PromptTemplate` 是 SQLAlchemy ORM 模型，而 `prompt_templates/models.py` 中的同名类是 Pydantic Schema。虽然通过 `from_attributes=True` 桥接，但 IDE 自动导入和类型检查容易混淆。

**影响范围**：开发者体验，类型安全。

**修复建议**：
1. 将 Pydantic 模型重命名为 `PromptTemplateSchema` 或 `PromptTemplateDTO`。
2. 使用 `typing.NewType` 区分两种类型。
3. 在 `__init__.py` 中显式导出正确的类型。

---

### P2-005: 前端 `apiFetch` 环回地址切换在 IPv6 环境下异常

**问题描述**：`fetchWithLoopbackRetry` 在 `localhost` 失败时回退到 `127.0.0.1`。在纯 IPv6 环境或 `::1` 绑定的主机上，这个回退可能失效。

**影响范围**：开发环境网络请求。

**修复建议**：
1. 检测 `window.location.hostname`，若已是 IP 地址则跳过环回切换。
2. 支持 `::1` 作为回退地址之一。
3. 将环回切换逻辑限制在开发环境（`process.env.NODE_ENV === 'development'`）。

---

### P2-006: `ConversationMessage` 的重复消息检测基于 `(turn, role, content)` 去重

**问题描述**：`common/conversation/storage.py` 中的去重逻辑使用 `(turn_number, role, content)` 三元组。如果用户或 AI 在相同 turn 发送了完全相同的文本（如重复的 "好的"），第二次消息会被丢弃。

**影响范围**：消息持久化，回放数据完整性。

**修复建议**：
1. 加入 `timestamp` 或 `message_id` 到去重键中，允许相同内容在相同 turn 出现。
2. 将去重改为 "最近 5 秒内相同内容" 而非严格的 turn 级别。
3. 添加 `deduplication_key` 字段，显式标记是否应被去重。

---

### P2-007: 销售训练 `sales_trainer_asset_revisions` 自引用外键的级联风险

**问题描述**：`sales_trainer_asset_revisions` 的 `source_revision_id` 是自引用外键。在级联删除或清理旧版本时，可能形成级联链，意外删除大量历史版本。

**影响范围**：配置版本管理，数据归档。

**修复建议**：
1. 将 `source_revision_id` 的 `ondelete` 改为 `SET NULL` 而非 `CASCADE`。
2. 在删除版本前检查 `sales_trainer_asset_active_revisions` 引用，拒绝删除活跃版本。
3. 添加版本归档机制（软删除），而非物理删除。

---

### P2-008: `question_categories` 自引用树的 RESTRICT 删除策略

**问题描述**：`question_categories.parent_id` 使用 `RESTRICT` 删除策略。当尝试删除一个有子分类的分类时，会直接触发数据库错误而非应用层可控的异常。

**影响范围**：题库管理后台。

**修复建议**：
1. 在删除 API 中先查询子分类数量，若 >0 则返回 `409 HAS_CHILD_CATEGORIES`。
2. 提供 "级联删除" 和 "转移到其他父分类" 两种选项。
3. 将数据库级 `RESTRICT` 改为 `SET NULL`，在应用层实现业务规则。

---

### P2-009: 企业微信 SSO 的 state cookie 未标记 SameSite=strict

**问题描述**：`set_wecom_oauth_flow_cookies` 设置的 state cookie 未显式标记 `SameSite`。在默认配置下，浏览器可能将其视为 `SameSite=Lax`，在跨站场景下（某些企业微信部署配置）可能导致 OAuth 流程失败。

**影响范围**：企业微信登录功能。

**修复建议**：
1. 显式设置 `SameSite=strict`（因 state 仅在 OAuth 回调中使用）。
2. 设置 `Secure` 标志（强制 HTTPS）。
3. 缩短 state cookie 的 TTL（建议 5 分钟，当前可能使用默认 session TTL）。

---

### P2-010: `config_bundle_audit_logs` 与 `business_rule_config_audit_logs` 结构冗余

**问题描述**：两个审计日志表结构几乎相同（`action`, `actor_id`, `before_snapshot_json`, `after_snapshot_json`, `trace_id` 等），但分别存储。这导致审计查询需要 `UNION ALL`，增加了查询复杂度和性能开销。

**影响范围**：审计追踪功能，Admin 审计页面。

**修复建议**：
1. 统一审计日志表，添加 `log_type` 字段区分不同来源。
2. 或保留物理分离但引入统一的审计日志写入接口（`AuditLogWriter`）。
3. 在查询层使用物化视图（PostgreSQL）或定期聚合表。

---

## 四、P3 级问题（低危/技术债）

### P3-001: `main.py` 向后兼容层污染命名空间

**问题描述**：`main.py` 为了兼容旧测试，从 `websocket_routes` 中导入了大量私有函数（以 `_` 开头）到模块命名空间。这违反了 Python 的私有约定，且使 `main` 模块承载了不应有的职责。

**修复建议**：
1. 更新测试以直接导入 `websocket_routes` 模块。
2. 在 `main.py` 中添加 `__all__` 限制公开接口。
3. 设置 deprecation timeline，逐步移除兼容层。

---

### P3-002: `Agent.system_prompt` 和 `default_knowledge_base_ids` 已弃用但未清理

**问题描述**：`agent/models.py` 中 `Agent` 的 `system_prompt` 和 `default_knowledge_base_ids` 已标记为弃用，但数据库列仍然存在，代码中也保留了兼容性读取逻辑。

**修复建议**：
1. 创建 Alembic 迁移删除这两个列。
2. 在前端和管理界面移除相关输入字段。
3. 更新所有测试不再引用这些字段。

---

### P3-003: `Scenario.persona_prompt` 标记为 legacy 但未清理

**问题描述**：`scenarios` 表的 `persona_prompt` 字段标记为 legacy compatibility only，运行时真相来自 `persona_policy`，但数据库列和代码兼容性逻辑仍然存在。

**修复建议**：
1. 确认所有 production 数据已完成迁移。
2. 删除 `persona_prompt` 列。
3. 从 `scenario` 相关 API 中移除该字段的序列化。

---

### P3-004: `zustand` 在 package.json 中存在但未被使用

**问题描述**：前端依赖中包含 `zustand`，但实际状态管理完全由 `@tanstack/react-query` 和 React `useState` 承担。

**修复建议**：
1. 从 `package.json` 中移除 `zustand` 依赖。
2. 清理 `node_modules` 和 lock 文件。

---

### P3-005: 前端 `useSearchParams` 过度使用导致 URL 臃肿

**问题描述**：大量页面使用 `useSearchParams` 传递 `unitId`、`sessionId`、`agent_id`、`persona_id`、`voice_mode` 等参数。部分参数（如 `voice_mode`）可能通过全局状态或 Context 更合适地管理。

**修复建议**：
1. 将运行时配置（`voice_mode`、`agent_id`）存入 `localStorage` 或全局 Context。
2. 仅在需要书签/分享的场景下保留 URL 参数。
3. 添加 URL 参数清理逻辑，移除无效或默认值参数。

---

### P3-006: `common/ai/encryption.py` 的 `mask_key` 实现过于简单

**问题描述**：`mask_key` 仅显示前 3 个字符和最后 4 个字符（如 `"sk-...9789"`），对于短密钥或内部调试场景，掩码强度不足。

**修复建议**：
1. 采用标准掩码格式：保留前缀标识（如 `sk-`），中间全部替换为 `*`。
2. 或根据密钥长度动态调整显示位数：长度 < 20 时显示更少位数。

---

### P3-007: `common/monitoring/health.py` 仅检查数据库 readiness

**问题描述**：`/health` 端点仅执行 `select 1` 检查数据库。未检查 ChromaDB 连接、StepFun API 连通性、LLM 配置有效性等关键依赖。

**修复建议**：
1. 扩展健康检查为多个维度：database, chromadb, stepfun_api, llm_configured。
2. 添加 "降级就绪"（degraded readiness）状态，允许部分依赖失败时仍提供服务。
3. 区分 `/health/live`（进程存活）和 `/health/ready`（可接受流量）。

---

### P3-008: `PresentationStepFunRealtimeHandler` 禁用销售能力的方式是运行时标记

**问题描述**：通过 `enabled=False` 在 `capabilities_config` 中禁用销售专属能力，而非代码层面的隔离。如果配置解析出错或被人为覆盖，这些能力可能在演讲场景中被意外启用。

**修复建议**：
1. 在 `PresentationStepFunRealtimeHandler` 中显式覆盖 `_load_capabilities` 方法，过滤掉销售专属能力 ID。
2. 添加能力白名单校验：演讲场景仅允许 `knowledge_retrieval` 和 `realtime_scoring`。

---

### P3-009: `admin/config_bundles/domains.py` 的 "migrated" 状态未持续验证

**问题描述**：`DOMAIN_REGISTRY` 中大量 domain 标记为 `status: "migrated"`，但缺乏自动化验证确保这些 domain 确实已完全迁移到 ConfigBundle 体系。

**修复建议**：
1. 添加启动时校验：对每个标记为 migrated 的 domain，检查对应的 bundle_keys 是否确实存在于数据库。
2. 添加集成测试：验证每个 migrated domain 的读写路径均经过 ConfigBundle。

---

### P3-010: `common/audio/tts_factory.py` 的降级链缺少指标

**问题描述**：TTS 降级链（阿里云 → Edge-TTS → 浏览器 TTS）的降级事件未记录到监控指标中，无法在生产环境中追踪降级频率。

**修复建议**：
1. 在每次降级时递增 Prometheus Counter：`tts_fallback_total{from="aliyun",to="edge-tts"}`。
2. 在 `LatencyTracker` 中记录每次 TTS 请求的 provider 和降级路径。

---

## 五、架构层面的系统性问题

### 5.1 配置漂移与多真相源

**问题**：同一业务概念存在多个配置入口：
- Agent 的 `capabilities_config` vs Persona 的 `behavior_config`
- `voice_runtime_profiles` vs `agent_voice_policies`
- `business_rule_configs` vs `config_bundles`
- `rag_profiles` vs `knowledge_config_versions`

运行时合并这些配置的优先级逻辑分散在多个文件中（`agent/context.py`, `common/services/practice_session_service.py`, `sales_bot/services/voice_instruction_compiler.py`），容易导致配置漂移和意外覆盖。

**建议**：
1. 建立统一的 "运行时配置编译器"，将所有配置来源按优先级合并为单一不可变的 `RuntimeConfig` 对象。
2. 在 `PracticeSession` 创建时即完成配置编译，将结果写入 `runtime_config_snapshot`。
3. 所有运行时逻辑只读取 snapshot，不再实时查询配置表。

### 5.2 错误处理策略的不一致性

**问题**：
- HTTP 层使用 `Result[T]` Monad（`common/error_handling/result.py`）。
- WebSocket 层使用异常捕获 + fallback 指令（`ErrorHandlerMiddleware._get_fallback_response`）。
- 部分服务层直接抛出 `RuntimeError` 或 `ValueError`。
- 前端对 HTTP 错误使用 `ApiRequestError`，对 WS 错误使用自定义事件。

这导致同一类错误（如 LLM 超时）在不同入口有不同的表现。

**建议**：
1. 统一错误分类体系（Terminal/Transient/Voluntary），在 L2 契约层定义。
2. 所有服务层返回 `Result[T]`，在传输层统一映射。
3. WebSocket 的 fallback 指令应从错误分类自动生成，而非硬编码映射。

### 5.3 测试金字塔失衡

**问题**：
- `pytest.ini` 中 `cov-fail-under=48` 的覆盖率门槛偏低。
- 存在大量单元测试，但端到端测试（playwright）可能未覆盖关键用户旅程（如完整的一次销售对话 → 报告生成）。
- `common/db/models.py` 的庞大体积导致模型相关测试难以维护。

**建议**：
1. 将覆盖率门槛提升至 70%（核心业务逻辑）+ 50%（基础设施）。
2. 增加关键用户旅程的 E2E 测试：登录 → 创建 session → WebSocket 对话 → 生成报告。
3. 使用 `factory-boy` 或类似工具简化模型测试数据构建。

### 5.4 前端组件与业务逻辑耦合

**问题**：
- 大量页面组件直接调用 `api.*` 方法，而非通过领域层抽象。
- `usePracticeWebSocket` 和 `useExaminerWebSocket` 各自实现了相似的重连、去重、背压逻辑，存在代码重复。
- Admin 页面中大量表单逻辑直接内嵌在 page.tsx 中。

**建议**：
1. 引入前端领域层（Domain Layer），将 API 调用封装为可测试的领域服务。
2. 提取通用的 WebSocket Hook 基类，将重连、去重、背压作为可组合的 Hook。
3. 将 Admin 表单逻辑提取为独立的 Form Container 组件。

---

## 六、前端特定问题

### 6.1 音频录制 Worklet 的浏览器兼容性

**问题**：`useAudioRecorder` 使用 `AudioWorklet` 进行音频处理。在 Safari < 14.1 和部分 Android WebView 中，`AudioWorklet` 不被支持，会导致练习页面完全无法使用麦克风。

**建议**：
1. 添加 `AudioWorklet` 特性检测，不支持时回退到 `ScriptProcessorNode`。
2. 或显示明确的浏览器兼容性提示，引导用户使用 Chrome/Edge。

### 6.2 流式 TTS 音频的内存泄漏

**问题**：`useStreamingAudioPlayer` 在组件卸载时可能未完全释放 `AudioBufferSourceNode` 和 `AudioContext`，导致内存泄漏。

**建议**：
1. 在 `useEffect` 的 cleanup 函数中显式调用 `audioContext.close()`。
2. 使用 `WeakRef` 追踪音频节点，在垃圾回收前主动断开连接。

### 6.3 React Server Components 与客户端状态的不一致

**问题**：Next.js App Router 的 `layout.tsx` 使用服务端组件获取当前用户（`requireServerSession`），但客户端使用 `useQuery` 重新获取用户。两者可能在登录/登出瞬间产生不一致（服务端渲染的是旧用户，客户端 hydrate 后更新为新用户）。

**建议**：
1. 在 `layout.tsx` 中将服务端获取的用户通过 `initialData` 传递给 React Query。
2. 添加客户端 hydration 不匹配检测，不一致时自动刷新页面。

### 6.4 训练偏好的 localStorage 与远程双写冲突

**问题**：`use-training-preferences.ts` 使用 localStorage + 远程 `/users/me/training-preferences` 双写。冲突解决仅按 `updatedAt` 时间戳合并，若客户端时钟偏差较大，可能导致数据被错误覆盖。

**建议**：
1. 使用服务器时间作为唯一权威时间源。
2. 添加版本向量（version vector）或 last-write-wins 的显式冲突提示。
3. 在设置页面添加 "检测到冲突，请选择保留本地或远程" 的对话框。

---

## 七、数据库与持久化问题

### 7.1 `practice_sessions` 表的字段膨胀

**问题**：`practice_sessions` 已有 30+ 个字段，涵盖会话元数据、运行时状态、评分结果、音频信息、报告状态等。这张表已成为 "万能表"，违反了单一职责原则。

**建议**：
1. 拆分为 `session_metadata`（核心字段）+ `session_runtime_state`（运行时动态字段）+ `session_scoring`（评分相关）。
2. 或使用 JSON 列进一步规范化：将 `voice_policy_snapshot`、`curriculum_snapshot`、`effectiveness_snapshot` 等合并为统一的 `runtime_snapshots` JSON。

### 7.2 `conversation_messages` 的文本搜索性能

**问题**：`conversation_messages.content` 是 `Text` 类型，无全文索引。当需要搜索历史消息时（如督导审查、高光片段检索），性能会随数据量增长而下降。

**建议**：
1. 在 PostgreSQL 下添加 `GIN` 全文搜索索引：`CREATE INDEX idx_msg_content_fts ON conversation_messages USING GIN (to_tsvector('chinese', content))`。
2. 在 SQLite 下使用 `FTS5` 扩展创建虚拟表。
3. 或将消息内容同步到 Elasticsearch/Meilisearch 做专用搜索。

### 7.3 `sales_trainer_ai_coach_turns` 的 raw_model_output 存储膨胀

**问题**：`raw_model_output` 存储了每次 LLM 调用的完整原始响应，对于长对话历史，这部分数据可能非常庞大。当前未设置清理策略。

**建议**：
1. 对 `raw_model_output` 添加 TTL 策略：30 天后自动清理或归档到对象存储。
2. 或将其存储到单独的 `ai_coach_turn_logs` 表，主表仅保留精简结果。

---

## 八、安全与合规问题

### 8.1 `api_key_encrypted` 的加密密钥管理

**问题**：`model_configs.api_key_encrypted` 使用 Fernet（AES-256）加密，密钥来自 `MODEL_CONFIG_ENCRYPTION_KEY` 环境变量。若该环境变量在运行时变更，已加密的旧密钥将无法解密。

**建议**：
1. 实现密钥轮换机制：支持同时保留新旧两个解密密钥。
2. 添加启动时密钥有效性检查：尝试解密一个测试值，失败则拒绝启动。
3. 考虑使用 HashiCorp Vault 或 AWS KMS 等外部密钥管理服务。

### 8.2 高光分享链接的 token 哈希碰撞风险

**问题**：`highlight_review_shares.token_hash` 使用 SHA-256 哈希。虽然 SHA-256 的碰撞概率极低，但分享 token 的熵源是随机字符串，若随机数生成器质量不足，可能导致可预测的 token。

**建议**：
1. 使用 `secrets.token_urlsafe(32)` 生成高熵 token。
2. 添加 token 速率限制：同一 IP 短时间内最多创建 N 个分享链接。
3. 在分享页面添加人机验证（reCAPTCHA 或类似）防止自动化扫描。

### 8.3 `session_audio_segments` 的 object_key 可能暴露存储路径

**问题**：`object_key` 直接存储在数据库中，若对象存储的 bucket 是公开的，object_key 的泄露可能导致未授权访问。

**建议**：
1. 使用预签名 URL（presigned URL）替代直接暴露 object_key。
2. 在 `GET /sessions/:id/audio-segments/:seq` 端点动态生成短期有效的签名 URL（TTL = 5 分钟）。
3. 确保对象存储 bucket 为私有，仅通过预签名 URL 访问。

---

## 九、性能与扩展性问题

### 9.1 ChromaDB 的单机限制

**问题**：当前使用本地 ChromaDB，所有 Embedding 和向量检索在单机上运行。随着知识库文档数量增长，内存占用和检索延迟会成为瓶颈。

**建议**：
1. 评估迁移到 ChromaDB 的分布式部署或 Pinecone / Weaviate / Milvus。
2. 添加 Embedding 缓存层，避免对相同查询重复计算 Embedding。
3. 实现知识库分片：按 domain 或 tenant 分割到不同的 collection。

### 9.2 `LatencyTracker` 的内存增长

**问题**：`LatencyTracker` 使用内存中的列表记录所有延迟样本，长时间运行后可能无限增长。

**建议**：
1. 添加采样窗口：仅保留最近 10,000 个样本。
2. 定期将聚合后的 P50/P95/P99 写入 Prometheus，清空原始样本。
3. 或使用环形缓冲区（`collections.deque(maxlen=...)`）替代列表。

### 9.3 前端 bundle 体积

**问题**：`recharts` 和 `framer-motion` 是较大的库，如果所有页面都包含它们，首屏加载时间会增加。

**建议**：
1. 使用 Next.js 的 `dynamic()` 懒加载图表组件。
2. 分析 `next-bundle-analyzer` 输出，识别最大的依赖项。
3. 考虑将 `recharts` 替换为更轻量的图表库（如 `chart.js`）。

---

## 十、改进路线图建议

### 第一阶段：稳定性（1-2 周）

1. 修复 P0 级问题：PPT 替换/删除的竞争条件、AI Coach 前后端对齐。
2. 修复 P1-003：WebSocket query token 生产环境硬阻断。
3. 修复 P1-004：CSRF 豁免列表启动时校验。
4. 修复 P1-006：多进程部署检测与警告。

### 第二阶段：可维护性（2-4 周）

1. 拆分 `common/db/models.py` 为按领域的模型文件。
2. 统一错误处理策略，消除 HTTP/WS 层的处理差异。
3. 提取前端通用 WebSocket Hook 基类。
4. 清理已弃用字段（Agent.system_prompt, Scenario.persona_prompt）。

### 第三阶段：性能与扩展性（4-8 周）

1. 评估 ChromaDB 的分布式方案或替代产品。
2. 实现运行时配置编译器，消除多真相源问题。
3. 添加全文搜索索引（conversation_messages）。
4. 优化前端 bundle 体积（懒加载、代码分割）。

### 第四阶段：安全加固（持续）

1. 实现 API Key 加密密钥轮换。
2. 高光分享链接迁移到预签名 URL。
3. 添加安全扫描（bandit, semgrep）到 CI 流程。
4. 实现统一的审计日志写入接口。

---

*文档结束。本文档基于 2026-06-09 的代码快照静态分析生成，未修改任何源代码。问题优先级和修复建议需结合业务实际和团队资源进一步评估。*
