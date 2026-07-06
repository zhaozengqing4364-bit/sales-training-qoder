# 新人训练完整闭环优化审计总账

> 日期：2026-06-27
>
> 来源：10 个并行 Agent 只读审计 + 主线程项目文档抽样。
>
> 范围：新人训练路径、销售训练后台、权限、配置、内容资产、前后端契约、UI/UX、可视化、测试、安全、审计、发布回滚。

## 用户已确认的产品决策

- 不同等级必须同时覆盖三类：角色等级、学员等级、训练阶段等级。
- 新人训练路径不强制顺序解锁，但必须清楚展示当前阶段、可见内容、未开放原因和下一步。
- 实时对练纳入新人训练完整闭环，不再长期只作为 disabled/coming-soon 占位；接入前必须补契约、权限、配置、回滚和运行时边界。
- 废弃 learner 首页 catalog fallback，active path revision 成为学员路径唯一真源；旧 fallback 只允许只读迁移和诊断。
- AI Coach 是首版完整闭环必过能力，不是可关闭的补练小功能；仍需可配置、可降级、可追踪。

## 当前系统已有基础

- 已有新人训练路径异步闭环骨架：路径配置、材料、文章、考卷、录音上传、转写、AI 评分、AI Coach、训练记录、后台工作台、操作日志。
- 路径配置已具备 working revision、active revision、publish、rollback preview、审计事件等能力。
- 题卷和题目链路已有较好的 attempt snapshot/revision 保护。
- `sales_trainer.phase2.closed_loop_policy` 是当前最成熟的业务规则配置样板，具备默认值、校验、fallback、管理入口和测试。
- 前端 API client 有统一 trace、401 处理和 `ApiRequestError` 标准化。
- 后端主链路不是纯前端隐藏：录音、做题、训练记录等多数路径已有 owner/department 级校验。

## 2026-06-27 审计时总体缺口

本节为原始审计基线，不代表当前实现状态；当前闭环状态以 `../audit-closure-matrix.md` 和 `../final-verification-report.md` 为准。

系统还没达到“完整闭环、可拓展可配置、无死数据、前后端紧密准确、等级可见内容区分、可视化充分、UI/UX 合格”的最终标准。最核心问题不是某个页面缺功能，而是以下治理面尚未完全收口：

- 单一真源：新 path revision 体系与旧 `unit.config.path` fallback 并存。
- 权限：通用 admin 权限表与 `sales_trainer.permissions` 两套体系并行，角色与 capability 粒度不一致。
- 配置：部分配置字段保存但不生效，部分运行参数仍在 env 或页面常量里。
- 内容流通：部分历史快照不完整，材料归档后历史回放可能不可达。
- 前后端契约：部分 TS 类型允许构造后端拒绝的数据，admin 页面混用 learner 接口推断状态。
- UI/UX：学员首页更像任务目录，不像可观察、可分析、可解释等级和阶段的训练看板。
- 测试：底层测试较多，但缺强制新人训练完整 E2E 和销售训练核心 CI gate。

## P0 / P1 风险总账

### P0 条件风险

1. 生产环境无 active path revision 时继续走 `unit_backfill` 生成新训练数据。
   - 影响：新数据带 legacy lineage，后续发布、回滚、审计、报表解释失真。
   - 处理方向：生产 guard；learner 路径缺 active revision 时显式诊断，不展示伪成功。

2. 实时对练直接接入新人训练但未补契约、权限、状态、回滚。
   - 影响：突破当前 `sales_trainer` 与 `sales_bot/training_runtime` 边界。
   - 处理方向：先做 ADR 和 API 契约，再接入运行时。

### P1 权限与安全

1. 已发布材料文件疑似只校验 `published`，缺少用户可访问路径/单元/等级对象级授权。
2. `content_admin` 可能看到商务礼仪学员测验记录。
3. `support/training_lead/training_manager` 当前可能看到 operation logs 和 settings。
4. 学员文章进度接口可传任意已发布 `learning_content_id`，没有强制当前模块绑定。
5. `SALES_TRAINER_MANAGER_ROLES` 非法值缺少 allowlist/fail-closed 语义，误配可能扩大或误保留权限。
6. 历史重评服务层缺对象范围校验，当前依赖 admin/ops 角色门槛兜底。
7. JWT 有默认密钥兜底风险，生产漏配会导致认证安全风险。
8. 配置资产导出审计默认关闭。
9. 模型配置变更只有结构化日志，缺持久化审计。

