# 新人训练完整闭环实现清单

> 更新时间：2026-07-02 11:20 CST
>
> 用途：用工程交付视角回答“本轮总共实现了什么”。验收矩阵见 `audit-closure-matrix.md`，长日志和命令证据见 `execution-plan.md`、`final-verification-report.md`、`external-verification-runbook.md`。

## 总体结论

- 已把新人训练从“多个入口各自拼页面/状态”的实现，收口为以 active path revision 和 TrainingJourney 为核心的闭环。
- 已修复 `audit-synthesis.md` 中可通过代码、测试和契约闭环的 P0/P1 问题；P2 与外部依赖项均有明确处理结果。
- 已把用户提供的 StepFun / DeepSeek 测试凭证写入 gitignore 的本地 `backend/.env` 做真实 provider 验证；受 Git 跟踪文件未写入明文密钥。
- AI Coach 真实 DeepSeek/OpenAI-compatible provider gate 已于 2026-06-29 09:08 CST 通过；StepFun Realtime 已于 2026-07-02 11:08 CST 使用 `stepaudio-2.5-realtime` 完成上游 WebSocket handshake，但 StepFun 会话内返回 `[STEPFUN_API_ERROR] invalid audio, check your audio format`，剩余为真实 provider 音频格式/提交策略适配问题。
- 最新 full gate `PLAYWRIGHT_SKIP_BROWSER_INSTALL=1 bash scripts/critical-quality-gate.sh` 已于 2026-07-01 11:52 CST 通过；本轮已把 StepFun prereq / transport / realtime handler / payload snapshot、audio result `storage_key` 脱敏、AI Coach learner-facing route gate、public material file route gate，以及 2026-07-01 `/units` TrainingJourney 列表过滤和轻量列表响应补强纳入 full gate 覆盖。

## 1. active path revision 成为 learner 唯一真源

- learner 首页、训练入口、unit list/detail/brief、文章、考试、录音、商务技巧页、结果页下一步建议均改为读取 active path projection 或 TrainingJourney；其中 learner `/sales-trainer/units` 列表已进一步收口为当前 learner TrainingJourney 中未 locked 的 target unit。
- 无 active revision 时返回空列表或 typed error，不再从全量 published catalog、`unit.config.path`、`unit_backfill` 伪造成功路径。
- 删除或退役 learner 运行链路中的旧 catalog fallback helper。
- `SalesTrainerPathService.list_paths_for_user()` 只读 `SalesTrainerPathConfigService.active_projection()`。
- 商务技巧学习页和考试页从 TrainingJourney module binding 读取 `learning_content_id` / `exam_paper_id` / `target_unit_ids`。
- learner unit brief 当前配置响应中的 `task_brief` 已从裸 `dict` / `Record<string, unknown>` 收口为 `SalesTrainerTaskBriefConfig` / `SalesTrainerTaskBrief`，录音上传页直接读取 typed fields，不再通过动态 key helper 吞掉 brief 字段漂移。
- 商务礼仪文章考试前置校验只读取 active path projection；旧 `SalesTrainerUnit.config.path` 不再能让 learner 端 article exam prerequisite 伪成功或伪失败。

## 2. 权限与对象级授权 fail-closed

- 材料文件下载和历史回放下沉到 service 级对象授权，必须经 `TrainingRecordService.get_record_for_viewer()` 复查 viewer 与部门 scope。
- 商务礼仪测验记录、training records、article progress、unit detail/brief、audio/quiz 提交均绑定 active path 和对象级权限。
- logs/settings 收紧到 admin/super_admin/ops 等治理角色，support/manager 不再误读。
- `SALES_TRAINER_MANAGER_ROLES` 做 allowlist 校验：缺失/空配置使用默认；显式非法值只保留合法项，全非法配置 fail-closed 为空集合并产生诊断。
- regrade preview/run 强制接收 `viewer/team_department`，即使未来 manager 获得重评能力，也无法跨部门重评。
- AI Coach submit turn 在 service 层复查 actor ownership，避免只依赖 route 层。
- 旧通用 `/api/v1/admin/training-records` 已对 `voice_policy_snapshot.external_binding.owner="sales_trainer"` 的 realtime session fail-closed：列表 SQL 层排除，详情和删除返回 404，防止绕过 `TrainingRecordService` 和新人训练对象级授权/审计语义。
- 配置资产导出和模型配置 CRUD/test/tts-preview 增加持久化审计。
- learner-facing active path gate 现在额外要求 actor 是 active learner/user；training_manager/admin 等非 learner 角色不能借 learner route 进入学习路径。
- learner unit brief 的材料版本响应使用 learner-safe DTO，不下发 `storage_key`、创建/发布人和内部时间戳；文件读取只能走后端对象级授权下载 API。
- `/sales-trainer/units`、`/sales-trainer/paths`、`/sales-trainer/journey` 和 public learner material file route 均前置 learner role gate；admin/ops/content_admin 下载材料文件必须走 admin file route。
- `/sales-trainer/units` 列表不再只看 active projection 的 `enabled=true`，而是按当前 learner Journey 过滤 `locked`、`learner_level_required` 不匹配、模块停用和配置错误单元；详情/brief 与列表的可见性一致。

