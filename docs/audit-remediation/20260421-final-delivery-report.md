# 2026-04-21 审计修复与产品迭代最终交付报告

## 0. 报告范围

本报告汇总 2026-04-21 审计修复与产品迭代全链路交付状态，依据以下权威材料整理：

- 审计输入：`项目代码审计与产品迭代建议.md`
- 计划与测试规格：
  - `docs/plans/2026-04-21-audit-product-remediation-plan.md`
  - `docs/plans/2026-04-21-audit-product-remediation-test-spec.md`
- 执行与验证报告：
  - `docs/audit-remediation/20260421-tracker.md`
  - `docs/audit-remediation/20260421-final-integrated-release-gate.md`
  - `docs/audit-remediation/20260421-backend-tests-ruff-cleanup.md`
  - `docs/audit-remediation/20260421-lane-a-runtime-safety-report.md`
  - `docs/audit-remediation/20260421-lane-a-deferred-adr.md`
  - `docs/adr/2026-04-21-growth-deferred-slices.md`

本报告只做最终交付总结，不新增功能、不改业务逻辑。

## 1. 当前 Git 状态

| 项目 | 结果 |
| --- | --- |
| 代码基线 HEAD（报告生成前） | `08e61c0` (`Record final closeout verification passing`) |
| 当前分支状态（报告生成前） | `main...origin/main [ahead 155]` |
| 工作区状态（报告生成前） | clean |
| 报告文件 | `docs/audit-remediation/20260421-final-delivery-report.md` |
| 说明 | 本报告提交后 ahead 数会 +1，最终 HEAD 以报告提交为准 |

近期关键提交包括：

- `08e61c0` — 记录最终收口验证通过。
- `7de591f` — 对齐 presentation flow / report flow 当前契约。
- `5219739` — 清理 backend tests 历史 ruff lint debt。
- `ca48831` — 修复麦克风权限拒绝后立即重试。
- `428efe2` — 修复 final gate 当前阻塞项。
- `76611b1` 及此前多条 `omx(team)` 提交 — 集成各 worker lane 结果。

## 2. 最终验证命令清单

最终收口验证已在 `$ralph` 中重新执行，结果如下。

| # | 命令 | 结果 |
| --- | --- | --- |
| 1 | `git status --short --branch` | PASS，报告生成前为 clean：`## main...origin/main [ahead 155]` |
| 2 | `git diff --check` | PASS |
| 3 | `cd backend && ruff check src tests --quiet` | PASS |
| 4 | `cd backend && .venv-test/bin/python -m pytest tests/integration/test_presentation_flow.py tests/integration/test_presentation_report_flow.py -q --no-cov` | PASS：`6 passed, 2 warnings` |
| 5 | `cd backend && .venv-test/bin/python -m pytest tests/unit/common/test_auth_transport_matrix.py tests/unit/test_history_service_evidence_projection.py tests/unit/test_session_runtime_authority.py tests/unit/test_stepfun_realtime_persistence.py tests/contract/test_audio_audit_contract.py tests/contract/test_presentations.py tests/unit/test_capability_base.py tests/unit/test_presentation_handler_persistence.py tests/unit/test_websocket_handler.py tests/unit/test_knowledge_retrieval.py tests/unit/test_presentation_ai_policy_service.py -q --no-cov` | PASS：`154 passed, 1 warning` |
| 6 | `pnpm --dir web exec tsc --noEmit --pretty false` | PASS |
| 7 | `pnpm --dir web exec eslint 'src/app/(dashboard)/page.tsx' 'src/app/(dashboard)/training/page.tsx' 'src/app/(user)/practice/[sessionId]/page.tsx' 'src/app/(user)/practice/[sessionId]/report/page.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.tsx' 'src/app/admin/page.tsx' 'src/app/(auth)/login/page.tsx' 'src/app/(user)/practice/[sessionId]/use-recording-state-machine.ts' 'src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.ts' 'src/hooks/use-practice-websocket.ts' 'src/app/(user)/practice/[sessionId]/use-practice-recording-hotkeys.ts' --quiet` | PASS |
| 8 | `pnpm --dir web exec vitest run 'src/app/(dashboard)/page.test.tsx' 'src/app/(dashboard)/training/page.test.tsx' 'src/app/(user)/practice/[sessionId]/page.test.tsx' 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' 'src/app/admin/page.test.tsx' 'src/app/(auth)/login/page.test.tsx' 'src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts' 'src/app/(user)/practice/[sessionId]/use-practice-recording-hotkeys.test.ts' 'src/hooks/use-practice-websocket.test.ts' 'src/hooks/websocket/message-handlers.test.ts' 'src/hooks/websocket/transport.test.ts' --reporter=dot` | PASS：`12 files, 172 tests` |