### P1 配置与发布

1. 顶层 `NewcomerPathConfigPayload.enabled` 保存但疑似未被 active projection 消费，属于伪配置风险。
2. `path_key`、`module_key`、`order_index`、`completion_rule` 等 payload 校验弱于契约。
3. AI Coach prompt/scoring prompt 只校验 UUID 形状，缺真实存在、已发布、用途匹配前置校验。
4. 文案 fallback 缺 `fallback_applied/fallback_reason` 可观测字段。
5. AI Coach GET 配置接口在模块不存在或 payload 损坏时返回默认值，fail-open。
6. ASR、Deucate、上传限制、provider 超时等仍主要靠 env，不是统一运行时配置快照。
7. Publish 缺 impact preview，rollback 有 preview 但发布高风险变更前无法看到影响范围。

### P1 内容资产与历史回放

1. 音频 submission 冻结了 score scheme 的 prompt id/version，但评分时可能按 prompt id 读取当前行。
2. 历史材料版本发布新版本后旧版本可能归档；下载接口只允许 published，历史回放可能不可达。
3. `curriculum_practice` 部分 frozen refs 只冻结引用元数据，不冻结完整 payload；源资产归档后已发布模板可能不可启动。
4. `case_item/role_profile/examiner_agent` unpublish -> draft 修改 -> republish 后 active revision 可能还指向旧 payload。
5. 商务礼仪小测 attempt 只存 `path_revision_id/no`，缺 `path_key` 和 `legacy_snapshot_only`。

### P1 前端契约与 UI

1. capability 主要控制 sidebar，工作台卡片、模块内导航、按钮、直链页未完全 fail-closed。
2. admin 页面用 learner 接口推断绑定状态，且把 403/500/网络错误吞成“无绑定/不可用”。
3. `/admin/sales-trainer/*` 与 `/admin/newcomer-training/*` 双路由/双 API surface 并存，`management_entry` 仍有旧地址。
4. 后台录音详情把 `passed === null` 渲染成“否”，把未知/待评分误判为失败。
5. 成功路径 loading 卡死：单元发布/归档、录音重试后按钮可能不复位。
6. 学员录音结果页 `getUnit` 失败后硬兜底通过线 `70`，会把配置故障伪装成正常阈值。
7. 工作台 DTO 使用 `Record<string, unknown>`，后端字段漂移时前端静默显示 `--`。

### P1 可视化与运营分析

1. 新人首页缺“全量可访问内容 + 核心路径 + 等级/阶段 + 未开放原因 + 下一步”的统一看板。
2. 管理者分析入口分散，缺从总览 -> 部门/等级 -> 学员 -> 记录 -> 证据 -> 补救的连续下钻。
3. 缺新人训练专属完成漏斗、模块通过率、能力弱项热图、趋势图、部门/等级筛选。
4. 管理端列表过滤偏技术编号，缺姓名、部门、角色等级、学员等级、训练阶段、模块、状态、通过结果、是否补救。
5. 表格移动端风险高，多处缺卡片化或横向滚动策略。

### P1 测试与门禁

1. 缺强制新人训练完整 E2E：路径首页 -> 商务技巧文章 -> 考试 -> AI Coach -> 录音 -> 报告/管理看板。
2. 前端配置异常态缺强门禁 E2E：缺失、非法、disabled、fallback、权限不足、发布失败。
3. CI 未显式纳入所有销售训练核心测试。
4. 真实 provider 测试可跳过，缺 release/nightly 明确门禁策略。

## 目标能力模型

### 三类等级

1. 角色等级：
   - learner：只看本人、已发布、可访问等级内容。
   - content_admin/newcomer_content_admin：管理内容配置，不能看学员训练记录。
   - training_lead/training_manager/support：看部门范围训练记录和分析，不看全局日志/系统设置。
   - ops/operator/sre：看配置健康、操作日志、失败任务、重试/重评，不改内容。
   - admin/super_admin：全量管理。

2. 学员等级：
   - 需要可配置等级或分层规则，例如新人、进阶、资深、重点辅导等。
   - 内容可见性、模块启用、推荐训练、可视化筛选都必须可按学员等级区分。

3. 训练阶段等级：
   - 未开始、进行中、已完成、未通过需重练、未解锁、已停用、异常。
   - 不强制顺序解锁，但 UI 必须解释每个阶段的完成条件、当前状态、下一步和不可用原因。