## 3. 配置治理、发布预览和回滚

- path payload 校验补齐：module key、order、enabled、completion rule、business skills 绑定、AI Coach 必需配置、realtime provider binding 等。
- publish preview 可以在发布前暴露高风险变更、缺依赖和不可运行原因。
- rollback preview / rollback 保留当前 path revision 治理语义。
- AI Coach prompt / scoring prompt 从 UUID 形状校验升级到存在、发布、用途匹配校验。
- fallback 诊断进入 typed DTO，前后端可读取 `fallback_applied` / `fallback_reason`。
- 阶段 2 闭环策略在管理工作台 `policy` 和 settings `phase2_policy` 中已从裸 `dict` 收口为 `SalesTrainerPhase2PolicyResponse` / `SalesTrainerPhase2Policy`，固定 key、source、治理入口、权限和生效时机，避免配置治理字段漂移被管理端吞掉。
- realtime provider registry / readiness 进入业务规则和 release gate。
- StepFun 默认模型已按用户最新要求统一为公开 Realtime model `stepaudio-2.5-realtime`，覆盖 DB server default、runtime policy/profile、admin 表单、seed/export 资产、示例文档和预检 allowlist。

## 4. 内容资产可追溯、可回放、可诊断

- 音频 submission / score result 冻结评分 prompt snapshot/revision，避免历史评分被当前 prompt 行漂移影响。
- Prompt revision 支持列表、查看、回滚和历史证据。
- archived material 可通过训练记录只读回放，历史证据不因材料归档而不可达。
- active/working 引用增加归档保护，减少发布模板引用失效资产。
- 商务礼仪 attempt 投影补 `path_key`、revision 信息和 legacy 标记。
- dead data diagnostics 覆盖 orphan material、missing/archived refs、legacy snapshot、不可启动模板、音频 lineage 缺失、path revision 断链、Prompt revision 缺失/断链、历史材料回放缺 confirmed reference 和本地历史材料文件缺失等；非音频训练记录材料回放由后端 service fail-closed。
- 新增只读导出脚本 `backend/scripts/export_newcomer_dead_data_diagnostics.py`，支持 dry-run、limit、material scan limit、sample limit、脱敏输出和 JSON 证据。

## 5. TrainingJourney 与状态机闭环

