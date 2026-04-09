# GSD Plan: system-audit-repair

## 1. 需求重述与工作假设

### 1.1 用户目标
- 基于 `SYSTEM_AUDIT_REPORT.md`，为文档中列出的**全部问题**制定一个**可执行、颗粒度足够细**的修复计划。
- 计划必须能被后续执行模型直接消费，而不是泛泛而谈的 TODO 清单。
- 计划必须结合当前仓库真实状态，不能把已修事项、产品 deferred 项和真实缺陷混在一起。

### 1.2 当前阶段目标
- 先完成 **SYSTEM_AUDIT_REPORT 的问题归一化**：区分“已修 / 需验证关闭 / 真实缺口 / 需专项审计 / 当前 defer”。
- 在此基础上给出一份覆盖所有 audit section 的 **GSD repair roadmap**。
- 保持与现有 `.gsd/`、尤其是活跃 **M012** 的要求和知识约束一致。

### 1.3 关键约束
- 不编造不存在的模块、接口或测试能力。
- 不把 `report export` 这类已被现有 KNOWLEDGE 约束为“当前应保持缺失”的条目误规划成必须实现。
- 不把移动端 / i18n / dark mode / PWA 等产品策略类议题混进 launchability 修复主线。
- 现有 `M012` 只覆盖 launchability 子集，本计划需要说明**扩展边界**，但不直接篡改系统状态文件。
- 验证命令必须使用当前仓库真实可执行命令；backend focused pytest 默认串行。

### 1.4 工作假设
- 用户本轮要的是**计划**，不是立刻实现。
- `SYSTEM_AUDIT_REPORT.md` 中的所有条目都需要进入计划，但不代表所有条目都必须进入“马上编码”的 In Scope。
- 当前应优先清理**真实缺口 + 高价值 stale audit**，再进入性能 / 安全 / 运维 discovery wave。

### 1.5 T01 原始归一化矩阵（audit section → finding → disposition）

#### 1.5.1 disposition 图例
- `already-fixed`: 当前仓库已用真实代码 / 启动门禁 / 已验证事实退休风险。
- `actionable-now`: 当前仓库存在可直接执行的真实缺口，可进入后续实现切片。
- `needs-discovery`: 风险方向成立，但在承诺修复前必须先做专项证据化审计 / contract proof。
- `deferred-by-product`: 当前产品方向明确不把该项作为近期交付目标。
- `contradicted-by-project-knowledge`: audit 建议与当前项目知识、既有约束或兼容性前提相冲突，不应直接拉入修复 backlog。

#### 1.5.2 归一化矩阵汇总
- 总 finding 数：**51**
- `already-fixed`: **1**
- `actionable-now`: **15**
- `needs-discovery`: **26**
- `deferred-by-product`: **8**
- `contradicted-by-project-knowledge`: **1**

#### 1.5.3 Frontend UX（第 1 节）

| Audit ID | Finding | Disposition | Evidence path(s) | Preliminary owner |
|---|---|---|---|---|
| 1.1.1 | 前端 `console.*` 调试输出散落在业务组件中 | actionable-now | `SYSTEM_AUDIT_REPORT.md`; `web/src/components/ErrorBoundary.tsx`; `web/src/app/(user)/practice/[sessionId]/page.tsx`; `web/src/app/admin/settings/page.tsx` | `M3-S01` |
| 1.1.2 | admin 页面仍使用 `alert()` / `confirm()` 原生弹窗 | actionable-now | `web/src/app/admin/records/page.tsx`; `web/src/app/admin/rag-profiles/page.tsx`; `web/src/app/admin/personas/[id]/page.tsx` | `M3-S02` |
| 1.1.3 | 业务跳转仍存在 `window.location.assign/href`（`window.location.reload()` 例外） | actionable-now | `web/src/components/layout/admin-shell.tsx`; `web/src/components/layout/dashboard-shell.tsx`; `web/src/app/admin/error.tsx`; `web/src/components/ErrorBoundary.tsx` | `M3-S02` |
| 1.1.4 | `bg-white` vs `bg-stone-50` 视觉 token 不统一 | deferred-by-product | `SYSTEM_AUDIT_REPORT.md`; `.codex/loop/PROJECT_GROWTH.md`; `.gsd/PROJECT.md` | `none` |
| 1.2.1 | 移动端溢出 / 断点适配风险 | deferred-by-product | `SYSTEM_AUDIT_REPORT.md`; `.gsd/PROJECT.md` | `none` |
| 1.3.1 | 录音切换仅靠 300ms 启动锁，重复触发保护偏弱 | actionable-now | `web/src/app/(user)/practice/[sessionId]/page.tsx` | `M2-S04` |

#### 1.5.4 Backend API / 业务逻辑（第 2 节）

| Audit ID | Finding | Disposition | Evidence path(s) | Preliminary owner |
|---|---|---|---|---|
| 2.1.1 | backend 仍存在 `print()` 调试输出 | actionable-now | `backend/src/common/ai/encryption.py`; `backend/src/common/services/password_reset.py` | `M4-S02` |
| 2.1.2 | backend 路由 / auth 仍大量直接抛 `HTTPException`，未统一到现有错误响应 contract | actionable-now | `backend/src/common/auth/service.py`; `backend/src/admin/api/users.py`; `backend/src/common/knowledge/api.py`; `backend/src/common/api/analytics.py` | `M4-S02` |
| 2.1.3 | `# TODO: parameterize` 仍留在 staged evaluation | actionable-now | `backend/src/evaluation/services/staged_evaluation.py` | `M4-S02` |
| 2.2.1 | 通用 `except Exception` / 过宽异常捕获仍存在 | actionable-now | `backend/src/prompt_templates/models.py`; `backend/src/presentation_coach/services/interruption_detector.py` | `M4-S02` |
| 2.3.1 | `SessionLifecycleService` 没有并发锁或版本控制证明 | needs-discovery | `backend/src/common/db/session_lifecycle.py`; `backend/tests/unit/test_session_lifecycle_service.py`; `backend/tests/integration/test_session_lifecycle_api.py` | `M5-S01` |

#### 1.5.5 前后端联调 / 实时链路（第 3 节）

| Audit ID | Finding | Disposition | Evidence path(s) | Preliminary owner |
|---|---|---|---|---|
| 3.1.1 | API error shape 与 frontend `apiFetch` 的期望仍未彻底统一 | actionable-now | `web/src/lib/api/client.ts`; `backend/src/common/api/analytics.py`; `backend/src/common/knowledge/api.py`; `backend/src/common/auth/api.py` | `M4-S02` |
| 3.2.1 | `usePracticeWebSocket` / realtime handler 体量过大，但“拆哪里”仍需基于已发货 contract 再判定 | needs-discovery | `web/src/hooks/use-practice-websocket.ts`; `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` | `M5-S02` |
| 3.2.2 | 重连策略仍是固定 `MAX_RECONNECT_ATTEMPTS = 5`，未形成 backoff / stop-condition contract | actionable-now | `web/src/hooks/use-practice-websocket.ts` | `M5-S02` |

#### 1.5.6 权限与安全（第 4 节）

| Audit ID | Finding | Disposition | Evidence path(s) | Preliminary owner |
|---|---|---|---|---|
| 4.1.1 | `JWT_SECRET` 默认值风险已被非开发环境启动门禁退休 | already-fixed | `backend/src/common/auth/service.py`; `backend/src/main.py` | `closed` |
| 4.1.2 | admin 细粒度 RBAC 风险范围过大，需先画 permission matrix 再切真实 fix | needs-discovery | `backend/src/admin/api/users.py`; `backend/src/admin/api/`; `backend/src/common/auth/service.py` | `M4-S03` |
| 4.2.1 | 敏感信息日志泄露风险需要先做高风险出口清点与脱敏策略 | needs-discovery | `web/src/components/ErrorBoundary.tsx`; `backend/src/common/services/password_reset.py`; `backend/src/common/monitoring/logger.py` | `M4-S03` |

#### 1.5.7 数据模型 / 状态流转（第 5 节）

| Audit ID | Finding | Disposition | Evidence path(s) | Preliminary owner |
|---|---|---|---|---|
| 5.1.1 | `String(36)` 存 UUID 是当前 SQLite / PostgreSQL 兼容策略，不应作为修复项推进 | contradicted-by-project-knowledge | `backend/src/common/db/models.py`; `.gsd/PROJECT.md` | `none` |
| 5.2.1 | session 状态转换边界是否完整，需先补 transition matrix / negative proof | needs-discovery | `backend/src/common/db/session_lifecycle.py`; `backend/tests/unit/test_session_lifecycle_service.py` | `M5-S01` |

#### 1.5.8 功能缺失 / 待完善项（第 6 节）

