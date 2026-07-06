# 独立架构审计报告 · 2026-07-03（二次复核修订版）

> **审计对象**：Enterprise AI Intelligent Practice System（企业级 AI 智能演练系统）  
> **审计基准日**：2026-07-03  
> **原始代码快照口径**：main 分支 @ commit `39d65976`。原稿记录工作区另有约 786 个未提交变更；二次复核期间又新增 Trellis 任务与本文档修改，工作区精确数量以当次 `git status --short` 为准。  
> **原审查文稿来源**：用户提供附件 `/Users/zhaozengqing/.codex/attachments/5efd4916-ad02-4606-af12-64d7ec0e0b15/pasted-text.txt`；本文件修改前内容为该审计稿在仓库内的落地版本。  
> **二次复核方式**：主 Agent 复核 + 4 个专项 Agent 第一轮交叉审查（架构、后端/安全、前端/体验、测试/CI）+ 2 个只读 Agent 第二轮重复审查（critic、reviewer）。第二轮发现已在本版吸收，见附录 B。  
> **审计边界**：本文是架构审计与整改路线图，不等同于已执行的功能验收报告。除特别说明外，结论来自静态代码、文档、CI 脚本与测试资产审查，未声明线上运行指标。

---

## 0. 二次复核摘要

**原稿总体方向成立，但不能逐条照单整改。**

成立的是大方向：系统不是简单功能堆叠，已经有 ADR、领域契约、ConfigBundle、受控 Adapter、状态机冻结、权限与发布治理等架构资产；同时也确实存在执行债，集中在可观测性接线不足、进程内异步任务、多实例 WebSocket 状态边界、RBAC 口径漂移、CI 白名单偏窄、文档与工作区纪律漂移。

需要修订的是证据精度：原稿把若干“风险”写成“已证实缺陷”，把局部缺口写成全局缺失，并存在数处事实错误。例如 `require_role` 并非只判断 `admin`，`supervisor` 和 `presentation_coach` 并非没有测试，审计表并非只有 2 张，`common/api/practice.py` 的按 `session_id` 查询也不是直接可定性的 IDOR 漏洞。

**可信度判断**：修订后结论可信度约 7/10。它足以指导下一轮架构治理优先级，但每个安全、权限、队列、WebSocket 发送语义整改项仍需要单独补测试与影响面分析。

---

## 1. 总体结论

**判断**：这是一个“架构治理型但执行欠债”的系统。骨架可继承，不应推倒重来；当前最应该做的是把治理骨架和运行时代码重新接实。

系统真实存在治理资产：

- ADR 与契约文档已经覆盖训练任务、PracticeSession、ConfigBundle、Sales/PPT Plugin、Roleplay Contract 等关键边界。
- `sales_trainer` 后台配置治理、发布预览、修订历史、操作日志、权限 fail-closed 等能力相对成熟。
- `curriculum_practice` 与 `sales_trainer` 存在受控跨域 Adapter 的明确 ADR 约束。
- StepFun、TTS、ASR、RuntimeGate、SessionStateService 等运行时已具备一定降级、Admission、快照与重连设计。
- 后端 389 个测试文件、前端 199 个测试文件（统计 `web/src` 与 `web/tests`，排除 `node_modules`）说明测试资产可观，问题不是“没有测试”，而是关键门禁覆盖和测试分布不均。

主要执行债：

1. **可观测性有定义但核心链路接线不足**  
   `common/monitoring/metrics.py` 里多项核心业务指标存在，但 WS、TTS、ASR、LLM、practice session、error 等 `track_*` 未在关键链路广泛接入。例外是 frontend analytics 与 roleplay situation pack dual-read mismatch 已有调用点，所以不能再写成“17 个 Prometheus 指标全是死代码”。

2. **运行时可靠性仍偏进程内**  
   Redis session snapshot 是跨实例状态源，但 WebSocket 连接表仍是进程内；Redis 启动期不可用会使 session state service 初始化失败；音频处理、知识库文档处理、报告生成触发、音频归档 scheduler 等存在 process-local `BackgroundTasks` / `asyncio.create_task` / lifespan-owned scheduler 形态，缺少统一持久队列、死信和补偿。

3. **权限与审计不是空白，但口径分裂**  
   角色词表、admin-only 依赖、`AdminRolePermission`、`sales_trainer.permissions`、`prompt_templates.permissions` 多套权限口径并存。统一审计 API 没有覆盖所有域内操作日志，尤其 `SalesTrainerOperationLog` 与全局审计视图之间仍有断层。

4. **CI 白名单偏窄，关键域未全部进入门禁**  
   `scripts/critical-quality-gate.sh` 当前前端白名单 29 项，后端主白名单 38 项，另有少量 smoke/newcomer 目标。相对 389 个后端测试文件和 199 个前端测试文件，门禁覆盖偏窄。问题不是测试资产少，而是关键测试未系统进入 release gate。

