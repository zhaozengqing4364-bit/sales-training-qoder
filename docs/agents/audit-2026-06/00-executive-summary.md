# 严苛架构师 · 8-Agent 全量审计执行摘要 (2026-06-03)

> **状态**：Draft → 待批准
> **范围**：全仓库代码、配置、文档、CI
> **方法**：8 个 agent 并行静态分析；**0 行代码修改、0 个现有文件改动**
> **产出**：`docs/agents/audit-2026-06/01..08-*.md` 8 份专题报告 + 本摘要 + 3 份聚合文档

---

## 0. 一句话结论

| 维度 | 评级 | 一句话 |
|------|------|--------|
| 后端架构 | **C+** | 边界有缺口、文档严重失真、降级链声明完整但生产 0 引用 |
| 错误处理 | **D+（43%）** | 骨架在、Result 范式 36% 覆盖，熔断/限流几乎全裸 |
| WebSocket 实时链路 | **B-/D** | 心跳/重连/背压认真，跨域继承 + 协议漂移是技术债 |
| 音频 / AI 能力 | **C-** | TTS 3 段声明、ASR 2 段，**降级链生产零调用**是最大骗局 |
| 数据库 | **B** | ORM 100% 2.0 化，迁移 0 孤儿，但 5 个 P0（JSONB 无 GIN、pool_recycle、零 selectinload、零分页、零软删除） |
| 安全 / 鉴权 / 隐私 | **B-** | 水平越权全挡，但 **WS 鉴权不绑 sub** 是 P1 阻断 |
| 前端 | **B-（60/100）** | 设计系统骨架在，**bg-white 543 处** (较 2026-06-03 审计时 526 处增加 17) + **WS binaryType 缺**是 R-1 风险 |
| 测试 / 可观测性 / CI | **D** | trace_id 15 文件断崖、**17/21 指标死代码**、**常规 PR 零门禁** |

**整体**：**C+（57/100）**，高复杂度 + 治理失能并存。骨架扎实但"看起来有、运行时没有"的债务已经到了"Sprint-1 不修、6.18 发版必翻"的程度。

---

## 1. Top-10 必修项（按 ROI 排序）

| # | 项 | 来源 Agent | 评 | 工作量 | 业务影响 |
|---|----|----------|---|------|---------|
| **1** | **CLAUDE.md 文档纠错**（`main.py 19655 行`→ 75 行；`common/` 30 子目录；新增 `bg-white`/`ErrorBoundary` 强约束） | Agent 1 F-04 | 🔴 | 0.5d | 防止后续 agent/工程师基于错误数据决策 |
| **2** | **跨域继承修复**（`presentation_stepfun_realtime_handler` → `sales_bot.StepFunRealtimeHandler` 单向破窗） | Agent 1 F-01 / 3 §10 | 🔴 | 3d | 场景隔离原则、加新场景不再 copy-paste 8244 行 mixin |
| **3** | **WebSocket 鉴权补完**（token 失败 `close(4401)` + `payload["sub"] == session.user_id` 强校验） | Agent 6 P1-3/4 | 🔴 | 1.5d | 学员可接入他人 session 风险 |
| **4** | **`bg-white` 526 → 100**（top-10 文件 0 处）+ design token 接入 | Agent 7 §1.4 | 🔴 | 2d (2 PR) | dark mode 落地、设计系统收敛 |
| **5** | **WebSocket `binaryType` 缺 + 二进制 PCM 入站**（R-1 P0） | Agent 7 §10.3 W-1/W-2 | 🔴 | 1d | 违宪 I 风险（用户体验永不中断） |
| **6** | **17 个 Prometheus 死指标接入或删除** | Agent 8 §5.1 | 🔴 | 2d | 监控失真、告警不可信 |
| **7** | **STEPFUN_API_KEY 走 Fernet 加密**（与 LLM/ASR/TTS 对称） | Agent 4 F-SEC-1 | 🔴 | 1.5d | 密钥管理合规对称 |
| **8** | **stdlib logger 15 文件 116 调用点 → `get_logger`** | Agent 8 P0-1 | 🔴 | 1d | trace_id 100% 覆盖、个保法重点文件 `audio_archival.py` 在列 |
| **9** | **5 个 P0 CI 工作流补全**（lint / unit / contract / coverage-gate / secret-hygiene） | Agent 8 P0-3 | 🔴 | 1d | PR 必过门禁，去掉 `--no-cov` 偷懒 |
| **10** | **销售训练 audio_submission DELETE 路由 + 软删除字段**（个保法被遗忘权） | Agent 4/6/8 D-SEC-2 / P0-4 | 🔴 | 1.5d | 法规合规底线 |