| Audit ID | Finding | Disposition | Evidence path(s) | Preliminary owner |
|---|---|---|---|---|
| 6.1 | admin “新增公告” 仍是空壳能力 | deferred-by-product | `web/src/app/admin/page.tsx`; `.gsd/PROJECT.md` | `none` |
| 6.2 | admin 系统监控卡片仍展示硬编码数字，truthfulness 不够 | actionable-now | `web/src/app/admin/page.tsx` | `M6-S03` |
| 6.3 | admin 全局搜索框无真实检索逻辑 | deferred-by-product | `web/src/app/admin/page.tsx`; `.gsd/PROJECT.md` | `none` |
| 6.4 | 日志导出按钮无真实闭环 | deferred-by-product | `web/src/app/admin/page.tsx`; `.gsd/PROJECT.md` | `none` |

#### 1.5.9 性能 / 测试 / 文档（第 7-9 节）

| Audit ID | Finding | Disposition | Evidence path(s) | Preliminary owner |
|---|---|---|---|---|
| 7.1 | 前端性能建议是泛化建议，缺少当前瓶颈证据 | needs-discovery | `web/src/app/(dashboard)/page.tsx`; `web/src/app/(user)/practice/[sessionId]/page.tsx`; `web/src/lib/performance.ts` | `M6-S01` |
| 7.2 | 后端性能建议缺少 query baseline / slow-path 证据 | needs-discovery | `backend/src/common/analytics/admin_analytics_service.py`; `backend/src/common/conversation/session_evidence.py` | `M6-S01` |
| 7.3 | WebSocket 性能建议缺少真实热点 / 序列化成本证据 | needs-discovery | `web/src/hooks/use-practice-websocket.ts`; `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` | `M5-S02` |
| 8.1 | 前端“覆盖率未知”需要先建立 focused verification baseline，而不是直接喊补测试 | needs-discovery | `web/src/app/(dashboard)/page.test.tsx`; `web/src/app/(auth)/login/page.test.tsx`; `web/src/hooks/use-practice-websocket.test.ts` | `M1-S02` |
| 8.2 | 后端“覆盖率未知”需要先建立 focused verification baseline，而不是直接喊补测试 | needs-discovery | `backend/tests/contract/test_practice_evidence_contract.py`; `backend/tests/integration/test_session_lifecycle_api.py`; `backend/tests/integration/test_password_reset_api.py` | `M1-S02` |
| 9.1 | API 文档是否与代码同步，当前只能确认文档存在，不能确认一致性 | needs-discovery | `api-spec.md`; `specs/001-ai-practice-system/contracts/openapi.yaml` | `M6-S02` |
| 9.2 | “部分复杂逻辑缺少注释”是泛化 maintainability 建议，当前不应优先转成注释 churn | deferred-by-product | `SYSTEM_AUDIT_REPORT.md`; `.gsd/PROJECT.md`; `.codex/loop/PROJECT_GROWTH.md` | `none` |

#### 1.5.10 数据库 / 内存 / 并发 / 依赖治理（第 11-14 节）

| Audit ID | Finding | Disposition | Evidence path(s) | Preliminary owner |
|---|---|---|---|---|
| 11.1 | N+1 查询风险需要真实 query baseline 才能确认 | needs-discovery | `backend/src/common/analytics/admin_analytics_service.py`; `backend/src/common/analytics/history_service.py` | `M6-S01` |
| 11.2 | 索引缺口需要基于真实 PostgreSQL 查询面确认 | needs-discovery | `backend/src/common/db/models.py`; `backend/src/common/analytics/admin_analytics_service.py` | `M6-S01` |
| 11.3 | 慢查询监控缺失需要先建立现状与告警基线 | needs-discovery | `backend/src/common/monitoring/`; `.github/workflows/nfr-performance-check.yml` | `M6-S01` |
| 12.1 | WebSocket 连接关闭 / 清理是否泄漏，需要 runtime evidence 才能下 fix 结论 | needs-discovery | `web/src/hooks/use-practice-websocket.ts`; `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` | `M5-S02` |
| 12.2 | `useEffect` cleanup 完整性需要专项审计而不是全文盲改 | needs-discovery | `web/src/hooks/use-practice-websocket.ts`; `web/src/hooks/use-audio-recorder.ts`; `web/src/hooks/use-streaming-audio-player.ts` | `M5-S02` |
| 12.3 | 全局事件监听器未移除风险需要专项审计而不是全文盲改 | needs-discovery | `web/src/components/layout/admin-shell.tsx`; `web/src/components/layout/dashboard-shell.tsx`; `web/src/app/(user)/practice/[sessionId]/use-practice-recording-hotkeys.ts` | `M5-S02` |
| 13.1 | 文件上传并发竞争需要沿 presentation upload / replace 真实链路先做 proof | needs-discovery | `backend/src/presentation_coach/api/presentations.py`; `web/src/app/admin/presentations/[id]/page.tsx` | `M5-S03` |
| 13.2 | 共享资源竞争条件需要先基于真实 runtime surface 出证据 | needs-discovery | `backend/src/common/storage/audio.py`; `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` | `M5-S03` |
| 13.3 | 分布式锁缺失不是独立 defect，需先确认多实例下哪些流程真的需要锁 | needs-discovery | `backend/src/common/db/session_lifecycle.py`; `backend/src/presentation_coach/api/presentations.py` | `M5-S03` |
| 14.1 | 依赖安全漏洞需要通过 `npm audit` / `pip-audit` 先生成真实清单 | needs-discovery | `web/package.json`; `backend/requirements.txt` | `M6-S02` |
| 14.2 | 许可证合规问题需要先做仓库级扫描清单 | needs-discovery | `web/package.json`; `backend/requirements.txt` | `M6-S02` |
| 14.3 | 仓库当前缺少明确的依赖更新节奏与验证门禁 | actionable-now | `web/package.json`; `backend/requirements.txt`; `.github/workflows/nfr-performance-check.yml` | `M6-S02` |

#### 1.5.11 i18n / a11y / DR（第 15-17 节）

| Audit ID | Finding | Disposition | Evidence path(s) | Preliminary owner |
|---|---|---|---|---|
| 15.1 | 硬编码中文字符串 | deferred-by-product | `SYSTEM_AUDIT_REPORT.md`; `.gsd/PROJECT.md` | `none` |
| 15.2 | 多语言支持缺失 | deferred-by-product | `SYSTEM_AUDIT_REPORT.md`; `.gsd/PROJECT.md` | `none` |
| 15.3 | 时区展示问题需要先确认真实用户面与 formatter 行为 | needs-discovery | `backend/src/common/db/models.py`; `web/src/app/(dashboard)/history/page.tsx`; `web/src/app/(dashboard)/leaderboard/page.tsx` | `M3-S03` |
| 16.1 | ARIA 标签缺失范围需要先做 baseline audit，当前代码已存在部分 a11y seam | needs-discovery | `web/src/components/layout/sidebar.tsx`; `web/src/app/(auth)/login/page.tsx`; `web/src/app/(user)/practice/[sessionId]/page.tsx` | `M3-S03` |
| 16.2 | 键盘导航支持不足需要先做关键路径 walkthrough | needs-discovery | `web/src/components/layout/sidebar.tsx`; `web/src/app/(user)/practice/[sessionId]/use-practice-recording-hotkeys.ts`; `web/src/components/ui/tabs.tsx` | `M3-S03` |
| 16.3 | 颜色对比度不足需要先做 design / a11y baseline，而不是盲目调色 | needs-discovery | `SYSTEM_AUDIT_REPORT.md`; `web/src/app/(dashboard)/page.tsx`; `web/src/app/admin/page.tsx` | `M3-S03` |
| 17.1 | 缺少数据库备份策略文档 / runbook | actionable-now | `SYSTEM_AUDIT_REPORT.md`; `.github/workflows/nfr-performance-check.yml` | `M6-S03` |
| 17.2 | 缺少标准化故障恢复流程 | actionable-now | `SYSTEM_AUDIT_REPORT.md`; `.github/workflows/nfr-performance-check.yml` | `M6-S03` |
| 17.3 | 缺少容灾演练基线 | actionable-now | `SYSTEM_AUDIT_REPORT.md`; `.github/workflows/nfr-performance-check.yml` | `M6-S03` |

#### 1.5.12 非 finding 性元信息处理
- 第 10 节“总结与优先级排序”是对前述 finding 的重新排序，不新增独立 backlog 项。
- 第 18 节“需要补充的信息”是 discovery 证据缺口列表，已被折叠进 `needs-discovery` disposition，而不是另起 5 个实现型问题。

#### 1.5.13 T02 disposition 复核补遗
- 复核结果：`51 / 51` finding 仍全部落入五类 disposition，本次补齐后不再存在“只有 disposition 名称、但缺少关闭证据 / 冲突来源 / 后续归属解释”的条目。
- 解释规则：
  - `already-fixed` 必须锚到真实 retirement seam，而不是只写“已修”。
  - `deferred-by-product` / `contradicted-by-project-knowledge` 必须明确写出冲突来源，避免后续执行时把产品边界误当 defect。
  - `needs-discovery` 必须写清承接 slice 与需要补出的 proof，避免 discovery 项在后续里程碑中漂成无主 TODO。

