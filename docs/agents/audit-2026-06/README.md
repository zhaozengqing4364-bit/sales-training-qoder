# 销售训练 qoder · 严苛架构师审计 (2026-06)

> 入口索引，链接到 12 份审计产出物
> 审计基线：`feat(sales-trainer): 落地销售训练 MVP 与配置资产中心` (3c14f5d5)
> 审计方法：8 agent 并行静态分析；**0 行代码修改、0 个现有文件改动**

---

## 0. 报告清单

| # | 主题 | 路径 |
|---|------|------|
| 00 | 执行摘要 | [00-executive-summary.md](./00-executive-summary.md) |
| 01 | 架构边界与模块依赖 | [01-architecture-boundary.md](./01-architecture-boundary.md) |
| 02 | 错误处理与 Result 范式 | [02-result-and-error-handling.md](./02-result-and-error-handling.md) |
| 03 | WebSocket 实时链路与 StepFun | [03-websocket-realtime.md](./03-websocket-realtime.md) |
| 04 | 音频 / AI 能力 | [04-audio-and-ai-capabilities.md](./04-audio-and-ai-capabilities.md) |
| 05 | 数据库与持久化 | [05-database-and-persistence.md](./05-database-and-persistence.md) |
| 06 | 安全 / 鉴权 / 数据隐私 | [06-security-and-privacy.md](./06-security-and-privacy.md) |
| 07 | 前端架构与用户体验 | [07-frontend-architecture.md](./07-frontend-architecture.md) |
| 08 | 测试 / 可观测性 / CI | [08-testing-observability-ci.md](./08-testing-observability-ci.md) |
| 09 | 文档治理清单 | [09-doc-cleanup-checklist.md](./09-doc-cleanup-checklist.md) |
| 10 | GitHub Issue 草稿 | [10-issue-drafts.md](./10-issue-drafts.md) |
| 11 | AGENTS.md / CLAUDE.md 回写 diff | [11-AGENTS-CLAUDE-patch.md](./11-AGENTS-CLAUDE-patch.md) |
| 12 | 代码问题追踪记录 | [12-code-issues-record.md](./12-code-issues-record.md) |

---

## 1. 评级总览

| 域 | 评级 | 关键问题 |
|----|------|---------|
| 架构边界 | **C+** | 跨域继承、文档失真 |
| 错误处理 | **D+ (43%)** | 36% 覆盖、熔断/限流几乎全裸 |
| WebSocket 实时 | **B-/D** | 心跳扎实 / 鉴权缺口 / 协议漂移 |
| 音频/AI | **C-** | 降级链声明完整 / 生产 0 引用 |
| 数据库 | **B** | ORM 完美 / 5 P0 性能 |
| 安全 | **B-** | 横向越权全挡 / WS 鉴权漏 |
| 前端 | **B- (60/100)** | bg-white 526 / binaryType 缺 |
| 测试/CI | **D** | 17 死指标 / PR 零门禁 |
| **综合** | **C+ (57/100)** | **高复杂度 + 治理失能并存** |

---

## 2. 数字速览

| 维度 | 数字 |
|------|------|
| 后端 Python 文件 | ~290 |
| 后端测试文件 | 338 |
| 前端 page.tsx | 117 |
| 前端测试文件 | 166 |
| Alembic 迁移 | 77（0 孤儿、1 head）|
| P0 阻断项 | **24** |
| P1 严苛项 | **~60** |
| P2/P3 持续项 | **~30** |
| 跨 Agent 串证主题 | 12 |

---

## 3. Sprint 路线（按 ROI 排序）

### Sprint-1（1-2 周，~14 人天，24 P0）
1. CLAUDE.md 文档纠错（main.py 行数、common/ 子目录、bg-white/ErrorBoundary 强约束）
2. WebSocket 鉴权补完（close(4401) + sub↔session 强校验）
3. 跨域继承修复（抽 common 基类，方案 A）
4. STEPFUN_API_KEY Fernet 加密
5. 17 死指标接入或删除
6. stdlib logger 15 文件 → get_logger
7. 销售训练 audio_submission DELETE 路由 + 软删除
8. `bg-white` top-10 文件迁移
9. binaryType + 二进制 PCM 入站
10. CI PR 5 门禁工作流
11. 3 处 `HTTPException(500)` 修复
12. `common/business_rules/validators.py` 80 raise 重构
13. `support/` + `supervisor/` Result 范式引入
14. `sales_trainer/services/*` 110+ raise 改 Result
15. `agent_service.py` 13 查询加 selectinload
16. 14 个 JSONB 列加 GIN 索引
17. `pool_recycle` 配置补全
18. sales_trainer list 加 LIMIT 分页
19. 项目级软删除字段
20. admin audio/quiz 列表脱敏 user_email
21. `X-Forwarded-For` 信任链加固
22. ASR/TTS 降级链接入
23. CLAUDE.md 恢复事实