**总估时**：约 14 人天。**6 周内可全部完成**（按 1 人/2 项 节奏）。

---

## 2. P0 / P1 跨 Agent 串证矩阵

| 串证主题 | Agent 1 | Agent 2 | Agent 3 | Agent 4 | Agent 6 | Agent 7 | Agent 8 |
|---------|---------|---------|---------|---------|---------|---------|---------|
| 跨域继承 `PresentationStepFunRealtimeHandler` | F-01 🔴 | — | §10 D | — | — | — | P1-5 |
| Result 覆盖率 36% / 熔断仅 ASR / 限流 1 处 | — | C-/D+/F | — | F-CB-1/D-LIMIT-1 | — | — | — |
| WS 鉴权 `close(4401)` / `sub` 绑定 | — | — | §3.2 GAP | — | P1-3/4 🔴 | — | P1-4 |
| STEPFUN_API_KEY 未走 Fernet | — | — | §3.2 GAP | F-SEC-1 🔴 | — | — | P1-1/2 |
| Prometheus 13→17 指标死代码 | — | — | — | F-OBS-1 | — | — | P0-2 🔴 |
| 销售训练 audio 无 DELETE | — | — | — | D-SEC-2 | — | — | P0-4 🔴 |
| 销售训练 admin 列表裸露 user_email | — | — | — | — | P1-1/2 | — | — |
| `bg-white` 526 / design system 失能 | — | — | — | — | — | §1 🔴 | — |
| trace_id 15 文件断崖（含 audio_archival） | — | — | — | — | P1-9 | — | P0-1 🔴 |
| CI 常规 PR 缺门禁 | — | — | — | — | — | — | P0-3 🔴 |
| CLAUDE.md 文档失真（main.py 行数） | F-04 🔴 | — | — | — | — | — | — |
| 降级链 `ASRServiceWithFallback` / `TTSServiceWithFallback` 生产 0 引用 | — | §3.1 B | — | F-ASR-1 / F-TTS-1 | — | — | — |

---

## 3. 严重度汇总

| 等级 | 数量 | 描述 |
|------|------|------|
| 🔴 **P0 阻断** | **24 项** | 跨域继承、WS 鉴权、个保法、STEPFUN 加密、17 死指标、trace_id 断崖、CI 零门禁、bg-white 526、binaryType 缺、CLAUDE.md 失真、DELETE 路由缺失、3 处 `HTTPException(500)`、80 处 raise、support/supervisor 0 Result、5 个 JSONB 无 GIN、pool_recycle 缺失、零 selectinload、零分页、零软删除、admin 列表邮箱裸露、IP 信任链、XSS download prompt |
| 🟡 **P1 严苛** | **约 60 项** | 错误码口语化、TTS env 5 个未消费、降级指令名不统一、9 个 WS 错误码无文档、protocol schema_version 缺失、knowledge_engine 6+ 自闭模块、KB Lock 衍生状态码未入文档、9 个日志脱敏 marker 缺、CORS ENV 误置风险、JWT 无 aud/iss、SQLite vs PG fixture 不一致、roleplay LLM grader 不可重复、`coverage.json` 4 月未刷新、49 端点失败态 1/49、admin sales-trainer 9 page 0 测试、49 端点 0 contract test 等等 |
| 🟢 **持续** | 约 30 项 | 17 个 `common/` 子目录无 `__init__.py`、`main.py` 9 个 shim、3 个 backup 文件（29.4 KB）、`asr_with_fallback.py` 降级链空、`result.py` 缺 `error_code`/`trace_id`/`and_then`、迁移命名 4 风格等等 |

> 完整分级详见各 Agent 报告 §严苛分级 / §P0-P3。

---

## 4. 跨域主题摘要

### 4.1 场景隔离与模块边界（Agent 1）
- `sales_bot → presentation_coach`：1 处破窗（继承）
- `common → 业务域`：3 处反向依赖
- 56.7% `common/` 子目录无 `__init__.py`（PEP 420 混用）
- Router prefix 冲突 2 处（`/admin/analytics` 双挂；`/admin/agents` 双挂）
- 启动链路合规，**限流未挂中间件**（仅装饰器）
- 67 个路由挂载点，0 遗漏