##### 已修项 retirement 证据

| Audit ID | Retirement seam | Why the risk is retired |
|---|---|---|
| 4.1.1 | `backend/src/common/auth/service.py` 仍保留本地开发默认 `JWT_SECRET` 兜底，但 `backend/src/main.py` 在 `ENVIRONMENT != development` 时会对默认值或缺失值直接 `raise RuntimeError("JWT_SECRET must be set in production via environment variable")` | 该风险已由真实启动门禁退休：非开发环境无法带着默认 secret 启动，所以 audit 所说的“默认值落生产”不再是待办实现项。 |

##### deferred / contradicted 条目的冲突来源

| Audit ID | Disposition | Conflict source | Why it stays out of the implementation backlog |
|---|---|---|---|
| 1.1.4 | deferred-by-product | `.codex/loop/PROJECT_GROWTH.md` 的 anti-goal 明确禁止 `cosmetic churn without evidence`；`.gsd/PROJECT.md` 也把当前主线定义为训练真相链与稳定性收口，而不是视觉细抠 | 视觉 token 不统一确实存在，但当前没有用户结果证据证明它值得挤占 launchability / truthfulness 修复主线。 |
| 1.2.1 | deferred-by-product | `.gsd/PROJECT.md` 已明确“先把桌面端稳定性做满，不在第一阶段绑定移动端 / 企业微信 / 外部系统集成”；`R018` 也把移动端首发列为 deferred | 这条是产品边界，不是当前 launch blocker；后续若首发边界变化，再单独升格为移动端专项。 |
| 5.1.1 | contradicted-by-project-knowledge | `backend/src/common/db/models.py` 顶部兼容性说明明确写明“使用 String(36) 存储 UUID 以兼容 SQLite 和 PostgreSQL” | audit 把这一点当 schema defect，但对当前仓库来说它是既有兼容策略；若直接改成数据库方言特化，反而会破坏现有跨 SQLite/PostgreSQL 运行假设。 |
| 6.1 | deferred-by-product | `.gsd/PROJECT.md` 把当前系统的北极星限定在“训练 → 反馈 → 复盘 → 再训练”的闭环；`R021` 也要求不要新增更多页面 / 控制台表层功能去掩盖主训练闭环问题 | admin “新增公告”属于外围运营表面，不是当前训练核心能力或 launchability 缺口。 |
| 6.3 | deferred-by-product | `.gsd/PROJECT.md` 当前治理主线集中在知识库 / Persona / PPT / runtime 等训练资产；`R021` 禁止用新的表层控制台能力替代核心链路修复 | admin 全局搜索是运营增强项，不应在 audit repair wave 中伪装成必修基础设施。 |
| 6.4 | deferred-by-product | `.gsd/PROJECT.md` 当前优先级是训练事实链、报告可信度和现有治理页 truthfulness；`R021` 约束本轮不要扩表层控制台能力 | 日志导出没有进入当前产品闭环目标；在没有明确运维使用场景和 owner 前，不应先当成当前必做功能。 |
| 9.2 | deferred-by-product | `.codex/loop/PROJECT_GROWTH.md` 明确反对 `cosmetic churn without evidence`；本计划 §2 Out of Scope 也排除了为 maintainability 建议做大规模注释 churn | “复杂逻辑缺少注释”是泛化工程建议，现阶段更应优先补 contract / test / runtime proof，而不是做大面积注释改写。 |
| 15.1 | deferred-by-product | 本计划 §2 Out of Scope 已把 `i18n / 多语言` 排除在当前 repair wave 之外；`.gsd/PROJECT.md` 也明确当前首发先做桌面端内部训练稳定性 | 硬编码中文是已知国际化议题，但当前不是首发桌面训练闭环的阻塞项。 |
| 15.2 | deferred-by-product | 本计划 §2 Out of Scope 已把 `i18n / 多语言` 排除在当前 repair wave 之外；`.gsd/PROJECT.md` 当前产品定位仍是企业内部中文训练闭环 | 多语言支持缺失是后续产品扩展方向，不属于本轮 audit repair 的“真实缺口马上修”。 |

##### needs-discovery 条目的后续归属

| Audit ID | Owning slice | Discovery proof required before implementation |
|---|---|---|
| 2.3.1 | `M5-S01` | 用 race-oriented lifecycle tests 证明 `pause / resume / end` 是否真的存在并发写冲突，再决定是否引入行锁或乐观并发控制。 |
| 3.2.1 | `M5-S02` | 先沿现有 shipped websocket contract 画出 hook / runtime 职责边界，再决定是否需要进一步拆分 `usePracticeWebSocket` 或 realtime handler。 |
| 4.1.2 | `M4-S03` | 先产出 admin route permission matrix，明确每个 surface 的角色边界，再切具体 RBAC 改动。 |
| 4.2.1 | `M4-S03` | 先做高风险日志出口盘点，给出 token / password / cookie / email 的脱敏规则与受影响入口。 |
| 5.2.1 | `M5-S01` | 先补 session transition matrix 与 negative proof，证明哪些非法状态迁移真的会穿透当前 lifecycle seam。 |
| 7.1 | `M6-S01` | 先对 dashboard / practice 热路径建立前端性能 baseline，确认真实热点后再决定是否做性能修复切片。 |
| 7.2 | `M6-S01` | 先收集后端 query baseline 与 slow-path 证据，避免把泛化性能建议直接当成待实现缺陷。 |
| 7.3 | `M5-S02` | 先拿到 websocket 热点与序列化成本证据，再判断 backpressure / batching / queue 策略是否需要调整。 |
| 8.1 | `M1-S02` | 先锁定 learner 关键面的 focused web verification baseline，再决定哪里是真正的测试缺口。 |
| 8.2 | `M1-S02` | 先锁定 auth / lifecycle / evidence 等核心 backend focused gates，再决定哪些模块确实需要新增测试。 |
| 9.1 | `M6-S02` | 先做 spec-vs-code 一致性审计，给出 openapi / api-spec 与 live route contract 的漂移清单。 |
| 11.1 | `M6-S01` | 先对 admin / history 等读取链做 query count / explain proof，确认是否真的存在 N+1。 |
| 11.2 | `M6-S01` | 先基于真实 PostgreSQL 查询面列出索引缺口证据，而不是从 ORM 定义静态猜测。 |
| 11.3 | `M6-S01` | 先明确慢查询监控现状、可采集指标和告警基线，再决定是否需要新监控面。 |
| 12.1 | `M5-S02` | 先为 websocket close / cleanup 路径建立 runtime evidence，确认是否存在连接泄漏或清理遗漏。 |
| 12.2 | `M5-S02` | 先对关键 hooks 做 cleanup 审计，证明哪些 `useEffect` teardown 真缺失、哪些只是代码体量大。 |
| 12.3 | `M5-S02` | 先对全局事件监听 attach/remove 配对做专项 walkthrough，再决定是否需要统一 listener seam。 |
| 13.1 | `M5-S03` | 先沿 presentation upload / replace 真实链路做并发复现，确认文件替换时是否真有竞争窗口。 |
| 13.2 | `M5-S03` | 先列出共享资源访问面并拿到 runtime contention 证据，再决定资源锁或隔离策略。 |
| 13.3 | `M5-S03` | 先按多实例场景画出“哪些流程真的需要锁”的 necessity matrix，而不是把分布式锁缺失单独当 defect。 |
| 14.1 | `M6-S02` | 先跑出 `npm audit` / `pip-audit` 的真实清单，再把高风险依赖漏洞转成 implementation backlog。 |
| 14.2 | `M6-S02` | 先做 license scan baseline，明确仓库当前许可证清单与风险分级，再决定治理动作。 |
| 15.3 | `M3-S03` | 先在 history / leaderboard 等真实 learner surfaces 上确认 formatter 与时区展示行为，再决定是否需要用户态时区策略。 |
| 16.1 | `M3-S03` | 先做 ARIA baseline audit，确定关键路径上哪些控件缺 label / role，避免全仓盲改。 |
| 16.2 | `M3-S03` | 先做键盘导航 walkthrough，证明 learner 关键任务链上哪些步骤不能仅靠键盘完成。 |
| 16.3 | `M3-S03` | 先建立 design / a11y contrast baseline，确认真实对比度问题后再做调色或 token 调整。 |

---

## 2. 范围定义（In / Out）

### In Scope
- 对 `SYSTEM_AUDIT_REPORT.md` 全文做问题分流与执行优先级设计。
- 产出可执行切片，覆盖：
  - learner UX / auth / dashboard / history / profile / practice
  - frontend hygiene（console / alert / window.location / error/loading coverage）
  - backend auth / error contract / session lifecycle / websocket hardening
  - admin UX 中断项与权限/日志安全
  - 性能 / 安全 / 依赖 / 备份等 discovery slices