结论：**用户指定的最终收口命令集全部通过。**

## 3. Q-01..Q-30 交付矩阵

| ID | 交付状态 | 交付说明 | 证据 / 后续 |
| --- | --- | --- | --- |
| Q-01 | 已完成（边界防回归） | common knowledge retrieval/search helper 已收敛到 `common.knowledge`，sales_bot 侧保留兼容 shim。 | `tests/unit/common/test_knowledge_import_boundaries.py`；全量 orchestration 迁移不再阻塞当前 gate。 |
| Q-02 | 已完成（characterization）/ 延期（完整拆分） | 增加 StepFun realtime payload snapshot tests，覆盖 response.create、KB-lock blocked、tool result、score feedback、resume、error fallback。 | 完整 4842 行 handler 分拆仍需单独 ADR/RALPLAN。 |
| Q-03 | 已完成 | `PresentationFeedbackService` 增加 TTL、max sessions、LRU/清理能力。 | `docs/audit-remediation/20260421-lane-a-runtime-safety-report.md`；targeted tests 已通过。 |
| Q-04 | 已完成 | legacy `SalesBotService` 增加会话 TTL、max active sessions、lazy LangChain 构建。 | `test_sales_bot_service_lifecycle` 相关验证；无 active session 泄漏路径。 |
| Q-05 | 已完成 | KnowledgeRetrieval fallback 使用并行单 KB 检索，保留 per-KB 错误隔离。 | `tests/unit/test_knowledge_retrieval.py`。 |
| Q-06 | 延期（协议专项） | TTS duration/source-level blockers 已修；完整 chunk 双协议与前端播放队列仍作为专项。 | 需单独 WebSocket audio contract/RALPLAN。 |
| Q-07 | 已完成 | StagedEvaluation 使用显式 bounds / message stage metadata 切片，不再 `stage_number * 2`。 | `tests/unit/evaluation/test_staged_evaluation_service.py`。 |
| Q-08 | 已完成 | CapabilityRunner 故障隔离扩展，OSError 使用 `[CAPABILITY_IO_ERROR]`，CancelledError 保持传播。 | `tests/unit/test_capability_base.py`。 |
| Q-09 | 已完成 | Base WebSocket queue 有界化并带 backpressure。 | `tests/unit/test_websocket_handler.py` 等。 |
| Q-10 | 已完成 | Sales handler mixed exception 中的 `CancelledError` 传播修正。 | Lane A targeted tests。 |
| Q-11 | 已完成 | response task 启动加锁，避免并发 LLM/TTS pipeline。 | Lane A runtime safety tests。 |
| Q-12 | 已完成 | Presentation websocket 不再跨 session fallback。 | `tests/unit/test_presentation_handler_persistence.py`。 |
| Q-13 | 已完成 | PCM duration 公式集中到 `common.audio.pcm_duration`，TTS path 使用 sample_rate/bytes/channels。 | Backend ruff + focused tests。 |
| Q-14 | 已完成（touched endpoints）/ 延期（全量迁移） | touched presentation AI admin endpoint 使用 shared response helper。 | 全 API family 迁移仍建议逐 endpoint family 单独推进。 |
| Q-15 | 已完成 | `PracticeRetryEntryAssembler` 提取到 `common.services.practice_helpers`，保留 re-export 兼容。 | Lane B focused tests。 |
| Q-16 | 已完成（scoped）/ 延期（全仓 strict） | touched helper/service 类型改善；未做全仓 mypy/pyright strict。 | 全仓类型治理需单独 lane。 |
| Q-17 | 已完成（scoped）/ 延期（全仓 sweep） | touched paths 的异常语义收敛；未做 179 处 broad-except 全量治理。 | 需单独 broad-except cleanup。 |
| Q-18 | 已完成（health/readiness）/ 延期（main.py 拆分） | `/health` DB readiness 与 503/not_ready 行为已补。 | 完整 `main.py` app_factory/routes/lifespan 拆分需单独 ADR。 |
| Q-19 | 已完成（ToolPolicyResolver）/ 延期（深拆） | 提取 ToolPolicyResolver 作为 KB/network/tool policy 单一 enforcement 点。 | 深拆 `VoiceRuntimePolicyService` 剩余职责需单独 lane。 |
| Q-20 | 阻塞：产品/教研决策 | PPT 评分算法 ruleset 需要产品/教研确认。 | `blocked-by-product-decision`，需评分规则 ADR。 |
| Q-21 | 已完成 | Presentation AI policy 增加 Result-style scope/session failure APIs，调用方测试覆盖。 | `tests/unit/test_presentation_ai_policy_service.py`。 |
| Q-22 | 已完成 | health payload/readiness tests 增强。 | backend targeted tests。 |
| Q-23 | 延期（ADR） | Redis-backed rate limiter 多实例策略涉及部署/Fail-open/Fail-closed 决策。 | `docs/audit-remediation/20260421-lane-a-deferred-adr.md`。 |
| Q-24 | 延期（ADR） | ASR provider fallback 链涉及 provider 选择、browser handoff 和 websocket 合约。 | `docs/audit-remediation/20260421-lane-a-deferred-adr.md`。 |
| Q-25 | 已完成 | Redis cache memory fallback 增加 LRU cap 与 glob pattern 删除。 | `tests/unit/common/cache/test_redis_cache.py`。 |
| Q-26 | 已完成 | Sales websocket router 连接时重新计算 effective policy，防 tampered snapshot bypass。 | `tests/unit/test_sales_websocket_router.py`。 |
| Q-27 | 阻塞：产品/教研决策 | Realtime scoring ruleset 配置化需规则版本和 seed 策略。 | `blocked-by-product-decision`，需 ruleset ADR。 |
| Q-28 | 已完成 | PromptRenderer 对 untrusted variable 的 Jinja delimiters 做递归 sanitization。 | `tests/unit/prompt_templates/test_renderer.py`。 |
| Q-29 | 已完成 | backend source `print(` 清理为 logger / doc-safe 示例。 | `ruff check src tests --quiet` 通过。 |
| Q-30 | 延期（ADR） | 魔法数字治理为全域配置盘点，已明确单独 config-governance sweep。 | `docs/audit-remediation/20260421-lane-a-deferred-adr.md`。 |