- 新增/完善 TrainingJourney 聚合服务，统一 path revision、module progress、audio、paper/quiz、business etiquette、AI Coach、realtime、remediation/regrade/retry history。
- append-only regrade run 已作为 `record_type="regrade"` 纳入 audio/quiz 模块 `outcome_history`；原始 outcome 保留，最新重评 outcome 使用 `regrade_snapshot`，不会覆盖历史训练记录。
- 统一 module status / outcome DTO，区分 `completion_satisfied`、`passed`、processing、failed、needs remediation、disabled、error 等状态语义。
- 训练记录详情中的 AI Coach 和 realtime 回放摘要已从裸对象收口为类型化 DTO：AI Coach 暴露 session/path/prompt/mastery/score 状态，且 article/path/config/coach_state 子快照显式建模关键字段；realtime 暴露 external binding、runtime snapshot 和三项 runtime scores；历史原始 snapshot 仍作为只读 evidence 保留。
- 训练记录详情中的商务礼仪小测快照已从裸对象收口为类型化 DTO：显式暴露 attempt、training pack、path revision、training pack revision、能力快照、题目快照、答案、能力得分、弱项、推荐章节和结果状态；admin detail 页面新增一等“商务礼仪小测快照”卡片，弱项优先展示能力名称，raw JSON 只作为回放证据保留；legacy 空快照已补 HTTP/UI 回放测试。
- 训练记录详情与音频提交响应中的历史回放三快照已从裸 `dict` / `Record<string, unknown>` 收口为类型化 DTO：`material_snapshot`、`score_scheme_snapshot.prompt_snapshot`、`task_brief_snapshot` 均有后端 Pydantic、前端 API 类型和契约接口；内部保留 `extra allow` / index signature，兼容旧 JSON 额外字段和 legacy 回放；admin detail 页面改为读取 typed snapshot 字段，仍保留 raw `audio_submission` fallback。
- 训练记录详情中的 `audio_submission` / `quiz_attempt` 子对象已从后端裸 `dict[str, Any]` 收口为 `AudioSubmissionResponse` / `QuizAttemptResponse`，HTTP detail contract test 会对每类记录执行 `SalesTrainerTrainingRecordResponse.model_validate()`，避免前后端类型契约继续分叉。
- 训练记录详情 `operation_logs[]` 已从裸 `dict` 收口为类型化审计 DTO，并显式建模 `training_context`，用于回放 path revision、训练阶段、学员等级和角色等级；原始 operation log metadata 仍不被改写。
- 训练记录顶层 phase2 投影字段已从裸对象收口为类型化 DTO：`effective_score`、`latest_regrade`、`score_explanation`、`ability_profile`、`remediation` 均进入后端 response model、前端 API 类型和 API 契约，避免管理端看板/详情页继续吞掉字段漂移。
- 2026-06-29 05:47 继续收口 `AudioScorePrompt` / `learner_rubric` / `output_schema`：后端新增 `SalesTrainerAudioScoreOutputSchema`，`AudioScorePromptCreate/Update/Response`、`SalesTrainerScoreSchemeSnapshot`、`SalesTrainerScoreSchemePromptSnapshot` 不再使用裸 `dict`；服务层对 prompt create/update、revision payload、publish/rollback、audio submission 历史快照和 regrade revision 统一 normalize。新请求由 Pydantic 严格拒绝坏结构，历史快照读取保留兼容默认值，避免破坏旧记录回放。
- 前端 `SalesTrainerAudioScorePrompt`、create/update request、`SalesTrainerScoreSchemeSnapshot` 和 unit brief `score_scheme.learner_rubric` 已同步为 `SalesTrainerAudioScoreOutputSchema` / `SalesTrainerLearnerRubric`，删除 `learner_rubric | Record<string, unknown>` 伪兼容；`SalesTrainerScorePromptForm` 增加结构校验，JSON 合法但缺 `criteria[].key` 或 `output_schema.required` 未声明 properties 时不会提交。
- learner 首页只读 Journey 展示等级、阶段、模块状态、下一步行动和不可用原因。
- audio result、quiz result、business skills workbench、next-step panel 不再前端合成 fallback 行动，而是消费后端 `next_action`。
- 训练记录详情回放会用 active TrainingJourney 为顶层记录和 `operation_logs[]` 附加 `training_stage`、`learner_level`、`role_level` 和 path revision 上下文；原始 operation log `metadata` 不被静默改写。

## 6. AI Coach 首版必过闭环

- AI Coach 已进入 path validation：缺 AI Coach 或缺生成 prompt 的 business skills module 不能发布。
- AI Coach session、turn、prompt snapshot、model config、训练记录、Journey module、admin record detail、analytics 均纳入闭环。
- AI Coach learner-facing session 创建入口已前置 active TrainingJourney module gate 和 learner 角色底线，admin 等非 learner 不能借 `/newcomer-training/ai-coach/*` 创建学习会话。
- AI Coach GET/发布配置坏数据 fail-closed，不再静默返回默认值。
- learner 选择 `continue_drill` / `increase_difficulty` 后，真实 LLM 也必须生成 governed `quiz_card`，不能只输出 followup prompt 伪通过。
- 使用本地 DeepSeek 测试凭证执行真实 provider gate 已通过，runtime audit 显示 `model=deepseek-chat`、`source=model_config`、`fallback_used=false`。
- 2026-06-29 09:08 用同一 gitignored `backend/.env` 复跑 AI Coach real provider gate：1 passed，证据 `newcomer-ai-coach-real-provider-gate.json` 为 `status=passed`、`classification=executed`、`provider=openai`、`model=deepseek-chat`。