### 4.2 错误范式与降级（Agent 2 / Agent 4）
- 814 处 Result 调用 / 36% 文件覆盖
- 99 个 `[SCREAMING_SNAKE]` 错误码，但 13+ 处口语化违例
- STEPFUN_*/CHROMADB_* 域错误码**完全缺失**
- TTS 3 段降级声明完整 + **0 引用**
- ASR 2 段 + **fallback_provider_factories 默认空**
- 熔断器仅 ASR 真保护（5/3/60s），TTS/LLM/StepFun/Chroma/OSS 全裸
- 限流器仅登录 1 个端点（auth）
- 3 处 `HTTPException(500)` 违宪 I
- 80 raise 在 `common/business_rules/validators.py`（头号违例）
- `support/` + `supervisor/` 整个子系统 0 Result 引用
- `Result` 类缺 `error_code` / `trace_id` / `and_then`
- 23+ `except Exception: # noqa: BLE001` WS 边界裸吞

### 4.3 WebSocket 实时链路与协议（Agent 3）
- 12 个 `BaseWebSocketHandler` 子类
- 跨域继承（`PresentationStepFunRealtimeHandler` ← `StepFunRealtimeHandler`）
- 5 个 mixin + 8 个 components 拆分合理，2 个 components 是空壳
- 协议无 `schema_version` 顶层字段
- 9 个新错误码无文档
- 5 个客户端期望的出站事件**服务端无发射点**（GAP）
- `pause`/`resume` 顶级 type 与 `control.action` 双轨
- WS 鉴权失败仅 `logger.warning` 不 `close(4401)`
- `payload["sub"]` 与 session 拥有者未绑定
- 心跳 30s、退避 1s→30s、5 次重试上限、5min idle timeout、512KB backpressure、Redis TTL 1800s **均到位**
- 客户端 `use-practice-websocket.ts` 1047 行编排器臃肿
- `prefer_binary: true` 协商但客户端未走 `WebSocket.send(arrayBuffer)`
- StepFun 模型/音色硬编码 3+ 处

### 4.4 AI 链路与配置（Agent 4）
- ASR 4 provider / 实际单链装配
- TTS 3 段声明 / 实际 0 引用
- StepFun 走原生 WS 直连，不走 TTS 降级
- `STEPFUN_API_KEY` 明文 `os.getenv`（**与 LLM/ASR/TTS 不对称**）
- LLM 成本埋点内存级，**Prometheus 0 导出**
- `common/knowledge` + `common/knowledge_engine` 双轨并存，6+ 自闭
- KB Lock 4 衍生状态码未入文档
- 销售训练音频**无 delete 函数**（个保法风险）
- 13 个 ASR/TTS/LLM Prometheus 指标全代码库 0 调用
- TTS 5 个必备 env（`TTS_TIMEOUT/SAMPLE_RATE/CONNECTION_POOL_SIZE/ENABLE_WARMUP/FALLBACK_CHAIN`）全部未消费
- `cost_per_1k_tokens` 单位注释混乱

### 4.5 数据库与持久化（Agent 5）
- ORM 100% 2.0 化（0 违规、0 孤儿、1 head）
- 87 个 Base 模型，77 个迁移
- 5 个 P0：JSONB 无 GIN、`pool_recycle` 缺、agent_service 13 查询零 `selectinload`、分页缺失、零软删除
- sales_trainer 12 表 / 25 FK / 11 Index / 30 索引列 / 0 关系（全显式 `select()`）
- RBAC 实质是 `users.role` 字符串枚举（075 迁移扩展）
- FK `ondelete` 覆盖率仅 28-44%
- 迁移命名 4 风格共存

### 4.6 安全 / 鉴权 / 隐私（Agent 6）
- JWT HS256 + 24h + `JWT_SECRET` 默认值（生产已 fail-fast）
- 密码 bcrypt/pbkdf2；HttpOnly + Lax + Secure cookie；CSRF double-submit
- **无 JWT 撤销机制**（无 jti、无 refresh token）
- 5 admin endpoint 抽查全部显式鉴权
- 销售训练 admin 列表裸露 `user_email`（与 `_mask_email` 标杆不一致）
- 9 P1：WS 鉴权 2 处 + admin 邮箱 2 处 + IP 信任链 + JWT aud/iss + material 文件下载 + CORS ENV 误置 + log marker 缺 `api_key`
- 7 P2：JWT 响应冗余、WEBSOCKET_QUERY_TOKEN_ENABLED 误设、extra_config 未加密、allow_methods `*`、MODEL_CONFIG_ENCRYPTION_KEY 未 fail-fast、original_filename XSS
- 水平越权（学员 A→B）**全挡**
- 垂直越权：admin 域 `get_current_admin_user` / sales_trainer 域 helper + 业务断言

