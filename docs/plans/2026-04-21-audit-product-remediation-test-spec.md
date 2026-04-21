# Test Spec：2026-04-21 审计修复与产品迭代落地验证规格

## 0. 验证原则

1. **测试先行**：安全、评分、会话、重构类任务必须先补 characterization/regression tests。
2. **分层验证**：unit -> contract -> integration -> frontend component -> browser smoke。
3. **配置异常必测**：每个新增配置至少覆盖命中、缺失、非法、停用/回退。
4. **用户可见不伪装**：接口失败不显示成空数据；非功能 UI 不展示。
5. **每个 PR 至少跑 touched-file lint + targeted tests + `git diff --check`。**

## 1. Phase 0 基线命令

```bash
git status --short --branch
git diff --check
pnpm --dir web exec tsc --noEmit --pretty false
pnpm --dir web exec eslint \
  'src/app/(dashboard)/page.tsx' \
  'src/app/(dashboard)/training/page.tsx' \
  'src/app/(user)/practice/[sessionId]/page.tsx' \
  'src/app/(user)/practice/[sessionId]/report/page.tsx' \
  'src/app/(user)/practice/[sessionId]/replay/page.tsx' \
  --quiet
pnpm --dir web exec vitest run \
  'src/app/(dashboard)/page.test.tsx' \
  'src/app/(dashboard)/training/page.test.tsx' \
  'src/app/(user)/practice/[sessionId]/page.test.tsx' \
  'src/app/(user)/practice/[sessionId]/report/page.test.tsx' \
  'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' \
  --reporter=dot
cd backend && .venv-test/bin/python -m pytest tests/unit tests/contract -q --no-cov
cd backend && ruff check src tests --quiet
```

若全量 backend tests/ruff 因历史问题失败，必须记录失败清单，并为本阶段使用 scoped 命令。

## 2. PR-1A Backend runtime safety tests

### Q-08 CapabilityRunner

新增/更新：`backend/tests/unit/agent/capabilities/test_runner.py`

用例：
- capability 抛 `ConnectionError` -> 返回 `CapabilityResult.fail`，错误码可观测。
- capability 抛 `OSError` -> 返回 fail，不破坏 pipeline。
- capability 超时 -> 现有 timeout 行为不回归。
- `asyncio.CancelledError` -> 按设计传播取消，不能伪装成功。

命令：

```bash
cd backend && .venv-test/bin/python -m pytest tests/unit/agent/capabilities/test_runner.py -q --no-cov
cd backend && ruff check src/agent/capabilities/runner.py tests/unit/agent/capabilities/test_runner.py --quiet
```

### Q-09 WebSocket bounded queue

新增/更新：`backend/tests/unit/common/websocket/test_base_handler_queue.py`

用例：
- 默认 `MAX_MESSAGE_QUEUE_SIZE=300`。
- 队列满时不无限增长，触发 backpressure/drop 策略。
- 非法配置回退默认值并记录 warning。

### Q-10 CancelledError propagation

新增/更新：`backend/tests/unit/sales_bot/websocket/test_base_sales_handler_cancellation.py`

用例：
- 每个原来混合捕获的位置，任务取消时 `CancelledError` 向上传播。
- RuntimeError/ValueError/OSError 仍按原降级路径处理。

### Q-11 Enhanced handler race

新增/更新：`backend/tests/unit/sales_bot/websocket/test_enhanced_handler_response_task.py`

用例：
- 两个消息并发调用 `_launch_response_task` 只产生一个 active task。
- task 完成后下一条消息可以创建新 task。

### Q-12 Presentation websocket isolation

新增/更新：`backend/tests/unit/presentation_coach/websocket/test_presentation_handler_connections.py`

用例：
- `session_id` 不在 connections 中返回 None。
- 不会返回其他 session websocket。
- 调用方对 None 走安全失败/重连路径。

### Q-13 TTS duration

新增/更新：`backend/tests/unit/sales_bot/websocket/components/test_tts_component.py`