## 7. 实时对练纳入闭环

- 新增 ADR 和 API 契约，明确 realtime 从 placeholder 进入新人训练闭环的 runtime binding、权限、配置健康、回滚和状态边界。
- learner 从 Journey 发起 realtime start，绑定 active path、module、unit 和 provider readiness。
- realtime learner start 已在 service 层复用 active TrainingJourney module access gate，等级不匹配、模块 locked/error_terminal 或 active path 不允许时 404 fail-closed 且不创建 `PracticeSession`。
- realtime start 响应契约已从裸 `dict`/`Record<string, unknown>` 收紧为类型化 `runtime_registry`、`provider_readiness_snapshot` 和 `external_binding`；后端 `RealtimeRoleplayStartResponse` 使用 `extra="forbid"`，前端同步 `RealtimeRoleplayRuntimeRegistrySnapshot` / `RealtimeRoleplayExternalBindingSnapshot`，避免 registry 或 binding 字段漂移被静默吞掉。
- `POST /api/v1/sales-trainer/realtime-roleplay/start` 已补 HTTP contract test，覆盖 ready 200 时冻结 runtime registry / provider readiness / external binding，以及 registry disabled 时 typed 503 fail-closed。
- training record 详情中的 realtime runtime outcome 子快照已继续收口：`runtime_registry`、`provider_readiness_snapshot`、`failure_policy`、`voice_policy_snapshot`、`effectiveness_snapshot`、`runtime_state` 均有前后端类型化 DTO 和契约文档，历史额外字段仍通过 `extra` / index signature 兼容回放。
- `/ws/sales` local deterministic provider 已覆盖完整 E2E，结果回流 Journey、training record 和 admin detail。
- `StepFunTransport` 统一 endpoint 构造、model query、401 分类和 `session.update.modalities=["text","audio"]` payload。
- 移除旧 StepFun 直连旁路，避免绕过统一 transport。
- 新增 `scripts/check_stepfun_realtime_prereqs.py`，不联网、不泄密地预检 key、URL、model 和 Step Plan URL。
- 使用本地 StepFun 测试凭证复跑真实 provider gate：2026-06-29 07:45/07:46 开放平台 URL 与候选 Step Plan URL 均为 HTTP 401，已定位为外部 key/账号/model Realtime 授权问题。
- 2026-06-29 04:51 按用户明确提供的 StepFun/DeepSeek 测试 key 更新 gitignored `backend/.env`，`scripts/check_stepfun_realtime_prereqs.py --env-file backend/.env` 脱敏输出 `status=ready`、`model=step-audio-2.3`、endpoint 不含密钥；真实 key 未写入受 Git 跟踪文件。
- 2026-06-29 09:01 再次按用户要求更新 gitignored `backend/.env`，脱敏预检仍为 `status=ready`、`api_key_configured=true`、`model=step-audio-2.3`、endpoint 不含密钥；`.gitignore` 命中且文件权限为 `0600`。
- 2026-06-29 09:07 用当前 gitignored `backend/.env` 复跑 StepFun real provider gate：secret scan 456 files passed，本地 smoke/seed/active path/sales websocket 均执行到 StepFun，上游仍返回 HTTP 401 `[STEPFUN_UPSTREAM_REJECTED]`；证据 `newcomer-real-provider-gate.json` 为 `status=failed`、`classification=upstream_auth_rejected`、`provider=stepfun_realtime`、`model=step-audio-2.3`。
- 2026-07-02 按用户最新提供的 StepFun 测试 key 复跑：预检 ready 且不输出密钥；强制真实 provider gate 在 `PLAYWRIGHT_SKIP_BROWSER_INSTALL=1` 下执行到 StepFun 上游后返回 HTTP 404 `[STEPFUN_UPSTREAM_REJECTED]`，证据 `newcomer-real-provider-gate.json` 为 `status=failed`、`classification=upstream_rejected`、`provider=stepfun_realtime`、`model=step-audio-2.3`。同次补强预检脚本，阻断并脱敏 `STEPFUN_REALTIME_URL` 中的 userinfo 与敏感 query。
- 2026-07-02 11:08 按用户最新要求切到 `stepaudio-2.5-realtime` 后复跑：预检 `status=ready`、`warnings=[]`、`model_in_public_realtime_docs=true`；真实 provider gate 已完成上游 WebSocket handshake，随后 StepFun 会话内返回 `[STEPFUN_API_ERROR] invalid audio, check your audio format`，证据 `newcomer-real-provider-gate.json` 为 `status=failed`、`classification=upstream_api_error`、`http_status=null`、`provider=stepfun_realtime`、`model=stepaudio-2.5-realtime`。