5. **文档、任务与工作区纪律降低可审计性**  
   工作区长期大量未提交变更、部分文档描述与现状不一致、Trellis 任务生命周期未完全收敛，会让“代码快照”和“审计结论”之间难以建立稳定对应关系。

---

## 2. 证据等级与勘误原则

本文按四类处理原稿结论：

| 等级 | 含义 | 本文处理 |
| --- | --- | --- |
| 已证实缺陷 | 代码、CI、文档或测试能直接证明 | 保留，并给出更精确证据 |
| 高置信风险 | 当前结构显示风险存在，但需要测试或运行验证定性 | 降级为风险，不写成漏洞或事故 |
| 需验证假设 | 有迹象但证据不足或样本偏窄 | 标注“需验证”，不进入 P0 |
| 已修正误判 | 被代码或测试证伪 | 删除或改写 |

**关键勘误**：

- `require_role` 是通用 `allowed_roles` 检查，不是 admin-only；admin-only 是 `get_current_admin_user` 与 `get_current_admin_user_for_app_routes`。
- 审计能力不是“仅 2 张表”。至少存在 `BusinessRuleConfigAuditLog`、`ConfigBundleAuditLog`、`SystemLog`、`SalesTrainerOperationLog` 及多个审计/日志入口。真正问题是统一审计视图和跨域操作留痕不完整。
- `common/api/practice.py` 的按 `session_id` 查询后存在 `_can_read_session` 校验，不能直接定性为 IDOR。更准确的风险是 lookup-before-auth 可能形成对象存在性差异与枚举面，需要用越权测试验证 403/404 语义。
- `supervisor` 与 `presentation_coach` 并非无测试。问题是测试深度、门禁纳入和 characterization 覆盖不足。
- 新人训练 e2e 覆盖新人主路径，但不能声称覆盖“主管要求复训 → 学员开始 → 完成 → before/after 对比”的完整浏览器闭环。
- “18 篇 ADR 均 Accepted/高质量”不准确。仓库确有 18 个 ADR 文件，但至少 `2026-05-12-case-item-role-profile-pilot-contract.md` 与 `2026-05-27-config-asset-b2-hitl-governance.md` 仍是 Proposed，且部分 ADR 状态表达不统一。
- ADR 状态口径需单独治理：二次复核发现 5 个 ADR 缺显式 Status，2 个 Proposed，1 个 Accepted(记债)，其余为 Accepted 或等价状态；其中 `2026-06-20-controlled-cross-domain-adapters.md` 作为关键边界文档也缺显式 Status。

---

## 3. 修订后证据摘要

| 类型 | 修订后证据 | 代表文件 / 模块 | 判断 |
| --- | --- | --- | --- |
| 治理 | 18 个 ADR 文件；多数核心契约已 Accepted，但 Adapter/sidecar 等关键文档仍缺显式 Status | `docs/adr/` | 治理资产真实，状态纪律需补齐 |
| 边界 | 受控跨域 Adapter 有 ADR；仍有非 adapter 文件直接 import `curriculum_practice` | `docs/adr/2026-06-20-controlled-cross-domain-adapters.md`、`backend/src/sales_trainer/services/` | 设计成立，执行需扫描门禁 |
| 状态 | ADR 生命周期与代码枚举存在漂移 | `docs/adr/2026-05-11-architecture-boundary-domain-contract.md`、`SessionStatus` | 文档需回写 |
| 运行时 | Redis session snapshot 跨实例，WebSocket 连接表进程内 | `session_state_service.py`、`session_manager.py` | 多实例边界需要明确 |
| 可靠性 | Redis ping 失败会使 session state service 启动失败 | `session_state_service.py:start()`、`app_lifespan.py` | 启动期硬依赖成立 |
| 异步 | 音频处理、知识库处理、报告生成、归档调度存在进程内任务形态 | `sales_trainer/api.py`、`common/knowledge/`、`evaluation/services/`、`common/jobs/audio_archival.py` | 需要队列或持久任务表 |
| 可观测 | 多个核心 `track_*` 未接入关键调用点；frontend analytics 与 dual-read mismatch 是例外 | `common/monitoring/metrics.py` | “未接实”成立，“全死”不成立 |
| 权限 | `User.role`、admin 依赖、`AdminRolePermission`、域内权限矩阵口径不一致 | `common/auth/service.py`、`common/db/models.py`、`sales_trainer/permissions.py` | RBAC 漂移是高风险 |
| 审计 | 存在多张审计/日志表和入口，但缺统一全域操作审计 | `BusinessRuleConfigAuditLog`、`ConfigBundleAuditLog`、`SystemLog`、`SalesTrainerOperationLog` | “分散”成立，“几乎没有”不成立 |
| 测试 | 后端 389 个测试文件，前端 199 个测试文件 | `backend/tests/`、`web/src`、`web/tests` | 资产可观；前端统计排除 `node_modules` |
| CI | critical gate 白名单偏窄：前端 29，后端主白名单 38，另有少量 smoke/newcomer | `scripts/critical-quality-gate.sh` | 门禁覆盖不足成立 |
| 前端 | sales-trainer 后台导航、权限 fail-closed、配置预览、操作日志 UX 较成熟 | `web/src/app/admin/sales-trainer/`、`web/src/lib/sales-trainer/` | 原稿低估了该子域 |
| 前端缺口 | 默认落点与 capability 可能不匹配；部分页面仍手写 capability 检查；操作日志检索不足 | `admin-shell.tsx`、`use-admin-route-access.ts`、`operation-logs/page.tsx` | 体验债更具体 |
| 工作区 | 原稿记录约 786 个未提交变更，二次复核时仍为大规模脏工作区 | `git status --short` | 卫生风险成立，精确数字不固定 |