### 完整闭环

```text
人员/角色/等级配置
  -> 内容资产和训练模块配置
  -> active path revision 发布
  -> 学员首页读取 active projection
  -> 文章学习 / 考试 / 录音 / AI Coach / 实时对练
  -> 状态机和结果快照
  -> 训练记录和可视化分析
  -> 管理者干预 / 补救 / 重评 / 重试
  -> 审计 / 回滚 / 配置健康 / 死数据诊断
```

## 分阶段优化路线

### Phase 0：决策与契约冻结

- 新增/更新 ADR：
  - active path revision 成为 learner 唯一真源，旧 fallback 退役策略。
  - 实时对练纳入新人训练闭环的边界与运行时接入方式。
  - 三类等级模型：角色等级、学员等级、训练阶段等级。
  - AI Coach 首版必过能力与治理边界。
- 更新 `docs/api-contract/sales-trainer.md`：
  - TrainingJourney / ModuleProgress / ModuleOutcome DTO。
  - RoleCapability / LearnerLevel / TrainingStage 统一语义。
  - realtime module 从 placeholder 到 runtime binding 的契约。
  - snapshot-first 历史展示契约。
  - dead data / dependency graph / config health API。

### Phase 1：安全权限与对象级授权优先修复

- 材料文件下载增加 path/module/unit/learner-level 对象级授权。
- 收紧 logs/settings：只允许 admin/super_admin/ops。
- 商务礼仪 quiz attempts 改用 view_records 权限并增加部门过滤。
- 学员 article-progress 不再接受任意 `learning_content_id`，只读 active module binding。
- `SALES_TRAINER_MANAGER_ROLES` 增加 allowlist 校验：缺失/空值使用默认；显式配置只保留合法角色；全非法配置 fail-closed 并记录诊断。
- 历史重评增加对象级 scope 校验，为未来部门负责人重评预留边界。
- 配置资产导出默认强制审计。
- 模型配置 CRUD/test/tts-preview 增加持久化审计。

### Phase 2：路径单一真源与配置治理

- learner 首页和训练入口只消费 active path revision projection。
- legacy `unit_backfill` 只读迁移，禁止生产新训练数据静默使用。
- path payload 校验补齐：
  - path_key 固定或明确 alias。
  - module_key canonical。
  - module_key/order_index 唯一。
  - module_type 与 completion_rule 匹配。
  - business_skills 必须有 learning_units。
  - realtime module 必须绑定 runtime 配置或明确 disabled。
- 顶层 path enabled 要么真实生效，要么移除并迁移为模块级状态。
- 文案/default fallback 返回 `fallback_applied/fallback_reason`。
- AI Coach 配置 GET fail-closed：坏配置返回 typed error，不静默默认。
- 新增 publish impact preview。
- 新增 config health / dependency graph 面板。
- ASR/Deucate/provider 形成 `RuntimeProviderConfigSnapshot`，统一 readiness、source、fallback、invalid reason。

### Phase 3：内容资产、快照和死数据治理

- 音频 submission/score result 增加 prompt_revision_id 或完整 prompt snapshot。
- 历史材料访问允许被 submission 引用的 archived version 只读下载，或基于 material_snapshot.storage_key 回放。
- 发布模板引用资产增加归档保护；必要时 frozen ref 升级为 frozen payload。
- 修复 `case_item/role_profile/examiner_agent` republish active revision 漂移。
- 老 paper attempt 分级回填 revision；不可回填则标记 `legacy_snapshot_only/regrade_unavailable`。
- situation pack legacy ref backfill，禁止无序 limit 1 重建历史版本。
- 新增 dead data dashboard：
  - orphan material。
  - 未绑定 paper/question。
  - active config 引用 archived/missing asset。
  - legacy_snapshot_only 记录。
  - published template 不可启动。

### Phase 4：完整 TrainingJourney 聚合

- 建立新人训练 journey aggregate，聚合：
  - path revision。
  - module progress。
  - audio submission。
  - paper attempt。
  - business etiquette quiz attempt。
  - AI Coach session。
  - realtime roleplay session。
  - remediation/regrade/retry history。
- 统一状态机：
  - not_started。
  - in_progress。
  - waiting_upload。
  - processing。
  - scored。
  - passed。
  - failed。
  - needs_remediation。
  - disabled。
  - archived。
  - error_terminal。
  - error_transient。
- 状态策略由后端返回机器可读字段，前端只渲染，不自行推断。