## 8. 前端契约、fail-closed 与 UI 状态

- admin sidebar、workbench card、module nav、按钮、直链页和 route capability 五层收口，未授权不请求数据、不渲染指标、不展示伪入口。
- admin dashboard 200 malformed response 进入错误态，不再显示 `--` 或伪空态。
- 文章绑定、路径配置中心、records、analytics 等页面补 loading / error / empty / retry 状态。
- `passed === null` 不再渲染为失败。
- 录音通过线不再硬兜底 `70`；配置缺失时禁用提交或显示诊断。
- 删除商务技巧旧 AI Coach fallback helper，`/paths.ai_coach_availability` 在契约中降级为 legacy 兼容读面。
- learner 模块卡片也不再从旧 `/paths.levels[].ai_coach_availability` 派生 AI Coach 入口；AI Coach 入口只来自 TrainingJourney `next_action`。
- training-records 和 analytics 移动端补横向滚动 region、语义 region、筛选请求断言和基础 a11y 检查；当前持久证据以 E2E 日志和断言为准，不依赖临时截图 artifact。

## 9. 管理端可视化与分析

- 新增/完善 admin Journey analytics：完成漏斗、模块通过率、弱项热图、趋势、风险学员、部门/等级/阶段/模块筛选。
- 管理工作台 dashboard 响应已从裸对象收口为类型化 DTO：summary、module summaries、weak dimensions、risk learners、intervention suggestions 均有后端 response model、前端 API 类型和 API 契约；页面不再用动态 `Record` helper 读取风险学员/弱项/干预建议。
- analytics 后端 `limit` 从聚合后截断改为构建 Journey 前生效，避免大数据量下伪分页。
- `risk_reasons` 由后端必填生成，前端不再用 `risk_module_keys` 冒充原因。
- 风险学员队列卡片可直接下钻到训练记录筛选页，链接携带 `user_id` 和首个风险 `module_key`；缺模块键时只按 `user_id` 下钻。
- learner/content_admin 访问 analytics 返回 403，manager 跨部门 analytics 返回空结果。
- training-records 明细列表支持 user、unit、material version、module、training stage、learner level、role level、status 等筛选。
- training-records 的 module / learner level / role level 筛选从自由输入改为受治理选项：默认模块集合、Journey analytics 聚合、当前记录和 URL 选中值合并生成下拉；AI Coach 已作为一等模块筛选项进入记录页。
- 真实学员等级枚举/来源由 2026-07-02 代理决策收口为：首版继续以 `unassigned` 为唯一生产安全默认，真实枚举只能通过 `sales_trainer.learner_level.policy` 发布；当前实现只提供默认治理、DTO、筛选和诊断能力，不在前端硬编码真实枚举。

## 10. 测试、E2E 和 CI 门禁

- `scripts/critical-quality-gate.sh` 已纳入 secret hygiene、ruff、web typecheck、lint、Vitest、Playwright smoke、新人训练 closed-loop E2E、backend newcomer coverage、backend mypy、backend core、backend smoke regression。
- full gate 后端测试已显式包含 `tests/unit/test_stepfun_realtime_prereqs.py`、`tests/unit/test_stepfun_transport.py`、`tests/unit/test_stepfun_realtime_handler.py`、`tests/unit/test_stepfun_payload_snapshots.py`；脚本在后端 pytest 子进程清空 E2E provider 环境，避免 local E2E 配置让 StepFun 单测误走 skip 分支。
- 新增完整 newcomer Playwright E2E，覆盖 learner 首页、文章/考试、录音评分、AI Coach、realtime local provider、管理端看板、权限不足、配置异常、历史回放、移动端 records/analytics。
- 新增真实 provider gate 分类：
  - `newcomer-ai-coach-real-provider`：2026-06-29 09:08 已用 DeepSeek 测试凭证通过。
  - `newcomer-real-provider`：2026-07-02 11:08 已用写入 gitignored `backend/.env` 的 StepFun 测试凭证和 `stepaudio-2.5-realtime` 执行到上游并完成 handshake，当前会话内返回 invalid audio，不伪装通过。
