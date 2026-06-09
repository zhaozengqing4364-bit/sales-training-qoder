# 文档治理清单 (2026-06-03)

> **目标**：识别仓库内老旧/失真/需补强的文档，**不直接删除/修改任何现有文档**。本清单作为后续 PR diff 的输入。
> **依据**：8 份 agent 报告 + 用户决策（"先进行文档的操作更新，创建文档，删除老旧的文档，代码相关问题创建一个文档记录"）。
> **范围**：`/Users/zhaozengqing/github/销售训练qoder/` 仓库根 + 各级 `*.md` + `AGENTS.md` + `CLAUDE.md` + `CONTEXT.md` + `.kiro/steering/` + `.claude/rules/` + `docs/` + `docs/adr/` + `docs/api-contract/`

---

## 0. 摘要

| 类别 | 数量 | 状态 |
|------|------|------|
| 🔴 **必须立即修**（CLAUDE.md 失真/事实错误） | 5 处 | 待批准后改 |
| 🟡 **建议修订**（与代码不同步） | 13 处 | 待批准后改 |
| 🟢 **建议合并 / 重构 / 拆分** | 6 处 | 待批准后改 |
| 📦 **可删除**（已被替代/长期未更新/事实错误且无引用） | 7 个文件 | **不直接删**，列删除清单待批准 |
| ➕ **需新建**（CLAUDE.md 强制回写） | 4 份 | 见 `11-AGENTS-CLAUDE-patch.md` |
| 🏷️ **需新增 ADR** | 6 份 | 见 §6 |

---

## 1. 🔴 必须立即修（事实错误 / 严重失真）

| # | 文件 | 行/段 | 现状（实测量） | 建议改为 | 来源 Agent |
|---|------|-------|--------------|---------|----------|
| **1.1** | `CLAUDE.md` | L45 "main.py (19655 lines)" | 实际 **75 行** | 改为"main.py 75 lines (thin entry; 实际应用由 `app_factory.create_app` 构造)" | Agent 1 F-04 |
| **1.2** | `CLAUDE.md` | L80 "common/ (35 子目录)" | 实际 **30 个子目录**（含 17 个 PEP 420 隐式） | 改为"`common/` 30 子目录，17 个无 `__init__.py`（PEP 420 混用）" | Agent 1 F-12 |
| **1.3** | `CLAUDE.md` | "禁止事项"段 "❌ `bg-white`（全页背景）" | 与现状不一致：实测 526 处 / 140 文件 | **强化禁令**："全仓 0 处 `bg-white`，违规率 100%。任何新增 PR 含 `bg-white` 一票否决" | Agent 7 §1.4 |
| **1.4** | `CLAUDE.md` | "禁止事项"段 缺少 `global-error.tsx` | `app/global-error.tsx` 缺失 | **新增条款**："每个 Next.js app 段必须有 `error.tsx`；`app/global-error.tsx` 必须存在（顶层兜底）" | Agent 7 §2.1 |
| **1.5** | `.claude/rules/L2-project/ai-practice-system.md` | §1 错误处理降级指令表 | 缺 `[STEPFUN_*]` `[CHROMADB_*]` `[RATE_LIMITED]` 等 | **补充**：13+ 个新错误码见 `10-issue-drafts.md` | Agent 2 §4.3 |

---

## 2. 🟡 建议修订（与代码不同步）