- 说明与当前 `.gsd/REQUIREMENTS.md`、`M012` 的重叠、冲突和接续方式。

### Out of Scope
- 直接修改现有 milestone DB/STATE。
- 直接实现任何功能。
- 在没有专项 discovery 证据前，承诺修复：N+1、所有索引、所有内存泄漏、所有并发锁、所有许可证问题。
- 直接把以下条目视为当前必须交付：
  - 自助注册 / 外部试玩
  - 全量移动端适配
  - i18n / 多语言
  - 暗色模式
  - PWA / 离线
  - report export（除非产品方向明确改变）

---

## 3. 工程分层分析

| 层级 | 当前项目现状 | 本轮是否纳入 | 说明 |
|---|---|---:|---|
| 产品/业务层 | 训练闭环已成型，launchability 与治理在补齐 | 是 | 本轮重点是把 audit finding 正确映射成产品真实 backlog |
| 前端层 | Next.js 16 + React 19，learner/admin 双壳并存 | 是 | 大量 audit finding 落在这里 |
| 后端层 | FastAPI + SQLAlchemy Async + WebSocket | 是 | auth/error contract/lifecycle/concurrency 都要规划 |
| 数据层 | Alembic + models + projection-backed read models | 是 | session lifecycle、索引、slow query discovery 属于本轮 |
| 集成/接口层 | `web/src/lib/api/client.ts` + 多个 FastAPI routes | 是 | API 错误格式和 auth 行为要收口 |
| 测试层 | Web Vitest + backend pytest 已成体系 | 是 | 每个切片都要挂真实验证命令 |
| 部署/运维层 | 仅有有限 workflow，backup/DR 治理弱 | 是 | 以 discovery/runbook 为主，不直接承诺自动化全套 |
| 文档/可观测性层 | `.gsd/` 完整，监控/logging基础在 | 是 | 需补 audit closeout、日志规范、敏感信息脱敏策略 |

---

## 4. 里程碑总览

### M1. 审计归一化与计划基线收口
- 目标：把 SYSTEM_AUDIT_REPORT 中的所有条目分成“已修 / 真实缺口 / 需 discovery / 当前 defer”，形成可信 backlog。
- 为什么先做：现在审计文档与当前仓库存在显著漂移，直接执行会浪费工时。
- 完成后得到：后续每个执行模型只处理真实问题，不会被 stale finding 误导。
- 依赖：现有 `.gsd/PROJECT.md`、`.gsd/REQUIREMENTS.md`、M012。
- 风险：如果不做，会把现有 requirement / knowledge 冲掉。

### M2. Learner 入口与体验闭环补齐
- 目标：把首页 / auth / history / profile / practice 里真正影响首次使用和复练的缺口补齐。
- 为什么先做：这部分最直接影响“第一次打开系统能不能顺利走通”。
- 完成后得到：launchability 质量明显提升，且与当前 M012 能自然衔接。
- 依赖：M1。
- 风险：容易把产品策略问题（移动端 / export / self-registration）误拉进来。

### M3. Frontend hygiene 与中断式交互清理
- 目标：系统性替换 console / alert / confirm / window.location 等不一致模式，补齐 learner 壳层 error/loading 覆盖。
- 为什么先做：这是大面积、低层级、跨页面的一致性问题，适合在 learner wave 后单独收口。
- 完成后得到：更稳定的错误表面、可观察性和 UX 一致性。
- 依赖：M1，可与 M2 后半并行。
- 风险：如果不设边界，会扩成“重写整个前端架构”。

### M4. Auth / API / Security contract hardening
- 目标：把 password reset、鉴权模式、错误响应、RBAC、日志脱敏从“能用”升到“可依赖”。
- 为什么先做：SYSTEM_AUDIT_REPORT 中真正的高优先级 backend 问题集中在这里。
- 完成后得到：认证与错误表面更加统一，可作为后续治理基线。
- 依赖：M1，部分依赖 M2 的 learner flow确认。
- 风险：会触及 shared auth seam，必须 strong model 牵头。

### M5. 实时状态与并发安全收口
- 目标：围绕 session lifecycle、practice websocket、上传并发与资源竞争建立明确的事实线和修复边界。
- 为什么先做：这些问题的风险高，但没有先证据就容易做成表面 patch。
- 完成后得到：状态机和 realtime 行为更可证伪、可维护。
- 依赖：M1，部分依赖 M3/M4。
- 风险：跨前后端、跨状态机、跨测试层。

### M6. 性能 / 依赖 / 运维治理 discovery
- 目标：把审计里“像问题但未证实”的性能、安全、容灾类条目转成有证据的后续 backlog。
- 为什么先做：这些条目价值高，但不该被伪装成已知 fix。
- 完成后得到：慢查询、索引、依赖漏洞、许可证、备份恢复现状的真实基线。
- 依赖：M1，可与 M4/M5 后段并行。
- 风险：如果没有边界，容易变成无限审计工程。

---

## 5. 详细切片清单

### [M1-S01] SYSTEM_AUDIT_REPORT 条目归一化

#### Goal
- 对 `SYSTEM_AUDIT_REPORT.md` 全文逐条建立 disposition：`already-fixed` / `actionable-now` / `needs-discovery` / `deferred-by-product` / `contradicted-by-project-knowledge`。

#### Why This Slice Exists
- 当前审计文档和真实代码状态有漂移；执行前必须先纠偏。

#### In Scope
- 全文条目清点
- 和当前代码、M012、REQUIREMENTS、KNOWLEDGE 做对照
- 形成覆盖矩阵

#### Out of Scope
- 改代码
- 改 REQUIREMENTS 状态
- 改 milestone 状态

#### Inputs / Preconditions
- `SYSTEM_AUDIT_REPORT.md`
- `.gsd/PROJECT.md`
- `.gsd/REQUIREMENTS.md`
- `.gsd/KNOWLEDGE.md`
- `M012-ROADMAP.md`

#### Target Files / Modules
- `.gsd/analysis/ARCHITECTURE_SCAN_SYSTEM_AUDIT_2026-04-08.md`
- `.gsd/plans/GSD_PLAN_system-audit-repair.md`

#### Implementation Notes
- 先做问题清单归类，再进入实现 slices。
- 对“已修”条目写明证据文件路径。
- 对“deferred”条目写明冲突来源（例如 PROJECT.md 的桌面优先首发）。

#### Done When
- SYSTEM_AUDIT_REPORT 的每个 section 都能落到某个 disposition 类别。

#### Verification
- 人工核对：问题清单中不存在“未归类条目”。
- `rg -n "already-fixed|actionable-now|needs-discovery|deferred-by-product|contradicted-by-project-knowledge" .gsd/plans/GSD_PLAN_system-audit-repair.md`

#### Deliverable
- 一份可信的 audit normalization matrix。

#### Risk Level
- Medium

#### Recommended Executor
- Strong model
- 原因：需要跨文档、跨代码、跨已有 GSD 事实做判断。

---

### [M1-S02] 审计相关验证基线补齐

#### Goal
- 为后续所有 repair slice 先锁定可复用的 web/backend focused 验证命令集合。

#### Why This Slice Exists
- audit 项覆盖面大，没有统一验证基线会让后续切片变成“做了但无法证明”。

#### In Scope
- 盘点现有测试文件
- 为 auth/dashboard/history/profile/practice/lifecycle/websocket/admin 选定 focused commands
- 标注必须串行的 backend proof

#### Out of Scope
- 大规模新增测试
- 改 CI workflow

#### Inputs / Preconditions
- `web/src/**/*.test.tsx?`
- `backend/tests/**/*`
- `.gsd/KNOWLEDGE.md`

#### Target Files / Modules
- `docs/plans/2026-04-08-system-audit-remediation-plan.md`
- 后续各 slice 的 Verification 段

#### Implementation Notes
- backend repo-root pytest 命令串行执行，避免 `.coverage` 竞争。
- 先复用现有 focused tests，再决定哪里补新用例。

#### Done When
- 每个后续切片至少有一个已存在的 focused verification command。

#### Verification
- `rg -n "npm --prefix web test|backend/venv/bin/python -m pytest" .gsd/plans/GSD_PLAN_system-audit-repair.md docs/plans/2026-04-08-system-audit-remediation-plan.md`

#### Deliverable
- audit wave 的 verification contract。

#### Risk Level
- Low

#### Recommended Executor
- Fast model
- 原因：主要是证据组织与命令落位，不涉及架构重构。

---

### [M2-S01] 首页硬编码与空壳动作收口

#### Goal
- 清理 dashboard 首页当前仍存在的静态更新内容、无动作按钮、假筛选与缺少 onboarding 的问题。

#### Why This Slice Exists
- 首页是新人首次进入后的第一屏，当前存在高密度“看起来能点、实际没闭环”的元素。

#### In Scope
- 首页版本/更新弹窗内容来源校正
- “下载报告 / 设定目标 / 分享分析 / 筛选”这类空壳动作的 disposition（实现 / 移除 / disabled + 文案）
- 新手 onboarding 入口（最小 3 步）