- `scripts/secret-scan.sh` 已改为优先使用 `backend/.venv/bin/python`，避免系统 `python3` 或旧环境导致 quality gate 在 `dataclass(slots=True)` 处误失败。
- `.github/workflows/release-truth-gate.yml` 支持 release truth gate / workflow dispatch。
- 当前最新 full gate 结果：2026-07-01 11:52 CST `Critical quality gate passed`；secret scan 461 files passed，Web lint 0 errors / 85 warnings，Vitest 28 files / 258 tests passed，Playwright smoke 9 passed，Newcomer E2E 11 passed / 1 skipped，presentation Phase 4 E2E 2 passed，sales Phase 4 E2E 1 passed，backend newcomer coverage 42 passed，coverage 48.05%，backend newcomer mypy 8 source files no issues，backend full 501 passed / 7 warnings，backend smoke 58 passed / 1 warning。
- 09:20 安全补强聚焦结果：后端非 learner gate / learner brief `storage_key` 脱敏 / public material file route / AI Coach learner-facing route gate 4 passed，前端音频结果页 2 files / 13 tests passed，后端相关 ruff/mypy 和 `git diff --check` 通过；已由 2026-07-01 11:52 full gate 覆盖。
- 2026-07-01 `/units` 等级 locked 列表补强：CodeGraph 反审计后将列表改为 TrainingJourney 真源过滤，新增 `learner_level_required` 不匹配的 active unit 不出现在 learner list 的测试；列表响应轻量化为基础信息、learner-safe config 和空 `questions`，题目详情保留在详情/brief/quiz 专用入口；验证后端 20 passed，ruff、服务层 mypy、diff-check、secret scan 通过，并已由 2026-07-01 11:52 full gate 覆盖。

## 仍不能写成已完成的项

| 项 | 当前状态 | 为什么不能伪装完成 |
|---|---|---|
| StepFun Realtime 真实 provider | 本地 `backend/.env` 已按用户要求写入 StepFun/DeepSeek 测试 key，且被 `.gitignore` 忽略、权限 `0600`；2026-07-02 11:08 真实 provider gate 使用 `stepaudio-2.5-realtime` 完成上游 handshake 后，会话内返回 `[STEPFUN_API_ERROR] invalid audio, check your audio format` | 需要按 StepFun Realtime 要求适配真实测试音频格式、事件顺序或 commit 策略 |
| 学员等级真实枚举与来源 | DTO、筛选、默认 `unassigned`、诊断和展示已具备；代理已决策首版不跨域复用课程画像字段，不前端硬编码真实枚举 | 真实枚举若要进入生产，仍需通过 `sales_trainer.learner_level.policy` 发布并保留回滚 |
| 历史生产数据回填 apply | dry-run/export/no-mutation 已具备；代理已决策本分支不实现也不执行生产 `--apply` | 生产写入需审批、备份、影响条数确认和回滚策略；当前脚本无 `--apply` |
| git 历史疑似 secret/token | 当前工作树扫描通过，测试 key 只在 ignored `backend/.env`；代理已决策不在本分支清史/force-push | 历史泄漏风险需凭证 owner 轮换/吊销，并由仓库维护者决定是否清理 git history |

## 快速复验命令

```bash
bash scripts/critical-quality-gate.sh
python3 scripts/check_stepfun_realtime_prereqs.py --env-file backend/.env
set -a; . backend/.env; set +a; CRITICAL_GATE_MODE=newcomer-ai-coach-real-provider NEWCOMER_AI_COACH_REAL_PROVIDER_REQUIRED=1 bash scripts/critical-quality-gate.sh
set -a; . backend/.env; set +a; CRITICAL_GATE_MODE=newcomer-real-provider NEWCOMER_REAL_PROVIDER_REQUIRED=1 bash scripts/critical-quality-gate.sh
```

最后一条当前预期仍是 StepFun 上游失败；2026-07-02 最新结果为会话内 invalid audio。只有按 StepFun Realtime 要求修正测试音频格式/提交策略后，才应该变成 passed。