| # | 文件 | 段/行 | 不一致 | 建议 | 来源 Agent |
|---|------|------|------|------|----------|
| **2.1** | `CLAUDE.md` "Project Structure" 段 | `presentation_coach/services/` 段 | 漏 `presentation_ai_policy_service.py` `prompt_role_resolver.py` `point_extraction.py` `semantic_point_tracker.py` `user_presentation_progress.py` `forbidden_matcher.py` `aho_matcher.py` | 补齐（同步实际 12 文件） | Agent 1 §7.3 |
| **2.2** | `CLAUDE.md` "Project Structure" 段 | `sales_bot/websocket/` 段 | 漏 `components/` 拆分说明、`stepfun_realtime_handler.py` 主类 | 补齐 | Agent 1 §7.3 |
| **2.3** | `CLAUDE.md` "环境变量" 段 | "StepFun Realtime" 块 | 未声明 STEPFUN_API_KEY 必须经 Fernet 加密（当前是明文 `os.getenv`） | 改为 "STEPFUN_API_KEY 必须经 `MODEL_CONFIG_ENCRYPTION_KEY` Fernet 加密后存 DB" | Agent 4 F-SEC-1 |
| **2.4** | `CLAUDE.md` "L1-global" 段 §9 熔断器表 | `recovery_timeout=30s` | 代码 `CircuitBreakerConfig.timeout_seconds=60` | 修正为 **60s** | Agent 4 D-CFG-2 |
| **2.5** | `CLAUDE.md` "L1-global" 段 §9 限流 | "全局/用户级/IP 级/端点级" | 实际仅"端点级装饰器 + 登录 1 个"，全局/用户级/IP 级为 0 | 改为"限流仅端点级装饰器实现，全局/用户级/IP 级 **待实现**" | Agent 1 F-06 / Agent 4 D-LIMIT-1 |
| **2.6** | `AGENTS.md`（根） | "核心架构模式" 段 "Result[T]" | 未声明 `error_code` / `trace_id` 字段、`and_then` monadic bind、`map` 异常捕获范围 | 补充完整 Result API 契约 | Agent 2 §7 |
| **2.7** | `AGENTS.md`（根） | 宪法原则 VII "所有日志含 trace_id" | 实测 15 个文件 116 调用点用 stdlib logger，**不注入 trace_id** | 改为"所有 logger 必须 `get_logger(__name__)`；stdlib `logging.getLogger` 一律替换" | Agent 8 P0-1 |
| **2.8** | `backend/AGENTS.md` | 业务逻辑禁入 common 规则 | 实际 3 处反向依赖（practice_session_service 等） | 补充"已发现 3 处违规待重构：F-02" | Agent 1 I-2~I-5 |
| **2.9** | `backend/AGENTS.md` | "legacy sales handler" 禁令 | 销售 plugin 仍以 `LEGACY_SALES_HANDLER_MODULES` 元组持有 | 建议改用 `runtime_mode` enum 表达 | Agent 3 §1.2 |
| **2.10** | `docs/api-contract/websocket.md` | "拒绝 close code" 表 | 缺 9 个新错误码（STEPFUN_KEY_MISSING / UPSTREAM_REJECTED / TRANSPORT_ERROR / CONNECTION_ERROR / GROUNDING_PREPARE_FAILED / RESPONSE_CREATE_FAILED / STATE_SAVE_FAILED / STATE_GET_FAILED / WS_QUEUE_OVERFLOW） | 补齐错误码字典 | Agent 3 §8.5 |
| **2.11** | `docs/api-contract/websocket.md` | 协议版本段 | 缺 `schema_version` 顶层字段约定；TTS chunk 局部 v1/v2 已存在 | 新增 "WebSocket Protocol Version Negotiation" 章节 | Agent 3 §3.3 |
| **2.12** | `docs/api-contract/sales-trainer.md` | 1146 行，**0 contract test** | 契约只活在文档里 | 在 `docs/agents/audit-2026-06/10-issue-drafts.md` 列专项 issue | Agent 8 §1.6 |
| **2.13** | `docs/architecture.md` | "可观测性" 段 | 实际 17/21 Prometheus 指标为死代码 | 标注"该段承诺 vs 实际状态" | Agent 8 §3.2 |

---

## 3. 🟢 建议合并 / 重构 / 拆分

| # | 文件 | 建议 | 理由 |
|---|------|------|------|
| **3.1** | `AGENTS.md` (根 243 行) + `backend/AGENTS.md` + `web/AGENTS.md` + `app/admin/sales-trainer/AGENTS.md` | 抽 `L0` 共享段（宪法/契约）→ 根文件；保留域 `L1` AGENTS.md 写域特定 | 现有 4 个 AGENTS.md 重复 70% 内容 |
| **3.2** | `.kiro/steering/README.md` + `.kiro/steering/QUICK-REFERENCE.md` + `.kiro/steering/rule.md` | 合并 `QUICK-REFERENCE.md` 进 `README.md`；删除空 `rule.md` | `rule.md` 0 字节、`QUICK-REFERENCE.md` 与 README 重复 |
| **3.3** | `.claude/rules/L1-global/programming-patterns.md` + `.claude/rules/L2-project/ai-practice-system.md` | 保留双层组织但加交叉引用 | 现状 OK，但缺失 `L3-domain/sales-trainer.md` 应建立 |
| **3.4** | `docs/adr/` (10 份) | 新增 6 份 ADR（见 §6） | 跨域继承、降级链落地、STEPFUN 加密、CI 治理、设计系统、bg-white 禁令均无 ADR 记录 |
| **3.5** | `docs/agents/audit-2026-06/` 本批 12 份新文档 | 在 `docs/agents/README.md` 建索引（不存在则创建） | 当前零索引 |
| **3.6** | `docs/api-contract/README.md` | 补 18 份契约文件 ↔ 24 合同测试对齐矩阵 | 当前仅列契约文件，缺对齐矩阵 |

---

## 4. 📦 可删除文件清单（**不直接删除，待批准**）