#### Out of Scope
- 新增独立 onboarding 系统后台
- 报告导出重新上线

#### Inputs / Preconditions
- `web/src/app/(dashboard)/page.tsx`
- `R030`
- 当前 history/report route family 能正常打开

#### Target Files / Modules
- `web/src/app/(dashboard)/page.tsx`
- 可能新增 `web/src/components/dashboard/*`
- 对应 page tests

#### Implementation Notes
- 先做“动作收口策略表”：实现、改为深链、改为 disabled 说明、直接删除。
- 不要重新引入 report export affordance。

#### Done When
- 首页不再存在“点了没反应”的主按钮/弹窗 CTA。
- 首页首屏存在最小 onboarding 指引。

#### Verification
- `npm --prefix web test -- --run "src/app/(dashboard)/history/page.test.tsx"`
- 若新增首页 focused tests，则并入 `dashboard` 相关 test 命令。
- 浏览器人工验证：首页首屏 CTA 至少一条通向真实训练入口。

#### Deliverable
- 清理后的 dashboard home 交互闭环。

#### Risk Level
- Medium

#### Recommended Executor
- Strong model
- 原因：首页既涉及产品取舍，也涉及现有 requirement/knowledge 约束。

---

### [M2-S02] 认证与个人中心体验补齐

#### Goal
- 把 learner 侧“能登录”提升到“能维护账号”：forgot/reset 正式化、profile 修改密码体验闭合、语速偏好持久化补齐。

#### Why This Slice Exists
- 现状是 forgot/reset 已存在，但实现偏过渡；profile 修改密码入口只是重定向忘记密码。

#### In Scope
- forgot/reset 体验补强
- profile 内可理解的修改密码路径
- 语速偏好落真实存储
- 通知开关 / 摆设项的 disposition

#### Out of Scope
- 自助注册
- 真正的消息通知系统

#### Inputs / Preconditions
- `web/src/app/(auth)/*`
- `web/src/app/(dashboard)/profile/page.tsx`
- `backend/src/common/auth/api.py`
- `backend/src/common/auth/service.py`

#### Target Files / Modules
- 前端 auth/profile 路由
- backend auth routes / services / migration
- `web/src/app/(auth)/login/page.test.tsx`
- `backend/tests/integration/test_auth_login_api.py`

#### Implementation Notes
- 分两步：先体验收口，再补 auth backend 正式化。
- profile 中“修改密码”不应继续使用 `window.location.href`。
- 语速偏好不可继续“try/catch 静默忽略”。

#### Done When
- 用户能从 profile 里走到正式的修改密码路径。
- 语速偏好刷新后仍保留，且有明确后端落点或明确的隐藏/移除策略。

#### Verification
- `npm --prefix web test -- --run "src/app/(auth)/login/page.test.tsx"`
- `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_auth_login_api.py -x -q`

#### Deliverable
- learner auth/profile 的可持续闭环。

#### Risk Level
- High

#### Recommended Executor
- Strong model
- 原因：触及 auth seam、数据持久化和用户体验。

---

### [M2-S03] Learner 导航、反馈入口与系统壳层补齐

#### Goal
- 补齐 learner 侧统一反馈入口、角色/使用说明、缺失导航和壳层级帮助信息。

#### Why This Slice Exists
- SYSTEM_AUDIT_REPORT 里的大量“不会用”问题，本质是缺少壳层说明而不是缺功能。

#### In Scope
- 联系管理员 / 反馈入口
- 角色/权限说明最小文案
- learner shell 导航一致性检查

#### Out of Scope
- 完整帮助中心
- 通知系统

#### Inputs / Preconditions
- `web/src/components/layout/sidebar.tsx`
- dashboard/profile/home 页面

#### Target Files / Modules
- `web/src/components/layout/sidebar.tsx`
- `web/src/app/(dashboard)/*`
- 可能新增 shared learner support component

#### Implementation Notes
- 优先在 learner shell 提供统一入口，而不是每页单独塞按钮。
- 如果某项信息不适合常显，用 profile/home 卡片承载。

#### Done When
- learner 至少有一个稳定的“遇到问题怎么办”入口。
- 不再需要靠隐性文案解释权限或联系管理员方式。

#### Verification
- `npm --prefix web test -- --run "src/app/(dashboard)/history/page.test.tsx"`
- 浏览器人工验证：从首页、profile、history 任一页都能找到帮助/反馈入口。

#### Deliverable
- learner 壳层帮助与导航一致性。

#### Risk Level
- Medium

#### Recommended Executor
- Fast model
- 原因：边界明确，主要是壳层补全与深链。

---

### [M2-S04] 训练前预期管理与中断恢复 UX 收口

#### Goal
- 补齐 practice 页的 preflight / pre-context / 中断恢复说明，减少“直接被扔进语音对话”的割裂感。

#### Why This Slice Exists
- practice 页已有 pause/resume/end，但训练前说明、场景预期和中断时的指引还不够成体系。

#### In Scope
- 训练前目标/评价标准/角色简介最小预告
- 暂停/恢复/结束失败的用户可理解文案
- `test-mic` 页的可访问性约束（隐藏/标记开发工具）

#### Out of Scope
- 文本输入模式（先做单独 spike 决策，不直接承诺）
- 新建单独 preflight route

#### Inputs / Preconditions
- `web/src/app/(user)/practice/[sessionId]/page.tsx`
- `usePracticeSessionLifecycle`
- `usePracticeWebSocket`

#### Target Files / Modules
- `web/src/app/(user)/practice/[sessionId]/page.tsx`
- `web/src/app/(user)/practice/[sessionId]/page.test.tsx`
- `web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts`

#### Implementation Notes
- 优先复用现有页面内 overlay / banner，不新增复杂路由。
- 文本输入模式先列入 spike，不和本 slice 混做。

#### Done When
- 用户在开始录音前能理解本次练习在练什么。
- 暂停/恢复/结束失败时页面有清晰指引。
- `test-mic` 不会再以普通 learner 功能暴露。

#### Verification
- `npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/page.test.tsx" "src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts"`

#### Deliverable
- practice preflight + interruption UX baseline。

#### Risk Level
- Medium

#### Recommended Executor
- Strong model
- 原因：涉及 learner 主链路和实时状态语义。

---

### [M3-S01] 前端日志出口统一化

#### Goal
- 把前端大量 `console.*` 调用收口到明确的 debug/observability seam，并区分 dev-only 与 durable error reporting。

#### Why This Slice Exists
- 这是广泛存在的系统性 hygiene 问题，逐个页面 patch 价值低。

#### In Scope
- `console.*` 清点
- 分类：debug-only / durable error / instrumentation / tests
- 使用 `@/lib/debug` 或 observability helper 收口

#### Out of Scope
- 重写整个观测体系
- 移除浏览器端所有错误上报

#### Inputs / Preconditions
- `web/src/lib/debug.ts`
- `web/src/components/ErrorBoundary.tsx`
- `web/src/instrumentation*.ts`

#### Target Files / Modules
- `web/src/lib/debug.ts`
- `web/src/components/ErrorBoundary.tsx`
- audit 命中的 admin/practice/audio hooks 等文件

#### Implementation Notes
- instrumentation 层允许保留少量结构化 console 输出，但必须解释其存在。
- route `error.tsx` 内的 `console.error` 也应纳入统一规则。

#### Done When
- 除 instrumentation/dev-only 例外外，不再有随意 `console.log/error` 散落业务页面。

#### Verification
- `rg -n "console\.(log|error|warn|info)" web/src`
- `npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/page.test.tsx" "src/hooks/use-practice-websocket.test.ts"`

#### Deliverable
- 前端统一日志出口规则与第一轮清理结果。

#### Risk Level
- Medium

#### Recommended Executor
- Fast model
- 原因：规则明确、搜索替换占比高，但需要少量 judgment。

---

### [M3-S02] 原生弹窗与 window.location 跳转清理

#### Goal
- 消除 admin/learner 中断式交互与直接浏览器跳转，统一到 toast/dialog/router/auth-handler seam。

#### Why This Slice Exists
- `alert/confirm/window.location` 是当前前端 UX 断裂和状态丢失的主要来源之一。

#### In Scope
- admin `alert/confirm` 替换
- learner/profile/admin shell 中 `window.location.assign/href` 替换
- 明确允许保留 `window.location.reload()` 的少数场景

#### Out of Scope
- 所有浏览器 API 的彻底禁用

#### Inputs / Preconditions
- `web/src/app/admin/records/page.tsx`
- `web/src/app/admin/rag-profiles/page.tsx`
- `web/src/app/admin/personas/[id]/page.tsx`
- `web/src/components/layout/*`
- `web/src/lib/auth-handler.ts`

#### Target Files / Modules
- 上述文件
- 可能新增 shared confirm dialog / action-confirm hook

