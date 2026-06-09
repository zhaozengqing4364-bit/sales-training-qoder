# 代码问题追踪记录 (2026-06-03)

> **状态**：Draft（待批准）
> **来源**：8 份专题报告（`00` ~ `08`）
> **关联**：`10-issue-drafts.md`（含 gh issue 草稿）+ `11-AGENTS-CLAUDE-patch.md`（规范回写 diff）
> **维护**：本文件为"代码问题总账"，每个 issue 提交后回填编号

---

## 0. 摘要

| 严重度 | 数量 | 关联 Issue 范围 |
|--------|------|--------------|
| 🔴 **P0 阻断** | **24 项** | `10-issue-drafts.md` P0-01 ~ P0-24 |
| 🟡 **P1 严苛** | **约 60 项** | `10-issue-drafts.md` P1-01 ~ P1-15 + 中小项 |
| 🟢 **P2/P3 持续** | **约 30 项** | 持续优化 |
| **合计** | **约 114 项** | Sprint-1 (24) + Sprint-2 (60+) + Sprint-3 (30+) |

---

## 1. P0 阻断 (24 项)

| 编号 | 主题 | 来源 | 关联 Issue | Sprint | 状态 |
|------|------|------|----------|--------|------|
| code-001 | 跨域继承 `PresentationStepFunRealtimeHandler` → `StepFunRealtimeHandler` | Agent 1 F-01 / Agent 3 §10 | P0-01 | 1 | 待办 |
| code-002 | WS 鉴权失败不 `close(4401)` | Agent 6 P1-3 | P0-02 | 1 | 待办 |
| code-003 | WS 鉴权 `payload["sub"]` 与 session 不绑 | Agent 6 P1-4 | P0-02 | 1 | 待办 |
| code-004 | `STEPFUN_API_KEY` 明文读取 | Agent 4 F-SEC-1 | P0-03 | 1 | 待办 |
| code-005 | 17 个 Prometheus 指标死代码 | Agent 4 F-OBS-1 / Agent 8 P0-2 | P0-04 | 1 | 待办 |
| code-006 | trace_id 15 文件 116 调用点断崖 | Agent 8 P0-1 | P0-05 | 1 | 待办 |
| code-007 | 销售训练 audio_submission 无 DELETE 路由 | Agent 4 D-SEC-2 / Agent 6 / Agent 8 | P0-06 | 1 | 待办 |
| code-008 | `bg-white` 526 处全量 | Agent 7 §1.4 | P0-07 | 1 | 待办 |
| code-009 | WS 客户端 `binaryType` 缺 + 二进制 PCM 入站 | Agent 7 §10.3 | P0-08 | 1 | 待办 |
| code-010 | CI 常规 PR 5 门禁缺失 | Agent 8 P0-3 | P0-09 | 1 | 待办 |
| code-011 | CLAUDE.md `main.py 19655 行` 失真 | Agent 1 F-04 | P0-24 | 1 | 待办 |
| code-012 | 3 处 `HTTPException(500)` 违宪 I | Agent 2 P0-1 | P0-11 | 1 | 待办 |
| code-013 | `common/business_rules/validators.py` 80 raise 违宪 I | Agent 2 P0-4 | P0-12 | 1 | 待办 |
| code-014 | `support/` + `supervisor/` 0 Result 引用 | Agent 2 P0-5 | P0-13 | 1 | 待办 |
| code-015 | `sales_trainer/services/*` 110+ raise | Agent 2 P0-6 | P0-14 | 1 | 待办 |
| code-016 | `agent_service.py` 13 查询零 `selectinload` | Agent 5 P0-3 | P0-15 | 1 | 待办 |
| code-017 | 14 个 JSONB 列无 GIN 索引 | Agent 5 P0-1 | P0-16 | 1 | 待办 |
| code-018 | `pool_recycle` 缺失 | Agent 5 P0-2 | P0-17 | 1 | 待办 |
| code-019 | sales_trainer list 接口零分页 | Agent 5 P0-4 | P0-18 | 1 | 待办 |
| code-020 | 项目级软删除字段缺失 | Agent 5 P0-5 | P0-19 | 1 | 待办 |
| code-021 | admin audio_submission 列表裸露 user_email | Agent 6 P1-1 | P0-20 | 1 | 待办 |
| code-022 | admin quiz_attempt 列表裸露 user_email | Agent 6 P1-2 | P0-21 | 1 | 待办 |
| code-023 | `X-Forwarded-For` 无条件信任 | Agent 6 P1-5 | P0-22 | 1 | 待办 |
| code-024 | `ASRServiceWithFallback` / `TTSServiceWithFallback` 生产 0 引用 | Agent 4 F-ASR-1 / F-TTS-1 | P0-23 | 1 | 待办 |