用例：
- 16kHz, 16bit, mono, 32000 bytes -> 1000ms。
- 24kHz, 16bit, mono, 48000 bytes -> 1000ms。
- metadata 缺失时使用默认 sample rate，并记录 fallback。

## 3. PR-1B Backend correctness/performance tests

### Q-03 FeedbackService TTL

文件：`backend/tests/unit/presentation_coach/services/test_feedback_service_lifecycle.py`

覆盖：TTL 到期清理、max_sessions 超限清理、`clear_session` 幂等、异常断开后 cleanup task 可回收。

### Q-04 SalesBotService dead code / TTL

文件：`backend/tests/unit/sales_bot/services/test_bot_service_lifecycle.py`

覆盖：active session 只存元数据或 TTL 清理；router 不引用 legacy service 的引用扫描。

引用扫描命令：

```bash
rg -n "SalesBotService|bot_service" backend/src backend/tests
```

### Q-05 Knowledge retrieval parallel fallback

文件：`backend/tests/unit/agent/capabilities/test_knowledge_retrieval.py`

覆盖：
- `search_multiple` 失败后多个 KB 并发调用。
- 单个 KB 失败不影响其他 KB 结果。
- 结果排序/去重与旧行为一致。

### Q-07 Staged evaluation slicing

文件：`backend/tests/unit/evaluation/services/test_staged_evaluation.py`

覆盖：
- trigger 有 `start_turn/end_turn` 时按真实范围切片。
- 某阶段超过 2 轮不丢失。
- 缺 trigger 时有安全 fallback，并明确标记 evidence insufficient。

### Q-29 print cleanup

命令：

```bash
rg -n "\bprint\(" backend/src | tee /tmp/print-usage.txt
```

预期：无普通运行时代码 `print()`；CLI 工具若保留必须有注释说明。

## 4. PR-1C Practice UX tests

目标文件：
- `web/src/app/(user)/practice/[sessionId]/use-practice-recording-hotkeys.test.ts`
- `web/src/app/(user)/practice/[sessionId]/page.test.tsx`
- `web/src/hooks/use-practice-websocket.test.ts`

用例：
- UX-01：焦点在输入框/按钮/可滚动历史时 Space 不 preventDefault；录音 scope 内 Space 可切换。
- UX-02：`isConnected=false -> true` 后 session timer 不归零。
- UX-03：快速双击/连按不会出现任意 300ms 死区；权限失败后可立即重试。
- UX-06：用户上滚超过阈值时新消息不强制回底；接近底部时仍自动滚动。
- UX-09：重连后重复 welcome/message_id 被去重；超过窗口后缓存自动裁剪。

命令：

```bash
pnpm --dir web exec vitest run \
  'src/app/(user)/practice/[sessionId]/use-practice-recording-hotkeys.test.ts' \
  'src/app/(user)/practice/[sessionId]/page.test.tsx' \
  'src/hooks/use-practice-websocket.test.ts' \
  --reporter=dot
pnpm --dir web exec eslint \
  'src/app/(user)/practice/[sessionId]/use-practice-recording-hotkeys.ts' \
  'src/app/(user)/practice/[sessionId]/page.tsx' \
  'src/hooks/use-practice-websocket.ts' \
  --quiet
```

## 5. PR-1D Report/replay/admin/login UX tests

目标文件：
- `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx`
- `web/src/app/admin/page.test.tsx`
- `web/src/app/(auth)/login/page.test.tsx`
- `web/src/app/(dashboard)/page.test.tsx`
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`
- 新增 `web/src/hooks/use-retry-session.test.ts` 或 route-local util tests。

用例：
- UX-05：jump-to-message 使用 ref map；目标不存在时显示/记录安全提示，不静默异常。
- UX-07：admin 搜索框不存在，或输入后卡片真实过滤。
- UX-08/13：密码显示/隐藏可切换；remember me 状态可提交且不伪保存。
- UX-10：dashboard 降级 banner 使用用户友好 label。
- UX-11：删除历史需二次确认或 undo；未确认不调用删除 API。
- UX-14/15：报告页与回放页 retry 校验结果一致。
- UX-16：旧 schema localStorage 不导致 crash，按策略清空/迁移。

命令：

```bash
pnpm --dir web exec vitest run \
  'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' \
  'src/app/admin/page.test.tsx' \
  'src/app/(auth)/login/page.test.tsx' \
  'src/app/(dashboard)/page.test.tsx' \
  'src/app/(user)/practice/[sessionId]/report/page.test.tsx' \
  --reporter=dot