### 4.7 前端架构与 UX（Agent 7）
- 总体 B-（60/100）
- `bg-white` **526 处 / 140 文件**（CLAUDE.md 重度违规）
- design system token 仓库**未被 `@import`**
- dark mode hook 在、样式 0
- ErrorBoundary class 组件齐，**`global-error.tsx` 缺失**
- sales-trainer **14 子段 0 error.tsx / 0 loading.tsx**
- `client.ts` 4648 行单点巨型
- 49 端点失败态测试 **1/49 (2%)**
- 3 处 raw `fetch` 绕过 `apiFetch`
- zustand 仅 1 store，React Query 仅 1 用例
- sales-trainer 272 处 `useState` 抓数据
- `use-practice-websocket.ts` 1047 行单文件
- `binaryType` **0 处设置**（R-1 P0）
- 0 `next/dynamic` / 3 `next/image`
- 117 个 page / 166 个测试文件
- a11y：C+，Radix 3/12，aria-label 87，sales-trainer 几乎 0
- 用户操作埋点 0
- 1 处 `window.location.href = '/'` 在 `admin/error.tsx` 违规

### 4.8 测试 / 可观测性 / CI（Agent 8）
- 后端 338 测试 / 48.66% 覆盖率（4 月前快照）/ `--cov-fail-under=48` 被 `--no-cov` 关闭
- 前端 166 测试 / lines 56.66% / `client.ts` 3.24% 灾难
- **trace_id 注入断崖**：149 文件走 StructuredLogger vs **15 文件 116 调用点用 stdlib**（含 `audio_archival.py` 个保法重点）
- **Prometheus 21 指标中 17 个死**（升级 Agent 4 的 13）
- OTel 1 文件包装，0 业务 span，OTEL_ENABLED 默认 false
- 日志脱敏 `SENSITIVE_LOG_FIELD_MARKERS` 仅 4 marker，缺 `api_key`/`secret`/`apikey`
- 3 个 CI 工作流：**常规 PR 零门禁**（无 ruff / mypy / unit / contract / coverage-gate）
- 24 contract 测试 vs 18 API 文档仅 2 域对齐，**sales-trainer 0 contract**
- NFR 5/10 并发 vs CI 50 vs 文档 200 **三方数字错位**
- 49 端点 0 contract / 0 失败态测试
- 10 个 seed 脚本无自动化冒烟

---

## 5. 严苛评分卡（多维度）

```text
[架构边界]              70%  B-   隔离 1 处破窗 + 3 处反向依赖
[文档真值]              40%  D    CLAUDE.md 严重失真
[Result 范式]           43%  D+   814 调用 / 36% 覆盖
[降级链]                55%  C+   声明完整 / 引用 0
[熔断器]                10%  F    仅 1/9 外部依赖
[限流]                   5%  F    仅 1 端点装饰
[WS 心跳/重连/状态]     90%  A    商业 SRE 标准
[WS 协议]               50%  C    schema_version 缺、5 GAP
[WS 鉴权]               40%  D    失败不 close(4401)、sub 不绑
[ASR/TTS 链路]          55%  C    声明完整 / 装配 0
[StepFun 加密]          30%  F    明文 os.getenv
[LLM 链路]              75%  B+   ConfigManager + Fernet 齐
[KB Lock]               85%  A-   主路径完整
[Cost 埋点]             40%  D    内存 / 不导出
[ORM 合规]              95%  A    0 违规
[Alembic]               95%  A    0 孤儿 / 1 head
[查询性能]              45%  D    0 selectinload / 0 分页
[认证鉴权]              80%  B+   横向越权全挡
[WS 鉴权完整性]         40%  D    失败无 close
[API 越权]              85%  B+   抽查全合规
[日志脱敏]              55%  C    4 marker 偏小
[前端设计系统]          35%  D+   bg-white 526 / token 孤岛
[ErrorBoundary]         60%  C+   global-error 缺
[API 客户端]            45%  D+   4648 行 / 失败态 2%
[状态管理]              45%  D+   zustand 闲置
[WS 客户端]             50%  C    binaryType 缺
[测试覆盖]              55%  C+   后 48% / 前 56%
[trace_id]              55%  C    15 文件断崖
[Prometheus]            20%  F    17/21 死
[CI 门禁]               25%  F    PR 零门禁
[契约 ↔ 文档]           25%  F    sales-trainer 0 contract
────────────────────────────────────────────────────
[综合]                  53%  D+   严苛结论：骨架在，治理失能
```