---

## 2. P1 严苛（约 60 项）

### 2.1 错误处理与 Result（code-025 ~ code-027）

| 编号 | 主题 | 来源 | 关联 Issue | 状态 |
|------|------|------|----------|------|
| code-025 | 错误码中心表缺失 + Result 缺 `error_code/trace_id/and_then` | Agent 2 §7 | P1-01 | 待办 |
| code-026 | TTS 5 个必备 env 未消费 | Agent 4 F-CFG-1 | P1-02 | 待办 |
| code-027 | 49 端点失败态测试 1/49 | Agent 7 §8.3 | P1-03 | 待办 |
| code-028 | sales-trainer 0 contract test | Agent 8 §6 | P1-03 | 待办 |
| code-029 | 9 个 admin sales-trainer page 0 测试 | Agent 7 §8.2 | P1-03 | 待办 |

### 2.2 限流 / 熔断 / 鉴权（code-030 ~ code-034）

| 编号 | 主题 | 来源 | 关联 Issue | 状态 |
|------|------|------|----------|------|
| code-030 | 全局/用户级/IP 级限流中间件缺失 | Agent 1 F-06 / Agent 4 D-LIMIT-1 | P1-04 | 待办 |
| code-031 | TTS/LLM/StepFun/ChromaDB 6 外部依赖零熔断 | Agent 4 D-CB-1 | P1-05 | 待办 |
| code-032 | JWT 无 `audience` / `issuer` 校验 | Agent 6 P1-7 | P1-06 | 待办 |
| code-033 | 9 个 WS 错误码无文档 | Agent 3 §8.5 | P1-07 | 待办 |
| code-034 | WS 协议无 `schema_version` 顶层字段 | Agent 3 §3.3 | P1-07 | 待办 |

### 2.3 日志 / 错误边界 / 状态管理（code-035 ~ code-040）

| 编号 | 主题 | 来源 | 关联 Issue | 状态 |
|------|------|------|----------|------|
| code-035 | 日志脱敏 marker 缺 `api_key/apikey/secret/authorization` | Agent 6 P1-9 | P1-08 | 待办 |
| code-036 | sales-trainer 14 子段 0 error.tsx | Agent 7 §2 | P1-09 | 待办 |
| code-037 | `app/global-error.tsx` 缺失 | Agent 7 §2 | P1-09 | 待办 |
| code-038 | React Query 未接入 sales-trainer（272 处 useState 抓数据） | Agent 7 §4 | P1-10 | 待办 |
| code-039 | `client.ts` 4648 行单点巨型 | Agent 7 §3 | P1-11 | 待办 |
| code-040 | `use-practice-websocket.ts` 1047 行单文件 | Agent 3 §9.4 | P1-12 | 待办 |

### 2.4 架构与配置（code-041 ~ code-048）

| 编号 | 主题 | 来源 | 关联 Issue | 状态 |
|------|------|------|----------|------|
| code-041 | `common/services/practice_session_service.py` 双向耦合业务域 | Agent 1 I-2 | P1-14 | 待办 |
| code-042 | NFR 性能测试 5/10/50/200 并发错位 | Agent 8 §4.5 | P1-15 | 待办 |
| code-043 | `common/knowledge` + `common/knowledge_engine` 双轨 6+ 自闭 | Agent 4 D-KNOW-1 | — | 待办 |
| code-044 | KB Lock 4 衍生状态码未入文档 | Agent 4 C-KB-1 | — | 待办 |
| code-045 | OTel 接入 0 业务 span | Agent 8 §3.3 | — | 待办 |
| code-046 | 3 处 raw `fetch` 绕过 `apiFetch` | Agent 7 §3.3 | — | 待办 |
| code-047 | `JWT_SECRET` 默认值硬编码（生产已 fail-fast） | Agent 6 P3-1 | — | 待办 |
| code-048 | `ModelConfig.extra_config` 未加密 | Agent 6 P2-4 | — | 待办 |