#### Implementation Notes
- 删除操作统一走 modal confirm。
- auth redirect 统一通过 `authHandler` / router，而不是页面本地 assign。
- ErrorBoundary 中 reload 保留为例外，不强行去掉。

#### Done When
- 业务页面中不再存在 `alert()/confirm()`。
- 业务跳转不再使用 `window.location.assign/href`。

#### Verification
- `rg -n "\b(alert|confirm)\s*\(|window\.location(\.assign|\.href)" web/src`
- `npm --prefix web test -- --run "src/app/admin/personas/[id]/page.test.tsx" "src/app/(auth)/login/page.test.tsx"`

#### Deliverable
- 统一的非中断式交互与路由跳转模式。

#### Risk Level
- Medium

#### Recommended Executor
- Fast model
- 原因：变更分散但语义清晰。

---

### [M3-S03] Learner error/loading 覆盖与 responsive/a11y/timezone baseline

#### Goal
- 补齐 learner 路由簇中缺失的 error/loading 壳层，并对响应式、a11y、时区问题形成最小基线。

#### Why This Slice Exists
- SYSTEM_AUDIT_REPORT 把 कई UX 风险归因到“没有统一壳层保护”；当前代码是部分有、部分没有。

#### In Scope
- learner route error/loading coverage matrix
- history/training/auth 等缺失路由补齐
- responsive/a11y/timezone 做 baseline audit，并只修低风险高价值项

#### Out of Scope
- 全量移动端改造
- 全站 WCAG 大重构
- 全量时区偏好系统

#### Inputs / Preconditions
- `find web/src/app -name 'error.tsx' -o -name 'loading.tsx'`
- dashboard/history/practice/auth 路由

#### Target Files / Modules
- `web/src/app/(dashboard)/**/error.tsx|loading.tsx`
- `web/src/app/(auth)/**`
- learner shared components

#### Implementation Notes
- 先补路由级 fallback，再做局部 a11y/responsive fixes。
- mobile full support 不纳入；仅避免明显不可操作的断点失败。

#### Done When
- learner 核心路由（auth/home/training/history/profile/practice/report/replay）都有明确的 error/loading 策略。
- baseline a11y/responsive/timezone 风险有证据记录和明确 disposition。

#### Verification
- `find web/src/app -type f \( -name 'error.tsx' -o -name 'loading.tsx' \) | sort`
- `npm --prefix web test -- --run "src/app/(dashboard)/history/page.test.tsx" "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx"`

#### Deliverable
- learner 壳层保护基线 + lightweight UX audit closeout。

#### Risk Level
- Medium

#### Recommended Executor
- Strong model
- 原因：需要控制 scope，避免被移动端/a11y 全面重写吞掉。

---

### [M4-S01] Password reset / auth backend 正式化

#### Goal
- 把当前 password reset 和 auth 实现从“演示可用”升级为“正式 contract 可维护”。

#### Why This Slice Exists
- 当前 auth API 已能跑通 forgot/reset，但实现里仍有运行时 DDL、无真实 email abstraction、无明确 rate limit 证明。

#### In Scope
- PasswordResetToken 正式模型与 migration
- token 生命周期、一次性使用、过期校验
- EmailService seam
- 限流策略
- 登录路径和 per-user hashed password contract 梳理

#### Out of Scope
- 接通真实第三方邮件服务
- WeCom SSO 实现

#### Inputs / Preconditions
- `backend/src/common/auth/api.py`
- `backend/src/common/auth/service.py`
- `backend/src/common/db/models.py`
- Alembic 环境

#### Target Files / Modules
- auth api/service/models/migrations/tests

#### Implementation Notes
- 不要继续在 request path 里 `CREATE TABLE IF NOT EXISTS`。
- shared password / user-specific password / reset password 三层逻辑必须显式建模。

#### Done When
- password reset 有正式持久化与 migration。
- forgot/reset 的安全与生命周期行为可被 focused tests 证明。

#### Verification
- `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_auth_login_api.py -x -q`
- 如新增 password reset focused tests，串行加入同一命令链。

#### Deliverable
- 正式化的 password reset / auth recovery seam。

#### Risk Level
- High

#### Recommended Executor
- Strong model
- 原因：直接触及认证安全与数据迁移。

---

### [M4-S02] API 错误契约与异常分类收口

#### Goal
- 统一后端 API 的错误响应格式，减少裸 `HTTPException` 与通用 `except Exception` 在业务层直接暴露。

#### Why This Slice Exists
- SYSTEM_AUDIT_REPORT 中真正的前后端联调痛点之一就是错误格式不统一。

#### In Scope
- prompt templates / presentations / auth 等高噪声路由先收口
- 区分 domain error、permission error、not found、validation error
- 保持现有 frontend `apiFetch` 能稳定解析

#### Out of Scope
- 一次性改完整个 backend 所有模块
- 重写 FastAPI 全局异常框架

#### Inputs / Preconditions
- `backend/src/prompt_templates/api/routes.py`
- `backend/src/presentation_coach/api/presentations.py`
- `backend/src/common/auth/service.py`
- `web/src/lib/api/client.ts`

#### Target Files / Modules
- 上述 route / service / schema / tests

#### Implementation Notes
- 先挑 SYSTEM_AUDIT 明确点名的 surface，不做全仓扫平。
- auth dependency 中保留 framework-level auth rejection 可以，但 outward JSON contract 要一致。

#### Done When
- audit 命中的高频 API surface 都返回统一错误 shape。
- frontend client 不需要 page-local 猜测错误格式。

#### Verification
- `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_presentations.py backend/tests/contract/test_practice_evidence_contract.py backend/tests/integration/test_presentation_flow.py -x -q`

#### Deliverable
- 第一批统一错误契约 surface。

#### Risk Level
- High

#### Recommended Executor
- Strong model
- 原因：涉及跨 route contract 与前端兼容。

---

### [M4-S03] RBAC、敏感日志与 admin 安全面 audit

#### Goal
- 为 admin routes 的权限粒度与日志脱敏建立明确的风险图谱，并先修高确定性问题。

#### Why This Slice Exists
- SYSTEM_AUDIT_REPORT 把权限粒度和敏感日志泄露列为高优先级，但当前仓库缺少显式 closeout 证据。

#### In Scope
- admin route permission matrix
- token/password/PII log redaction points
- 最小权限审计日志策略

#### Out of Scope
- 自定义 RBAC 系统重写
- 完整 SIEM 集成

#### Inputs / Preconditions
- `backend/src/admin/api/*`
- `backend/src/common/monitoring/*`
- auth dependencies

#### Target Files / Modules
- admin APIs
- logger / middleware / helper
- focused backend tests

#### Implementation Notes
- 先做“谁可访问什么”的矩阵，再决定代码层改动。
- 日志脱敏优先处理 token、password、cookie、email 全量输出风险。

#### Done When
- admin 高风险接口有明确权限证明。
- 日志敏感字段脱敏规则成文并落到高风险出口。

#### Verification
- `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_admin_users_api.py backend/tests/unit/admin/test_admin_users_api_models.py -x -q`

#### Deliverable
- admin security audit baseline + 第一批 hardening。

#### Risk Level
- High

#### Recommended Executor
- Strong model
- 原因：安全边界与角色访问控制需要架构判断。

---

### [M5-S01] Session lifecycle 并发安全 proof

#### Goal
- 为 `SessionLifecycleService` 建立并发安全证据，并在需要时引入行锁/乐观并发控制。

#### Why This Slice Exists
- 当前服务已集中状态机逻辑，但没有数据库级并发安全证明。

#### In Scope
- transition race 场景设计
- paused/resume/end 竞争路径验证
- 锁策略或版本控制策略选型

#### Out of Scope
- 重写整个 PracticeSession 生命周期架构

#### Inputs / Preconditions
- `backend/src/common/db/session_lifecycle.py`
- session lifecycle API / practice runtime
- 现有 session lifecycle tests

#### Target Files / Modules
- `backend/src/common/db/session_lifecycle.py`
- `backend/tests/unit/test_session_lifecycle_service.py`
- `backend/tests/integration/test_session_lifecycle_api.py`

#### Implementation Notes
- 先写 race-oriented failing tests，再选锁策略。
- 与 `status=scoring/completed` 的现有事实线兼容。

#### Done When
- pause/resume/end 并发场景有明确测试与收敛策略。
- 不再只有“理论上可能竞态”的审计描述。

#### Verification
- `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_session_lifecycle_service.py backend/tests/integration/test_session_lifecycle_api.py -x -q`

#### Deliverable
- 有证据支撑的 lifecycle concurrency contract。

#### Risk Level
- High

#### Recommended Executor
- Strong model
- 原因：状态机 + DB 行为 + API 语义耦合高。

---

### [M5-S02] Practice WebSocket 复杂度与重连策略收口

#### Goal
- 把当前 practice websocket orchestrator 的复杂度、重连策略和 backpressure 规则再收口一轮。