### Sprint-2（2-4 周，~18 人天）
- 49 端点失败态测试 / 49 端点 contract test
- 错误码中心表 + Result 升级
- 全局/用户级/IP 级限流中间件
- TTS/LLM/StepFun/ChromaDB 熔断补全
- JWT aud/iss + 撤销机制
- 14 sales-trainer 子段 error.tsx + loading.tsx
- JSONB GIN 索引 + selectinload + 分页
- React Query 接入 sales-trainer
- 9 个 WS 错误码文档化 + schema_version
- 日志脱敏 marker 补全

### Sprint-3（1-3 月，~25 人天）
- 双轨知识库合并
- 软删除标准字段
- Grafana 仪表盘 + 告警
- 设计系统 dark mode
- OTel 业务 span 注入
- 迁移命名规范化 + ADR 补齐
- contract ↔ doc 全量对齐
- a11y 提升
- 持续清理死代码

---

## 4. 协作规则

按 CLAUDE.md 协作规则：Draft → Approved → In Progress → Changed → Reapproved → Done。
本审计产出物均处于 **Draft** 状态，等待您批准后进入实施。

---

## 5. 关键证据

| 主题 | 来源 | 评级 |
|------|------|------|
| 跨域继承 | Agent 1 F-01 / 3 §10 | 🔴 |
| 文档失真（main.py 19655 vs 75） | Agent 1 F-04 | 🔴 |
| WebSocket 鉴权不 close(4401) | Agent 6 P1-3/4 | 🔴 |
| STEPFUN_API_KEY 明文 | Agent 4 F-SEC-1 | 🔴 |
| 17 Prometheus 指标死代码 | Agent 4 F-OBS-1 / 8 P0-2 | 🔴 |
| trace_id 15 文件断崖 | Agent 8 P0-1 | 🔴 |
| 销售训练 audio_submission 无 DELETE | Agent 4 D-SEC-2 | 🔴 |
| `bg-white` 526 / 140 文件 | Agent 7 §1.4 | 🔴 |
| WS binaryType 缺（R-1 P0） | Agent 7 §10.3 | 🔴 |
| CI 常规 PR 零门禁 | Agent 8 P0-3 | 🔴 |
| ASR/TTS 降级链生产 0 引用 | Agent 4 F-ASR-1/F-TTS-1 | 🔴 |
| 3 处 HTTPException(500) | Agent 2 P0-1 | 🔴 |
| 80 raise in `common/business_rules/validators.py` | Agent 2 P0-4 | 🔴 |
| 110+ raise in `sales_trainer/services/*` | Agent 2 P0-6 | 🔴 |
| admin 列表裸露 user_email | Agent 6 P1-1/2 | 🔴 |
| X-Forwarded-For 无条件信任 | Agent 6 P1-5 | 🔴 |
| 14 个 JSONB 列无 GIN 索引 | Agent 5 P0-1 | 🔴 |
| pool_recycle 缺失 | Agent 5 P0-2 | 🔴 |
| agent_service 13 查询零 selectinload | Agent 5 P0-3 | 🔴 |
| sales_trainer 0 分页 | Agent 5 P0-4 | 🔴 |
| 项目级软删除缺失 | Agent 5 P0-5 | 🔴 |

---

## 6. 严苛评分卡

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

## 7. 与 CLAUDE.md 协作规则对齐

- **执行流程**：人描述目标 → Agent 草拟规范 → 人审阅批准 → Agent 实施 → 偏差回写规范
- **强制回写触发**：跨域继承、降级链失能、StepFun 加密、CI 治理、bg-white 禁令、文档失真 6 大类
- **回写颗粒度**：仅记录"改变方向的决策"和"影响交付的事实"
- **评审门禁**：本审计所有产出物处于 **Draft** 状态，等待您批准
- **可追溯要求**：每条回写关联 8 份 agent 报告 + 文件:line 证据

---

**审计完成**。等待您决策：批准 → 进入 Sprint-1 实施 / 调整范围 / 拆分阶段。