---

## 4. 九维度评分（修订）

评分范围 1 到 5 分。

| 维度 | 评分 | 修订后判断 | 关键建议 |
| --- | ---: | --- | --- |
| 有用 | 4 | 新人训练、课程训练、PPT 演练、销售对练、主管复训等场景真实存在；新人主路径 e2e 可观，但主管复训完整闭环不能直接宣称已覆盖 | 补“主管要求复训 → 学员完成 → 对比复盘”端到端验收 |
| 易用 | 3 | sales-trainer 后台体验强于原稿判断；学员端仍有 `TrainingJourney`、`terminal`、`failure_code` 等技术词泄露风险 | 学员端文案做 presenter 层收敛 |
| 可维护 | 3 | ADR、契约测试、状态机冻结是优势；巨型模型文件、巨型 API types/client、StepFun mixin 单体仍增加维护成本 | 先拆低风险前端类型与 client，再做高风险运行时组件化 |
| 可扩展 | 3 | ConfigBundle、plugin、Adapter 有扩展基础；进程内异步、多实例连接状态、无租户概念限制横向扩展 | 明确多实例运行契约，引入持久任务机制 |
| 架构合理 | 3 | 边界设计合理，执行存在绕行；Presentation 复用位于 `sales_bot.websocket` 包内的 shared runtime components，有测试但仍有包归属/共享边界耦合 | 补全跨域 import 扫描门禁 |
| 抽象合理 | 3 | 状态机、ConfigBundle、Adapter 是有效抽象；StepFun mixin 通过共享 `self` 抽象不足 | 运行时拆成显式依赖对象，先补 characterization tests |
| 可靠 | 2 | 降级链和快照机制存在；Redis 启动硬依赖、send_json 失败语义、进程内任务、无死信仍是核心风险 | P0/P1 优先处理 |
| 安全 | 3 | JWT、上传校验、脱敏、API key 加密等基础不错；RBAC 口径漂移、对象级权限语义与审计聚合不足 | 统一角色矩阵和对象级权限测试 |
| 可观测 | 2 | structlog/trace_id 与 `/metrics` 面存在；核心业务指标接线、告警、SLO 不足 | 接入关键指标并建立最小告警 |

---

## 5. 后台与前端体验专项修订

原稿对后台体验的判断偏粗，需要区分 `sales-trainer` 子域和其它 admin 子域。

| 能力 | 修订后判断 | 证据与说明 |
| --- | --- | --- |
| 入口按任务组织 | `sales-trainer` 已成立，其它 admin 子域需另审 | `admin-sidebar.tsx` 有业务域分组；`module-nav.tsx` 与 `routes.ts` 提供新人训练子域内任务导航 |
| 权限可见性 | `sales-trainer` 较成熟 | capability 先行、fail-closed、导航按 capability 过滤，有测试覆盖 |
| 配置预览 | 原稿证据错位，应改用 `sales-trainer` 自身证据 | 路径发布预览、小测组卷预览、历史重评预览等更能说明问题 |
| 回滚与恢复 | 版本回滚/历史重评已落地，删除恢复/统一回收站仍弱 | 不能笼统写“危险操作可恢复弱”，应拆成版本治理与删除恢复两类 |
| 操作日志 UX | 比原稿判断更好 | `operation-log-display.ts` 做动作、目标、字段、人角色翻译，页面支持摘要和原始 JSON 展开 |
| 操作日志检索 | 仍不足 | 固定 `limit: 100`，缺时间、动作、目标对象、操作者筛选，缺分页/导出/trace 下钻 |
| 默认落点 | 存在 capability 不匹配风险 | `AdminShell` 将部分角色导向 `/admin/sales-trainer/units`，但部分合法角色可能只有查看记录能力 |
| 权限判断复用 | 有集中规则，但页面使用不完全 | `use-admin-route-access.ts` 存在，但不少页面仍手写 `getCapabilities + path check` |
| 学员端文案 | 存在技术词泄露 | `primary_cta`、`retry_action`、`failure_code` 一类原始值不应直接暴露给学员 |
| 测试缺口 | 不是“前端无测试”，而是局部缺页测 | `score-prompts` 等页面、部分报告页仍需补同名测试 |