---

## 6. 修复 Sprint 建议（按 ROI 排序）

### Sprint-1 (S, 1-2 周，10 项) — 阻断 + 合规底线
1. CLAUDE.md 文档纠错（main.py 行数 + common/ 30 + bg-white/ErrorBoundary 强约束）
2. WebSocket 鉴权补完（close(4401) + sub↔session 强校验）
3. 跨域继承修复（抽 common 基类，方案 A）
4. STEPFUN_API_KEY Fernet 加密
5. 17 死指标接入或删除
6. stdlib logger 15 文件 → get_logger
7. 销售训练 audio_submission DELETE 路由 + 软删除
8. `bg-white` top-10 文件迁移
9. binaryType + 二进制 PCM 入站
10. CI PR 5 门禁工作流

### Sprint-2 (M, 2-4 周)
- 49 端点失败态测试 / 49 端点 contract test
- 错误码中心表 + 升级 Result（含 error_code/trace_id/and_then）
- 销售训练 admin 列表邮箱脱敏
- 限流中间件 + 业务熔断补全
- React Query 接入 sales-trainer
- JWT aud/iss + 撤销机制
- 14 sales-trainer 子段 error.tsx + loading.tsx
- JSONB GIN 索引 + selectinload + 分页

### Sprint-3 (L, 1-3 月)
- 双轨知识库合并
- 软删除标准字段
- Grafana 仪表盘 + 告警
- 设计系统 dark mode
- OTel 业务 span 注入
- 迁移命名规范化 + ADR 补齐
- contract ↔ doc 全量对齐

---

## 7. 关联文档索引

| 主题 | 路径 |
|------|------|
| 架构边界 | `docs/agents/audit-2026-06/01-architecture-boundary.md` |
| 错误处理 & Result | `docs/agents/audit-2026-06/02-result-and-error-handling.md` |
| WebSocket & StepFun | `docs/agents/audit-2026-06/03-websocket-realtime.md` |
| 音频 / AI 能力 | `docs/agents/audit-2026-06/04-audio-and-ai-capabilities.md` |
| 数据库 | `docs/agents/audit-2026-06/05-database-and-persistence.md` |
| 安全 / 鉴权 / 隐私 | `docs/agents/audit-2026-06/06-security-and-privacy.md` |
| 前端架构 | `docs/agents/audit-2026-06/07-frontend-architecture.md` |
| 测试 / 可观测性 / CI | `docs/agents/audit-2026-06/08-testing-observability-ci.md` |
| 文档治理清单 | `docs/agents/audit-2026-06/09-doc-cleanup-checklist.md` |
| Issue 草稿 | `docs/agents/audit-2026-06/10-issue-drafts.md` |
| AGENTS.md / CLAUDE.md 回写 diff | `docs/agents/audit-2026-06/11-AGENTS-CLAUDE-patch.md` |

---

## 8. 后续流程（按 CLAUDE.md 协作规则）

| 阶段 | 动作 | 责任 | 状态 |
|------|------|------|------|
| **Draft** | 本摘要 + 8 份专题报告 + 3 份聚合文档 | 严苛架构师 | ✅ 完成 |
| **Approved** | 您审阅本摘要并决策优先级 | 您 | ⏳ 等待 |
| **In Progress** | 按 Sprint-1 实施修复（含 Issue 草稿评审） | Agent 团队 | ⏸ 待启动 |
| **Changed** | 关键偏差回写规范 | 主 Agent | ⏸ 待触发 |
| **Reapproved** | Sprint 验收 + 规范再对齐 | 您 | ⏸ 待触发 |
| **Done** | 全部 Sprint 完成 + 规范最终态 | 团队 | ⏸ 待触发 |

---

**本摘要未修改任何源代码或现有文档**。所有结论基于静态分析，命令与 grep 证据详见各 Agent 专题报告。