## 4. UX-01..UX-18 交付矩阵

| ID | 交付状态 | 交付说明 | 证据 / 后续 |
| --- | --- | --- | --- |
| UX-01 | 已完成 | 录音快捷键增加 scope 与输入/滚动保护。 | `use-practice-recording-hotkeys.test.ts`。 |
| UX-02 | 已完成 | 练习计时器改为绝对时间，重连不归零。 | `page.test.tsx` targeted tests。 |
| UX-03 | 已完成 | 移除固定 300ms 死区，录音 start/stop 由状态机保护；权限重试不被 transition guard 阻断。 | `page.test.tsx` 权限拒绝立即重试测试。 |
| UX-04 | 延期（深拆专项） | 报告页全量拆分/并行加载仍为 Phase 2/4 大任务。 | 当前 report targeted tests 绿；深拆需单独 RALPLAN。 |
| UX-05 | 已完成 | Replay 消息定位使用 refs Map，避免 querySelector 静默失败。 | `replay/page.test.tsx`。 |
| UX-06 | 已完成 | practice 消息列表增加底部判断/可访问 label，自动滚动不打断阅读。 | `page.test.tsx` auto-scroll tests。 |
| UX-07 | 已完成 | admin 首页装饰性搜索被移除，避免假 affordance。 | `admin/page.test.tsx`。 |
| UX-08 | 已完成 | 登录密码显示/隐藏与 remember-email-only truthfulness。 | `login/page.test.tsx`。 |
| UX-09 | 已完成 | WebSocket AI welcome/message dedupe 跨 reconnect 稳定。 | `use-practice-websocket.test.ts`。 |
| UX-10 | 已完成 | Dashboard degraded banner / labels 收敛为用户可理解文案。 | `dashboard/page.test.tsx`。 |
| UX-11 | 已完成 | 移除无后端权威的 swipe delete 假入口，避免误删 affordance。 | `dashboard/page.test.tsx`。 |
| UX-12 | 已完成 | 会话结束转报告加入 learner-controlled transition / stay action。 | `use-practice-session-lifecycle.test.ts`。 |
| UX-13 | 已完成 | 与 UX-08 合并完成，未伪造后端 session TTL。 | login tests。 |
| UX-14 | 已完成 | 报告 retry validation 行为收敛并有测试覆盖。 | report/replay targeted tests。 |
| UX-15 | 已完成 | replay/report retry 路径一致性在 targeted suite 中通过。 | `replay/page.test.tsx` / `report/page.test.tsx`。 |
| UX-16 | 已完成 | 高光 review localStorage 加 schema_version，腐坏/旧 schema 安全丢弃。 | `report/page.test.tsx`。 |
| UX-17 | 已完成 | 录音状态机 hook 引入并通过 React Compiler lint 与状态机测试。 | `use-recording-state-machine.test.ts`。 |
| UX-18 | 延期（低优） | 相对时间时区感知仍为独立低优任务。 | 建议后续统一时间格式化工具/服务端时区策略。 |