**修订结论**：`sales-trainer` 的配置治理、发布、版本、日志展示和 fail-closed 已具备运营基础，但还不能按全后台可运营标准验收。更真实的问题是跨子域一致性、权限默认落点、日志检索深度、删除恢复和学员端文案 presenter 层。

---

## 6. 架构边界与运行时风险修订

### 6.1 边界设计成立，但缺执行门禁

`docs/adr/2026-05-11-architecture-boundary-domain-contract.md` 与 `docs/adr/2026-06-20-controlled-cross-domain-adapters.md` 确实提供了边界设计。当前受控 Adapter 的测试主要锁导出面，尚不足以禁止全仓违规 import。因此“7 个 sales_trainer 文件绕 Adapter”应表述为：存在非 adapter 文件直接 import `curriculum_practice` 的现象，需要全仓扫描测试纳入 CI，而不是只检查 Adapter `__all__`。

### 6.2 Presentation 复用 sales_bot 包内共享运行时，不是直接继承 Sales handler

原稿说 `presentation_coach` 继承 `sales_bot` handler “无测试”不成立。实际 `PresentationStepFunRealtimeHandler` 继承 `StepFunRealtimeSharedHandler`，且测试明确断言它不继承 sales stage mixin；当前也存在 `backend/tests/unit/test_presentation_stepfun_realtime_handler.py` 与 `backend/tests/unit/test_main_presentation_ws_runtime.py`。问题不是“无测试”或“直接继承 Sales handler”，而是共享运行时组件仍位于 `sales_bot.websocket` 包内，包归属与共享边界容易继续耦合，后续应评估下沉共享运行时组件或改组合式依赖。

### 6.3 Redis 与 WebSocket 的状态权威需要写清

`SessionStateService.describe_authority()` 已明确：

- `session_snapshot` 属于 Redis，跨实例共享，可耐重启。
- `runtime_connections` 属于 `session_manager.sessions`，是进程内状态，不跨实例，不耐重启。

风险不是“没有状态管理”，而是多实例运行时必须承认两个权威边界：连接态只能本进程处理，快照态可跨实例恢复。负载均衡、重连、实例滚动发布都需要围绕这个事实设计。

### 6.4 Redis 是启动期硬依赖

`session_state_service.py:start()` 会创建 Redis client 并执行 `ping()`；失败后抛 `RuntimeError`。`app_lifespan.py` 在启动期调用 `init_session_state_service()`，没有降级捕获。因此“Redis 不可用会阻断启动”成立。是否应该降级为可选，需要先定义 realtime 能力开关与健康检查语义，不能直接吞异常。

### 6.5 Roleplay record-only 改造仍有残留风险

ADR `2026-07-03-roleplay-realtime-record-only.md` 要求退役 `cancel_current_turn`、`regenerate_current_turn`、`repair_audio` 等主动修复动作。代码中仍能看到 roleplay 相关 suppressed/cancel/regenerate/repair 语义字段或发送路径残留。当前主链路可能已通过 observe-only 覆盖，但底层 checker 如果仍能返回 cancel/regenerate，就存在被旁路调用的风险。

---

## 7. 后端、安全、审计与 AI 治理修订

### 7.1 RBAC 问题是口径漂移，不是单点函数错误

`require_role(allowed_roles)` 本身是通用角色列表检查。真正的问题是多套角色体系并存：

- `User.role` / CheckConstraint 中的角色词表较丰富。
- `get_current_admin_user` 与 `get_current_admin_user_for_app_routes` 只放行 `admin`。
- `AdminRolePermission` 有自己的角色范围。
- `sales_trainer.permissions` 和 `prompt_templates.permissions` 又各自维护能力矩阵。

这会导致“数据库允许的角色”“路由依赖理解的角色”“后台 capability 理解的角色”“页面导航理解的角色”不完全一致。风险等级高于单个函数判断错误，因为它会制造合法用户被拒、非法用户漏放、审计解释不一致三类问题。

### 7.2 对象级权限风险需测试定性

`common/api/practice.py` 多处按 `session_id` 加载对象后再检查 `_can_read_session`。这不是直接 IDOR，但属于 lookup-before-auth 风险形态。建议补测试验证：