### 2.5 CORS / XSS / 杂项（code-049 ~ code-058）

| 编号 | 主题 | 来源 | 关联 Issue | 状态 |
|------|------|------|----------|------|
| code-049 | `CORS` 生产误置 `ENVIRONMENT=development` 风险 | Agent 6 P1-8 | — | 待办 |
| code-050 | `allow_methods=["*"]` + `allow_credentials=True` | Agent 6 P2-5 | — | 待办 |
| code-051 | `original_filename` 反射 Content-Disposition 浏览器下载 XSS | Agent 6 P2-7 | — | 待办 |
| code-052 | `WEBSOCKET_QUERY_TOKEN_ENABLED` 误设 → token 进入 URL | Agent 6 P2-3 | — | 待办 |
| code-053 | `admin/error.tsx` `window.location.href = '/'` 违规 | Agent 7 §9 | — | 待办 |
| code-054 | `coverage.json` 4 月未刷新 | Agent 8 P2-4 | — | 待办 |
| code-055 | `roleplay-contract-eval` 依赖 LLM grader 不可重复 | Agent 8 P3-2 | — | 待办 |
| code-056 | contract 24 / docs 18 结构性不对齐 | Agent 8 §6 | — | 待办 |
| code-057 | `client.ts` 3.24% 覆盖率（灾难） | Agent 8 §2.4 | — | 待办 |
| code-058 | `learn/[unitId]/page.test.tsx` 0 测试 | Agent 7 §8.2 | — | 待办 |

### 2.6 前端架构（code-059 ~ code-068）

| 编号 | 主题 | 来源 | 关联 Issue | 状态 |
|------|------|------|----------|------|
| code-059 | 9 admin sales-trainer 测试 0 失败态 | Agent 7 §8.3 | — | 待办 |
| code-060 | `useState` 抓数据 1177 处 | Agent 7 §4.2 | — | 待办 |
| code-061 | `next/dynamic` 0 处使用 | Agent 7 §7 | — | 待办 |
| code-062 | `lucide-react` 全量导入 | Agent 7 §7 | — | 待办 |
| code-063 | a11y: Radix 3/12 + aria-label 87 处 | Agent 7 §6 | — | 待办 |
| code-064 | `useTheme()` hook 在、dark mode 样式 0 | Agent 7 §1.3 | — | 待办 |
| code-065 | design system token 仓库未被 `@import` | Agent 7 §1.2 | — | 待办 |
| code-066 | 销售训练 admin 36 method 0 失败态测试 | Agent 7 §3 | — | 待办 |
| code-067 | admin audio_submission admin page 0 testing | Agent 7 §8.2 | — | 待办 |
| code-068 | `_mask_email` 标杆在 users，未在 audio/quiz 实施 | Agent 6 P1-1/2 | P0-20/21 | 待办 |

### 2.7 WS / 协议细节（code-069 ~ code-078）

| 编号 | 主题 | 来源 | 关联 Issue | 状态 |
|------|------|------|----------|------|
| code-069 | `_load_sales_stage_runtime_config` 与 `_disable_sales_capabilities` 重复 | Agent 3 P2 | — | 待办 |
| code-070 | `_send_status` / `_send_heartbeat` 在 sales_stage + event_payloads 重复 | Agent 3 P1 | — | 待办 |
| code-071 | `BoundedSemaphore` 协商未实际使用 | Agent 3 P2 | — | 待办 |
| code-072 | `tts_audio` + `tts_chunk` 双轨 | Agent 3 P2 | — | 待办 |
| code-073 | UNHANDLED 事件无 metrics | Agent 3 P2 | — | 待办 |
| code-074 | 5 个客户端期望出站事件服务端无发射点（response/transcript/evaluation_feedback/audio_drop_notice/system_backpressure） | Agent 3 §3.2 GAP | — | 待办 |
| code-075 | `pause`/`resume` 顶级 type 与 `control.action` 双轨冗余 | Agent 3 P0 | — | 待办 |
| code-076 | 非法 JSON / 缺失字段 / 未知 type 静默吞噬 | Agent 3 P0 | — | 待办 |
| code-077 | `_save_session_state` 失败仅日志无 metrics | Agent 3 P1 | — | 待办 |
| code-078 | `prefer_binary: true` 协商但客户端未走 `WebSocket.send(arrayBuffer)` | Agent 7 §10.3 | P0-08 | 待办 |