#### Why This Slice Exists
- hook 已拆分过一次，但仍然很大；reconnect/backpressure/interrupt 是高风险面。

#### In Scope
- reconnect 策略（固定次数 vs 指数退避 + 退出条件）
- hook 职责再拆分的边界
- 内存/队列清理 proof

#### Out of Scope
- 推倒重写整个 realtime 协议
- 引入重量级状态机框架（除非 discovery 明确证明需要）

#### Inputs / Preconditions
- `web/src/hooks/use-practice-websocket.ts`
- practice page
- backend websocket runtime

#### Target Files / Modules
- `web/src/hooks/use-practice-websocket.ts`
- `web/src/hooks/use-practice-websocket.test.ts`
- `web/src/hooks/use-practice-websocket.presentation-flow.test.ts`
- `web/src/app/(user)/practice/[sessionId]/page.test.tsx`

#### Implementation Notes
- 当前代码已存在 backpressure、interrupt、binary frame negotiation，不要忽略这些 shipped facts。
- 把“文件大”转成具体的 seam，而不是为拆分而拆分。

#### Done When
- reconnect/backpressure/interrupt 的 contract 更清晰，复杂度下降且测试保持通过。

#### Verification
- `npm --prefix web test -- --run "src/hooks/use-practice-websocket.test.ts" "src/hooks/use-practice-websocket.presentation-flow.test.ts" "src/app/(user)/practice/[sessionId]/page.test.tsx"`

#### Deliverable
- 更稳定、更可维护的 websocket orchestration seam。

#### Risk Level
- High

#### Recommended Executor
- Strong model
- 原因：实时交互主链路，回归代价高。

---

### [M5-S03] 文件上传 / 资源竞争 / 分布式锁风险 discovery

#### Goal
- 把文件上传并发、资源竞争、分布式锁缺失这类“风险项”先转成可证据化的 discovery 结论。

#### Why This Slice Exists
- SYSTEM_AUDIT_REPORT 直接给出修复建议，但当前并没有足够 evidence 证明真实故障面。

#### In Scope
- presentation upload / replace 路径并发行为
- 共享资源访问冲突点识别
- 多实例场景下需要锁的关键点清单

#### Out of Scope
- 直接引入 Redis 分布式锁到全系统
- 全量并发治理框架

#### Inputs / Preconditions
- `backend/src/presentation_coach/api/presentations.py`
- 相关 integration/contract tests

#### Target Files / Modules
- presentations API/service/tests
- discovery artifact

#### Implementation Notes
- 先回答“哪里真的存在竞争”再决定是否上锁。
- 和现有 active-session blocker 机制一起看，不要重复治理已覆盖场景。

#### Done When
- 并发风险点有明确列表、可复现路径和下一步建议。

#### Verification
- `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_presentations.py backend/tests/integration/test_presentation_flow.py backend/tests/integration/test_presentation_delete_permissions.py -x -q`

#### Deliverable
- upload/resource race discovery report。

#### Risk Level
- Medium

#### Recommended Executor
- Strong model
- 原因：要区分真实风险与想象中的并发问题。

---

### [M6-S01] 数据库性能基线 discovery

#### Goal
- 对 N+1、索引、slow query 做第一轮基线审计，产出真实优化 backlog。

#### Why This Slice Exists
- SYSTEM_AUDIT_REPORT 的数据库性能条目目前都是“可能”，还不是证据化问题。

#### In Scope
- 热点查询梳理
- projection/history/admin/leaderboard 关键 SQL 检查
- 索引缺口假设列表
- slow query / explain 分析方案

#### Out of Scope
- 立即新增大量索引
- 直接承诺全站性能优化完成

#### Inputs / Preconditions
- `backend/src/common/analytics/*`
- `backend/src/common/conversation/session_evidence.py`
- admin/history/leaderboard APIs

#### Target Files / Modules
- discovery 文档
- 如有高确定性索引缺口，再生成后续 implementation slice

#### Implementation Notes
- 先看 shared projection 路径，再看 admin/history/leaderboard 消费面。
- 不要把 SQLite 测试表现当 PostgreSQL 真结论。

#### Done When
- 有一份真实的 query/index baseline，而不是审计猜测。

#### Verification
- `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_analytics.py backend/tests/unit/common/test_admin_analytics_service.py backend/tests/unit/common/test_leaderboard_service.py -x -q`

#### Deliverable
- DB performance discovery artifact。

#### Risk Level
- Medium

#### Recommended Executor
- Strong model
- 原因：需要跨 query surface 与读模型判断。

---

### [M6-S02] 依赖安全、许可证与更新策略基线

#### Goal
- 把依赖安全、许可证、更新策略从口头建议变成明确维护流程。

#### Why This Slice Exists
- 这是 audit 里的治理类条目，适合独立成 lightweight ops baseline。

#### In Scope
- npm / pip 漏洞扫描流程
- license 扫描建议
- 更新节奏与验证门禁

#### Out of Scope
- 一次性升级所有依赖
- 引入重量级依赖机器人平台

#### Inputs / Preconditions
- `web/package.json`
- `backend/requirements.txt`
- `.github/workflows/nfr-performance-check.yml`

#### Target Files / Modules
- docs / scripts / workflow suggestions

#### Implementation Notes
- 先落人工可执行流程，再决定是否自动化。
- backend 依赖变更仍需同步 `backend/requirements.txt`。

#### Done When
- 有明确的依赖扫描和升级策略文档，且可在仓库中执行。

#### Verification
- `npm audit --prefix web`
- `backend/venv/bin/python -m pip_audit`（若环境具备）

#### Deliverable
- dependency governance baseline。

#### Risk Level
- Low

#### Recommended Executor
- Fast model
- 原因：主要是治理流程与脚本落位。

---

### [M6-S03] 备份 / 故障恢复 / 容灾 runbook 基线

#### Goal
- 把备份频率、恢复流程、灾难恢复演练从“缺失”转成最小可执行 runbook。

#### Why This Slice Exists
- 这些条目重要，但当前更适合文档与流程建设，而不是直接搞复杂自动化。

#### In Scope
- DB backup 当前做法盘点
- 恢复步骤 runbook
- 季度演练建议
- 关键负责人 / 证据位置

#### Out of Scope
- 自动故障转移
- 异地备份平台建设

#### Inputs / Preconditions
- 当前部署方式、scripts、数据库连接方式

#### Target Files / Modules
- `docs/` 或 `.gsd/analysis/` 下的 runbook 文档

#### Implementation Notes
- 先写真实现状和恢复步骤，不写理想架构空话。

#### Done When
- 有一份可跟着操作的 backup/recovery baseline 文档。

#### Verification
- 人工走查 runbook 是否依赖真实路径/命令。

#### Deliverable
- backup / DR baseline runbook。

#### Risk Level
- Medium

#### Recommended Executor
- Fast model
- 原因：以现状梳理和文档化为主。

---

## 6. 依赖关系图（文字版）

- M1-S01 → M1-S02 → 所有后续切片
- M2-S01 依赖 M1-S01；M2-S02 / M2-S03 / M2-S04 依赖 M1-S01，可并行但建议按首页→auth/profile→practice 顺序执行
- M3-S01 → M3-S02 → M3-S03
- M4-S01 与 M4-S02 共享 auth/api seam，建议先 M4-S01 再 M4-S02
- M4-S03 依赖 M4-S02 的错误/权限分类结果
- M5-S01 先于 M5-S02，因为 lifecycle 语义决定 websocket 行为边界
- M5-S03 可在 M5-S01 后并行
- M6-S01 / M6-S02 / M6-S03 都依赖 M1-S01 的审计归一化，但彼此可并行

---

## 7. 执行模型分流建议

### 适合 Fast model 的切片
- M1-S02 审计验证基线补齐
- M2-S03 learner 导航与反馈入口补齐
- M3-S01 前端日志出口统一化
- M3-S02 alert/confirm/window.location 清理
- M6-S02 依赖安全与更新策略基线
- M6-S03 备份/恢复 runbook 基线

### 必须 Strong model 处理的切片
- M1-S01 审计归一化
- M2-S01 首页硬编码与空壳动作收口
- M2-S02 认证与个人中心体验补齐
- M2-S04 practice preflight / interruption UX 收口
- M3-S03 learner error/loading + responsive/a11y/timezone baseline
- M4-S01 password reset / auth backend 正式化
- M4-S02 API 错误契约与异常分类收口
- M4-S03 RBAC / 敏感日志审计
- M5-S01 lifecycle 并发安全 proof
- M5-S02 websocket 复杂度与重连策略收口
- M5-S03 上传/资源竞争 discovery
- M6-S01 数据库性能基线 discovery

### 分流原则
- 涉及现有 requirement/knowledge 冲突判断、跨模块 contract、状态机、安全边界的，归 Strong model。
- 边界清晰、以搜索替换/文档化/壳层补全为主的，归 Fast model。
- “需要先做 discovery 才能决定实现”的切片，也归 Strong model，因为关键产出是判断而不是编码量。