- B 用户访问 A 用户 session report、knowledge-check、enhanced-report 中的 `ConversationMessage` 投影、audio upload urls、audio segments 等接口时返回 403 还是 404。
- 不存在 session 与存在但无权 session 的响应差异是否会泄露对象存在性。
- admin、普通用户、停用用户的语义是否一致。

只有越权测试失败后，才能定性为 IDOR 漏洞。

### 7.3 审计能力分散，统一视图不足

至少存在如下审计或日志能力：

- `BusinessRuleConfigAuditLog`
- `ConfigBundleAuditLog`
- `SystemLog`
- `SalesTrainerOperationLog`
- `/admin/audit-trail`
- `/admin/system-logs`
- `/admin/sales-trainer/operation-logs`（完整 API 路径为 `/api/v1/admin/sales-trainer/operation-logs`）

因此原稿“审计表仅 2 张”错误。更准确的问题是：统一审计 API 没有纳入所有域内日志，`SalesTrainerOperationLog` 与全局审计/系统日志之间缺少统一查询、trace 串联、对象级下钻和数据范围过滤。

另一个具体风险是：`SalesTrainerOperationLog` 的团队范围过滤如果按操作者部门而不是目标对象或学员部门，主管审计可能出现盲区。这需要读服务和测试进一步确认。

### 7.4 AI 治理仍有短板

AI 能力不是完全失控，但治理不完整：

- prompt 与模型配置有管理面，但历史修订并不总是一等 revision 表。
- `LLMService` 的 fallback/cost/quality events 若只保留在进程内，则复盘和成本审计不足。
- AI 评分 JSON 解析失败给默认分的路径需要重点审查，避免把模型失败伪装成业务正常。
- AI 配置刷新失败如果只记录日志并继续使用旧缓存，需要在管理面显示 stale 状态、更新时间、失败原因。

---

## 8. 测试与 CI 修订

### 8.1 测试资产真实存在

二次复核命令显示：

- `backend/tests` 下 Python 测试文件：389 个。
- `web/src` 与 `web/tests` 下前端测试文件：199 个，统计 `*.test.*` / `*.spec.*`，排除 `node_modules`。

因此不能把系统描述为“缺少测试”。问题是关键域的测试是否足够深、是否进入门禁、是否覆盖真实用户旅程。

### 8.2 CI 白名单偏窄

`scripts/critical-quality-gate.sh` 中：

- `VITEST_GATE_TARGETS` 为 29 项。
- `BACKEND_GATE_TARGETS` 为 38 项。
- `BACKEND_SMOKE_REGRESSION_TARGETS` 为 4 项。
- `BACKEND_NEWCOMER_COVERAGE_TARGETS` 为 4 项。

这说明 release gate 是有选择地跑关键集合，不是全量回归。该策略本身可以成立，但需要把高风险域逐步纳入，否则 ADR 和测试资产无法转化成发布质量。

### 8.3 必须修正的测试误判

- `supervisor` 并非只有 1 个测试引用。存在 `backend/tests/integration/test_supervisor_retraining_api.py`、`web/src/app/admin/supervisor-training/page.test.tsx` 等。但 `supervisor/service.py` 仍需要更细 characterization tests，且关键路径应进入 critical gate。
- `presentation_coach` StepFun 并非无测试。存在 `backend/tests/unit/test_presentation_stepfun_realtime_handler.py` 与 `backend/tests/unit/test_main_presentation_ws_runtime.py`。问题是架构耦合和门禁覆盖，不是零测试。
- `web/tests/e2e/newcomer-training-closed-loop.spec.ts` 覆盖新人路径、AI Coach、quiz、audio、admin records、实时对练等，但不能证明主管复训 before/after 完整闭环。
- 原稿建议的 `pytest tests/unit/test_metrics*` 不可靠，因为该路径/模式不一定存在。更合适的现有测试面包括 `backend/tests/integration/test_observability_surfaces.py`、`backend/tests/performance/test_nfr_metrics.py`、`backend/tests/unit/test_stepfun_runtime_metrics_helpers.py`。

### 8.4 文档缺可运行证据

原稿没有“命令、退出码、输出摘要、失败/跳过原因”的证据区块。本文也只声称执行了静态复核命令，不声称后端/前端测试新鲜通过。后续每个整改 PR 必须补：

- 执行命令。
- 退出码。
- 关键输出摘要。
- 未执行项与原因。
- 与变更相关的最小用户路径验证。

---

## 9. 修订后 P0 / P1 / P2 / P3 路线图