### 2.8 数据库（code-079 ~ code-083）

| 编号 | 主题 | 来源 | 关联 Issue | 状态 |
|------|------|------|----------|------|
| code-079 | `_load_persisted_state` 另起 `async_sessionmaker` 可见性偏移 | Agent 5 P1 | — | 待办 |
| code-080 | `User.email` `unique=True, nullable=True` 多 NULL | Agent 5 P1 | — | 待办 |
| code-081 | `_startup_schema_repairs_allowed` 在 staging 应禁用 | Agent 5 P1 | — | 待办 |
| code-082 | 迁移命名 4 风格共存 | Agent 5 P1 | — | 待办 |
| code-083 | `get_db()` `except` 列表未覆盖 `OperationalError` | Agent 5 P1 | — | 待办 |

### 2.9 Result 细节（code-084 ~ code-085）

| 编号 | 主题 | 来源 | 关联 Issue | 状态 |
|------|------|------|----------|------|
| code-084 | `Result` 缺 `and_then` (monadic bind) | Agent 2 P2-1 | P1-01 | 待办 |
| code-085 | `Result.fail` 静默接受空串 | Agent 2 P2-3 | P1-01 | 待办 |

---

## 3. OK 标杆（参考模式，不需修）

| 编号 | 主题 | 来源 | 备注 |
|------|------|------|------|
| code-OK-1 | `path_service.outerjoin` 一次取 submission+score | Agent 5 | 范式 |
| code-OK-2 | `curriculum_practice/learning_path.py` `selectinload(scenario)` | Agent 5 | 范式 |
| code-OK-3 | Alembic 链 0 孤儿、单头 | Agent 5 | 100% 干净 |
| code-OK-4 | `pool_pre_ping=True` | Agent 5 | 长连接保护 |
| code-OK-5 | RFC 4122 UUID in user_id（规范化） | Agent 6 | OK |
| code-OK-6 | `CORS` `_validate_cors_origins` 拒绝通配符 + 凭据 | Agent 6 | OK |
| code-OK-7 | `WeCom SSO` state 验证 + return_to 防越权 | Agent 6 | OK |
| code-OK-8 | 水平越权（学员 A → B）已挡 | Agent 6 | OK |
| code-OK-9 | 5 admin endpoint 抽查全部显式鉴权 | Agent 6 | OK |
| code-OK-10 | 心跳/重连/背压/状态保存基础设施 | Agent 3 | 商业 SRE 标准 |
| code-OK-11 | LLM 错误码统一性 | Agent 4 | A |
| code-OK-12 | TTS 3 级降级声明完整 | Agent 4 | A |
| code-OK-13 | KB Lock 主决策流 | Agent 4 | A |
| code-OK-14 | `SalesTrainerAudioSubmission.user_id` 规范化 | Agent 6 | OK |
| code-OK-15 | `MaterialConfig.api_key_encrypted` Fernet | Agent 6 | OK |
| code-OK-16 | `password_reset_tokens` 单 token 约束 | Agent 6 | OK |
| code-OK-17 | ORM 100% 2.0 化（0 违规） | Agent 5 | 优 |
| code-OK-18 | `async with AsyncSessionLocal()` 全栈 | Agent 5 | 优 |
| code-OK-19 | 销售训练 RBAC 5 helper 函数覆盖到位 | Agent 6 | OK |
| code-OK-20 | `path_service` 一次外连接取 submission + score | Agent 5 | 范式 |

---

## 4. P2 / P3 持续（约 30 项 — 仅列主题）

> 不进 Issue tracker，作为 backlog 持续优化

### 4.1 死代码 / 备份
- PEP 420 17 个子目录 + 3 根包无 `__init__.py`
- `main.py` 9 个 shim helper + `create_app` 自赋值
- `_normalize_requested_voice_mode` / `_default_voice_mode` / `_is_admin_user_id` 在 `main.py` 与 `sales_bot/websocket/router.py` 重复
- `sales_handler.py.deprecated` + `presentations.py.backup` + `broadcaster.py.backup` 29.4 KB 死代码
- `presentation_coach/websocket/presentation_handler.py` 仍作 legacy fallback
- `_build_knowledge_bases_alias_router` 旧路径别名
- `stepfun_knowledge_helpers.py` / `stepfun_internal_knowledge_searcher.py` 空壳