---

## 8. 重规划触发条件

- 连续两次 focused verification 失败，且失败面扩大到原切片之外。
- 发现 SYSTEM_AUDIT_REPORT 的更多条目与现有代码严重不一致，导致当前 backlog 分类失真。
- auth / session lifecycle / websocket 任何一个 shared seam 改动后影响 report/replay/history/admin 的统一事实线。
- 为解决某个 learner UX 问题，不得不引入新的数据模型、鉴权流程或跨页面状态框架。
- performance/security/ops discovery 证明真实风险远高于当前预期，需要单独新 milestone。
- 用户明确改变产品边界：例如要求恢复 report export、推进移动端、推进 i18n、自助注册。
- 现有 M012 与本计划执行面明显冲突，需要将 SYSTEM_AUDIT repair 正式升级成新 milestone。

---

## 9. 对当前项目的 GSD / GSD auto 落地建议

### 目录建议
- 架构扫描：`.gsd/analysis/ARCHITECTURE_SCAN_SYSTEM_AUDIT_2026-04-08.md`
- 审计修复计划：`.gsd/plans/GSD_PLAN_system-audit-repair.md`
- 执行交接文档：`docs/plans/2026-04-08-system-audit-remediation-plan.md`

### 命名建议
- 继续沿用当前 `.gsd/` 体系，不新造 “specs/tasks/roadmap” 平行体系。
- 若后续决定把本计划升格为 milestone，再正式生成新的 M 编号，而不是现在手工伪造。

### 执行顺序建议
1. 先执行 M1（审计归一化）
2. 再执行 M2（learner 入口体验）
3. 同步推进 M3（frontend hygiene）
4. 再推进 M4 / M5（backend contract + realtime safety）
5. 最后做 M6（performance/security/ops discovery）

### 风险控制建议
- backend focused pytest 串行跑，避免 `.coverage` 冲突。
- 不要为了“消灭所有 audit 条目”而强推 deferred feature。
- 对 report export / mobile / i18n / dark mode / PWA 这类条目，优先做 disposition 明确，而不是偷偷混入实现。
- 先补 tests / verification，再做 shared seam 改动。

---

## 10. 可直接给执行模型的任务单模板（展开 6 个）

### Task Card 1
- Task ID: M1-S01-T01
- Title: 建立 SYSTEM_AUDIT_REPORT 问题归一化矩阵
- Goal: 逐条整理 SYSTEM_AUDIT_REPORT 的 disposition，并补上代码证据路径。
- In Scope: 全文 audit 条目、当前代码、M012、REQUIREMENTS、KNOWLEDGE 对照。
- Out of Scope: 改代码、改 requirement 状态、改 milestone 状态。
- Preconditions: 已读 `.gsd/PROJECT.md`、`.gsd/REQUIREMENTS.md`、`.gsd/KNOWLEDGE.md`、`SYSTEM_AUDIT_REPORT.md`。
- Files/Modules to Inspect: `SYSTEM_AUDIT_REPORT.md`, `.gsd/PROJECT.md`, `.gsd/REQUIREMENTS.md`, `.gsd/KNOWLEDGE.md`, `.gsd/milestones/M012/*`。
- Constraints: 必须标明 stale finding；不得把 deferred feature 伪装成 bug。
- Done When: 每个 audit section 都有 disposition 和后续 slice 归属。
- Verification Steps: `rg -n "already-fixed|actionable-now|needs-discovery|deferred-by-product|contradicted-by-project-knowledge" .gsd/plans/GSD_PLAN_system-audit-repair.md`
- Expected Output: 一份可执行的 audit normalization matrix。
- Recommended Executor: Strong model

### Task Card 2
- Task ID: M2-S01-T01
- Title: 首页空壳动作清点与收口策略
- Goal: 把 dashboard 首页所有“可点击但无闭环”的动作归类为实现、深链、禁用提示或删除。
- In Scope: 首页按钮、版本弹窗、筛选弹窗、分享/设定目标类 CTA、新手 onboarding 最小入口。
- Out of Scope: 报告导出恢复、全量帮助中心。
- Preconditions: Task 1 完成，已确认 report export 属于当前受限项。
- Files/Modules to Inspect: `web/src/app/(dashboard)/page.tsx`, `web/src/app/(dashboard)/history/page.tsx`, `web/src/components/layout/sidebar.tsx`。
- Constraints: 不得重新引入被 KNOWLEDGE 明确禁止的“导出报告” affordance。
- Done When: 首页无主按钮空壳；首屏有最小 onboarding 指引。
- Verification Steps: `npm --prefix web test -- --run "src/app/(dashboard)/history/page.test.tsx"`
- Expected Output: 首页 CTA 收口方案 + focused 测试补丁。
- Recommended Executor: Strong model

### Task Card 3
- Task ID: M2-S02-T01
- Title: 把 forgot/reset 从过渡实现升级为正式 auth seam
- Goal: 正式化 password reset token 存储、过期/一次性使用、email abstraction、rate limit。
- In Scope: auth api/service/model/migration/tests。
- Out of Scope: 真正接入外部邮件平台、WeCom SSO。
- Preconditions: 已确认当前 forgot/reset 页面与 API 已存在，需要 harden 而不是从零构建。
- Files/Modules to Inspect: `backend/src/common/auth/api.py`, `backend/src/common/auth/service.py`, `backend/src/common/db/models.py`, `web/src/app/(auth)/*`。
- Constraints: 不得继续在 request path 中做 DDL；必须保持现有登录兼容路径可解释。
- Done When: reset token 有正式持久化与 focused proof。
- Verification Steps: `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_auth_login_api.py -x -q`
- Expected Output: 正式化 password reset seam。
- Recommended Executor: Strong model

### Task Card 4
- Task ID: M3-S02-T01
- Title: 清理 alert/confirm/window.location 使用点
- Goal: 系统性替换业务页面里的原生弹窗和直接 location 跳转。
- In Scope: admin records/rag-profiles/personas、profile、admin shell、dashboard shell、auth redirect。
- Out of Scope: `window.location.reload()` 在 ErrorBoundary 的少数例外。
- Preconditions: 已确认 toast/dialog/router/auth-handler 的可复用 seam。
- Files/Modules to Inspect: `web/src/app/admin/records/page.tsx`, `web/src/app/admin/rag-profiles/page.tsx`, `web/src/app/admin/personas/[id]/page.tsx`, `web/src/app/(dashboard)/profile/page.tsx`, `web/src/components/layout/*`, `web/src/lib/auth-handler.ts`。
- Constraints: 删除确认必须保留；不能因为替换而降低安全确认等级。
- Done When: 业务代码里不再有 `alert()/confirm()` 与 `window.location.assign/href`。
- Verification Steps: `rg -n "\b(alert|confirm)\s*\(|window\.location(\.assign|\.href)" web/src`
- Expected Output: 统一的非中断式交互模式。
- Recommended Executor: Fast model

### Task Card 5
- Task ID: M5-S01-T01
- Title: 为 session lifecycle 写并发证明用例
- Goal: 用 failing tests 明确 pause/resume/end 的 race 行为，再决定锁策略。
- In Scope: lifecycle service、API 行为、并发状态转移。
- Out of Scope: 重写 session 模型。
- Preconditions: 已读 `backend/src/common/db/session_lifecycle.py` 和相关 integration tests。
- Files/Modules to Inspect: `backend/src/common/db/session_lifecycle.py`, `backend/tests/unit/test_session_lifecycle_service.py`, `backend/tests/integration/test_session_lifecycle_api.py`。
- Constraints: 必须保持 sales `scoring` / presentation `completed` 的既有终态差异。
- Done When: 竞态场景有测试和明确收敛策略。
- Verification Steps: `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_session_lifecycle_service.py backend/tests/integration/test_session_lifecycle_api.py -x -q`
- Expected Output: lifecycle concurrency proof + 后续锁策略建议。
- Recommended Executor: Strong model

### Task Card 6
- Task ID: M6-S01-T01
- Title: 建立数据库性能 discovery 基线
- Goal: 把 N+1 / 索引 / slow query 风险从猜测变成证据化 backlog。
- In Scope: analytics/history/leaderboard/projection 关键路径。
- Out of Scope: 一次性上线大规模索引优化。
- Preconditions: 已确认 backend focused pytest 需串行运行。
- Files/Modules to Inspect: `backend/src/common/analytics/*`, `backend/src/common/conversation/session_evidence.py`, 相关 contract/unit tests。
- Constraints: 不得把 SQLite 测试数据直接当 PostgreSQL 结论。
- Done When: 有一份 query/index baseline 和后续优化列表。
- Verification Steps: `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_analytics.py backend/tests/unit/common/test_admin_analytics_service.py backend/tests/unit/common/test_leaderboard_service.py -x -q`
- Expected Output: DB performance discovery artifact。
- Recommended Executor: Strong model