| 优先级 | 问题 | 修订后动作 | 验收标准 | 风险 |
| --- | --- | --- | --- | --- |
| P1 | 核心业务指标未接线 | 接入 WS 连接、TTS/ASR/LLM 调用、降级、practice session、error 指标；保留现有 frontend analytics 和 dual-read mismatch 指标；在缺少事故/SLO/发布阻断证据前不列 P0 | `/metrics` 有可触发样本，新增告警规则，测试覆盖指标 helper | 低到中 |
| P0 | `send_json` 失败语义不清 | 先做影响面清单和 characterization tests，再让关键路径能识别发送失败 | 注入发送失败时 AI 回复/评分消息不静默丢失 | 中，高调用面 |
| P0 | Redis 启动期硬依赖未产品化 | 明确 Redis 不可用时系统应 fail-fast 还是降级关闭 realtime；补健康检查和管理面提示 | Redis 不可用行为可预测、可观测、可回滚 | 中 |
| P0 | 工作区长期大规模未提交 | 按主题拆分提交或归档，先建立可审计快照 | `git status` 可解释，提交与任务/ADR 对齐 | 低 |
| P1 | 进程内异步任务缺持久性 | 评估 RQ/Arq/持久任务表；先覆盖音频处理、知识库处理、报告生成、归档调度 | 任务可重试、可补偿、可查失败原因 | 高 |
| P1 | RBAC 多口径漂移 | 建统一角色/能力矩阵，路由、后台 capability、页面导航统一消费；对象级 `_can_read_session` 也纳入统一权限审查 | 角色矩阵测试覆盖 `user/admin/super_admin/support/training_lead/training_manager/content_admin/newcomer_content_admin/operations/ops/operator/sre/readonly_auditor` | 中 |
| P1 | 对象级权限语义待定 | 补 practice session 越权测试，确认 403/404 策略后再修查询层 | 无权访问不会泄露敏感对象或数据 | 中 |
| P1 | Adapter 禁令无全仓门禁 | 加跨域 import 扫描测试，允许列表只保留受控 Adapter 和 composition root | 违规 import 在 CI 失败 | 低 |
| P1 | 关键测试未进 gate | 把 supervisor、presentation StepFun、observability、roleplay record-only 纳入 critical gate | 关键路径测试出现在 `critical-quality-gate.sh` | 中 |
| P2 | 巨型前端 API 类型与 client | 按域拆 `web/src/lib/api/types.ts`、`client.ts` | 单文件规模下降，前端类型检查和测试通过 | 低 |
| P2 | `common/db/models.py` god file | 分域迁移模型文件，先不改表结构 | import 兼容，迁移无变化 | 高 |
| P2 | StepFun mixin 共享 `self` 过深 | 先补行为测试，再拆显式依赖对象 | mixin 可独立测试，关键 WS 测试通过 | 高 |
| P2 | 文档漂移 | 回写 CLAUDE、ADR 状态、API contract、端口和开发命令 | 文档命令可执行或标注不可执行 | 低 |
| P3 | 删除恢复与统一回收站 | 区分版本回滚、软删除、归档、恢复 | 关键运营对象可恢复并有审计 | 中 |
| P3 | 多租户/组织隔离 | 在明确商业需求前只记录 ADR，不贸然改模型 | 有租户路线图和数据迁移方案 | 高 |

---

## 10. 前 5 个 AI Task Brief（修订版）

### Task Brief #1：接通核心业务 Prometheus 指标

- **Task ID**：OBS-01
- **Mission**：把已定义但未接入关键链路的核心指标接到真实调用点。
- **Context**：`track_practice_session`、`track_llm_request`、`track_asr_request`、`track_tts_request`、`track_websocket_connection`、`track_websocket_message`、`track_error` 等需要审查调用点。`track_frontend_analytics_event` 与 `track_situation_pack_dual_read_mismatch` 已有调用点，不得当作死代码删除。
- **Files / Modules to Inspect**：`backend/src/common/monitoring/metrics.py`、`backend/src/common/websocket/base_handler.py`、`backend/src/common/audio/`、StepFun runtime、practice session lifecycle。
- **Allowed Changes**：只加观测调用和测试，不改变业务状态流转。
- **Forbidden Changes**：不重命名指标，不删除已有指标，不引入新监控依赖。
- **Acceptance Criteria**：关键指标可在测试或本地 `/metrics` 中触发；告警规则至少覆盖 health、WS 连接异常、ASR/TTS/LLM 失败率或降级计数。
- **Tests to Run**：优先运行 `backend/tests/integration/test_observability_surfaces.py`、`backend/tests/performance/test_nfr_metrics.py`、相关 metrics helper 单测；再按改动路径跑对应 WS/audio 测试。

### Task Brief #2：定义并修复 WebSocket 发送失败语义