> 以下文件**未被任何生产代码 import** 或**长期未更新 / 事实错误**。删除前需 PR 评审 + grep 二次确认 + CI 全跑。

| # | 文件 | 大小 | 最后修改 | 删除理由 | 注意事项 |
|---|------|------|----------|---------|---------|
| **4.1** | `backend/src/sales_bot/websocket/sales_handler.py.deprecated` | 12 773 B | 2025-04-20 | `.deprecated` 后缀，0 生产引用 | ⚠️ `training_runtime/plugins.py:14` `LEGACY_SALES_HANDLER_MODULES` 元组持有并要求**存在**（用于"必须缺失"审计）。**删除前必须先删除 LEGACY 列表 + 审计调用** |
| **4.2** | `backend/src/presentation_coach/api/presentations.py.backup` | 7 411 B | 2025-02-05 | `.backup` 后缀，0 引用 | 内含 1 处 `HTTPException(500)` 违宪。**直接删**即可 |
| **4.3** | `backend/src/evaluation/websocket/broadcaster.py.backup` | 9 275 B | 2025-02-04 | `.backup` 后缀，0 引用 | 直接删 |
| **4.4** | `web/src/hooks/websocket/_unused/*`（如存在） | n/a | n/a | 0 引用 | 先 grep 验证 |
| **4.5** | `.kiro/steering/rule.md` | 0 B | n/a | 空文件，0 用途 | 删 |
| **4.6** | `backend/coverage.json`（如需刷新而非删除） | 旧快照 | 2026-02-12 | 4 个月未刷新，已无价值 | **建议不删**，覆盖刷新策略见 Agent 8 P2-4 |
| **4.7** | `backend/htmlcov/`（如存在且被 gitignore 排除） | 100MB+ | n/a | 覆盖率产物，不入版本库 | `.gitignore` 验证 |

**删除流程建议**：
1. 开 PR `chore(cleanup): delete deprecated files per audit-2026-06-09`
2. PR body 引用本文件 §4 编号
3. 必须跑完整单测 + 集成测试 + 契约测试
4. 删除前用 `rg "sales_handler.py.deprecated"` 二次确认 0 生产引用

---

## 5. ➕ 需新建文档

详见 `docs/agents/audit-2026-06/11-AGENTS-CLAUDE-patch.md`：

- `L3-domain/sales-trainer.md`（销售训练域 L3 规则）
- `docs/error-codes.md`（错误码中心表）
- `docs/observability/dead-metrics-action-plan.md`（17 死指标接入路径）
- `docs/agents/audit-2026-06/README.md`（本次审计索引）

---

## 6. 🏷️ 需新增 ADR（架构决策记录）

`docs/adr/` 当前 10 份，建议新增：

| ADR 编号 | 主题 | 触发 |
|---------|------|------|
| `2026-06-03-cross-domain-inheritance-fix.md` | 跨域继承修复：抽 `common/websocket/stepfun_realtime_handler.py` 模板基类 | Agent 1 F-01 / Agent 3 §10 |
| `2026-06-03-fallback-chain-actual-callers.md` | 降级链声明 ≠ 落地：接入 `ASRServiceWithFallback` / `TTSServiceWithFallback` 的实际 caller | Agent 4 F-ASR-1 / F-TTS-1 |
| `2026-06-03-stepfun-key-encryption.md` | `STEPFUN_API_KEY` 走 Fernet 加密，与 LLM/ASR/TTS 对称 | Agent 4 F-SEC-1 |
| `2026-06-03-pr-ci-gates.md` | 5 个 PR 必过门禁（lint / unit / contract / coverage-gate / secret-hygiene） | Agent 8 P0-3 |
| `2026-06-03-design-system-tokens.md` | 设计系统 token 单一真源 + bg-white 全量替换 | Agent 7 §1.4 |
| `2026-06-03-websocket-protocol-version.md` | WebSocket 协议 `schema_version` 顶层字段约定 | Agent 3 §3.3 |

每份 ADR 模板：
```markdown
# YYYY-MM-DD · <决策标题>

## 状态
Proposed / Accepted / Deprecated / Superseded by [ADR-XXX]

## 背景
<问题陈述 + 量化证据>

## 决策
<最终选择 + 备选>

## 后果
- 正面：...
- 负面：...
- 中和：...

## 关联
- 代码：file:line
- 报告：docs/agents/audit-2026-06/XX-*.md
- Issue：#NNN
```

---

## 7. 代码相关问题"创建文档记录"

按用户决策"代码相关问题创建一个文档记录"，将 30+ 个代码 P0/P1 整理为单文件：