## 5. G-01..G-10 交付矩阵

| ID | 交付状态 | 交付说明 | 证据 / 后续 |
| --- | --- | --- | --- |
| G-01 | 已完成 | Achievement/UserAchievement 规则与 dashboard badge wall。 | Growth targeted backend/frontend tests。 |
| G-02 | 已完成 | 报告同场景 completed/evaluable 趋势对比。 | `test_report_trends.py` + report tests。 |
| G-03 | 已完成 | Ruleset-backed next-practice recommendation，带 rule_version/source/evidence。 | `test_next_practice_recommendation.py`。 |
| G-04 | 延期（ADR） | 当前保留 source highlights；review-list CRUD/share token 延期。 | `docs/adr/2026-04-21-growth-deferred-slices.md`。 |
| G-05 | 已完成 | UserPresentationProgress + practice resume prompt/save。 | `test_user_presentation_progress.py` + practice tests。 |
| G-06 | 已完成 | Notification model/API/dashboard foundation。 | Growth center tests。 |
| G-07 | 已完成 | AI coach notification 基于真实 completed/evaluable 弱项生成。 | Growth tests；不编造样本不足事实。 |
| G-08 | 阻塞/延期（ADR） | 自适应难度默认 disabled；需离线 simulation 与教研确认。 | `docs/adr/2026-04-21-growth-deferred-slices.md`。 |
| G-09 | 已完成 | UserGoal + progress dashboard。 | Growth tests。 |
| G-10 | 阻塞/延期（ADR） | WeCom 分享需 token/domain/privacy review；未展示假入口。 | `docs/adr/2026-04-21-growth-deferred-slices.md`。 |

## 6. 配置项与治理说明

本轮新增/修改的主要配置与治理项包括：