- **Task ID**：REL-01
- **Mission**：避免 `send_json` 失败被静默吞掉后业务状态继续推进。
- **Context**：WebSocket 发送失败可能影响 AI 回复、评分、状态通知。不能直接批量改所有调用点，应先做调用点分级。
- **Files / Modules to Inspect**：`backend/src/common/websocket/base_handler.py`、StepFun handler、presentation handler、测试中的 websocket fake。
- **Allowed Changes**：先补 characterization tests；关键路径返回结构化 Result 或显式失败状态。
- **Forbidden Changes**：不无差别抛异常导致连接层行为突变。
- **Acceptance Criteria**：注入发送失败时关键路径有日志、指标、状态或重试/降级语义；现有 WS 测试通过。
- **Tests to Run**：`python -m pytest -c pyproject.toml backend/tests/unit/test_websocket_handler.py backend/tests/unit/test_stepfun_realtime_handler.py backend/tests/unit/test_presentation_stepfun_realtime_handler.py backend/tests/unit/test_main_presentation_ws_runtime.py --no-cov -q`，并按改动调用点追加对应 WS contract tests。

### Task Brief #3：统一 RBAC 角色与 capability 口径

- **Task ID**：SEC-01
- **Mission**：消除 `User.role`、admin dependency、`AdminRolePermission`、sales-trainer capability、prompt permissions 的口径漂移。
- **Context**：当前问题不是 `require_role` 写错，而是多套角色解释并存。
- **Files / Modules to Inspect**：`backend/src/common/auth/service.py`、`backend/src/common/db/models.py`、`backend/src/admin/api/permissions.py`、`backend/src/sales_trainer/permissions.py`、`backend/src/prompt_templates/permissions.py`、`backend/src/common/api/practice.py`、`backend/src/common/analytics/report_trends.py`、`web/src/lib/auth/current-user.ts`、`web/src/lib/sales-trainer/routes.ts`。
- **Allowed Changes**：先输出角色矩阵和测试，再做最小统一读取层。
- **Forbidden Changes**：不直接扩大 admin 权限，不只靠前端隐藏按钮。
- **Acceptance Criteria**：完整代码角色词表 `user/admin/super_admin/support/training_lead/training_manager/content_admin/newcomer_content_admin/operations/ops/operator/sre/readonly_auditor` 的可见、可改、可发布、可审计能力有后端测试和前端导航测试；若使用业务分组名，必须映射到真实代码角色。
- **Tests to Run**：`python -m pytest -c pyproject.toml backend/tests/integration/test_rbac_access_control_api.py backend/tests/integration/test_newcomer_training_path_rbac_api.py backend/tests/integration/test_prompt_templates_api_rbac.py backend/tests/unit/test_newcomer_training_path_permissions.py --no-cov -q`；前端运行 `npx vitest run web/src/lib/sales-trainer/routes.test.ts web/src/components/admin/sales-trainer/module-nav.test.tsx`。

### Task Brief #4：补 practice session 对象级权限测试

- **Task ID**：SEC-02
- **Mission**：验证并收敛按 `session_id` 查询后的对象级权限语义。
- **Context**：当前不能直接定性 IDOR，但 lookup-before-auth 风险需要测试锁住。
- **Files / Modules to Inspect**：`backend/src/common/api/practice.py`、`backend/src/common/analytics/report_trends.py`、相关 integration tests。
- **Allowed Changes**：先补 A 用户/B 用户越权访问测试，再根据失败结果修复。
- **Forbidden Changes**：不在未验证前大改查询层，不改变 admin 可读语义。
- **Acceptance Criteria**：无权用户访问他人 session report、knowledge-check、enhanced-report 中 `ConversationMessage` 投影、audio upload urls、audio segments 等接口时不泄露数据；不存在对象与无权对象的错误语义符合安全策略。
- **Tests to Run**：新增对象级越权 integration tests；运行 `python -m pytest -c pyproject.toml backend/tests/contract/test_sessions.py backend/tests/contract/test_sales_sessions.py backend/tests/integration/test_session_lifecycle_api.py backend/tests/unit/common/analytics/test_report_trends.py --no-cov -q`。

### Task Brief #5：把关键测试纳入 critical gate