**新建**：`docs/agents/audit-2026-06/12-code-issues-record.md`（本批次内最后一份新增）

内容结构：
```markdown
# 代码问题追踪记录 (2026-06-03)

> 状态：Draft（待批准）
> 来源：8 份专题报告
> 关联：10-issue-drafts.md（含 gh issue 草稿）

## P0 阻断 (24 项)
- [code-001] 跨域继承 — Agent 1 F-01 / Agent 3 §10
- [code-002] WebSocket 鉴权 sub 不绑 — Agent 6 P1-3
- [code-003] WebSocket 鉴权不 close(4401) — Agent 6 P1-4
- [code-004] STEPFUN_API_KEY 明文 — Agent 4 F-SEC-1
- [code-005] 17 Prometheus 指标死代码 — Agent 8 P0-2
- [code-006] trace_id 15 文件断崖 — Agent 8 P0-1
- [code-007] 销售训练 audio_submission 无 DELETE — Agent 4/6/8
- [code-008] bg-white 526 处 — Agent 7 §1.4
- [code-009] WS binaryType 0 — Agent 7 §10.3
- [code-010] CI PR 0 门禁 — Agent 8 P0-3
- [code-011] CLAUDE.md main.py 行数失真 — Agent 1 F-04
- [code-012] 3 处 HTTPException(500) — Agent 2 P0-1
- [code-013] common/business_rules/validators 80 raise — Agent 2 P0-4
- [code-014] support+supervisor 0 Result — Agent 2 P0-5
- [code-015] sales_trainer/services 110+ raise — Agent 2 P0-6
- [code-016] agent_service 13 查询 0 selectinload — Agent 5 P0-3
- [code-017] JSONB 列无 GIN 索引 — Agent 5 P0-1
- [code-018] pool_recycle 缺失 — Agent 5 P0-2
- [code-019] 分页缺失 — Agent 5 P0-4
- [code-020] 软删除标准字段缺失 — Agent 5 P0-5
- [code-021] admin audio_submission 列表裸露 user_email — Agent 6 P1-1
- [code-022] admin quiz_attempt 列表裸露 user_email — Agent 6 P1-2
- [code-023] X-Forwarded-For 无条件信任 — Agent 6 P1-5
- [code-024] ASRServiceWithFallback / TTSServiceWithFallback 生产 0 引用 — Agent 4 F-ASR-1 / F-TTS-1

## P1 严苛（约 60 项）
[同上模式，逐条编号 code-025 ~ code-085]

## P2 重要
[…]

## Sprint 分组（参见 00-executive-summary.md §6）
- Sprint-1: code-001 ~ code-010
- Sprint-2: code-011 ~ code-040
- Sprint-3: code-041 ~ code-085
```

---

## 8. 文档治理操作清单（按建议执行顺序）

| 阶段 | 动作 | 风险 | 评审要求 |
|------|------|------|---------|
| **Phase 1 (本周)** | 修 §1 五处 🔴 必修（CLAUDE.md + ai-practice-system.md） | 文档失真误导后续 agent/工程师 | PR review + 二次 grep 验证 |
| **Phase 1 (本周)** | 新建 §5 四份文档（L3-domain/error-codes/dead-metrics-action-plan/agents-audit-index） | 0 | 0 |
| **Phase 1 (本周)** | 新建 §7 代码问题记录 | 0 | 0 |
| **Phase 2 (下周)** | 修 §2 十三处 🟡 建议修订 | 中（CLAUDE.md 多段改） | PR review |
| **Phase 2 (下周)** | 合并 §3 三处（AGENTS.md 双层、steering/QUICK-REFERENCE.md 合并、api-contract/README 对齐矩阵） | 中 | PR review |
| **Phase 2 (下周)** | 新建 §6 六份 ADR | 0 | 0 |
| **Phase 3 (两周内)** | 删除 §4 七个文件（先 grep 二次确认 + LEGACY 元组处理） | 高 | 全测试套件 + CodeOwner 评审 |
| **Phase 3** | 文档评审：每份 ADR/规则文件 owner 签批 | 低 | 0 |

---

## 9. 关联文件清单

- `docs/agents/audit-2026-06/00-executive-summary.md` — 8 agent 综合摘要
- `docs/agents/audit-2026-06/01-08-*.md` — 8 份专题报告
- `docs/agents/audit-2026-06/10-issue-drafts.md` — GitHub Issue 草稿
- `docs/agents/audit-2026-06/11-AGENTS-CLAUDE-patch.md` — 规范回写 diff
- `docs/agents/audit-2026-06/12-code-issues-record.md` — 代码问题追踪（待新建）

---

**本清单不直接修改/删除任何现有文档**。所有变更需走 PR 评审流程。