### Phase 5：AI Coach 必过闭环

- AI Coach 作为必过模块纳入 active path validation。
- prompt、model、temperature、timeout、retry、max tokens、成本阈值、降级策略集中治理。
- prompt/scoring prompt 必须已发布、用途匹配。
- AI 输出失败有可恢复状态和管理员诊断。
- AI Coach session 写入 journey、训练记录、可视化、审计。
- 前端 workbench copy/rules 从后端配置读取，至少契约化，避免页面常量漂移。

### Phase 6：实时对练纳入闭环

- 新增 ADR 和契约，明确 sales_trainer 与 training_runtime/sales_bot 的边界。
- path module 绑定 realtime runtime config，不直接创建无治理 PracticeSession。
- 增加 realtime 权限、配置健康、发布影响预览、回滚策略。
- 实时对练结果写入 TrainingJourney 和 manager dashboard。
- 区分 terminal/transient/voluntary failure，禁止用重连掩盖契约错误。

### Phase 7：前后端契约和 UI/UX 收口

- capability 做到 sidebar、workbench card、module nav、操作按钮、直链页五层一致。
- admin 绑定态读取统一基于 admin revision/path-config 真源，不用 learner 接口侧推。
- 修复吞错：404 才是无绑定，403/500/network 必须显示错误和 trace_id。
- 修复成功路径 loading 卡死和 `passed=null` 三态显示。
- 移除录音结果页 `70` 硬兜底，改为 snapshot-first 或配置错误状态。
- 新人首页升级为训练看板：
  - 全部可访问内容。
  - 核心路径。
  - 三类等级。
  - 阶段状态。
  - 未开放原因。
  - 下一步动作。
- 管理端新增或强化新人训练分析页：
  - 完成漏斗。
  - 模块通过率。
  - 能力弱项热图。
  - 风险学员队列。
  - 部门/等级对比。
  - 7/30/90 天趋势。
- 列表统一分页、筛选、空态、错误态、移动端卡片视图。

### Phase 8：测试、CI 与发布门禁

- 新增后端闭环集成测试：
  - active path 存在。
  - article -> paper -> record。
  - audio -> prompt snapshot -> score。
  - AI Coach -> journey。
  - realtime -> journey。
  - manager dashboard 可见同一 learner 闭环。
- 新增 Playwright E2E：
  - learner 完整新人训练路径。
  - 配置缺失/非法/disabled/fallback。
  - 多角色权限矩阵。
  - 移动端关键页面截图。
- 新增 contract tests：
  - error envelope。
  - capability projection。
  - TrainingJourney DTO。
  - ModuleProgress DTO。
  - path config validation。
- CI gate 增加销售训练核心测试集。
- release/nightly 增加真实 provider smoke，允许分类 skip 但 release 前必须有环境门禁或人工确认。

## 推荐拆分任务

1. P0/P1 权限与材料对象级授权修复。
2. active path revision 唯一真源与 fallback 退役。
3. path config schema validation 与 publish impact preview。
4. AI Coach 必过配置治理与 session 记录入 journey。
5. 音频 prompt snapshot 与历史材料只读回放。
6. TrainingJourney aggregate 与模块状态机。
7. 实时对练接入新人训练闭环 ADR + runtime binding。
8. 前端 capability fail-closed 与 admin 绑定态真源修复。
9. 新人训练首页看板与管理端 analytics。
10. 测试门禁和完整 E2E。

## 验收总标准

- 给定已发布 active path revision，学员可完成文章、考试、录音、AI Coach、实时对练至少一条完整训练闭环。
- 不强制顺序解锁，但每个模块必须显示可见性、阶段、完成条件、当前状态和下一步。
- 三类等级均可配置、可展示、可筛选、可审计。
- learner 首页不再展示 catalog fallback 伪成功。
- 所有可调整业务规则有默认值、校验、fallback、读取层、管理入口或明确不做后台管理的原因。
- 后端权限不是只靠前端隐藏，所有读写接口 fail-closed。
- 历史记录 snapshot-first，可回放、可解释、可重评或明确标记不可重评原因。
- dead data dashboard 能发现不可达、孤儿、悬空、legacy 数据。
- 管理者 3 次点击内能从风险学员进入证据并发起补救。
- 所有关键操作有 actor、action、target、before/after 或 metadata、trace_id。
- 核心路径有 unit/integration/contract/e2e 覆盖并进入 CI gate。