- **Task ID**：TST-01
- **Mission**：让 supervisor、presentation StepFun、observability、roleplay record-only 等关键域进入发布门禁。
- **Context**：测试资产足够，但门禁白名单偏窄。
- **Files / Modules to Inspect**：`scripts/critical-quality-gate.sh`、`backend/tests/integration/test_supervisor_retraining_api.py`、`backend/tests/unit/test_presentation_stepfun_realtime_handler.py`、`backend/tests/unit/test_main_presentation_ws_runtime.py`、observability tests、roleplay record-only tests。
- **Allowed Changes**：逐步纳入门禁，必要时先拆慢测或标记 smoke subset。
- **Forbidden Changes**：不把慢测简单跳过，不用空断言制造覆盖。
- **Acceptance Criteria**：critical gate 能覆盖上述关键域，运行时间可接受，失败输出可定位。
- **Tests to Run**：先运行 `python -m pytest -c pyproject.toml backend/tests/integration/test_supervisor_retraining_api.py backend/tests/unit/test_presentation_stepfun_realtime_handler.py backend/tests/unit/test_main_presentation_ws_runtime.py backend/tests/integration/test_observability_surfaces.py backend/tests/unit/test_roleplay_observability_contract.py backend/tests/unit/test_sales_trainer_roleplay_observation_service.py --no-cov -q`；纳入门禁后运行 `bash scripts/critical-quality-gate.sh`。

---

## 11. 结论

这个系统值得继续投入，且不建议推倒重来。真正的工作不是“补几个功能”，而是把已有治理资产接到运行时和发布门禁上。

原稿最有价值的判断是：架构骨架存在，执行债也真实存在。原稿最大的问题是：若干结论把风险写成事实，把局部缺口写成全局空白。修订后的优先级应从“全盘重构”收敛到四件事：

1. 可观测性接实，避免指标和告警停留在定义层。
2. 运行时可靠性接实，特别是 Redis、WebSocket 发送失败和进程内异步任务。
3. 权限与审计接实，统一 RBAC 口径和跨域操作留痕。
4. CI 与文档接实，让 ADR、测试资产、发布门禁和工作区快照相互对得上。

骨架仍在，债可还；但下一轮整改必须以可运行证据和门禁覆盖收尾，不能只停留在文档判断。

---

## 附录 A：本轮多 Agent 复核摘要

| Agent 方向 | 主要贡献 | 对本文的影响 |
| --- | --- | --- |
| 架构边界 | 校正 ADR 状态、Adapter 门禁、Redis/进程内状态边界、Roleplay record-only 残留 | 降级过度断言，新增运行时边界风险 |
| 后端/安全 | 纠正 `require_role`、审计表、IDOR 定性；指出 RBAC 多口径、统一审计缺口、AI 治理短板 | 重写安全与审计章节 |
| 前端/体验 | 证明 `sales-trainer` 后台导航、权限 fail-closed、配置治理、操作日志 UX 强于原稿判断；指出默认落点与日志检索缺口 | 重写后台体验章节 |
| 测试/CI | 校正测试文件数、CI 白名单、supervisor/presentation 测试误判、新人 e2e 覆盖范围和 metrics 测试命令 | 重写测试与 CI 章节 |

## 附录 B：第二轮重复审查与吸收记录

第二轮复核由 2 个只读 Agent 对本文修订稿做重复审查：

| Agent | 结论 | 已吸收修改 |
| --- | --- | --- |
| Critic `019f272a-47a0-71e0-aa37-a80d489afb17` | 未发现 P0 级事实错误；指出 ADR 状态、Presentation 继承表述、RBAC 角色词表、Prometheus P0 定级、IDOR route 精度、前端运营表述、测试统计口径仍需修正 | 已补 ADR 状态口径；删除“直接继承 Sales handler”措辞；RBAC 改为完整代码角色词表；指标接线降为 P1；对象级权限任务改写具体接口；前端结论降级为“具备运营基础”；补前端测试统计口径 |
| Reviewer `019f272a-4932-7161-9912-bea11e2507db` | 初评不建议通过；指出多 Agent/重复审查证据链不足、原稿来源缺失、操作日志路由错误、RBAC 角色名错误、Task Brief 缺验证命令 | 已在文首补原稿来源和第二轮复核说明；修正 `/admin/sales-trainer/operation-logs` 路径；RBAC 角色名改为真实枚举；Task Brief #2-#5 补 `Tests to Run` |

## 附录 C：原稿中已删除或降级的重点表述

- 删除：“18 篇 ADR 均高质量/Accepted”。
- 删除：“17 个 Prometheus 指标零调用点/全死代码”。
- 删除：“`require_role` 实际只判 `admin`”。
- 删除：“审计表仅 2 张”。
- 删除：“presentation_coach 继承 sales_bot 无测试”。
- 删除：“supervisor 域几乎无测试/仅 1 个测试引用”。
- 删除：“新人训练 e2e 覆盖主管复训完整闭环”。
- 降级：“practice 按 session_id 查询存在 IDOR”改为“对象级权限和对象存在性语义需越权测试验证”。
- 降级：“危险操作可恢复弱”改为“版本回滚/历史重评已落地，删除恢复/统一回收站弱”。
- 降级：“后台入口无法确认”改为“sales-trainer 已有任务式导航，其它 admin 子域需另审”。