| 配置/治理项 | 默认/策略 | 读取位置 | 治理说明 |
| --- | --- | --- | --- |
| `WEBSOCKET_MAX_MESSAGE_QUEUE_SIZE` | env-backed bounded int | `common.config.Settings` / `BaseWebSocketHandler` | 防无界队列；非法值回退默认。 |
| `WEBSOCKET_BACKPRESSURE_POLICY` | env choice | `BaseWebSocketHandler` | 队列满时发送 backpressure/error。 |
| `TTS_DEFAULT_SAMPLE_RATE_HZ` | env-backed int | `common.audio.pcm_duration` | PCM duration 公式可配置。 |
| `TTS_BYTES_PER_SAMPLE` | env-backed int | `common.audio.pcm_duration` | PCM duration 公式可配置。 |
| `TTS_CHANNELS` | env-backed int | `common.audio.pcm_duration` | PCM duration 公式可配置。 |
| `PRESENTATION_FEEDBACK_SESSION_TTL_SECONDS` | env-backed TTL | `PresentationFeedbackService` | 单例内存状态自动过期。 |
| `PRESENTATION_FEEDBACK_MAX_SESSIONS` | env-backed cap | `PresentationFeedbackService` | 超限 LRU 清理。 |
| `CACHE_MEMORY_MAX_ENTRIES` | env-backed cap | `RedisCache` fallback | 内存 fallback LRU 防泄漏。 |
| `SALES_BOT_SESSION_TTL_SECONDS` | env-backed TTL | `SalesBotService` | legacy active session 清理。 |
| `SALES_BOT_MAX_ACTIVE_SESSIONS` | env-backed cap | `SalesBotService` | legacy session 上限清理。 |
| `GROWTH_RECOMMENDATION_RULESET_JSON` | env/validated ruleset | `common.recommendations.next_practice` | 推荐规则版本化与证据说明。 |
| `GROWTH_ACHIEVEMENT_RULESET_JSON` | env/validated ruleset | `common.growth.growth_service` | 徽章规则配置化。 |
| `GROWTH_AI_COACH_RULESET_JSON` | env/validated ruleset | `common.growth.growth_service` | AI 教练触发规则配置化。 |
| `GROWTH_ADAPTIVE_DIFFICULTY_POLICY_JSON` | 默认 disabled/dry-run | `common.growth.safety_policies` | G-08 高风险功能默认不启用。 |
| `GROWTH_WECOM_SHARE_POLICY_JSON` | 默认 disabled | `common.growth.safety_policies` | G-10 分享默认不启用，需后续域名/token/隐私审查。 |

治理原则：业务规则、阈值、推荐、徽章、通知、AI 教练、自适应难度和分享策略均不得散落硬编码；当前已采用 env/ruleset/default disabled 的轻量治理，后续如进入后台管理阶段，应补齐 CRUD、启停、版本、回滚、审计日志。

## 7. 后台管理、权限、审计、回退覆盖情况

| 维度 | 当前覆盖 | 后续建议 |
| --- | --- | --- |
| 后台管理 | AI model config、knowledge answer config、voice runtime、presentation AI 等已有后台 API；本轮未新增完整统一配置后台。 | 对 growth/ruleset/notification/goal/adaptive/share 增加统一后台 CRUD。 |
| 权限 | Presentation upload/replace/delete 保持 admin-only；contract tests 已按当前契约对齐。 | manager/运营/教研细分权限需在后台配置阶段继续细化。 |
| 审计 | 现有 system/knowledge audit 与 tracker/final gate 文档记录；本轮未新增统一 audit table。 | 配置变更必须记录 actor/action/before/after/version/reason/trace_id。 |
| 回退 | 高风险增长能力默认 disabled；G-04/G-08/G-10 有 ADR；StepFun/main/voice deeper refactor deferred。 | 后续每个规则发布需支持 active version rollback。 |
| 数据隔离 | learner progress、growth、notification 均按 current-user 设计；presentation admin 操作仍需 admin。 | 分享 token / coach share 需后续隐私与访问审计。 |

## 8. 已知 warnings 与非阻塞风险

最终验证通过时仍有 warning，但不构成失败：

- Web Vitest login 测试出现 React `act(...)` warning；测试通过。
- Replay 测试会记录 completion-gated error path；这是测试用例覆盖的预期降级路径。
- Backend pytest 中 `chromadb` / Python 3.14 deprecation warning；测试通过。
- Presentation concurrent replace race proof 出现 SQLAlchemy delete row warning；这是并发 race 证明测试的预期副作用之一。

非阻塞风险：

1. Full backend pytest 未作为最终命令集执行；当前最终命令集、targeted backend/web suites 均通过。
2. Q-02 / Q-18 / 深层 Q-19 属于高风险架构专项，当前只完成 characterization / bounded slice。
3. G-04 / G-08 / G-10 未开放高风险用户功能，只以 ADR/安全默认关闭收口。
4. 统一后台配置、统一操作审计、完整规则版本管理仍需专门阶段。

## 9. 剩余需单独 ADR / RALPLAN 的事项