pnpm --dir web exec tsc --noEmit --pretty false
```

## 6. PR-1E Security tests

### Q-26 KB lock bypass

文件：`backend/tests/unit/sales_bot/websocket/test_router_kb_lock.py`

用例：
- session snapshot 声称 unbound，但 runtime effective policy 要求 KB lock -> 仍走 locked handler。
- 管理员修改 snapshot 不能单独改变连接期安全策略。

### Q-28 PromptRenderer injection

文件：`backend/tests/unit/prompt_templates/test_renderer_security.py`

用例：
- 用户变量包含 `{{ 7*7 }}`、`{% for %}` 等不被二次执行。
- HTML/JS 文本被按 prompt-safe 策略转义或标记为原文，不破坏模板结构。
- 代码块/业务提示词格式不回归。

## 7. PR-1F Growth low-risk tests

### G-02 Trend comparison

后端：`backend/tests/unit/common/analytics/test_report_trends.py`

- 只统计当前用户、同场景、completed/evaluable。
- 返回最近 N 次维度分数和 delta。
- 无历史时返回 explanation，不伪造 0。

前端：`web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`

- 展示趋势图/列表；相比上次 +X/-X；无数据显示行动化说明。

### G-05 PPT progress

后端：`backend/tests/unit/presentation_coach/test_user_presentation_progress.py`

- 保存当前用户当前 presentation 的 last_page_number。
- 用户 A 不能读取用户 B 的进度。
- 非法 page 拒绝或忽略并记录错误。

前端：practice page tests 覆盖“继续上次第 N 页”。

### G-03 Recommendation contract

后端：`backend/tests/unit/common/recommendations/test_next_practice_recommendation.py`

- product_knowledge < threshold 推荐知识型训练。
- objection_handling 低分推荐抗拒处理。
- 推荐 payload 带 `source_session_id`、`rule_version`、`explanation`。

## 8. Phase 2 architecture/growth test suites

### Q-01 import boundary

命令：

```bash
python3 scripts/check_import_boundaries.py --layer common --forbid sales_bot,presentation_coach,evaluation
```

若无脚本，新增最小测试：遍历 `backend/src/common/**/*.py` AST import，禁止导入上层场景实现；允许协议/typing-only 需显式白名单。

### Q-14/Q-15 API/helper contract

- `backend/tests/contract/test_api_response_envelope.py`
- `backend/tests/unit/common/services/test_practice_helpers.py`
- 断言 touched endpoints 统一 `success/error/trace_id`。
- 断言 practice API 与 service 共享 helper 输出一致。

### Q-16/Q-17 type/exception governance

- 每个 touched backend file 必须 `ruff check <files> --quiet`。
- 类型治理用 scoped mypy/pyright，不要求一次全仓 strict。
- Broad exception 若保留，测试需覆盖降级路径，注释需说明原因。

### Q-18 main split

- `backend/tests/contract/test_health.py`
- `backend/tests/integration/test_app_startup_routes.py`
- `/health`、CORS、static、dev auth、API routers 路径不回归。

### Q-19 policy resolver

- profile/agent/persona merge matrix。
- require_kb_grounding/network_access_mode 单一 truth source。
- inactive/default profile fallback。

### Q-21 Result mode

- invalid scope returns `Result.fail('[INVALID_SCOPE_TYPE]')`。
- missing session returns `Result.fail('[SESSION_NOT_FOUND]')`。
- 调用方不需要捕获 ValueError。

### Q-22 health readiness

- DB 正常 -> ready true。
- DB down -> readiness false/503。
- optional Redis down -> degraded but liveness true（除非配置为 critical）。

### Q-24/Q-25 ASR/cache

- ASR provider fallback order and terminal error code。
- Cache fallback LRU eviction; `delete_pattern('user:*:profile')` 使用 glob，不误删 `user_123_profile`。

### UX-04/UX-12

- 报告页面 skeleton/主报告先显示，secondary sections 独立 loading/error。
- session ended overlay 出现；点击立即查看跳转；留在当前页取消自动跳转。

### G-01/G-04/G-06/G-07/G-09

后端：
- Achievement unlock 幂等；规则 disabled 不解锁。
- Highlight CRUD 当前用户隔离；分享 token TTL/撤销。
- Notification unread/read/list；AI coach template 缺失不发送。
- UserGoal progress 只统计 eligible sessions。

前端：
- Dashboard badge wall、notification bell、goal card。
- Report new badge/highlight persistence state。
- AI coach 卡片 explainable CTA。

## 9. Phase 3/4 long-horizon tests

### Q-20/Q-27 scoring config

- seed ruleset 与旧硬编码结果一致。
- 新 ruleset 生效范围可控；历史 report 按 `ruleset_version` 展示。
- 缺失/非法 ruleset fallback 且告警。

### Q-23 Redis rate limiter

- memory backend 加锁并发测试。
- Redis backend 原子计数测试（可用 fake redis 或集成容器，若无容器则 mock）。
- fail-open/fail-closed 策略按环境配置验证。

### Q-30 constants/config

- `rg` 检查新增 magic numbers；业务阈值必须在 config/rules table。
- 稳定技术常量有命名常量与注释。

### UX-17/UX-18

- Recording state machine transition table tests。
- UTC/server timezone relative time tests。

### G-08/G-10

- Adaptive difficulty offline simulation：不会在低样本下调整；调整幅度有上限；用户可解释。
- WeCom share：token 生成/过期/撤销；分享 payload 不含敏感原文，除非用户明确授权。

## 10. 最终回归矩阵

```bash
git diff --check
pnpm --dir web exec tsc --noEmit --pretty false
pnpm --dir web exec eslint . --quiet
pnpm --dir web exec vitest run --reporter=dot
cd backend && ruff check src tests --quiet
cd backend && .venv-test/bin/python -m pytest tests -q --no-cov
```

若全量命令存在历史失败，最终报告必须列出：失败命令、失败原因、是否本轮引入、已运行的替代 targeted 命令、后续修复计划。


---

## 11. RALPLAN-DR 测试补丁：显式 ID、配置治理、权限审计与回退

本节补齐 `$ralplan` Critic 指出的测试规格缺口。后续进入实施前，必须把本节测试项并入对应阶段的验收清单。

### 11.1 显式 ID 补齐测试

#### Q-02 StepFunRealtimeHandler 拆分专项测试

在任何 Q-02 拆分前必须先建立：

- WebSocket payload snapshot tests：覆盖 response、function_call、tool_result、KB lock blocked、feedback、resume、error fallback。
- replay fixture tests：用固定上游事件序列重放，断言拆分前后 outward payload 完全一致。
- state object tests：`RealtimeResponseState`、`FunctionCallState` 等提取后有纯单元测试。
- adapter compatibility tests：旧 handler 入口仍可调用新组件；回退到旧路径时协议不变。

#### Q-06 TTS chunk protocol 测试

- 后端 contract：`tts_audio_chunk` 包含 stream_id、request_id、chunk_index、is_final、duration_ms、sample_rate 或可推导元数据。
- legacy fallback：前端不支持 chunk 或服务端 chunk 失败时，仍可收到旧 `tts_audio` 或 browser TTS fallback。
- 前端播放队列：chunk 顺序乱序/重复/缺失时有安全处理，不重叠播放。
- 音频证据链：chunk 模式下 duration、audio evidence flush、报告/回放仍一致。

#### UX-13 登录密码可见性与记住我安全测试

- 密码显示/隐藏按钮可切换，aria label 可访问。
- 记住我未勾选时使用默认 session TTL；勾选时使用受限 TTL。
- 登出后清除持久状态。
- 管理员禁用 remember-me 时 UI 不展示或展示禁用说明。
- 共享设备提示文案存在，且不是纯装饰。

#### UX-15 回放页 retry hook 一致性测试

- 报告页与回放页使用同一 retry validation / creation utility 或 hook。
- 同一 invalid retry_entry 在两个页面显示一致错误与 fallback path。
- 同一 valid retry_entry 在两个页面创建 session payload 一致。
- API 失败时两个页面都不伪装成功。

### 11.2 配置治理测试

每个新增/迁移配置项必须覆盖：

1. 配置存在且合法：业务命中配置值。
2. 配置缺失：使用安全默认值或禁用非核心能力，并记录 warning。
3. 配置非法：保存前 400/422；运行时非法 active config 回退上一有效版本。
4. 配置停用：业务逻辑识别 disabled，不继续命中新规则。
5. 读取失败：核心训练流程不崩溃，非核心功能降级。
6. 版本切换：active version 切换后生效范围和时机符合定义。
7. 回滚：回滚到上一版本后读取结果恢复。

### 11.3 后台权限与审计测试

- 普通用户不能访问全局配置 CRUD。
- manager 不能修改评分、推荐、通知全局规则。
- 运营只能管理通知、徽章、目标等运营配置，不得修改安全底线。
- 教研/内容管理员可提交评分 ruleset 草稿，但启用/回滚需 admin 或审批流。
- admin 修改、启用、停用、回滚配置时必须写 audit log。
- audit log 断言包含 actor、role、action、before、after、version、reason、timestamp、trace_id。
- 未授权访问返回 401/403，不返回敏感配置详情。

### 11.4 Ruleset 版本化测试

覆盖 Q-20、Q-27、G-03、G-08：

- 新评分 ruleset dry-run 输出历史样本差异，不直接影响线上报告。
- 报告生成保存 `ruleset_version`。
- 老报告在新 ruleset 发布后仍按旧版本展示。
- 推荐结果保存/返回 `rule_version`、`source_session_id`、`evidence_summary`。
- 非法 ruleset 不可发布；运行时发现非法 active ruleset 时回退上一有效版本并告警。
- 自适应难度默认 disabled；样本不足时不得自动调难度。

### 11.5 通知、AI 教练与分享隐私测试

#### G-04 高光分享

- 分享 token 有 TTL、可撤销、可审计。
- token 过期后 401/403。
- 默认分享 payload 不含完整训练原文，除非用户明确选择。
- 非 owner 或无权限访问时拒绝。

#### G-06 应用内通知

- list/read/unread/mark-read 正常。
- 模板缺失或变量缺失时不发送通知。
- 用户关闭某类通知后不再收到同类通知。
- 通知过期后不展示在默认列表。

#### G-07 AI 教练主动触达

- 触达必须基于真实 completed/evaluable 数据。
- 样本不足时不生成“连续低分”等断言。
- 频控命中时不重复发送。
- 文案包含证据来源和下一步 CTA。

#### G-10 企业微信分享

- WeCom SDK/token 获取失败时安全降级，不影响报告页。
- 分享链接权限、TTL、撤销、访问审计生效。
- 分享内容不泄露超出用户选择范围的训练文本、客户信息或企业敏感数据。

### 11.6 最终覆盖与治理断言

最终计划验收必须运行文档覆盖脚本，断言主计划与测试规格合并文本包含：

- `Q-01..Q-30`
- `UX-01..UX-18`
- `G-01..G-10`
- `配置`、`默认值`、`校验`、`权限`、`审计`、`回退`、`兜底`、`后台`、`停用`、`非法`、`缺失`、`操作记录`
- `Q-02`、`Q-06`、`UX-13`、`UX-15` 的显式测试章节

若任一断言失败，不得进入 `$ralph`、`$team`、`autopilot` 或任何实施模式。