### 4.2 WS handler 设计债务
- `__getattr__` raise 模板（state_base.py:158）
- `_load_sales_stage_runtime_config` 与 `_disable_sales_capabilities` 重复
- StepFun 模型/音色/voice_mode 默认值硬编码 3+ 处
- `MAX_RECONNECT_ATTEMPTS=5` 硬编码
- 5 个客户端期望出站事件服务端无发射点
- `pause` / `resume` 顶级 type 与 `control.action` 双轨
- `ScorePanel` / `SlideViewer` 未懒加载
- `_save_session_state` 失败无 metrics

### 4.3 错误处理细节
- 23+ `except Exception: # noqa: BLE001` WS 边界裸吞
- 13+ 处口语化错误码违例（`Result.fail("...")`）
- CORS 配置占 `app_factory.py` 50% 行数
- `LEGACY_SALES_HANDLER_MODULES` 元组持有死代码
- `SalesBotWebSocketHandler_DEPRECATED` 类
- `tts_factory.py` 4 处 metrics TypedDict 未导出

### 4.4 测试 / 性能
- 测试 fixtures SQLite vs PostgreSQL 不一致
- Redis fixture 未自动启动
- 10 个 seed 脚本无冒烟
- `tests/scripts/run_nfr_tests.sh` 仅 1 个文件
- `coverage.json` 4 月未刷新（已升级到 P1-054）
- 49 端点 0 contract（已升级到 P1-028）

---

## 5. Sprint 分组（按 ROI）

| Sprint | 编号范围 | 估时 | 备注 |
|--------|---------|------|------|
| **Sprint-1（1-2 周）** | code-001 ~ code-024 | ~14 人天 | 24 P0 阻断 + 合规底线 |
| **Sprint-2（2-4 周）** | code-025 ~ code-058 | ~18 人天 | P1 主要项（含 React Query / binaryType / 49 端点 contract） |
| **Sprint-3（1-3 月）** | code-059 ~ code-085 + §4 P2/P3 | ~25 人天 | 持续优化 + 设计系统 + 观测性 + 文档治理 |

---

## 6. 状态更新约定

| 阶段 | 状态 | 备注 |
|------|------|------|
| 草稿 | `待办` | 当前 |
| 提交 issue | `提交 #NNN` | 回填 issue 编号 |
| 实施中 | `In Progress (PR #NNN)` | 关联 PR 编号 |
| 已合并 | `已修 (#NNN merged @YYYY-MM-DD)` | 关闭 |
| 跳过 | `won'tfix (#NNN)` | 标注原因 |
| 重复 | `duplicate (#NNN)` | 引用原 issue |

---

## 7. 状态总览

| 严重度 | 总数 | 待办 | 提交 | In Progress | 已修 | 关闭 |
|--------|------|------|------|-------------|------|------|
| P0 阻断 | 24 | 24 | 0 | 0 | 0 | 0 |
| P1 严苛 | 61 | 61 | 0 | 0 | 0 | 0 |
| P2/P3 持续 | ~30 | ~30 | 0 | 0 | 0 | 0 |
| OK 标杆 | 20 | n/a | n/a | n/a | n/a | n/a |
| **合计** | **~115** | **~115** | **0** | **0** | **0** | **0** |

---

## 8. 关联文档

- `docs/agents/audit-2026-06/00-executive-summary.md` — 综合摘要
- `docs/agents/audit-2026-06/01-08-*.md` — 8 份专题报告
- `docs/agents/audit-2026-06/09-doc-cleanup-checklist.md` — 文档治理清单
- `docs/agents/audit-2026-06/10-issue-drafts.md` — GitHub Issue 草稿
- `docs/agents/audit-2026-06/11-AGENTS-CLAUDE-patch.md` — AGENTS.md / CLAUDE.md 回写 diff
- `docs/agents/audit-2026-06/README.md` — 审计索引

---

**本文件不修改任何源代码或现有文档**。所有 issue 内容仅作为追踪总账。