| 项目 | 原因 | 建议下一步 |
| --- | --- | --- |
| Q-02 StepFunRealtimeHandler 完整拆分 | 核心实时协议复杂，不能一次性重写。 | 单独 RALPLAN：每次只拆一个 outward contract，保留 snapshot/replay tests。 |
| Q-06 TTS chunk 双协议播放链 | 涉及后端 chunk、前端播放队列、音频证据、回放时长。 | 单独 WebSocket audio contract 任务。 |
| Q-18 main.py 完整拆分 | 路由/lifespan/middleware/static/dev auth 多职责。 | 单独 app factory / router registry 重构计划。 |
| Q-19 VoiceRuntimePolicyService 深拆 | 已完成 ToolPolicyResolver，但完整服务拆分仍大。 | 后续按 profile/agent/persona/tool policy 分阶段。 |
| Q-20/Q-27 评分 ruleset | 需要产品/教研确认评分权重与历史报告口径。 | ruleset ADR + dry-run 差异报告。 |
| Q-23 Redis-backed rate limiter | 涉及多实例部署和 fail-open/fail-closed 策略。 | 部署前单独安全/性能评审。 |
| Q-24 ASR fallback chain | 涉及 provider、浏览器 handoff、用户提示。 | 单独音频容灾 RALPLAN。 |
| Q-30 魔法数字治理 | 全仓配置/常量盘点。 | 单独 config governance sweep。 |
| UX-04 报告页深拆 | 2177 行复杂页面，需组件/数据 hook 分阶段拆。 | 单独 frontend report refactor。 |
| UX-18 时区感知相对时间 | 低优边缘场景。 | 增加统一时间格式化工具。 |
| G-04 高光 review list 后端持久化与分享 | 分享 token/TTL/撤销/隐私审计复杂。 | 单独 share-token ADR。 |
| G-08 自适应难度 | 需要离线 simulation 和教研确认。 | 先 dry-run，不直接启用。 |
| G-10 企业微信分享 | 需要 WeCom token/domain/privacy review。 | 单独企业微信分享安全方案。 |

## 10. 回退方案

### 10.1 文档与计划回退

- 本报告是文档提交，可用 `git revert <report-commit>` 回退。
- 计划文件与最终 gate 报告均在 `docs/audit-remediation/` 和 `docs/plans/` 下，回退不会影响运行时代码。

### 10.2 运行时代码回退

- 使用 `git log --oneline 2fb85a4..HEAD` 查看从计划追踪提交后的全部交付提交。
- 若需整体回退实现，可按提交顺序反向 `git revert` 从当前 HEAD 到 `2fb85a4` 之后的实现提交；不建议直接 reset 已共享分支。
- 若只回退某个 lane，优先按报告中 lane 归属定位文件和提交：
  - Lane A：runtime safety / backend stability。
  - Lane B：architecture/contracts。
  - Lane C/D：frontend practice/report/replay/admin/login UX。
  - Lane E：growth。
  - Lane F：docs/release gate。

### 10.3 配置回退

- env-backed 配置可通过删除/恢复 env 变量回到默认值。
- growth 高风险策略默认 disabled；若配置异常，删除对应 `GROWTH_*_JSON` 即回退默认。
- 后续引入后台 active version 后，必须提供上一有效版本回滚。

## 11. 后续建议

1. 若目标是发布前稳定性：先跑完整 backend pytest 和完整 web test，并记录全量耗时与剩余 warning。
2. 若目标是架构治理：启动 Q-02/Q-18/Q-19 的单独 RALPLAN，禁止一次性大改。
3. 若目标是产品增长深化：先完成 G-04 share token / G-08 dry-run / G-10 WeCom 安全 ADR，再写代码。
4. 若目标是配置治理：建立统一系统配置后台、规则表、操作审计和版本回滚能力。
5. 若目标是 PR/合并：用本报告 + `20260421-final-integrated-release-gate.md` 作为交付说明基础。

## 12. 最终交付结论

截至本报告生成时：

- 审计修复和产品迭代的关键 lane 已完成并集成。
- 当前用户指定的最终收口验证命令集全部通过。
- 后端 `ruff check src tests --quiet` 已通过。
- 前端 targeted typecheck/lint/tests 已通过。
- 后端 targeted integration/regression/focused suites 已通过。
- 高风险长期项均有 ADR/延期边界或产品决策阻塞说明。

最终状态：**可作为当前审计修复迭代的交付基线**；后续大项应拆成独立 ADR/RALPLAN，而不是继续混入本轮交付。
