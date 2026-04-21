# PRD：2026-04-21 代码审计修复与产品迭代落地计划

## 0. 元数据

- 来源审计：`/Users/zhaozengqing/.claude/projects/-Users-zhaozengqing-github-----qoder/项目代码审计与产品迭代建议.md`
- 计划日期：2026-04-21
- 仓库：`/Users/zhaozengqing/github/销售训练qoder`
- 计划类型：全面修复 + 产品迭代落地路线；**本文件只规划，不实施、不改业务源码**。
- 直接产物：本 PRD + 配套测试规格 + 执行交接计划；后续如需实施，必须另行按阶段授权。
- 覆盖承诺：审计文档中的 30 项代码质量问题、18 项用户体验问题、10 项用户粘性建议全部进入覆盖矩阵；不能实现的内容必须明确延期原因、前置条件、验证口径。

## 0.1 计划边界声明

本计划基于仓库根目录审计文件 `项目代码审计与产品迭代建议.md` 编写。当前交付仅包含计划、测试规格、阶段拆解、配置化与验收标准，不包含任何业务源码实现。所有实施动作必须在后续独立任务中按阶段执行，并在执行前重新确认工作区状态与现有配置体系。

## 1. 背景与目标

### 1.1 背景

项目已具备销售对练、PPT 演练、实时语音、报告、回放、排行榜、训练历史、复练推荐、主管干预、高光回顾等完整产品骨架。2026-04-21 审计指出当前主要风险集中在四类：

1. **架构债务**：`common/` 反向依赖上层场景模块，`stepfun_realtime_handler.py`、`main.py`、报告页等核心文件过大。
2. **生产稳定性/安全**：内存泄漏、无界 WebSocket 队列、竞态条件、错误 WebSocket 回退、KB 锁绕过、提示词注入、宽泛异常处理。
3. **用户体验摩擦**：热键拦截滚动、计时器重连重置、录音 300ms 死区、自动滚动打断阅读、报告瀑布加载、回放定位不稳、装饰性搜索、登录体验不足。
4. **用户粘性增量**：已有 streak、排行榜、周目标、今日复练、主管干预、能力地图、高光回顾等基础，但缺少徽章、趋势对比、练后推荐、通知/AI 教练触达、高光后端持久化、PPT 续练。

### 1.2 总目标

1. 建立一份可以交给 `$ralph` 或 `$team` 分批执行的无遗漏路线图。
2. 将高风险架构重构拆成可验证小切片，每切片优先补测试再改代码。
3. 将安全/稳定性问题置于第一周优先队列，避免生产 DoS、会话混淆、内存泄漏和竞态扩大。
4. 修复高频核心路径 UX，使练习、报告、回放、登录和管理入口不再产生明显错误 affordance 或状态错乱。
5. 所有业务规则、文案、阈值、排序、推荐、徽章、通知、评分必须配置化或至少预留集中配置读取层。
6. 每个阶段结束必须有命令级验证证据、回退方案、剩余风险说明。

### 1.3 非目标

1. 不直接改 Docker、部署、运维或基础设施脚本。
2. 不一次性重写 StepFun handler、main.py、报告页或全项目 response envelope。
3. 不用新增长功能掩盖基础评分、会话、音频、权限、安全不可信的问题。
4. 不引入新依赖作为默认方案；若必须引入，如图表/分享图片生成，需要单独 ADR。
5. 不把业务阈值、提示文案、徽章条件、评分规则、通知模板、推荐规则直接硬编码进页面或 handler。

## 2. 实现前配置化与管理性判断

> 按项目“功能实现的可管理性与配置化约束”执行。以下判断必须在后续任何代码实现前复核。

### 2.1 稳定代码逻辑

这些属于系统底线或技术约束，可保留在代码中，但需要测试保护：

- 依赖方向：`common/` 不能反向依赖 `sales_bot/`、`presentation_coach/`、`evaluation/` 的具体实现。
- 异步取消语义：`asyncio.CancelledError` 必须单独传播，不能被普通异常降级吞掉。
- WebSocket 会话隔离：找不到当前 session 的连接时必须返回 `None` 或明确错误，绝不能回退到任意连接。
- 有界资源原则：队列、缓存、会话内存状态必须有 maxsize/TTL/清理机制。
- TTS 时长公式：`duration_ms = bytes * 1000 / (sample_rate * bytes_per_sample * channels)` 是稳定技术公式。
- React refs 替代 `querySelector` 的 DOM 定位原则。
- API 响应统一 helper 的 envelope 结构与 trace_id 生成底线。
- 权限与安全底线：用户只能访问自己的数据；管理员配置入口必须有 admin 权限；KB 锁不能被持久化快照绕过。

### 2.2 可配置业务规则

以下不得散落硬编码，必须使用现有配置体系或新增集中配置/规则表：

- 评分维度、权重、扣分、通过阈值、PPT 完整度/准确性/逻辑性算法参数。
- WebSocket 队列上限、反馈服务 TTL、清理周期、缓存 LRU 上限、速率限制窗口。
- 练习快捷键及生效范围、自动跳转倒计时、自动滚动阈值、消息去重窗口。
- Dashboard 降级 banner 文案、各 section 用户可见名称、登录“记住我”有效期。
- 成就徽章条件、图标、展示顺序、解锁文案。
- 历史趋势窗口大小、同场景/同 Agent/同 Persona 对比口径。
- “下次练什么”推荐规则、弱项阈值、推荐优先级。
- 通知模板、AI 教练触发条件、沉默用户召回窗口、周目标提醒阈值。
- PPT 续练提示文案、默认是否从上次页继续。
- 高光回顾最大条数、分享链接有效期、分享权限。
- 自适应难度上下调阈值与最大调整幅度。

### 2.3 可复用配置来源

已确认可复用/扩展的配置入口：

- 环境和基础系统配置：`backend/src/common/config.py`。
- AI 模型配置与热更新：`backend/src/common/ai/config_manager.py`、`backend/src/admin/api/model_configs.py`。
- 知识库回答配置：`backend/src/admin/api/knowledge_answer_config.py`。
- 语音运行时策略：`backend/src/admin/api/voice_runtime.py`、`backend/src/sales_bot/services/voice_runtime_policy.py`。
- 前端管理页面：`web/src/app/admin/settings`、`web/src/app/admin/voice-runtime`。

基于当前快速盘点，暂无法确认是否存在**统一业务规则配置表、统一操作审计表、统一系统设置后台**。如后续实现找不到这些模块，必须补充配置模块、后台管理模块、字典表、权限模块或系统设置相关代码，不得把业务规则写死。

### 2.4 新增配置项清单（首批默认值）

| 配置项 | 用途 | 类型/默认值 | 校验 | 读取位置 | 管理入口 | 权限 | 兜底/非法处理 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `websocket.max_message_queue_size` | 基类 WS 队列上限 | int / `300` | 1-5000 | `common.websocket.base_handler` | 系统设置或 env | admin | 缺失用 300；非法记录 warning 后用 300 |
| `websocket.backpressure_policy` | 队列满时行为 | enum / `drop_newest` | allowlist | WS handler | 系统设置 | admin | 非法用 `drop_newest` 并告警 |
| `presentation_feedback.session_ttl_seconds` | PPT 反馈内存状态 TTL | int / `86400` | 60-604800 | `feedback_service` | 系统设置 | admin | 缺失用 24h；非法不启动新值 |
| `presentation_feedback.max_sessions` | 单进程最大会话状态 | int / `10000` | 100-100000 | `feedback_service` | 系统设置 | admin | 超限清理最旧状态 |
| `tts.default_sample_rate_hz` | TTS 时长 fallback | int / `16000` | 8000/16000/24000/48000 | `tts_component` | 模型/语音设置 | admin | 优先音频元数据，缺失用默认 |
| `tts.bytes_per_sample` | 时长公式 | int / `2` | 1-4 | `tts_component` | 模型/语音设置 | admin | 非法用 2 |
| `practice.hotkey.recording_toggle` | 录音快捷键 | string / `Space` | KeyboardEvent key allowlist | practice hotkeys hook | 用户偏好/系统默认 | user/admin | 非法禁用快捷键并提示 |
| `practice.autoscroll.bottom_threshold_px` | 底部附近自动滚动阈值 | int / `100` | 0-500 | practice page | 系统设置 | admin | 缺失用 100 |
| `practice.session_end.redirect_delay_seconds` | 结束后跳报告宽限 | int / `5` | 0-60 | lifecycle hook | 系统设置 | admin | 0 表示立即跳转 |
| `practice.message_dedupe.window_seconds` | 重连消息去重窗口 | int / `300` | 30-3600 | `use-practice-websocket` | 系统设置 | admin | 缺失用 300 |
| `dashboard.degraded_section_labels` | 用户友好降级文案 | dict | key/value 非空 | dashboard page | 文案配置 | admin/运营 | 缺失回退稳定中文标签 |
| `highlight_review.schema_version` | 高光回顾 schema | string / `highlight_review_v1` | 非空 | report page/API | 代码常量+迁移配置 | admin | 版本不匹配安全清空/迁移 |
| `highlight_review.max_items` | 高光最多条数 | int / `3` | 1-50 | report page/API | 系统设置 | admin | 缺失用 3 |
| `highlight_share.ttl_days` | 教练分享有效期 | int / `7` | 1-90 | highlight API | 系统设置 | admin | 非法拒绝保存 |
| `scoring.ruleset_version` | 评分规则版本 | string / `default_v1` | active version exists | scoring services | 评分规则后台 | admin/教研 | 缺失使用安全默认 ruleset |
| `presentation_scoring.forbidden_word_penalty` | 唯一禁忌词扣分 | int / `10` | 0-100 | coach_service/rules | 评分规则后台 | admin/教研 | 非法禁用发布 |
| `recommendation.weakness_threshold` | 弱项推荐阈值 | int / `60` | 0-100 | recommendation service | 推荐规则后台 | admin/运营 | 缺失用 60 |
| `achievement.rules` | 徽章条件 | JSON/rule table | schema + dry-run | achievement service | 成就后台 | admin/运营 | 无 active rules 时不解锁新徽章 |
| `notification.templates` | 通知/AI 教练文案 | template table | 必填变量校验 | notification service | 通知后台 | admin/运营 | 模板缺失不发送，记录告警 |
| `ai_coach.trigger_rules` | 主动触达条件 | JSON/rule table | schema + limit | notification service | 触达规则后台 | admin/运营 | 默认 disabled |
| `user_goal.presets` | 目标类型预设 | JSON/table | target > 0 | goals service | 目标设置后台 | admin/运营 | 缺失只显示个人自定义入口 |
| `adaptive_difficulty.rules` | 难度调节策略 | JSON/table / disabled | score range + cap | difficulty service | 策略后台 | admin/教研 | 默认禁用 |
| `rate_limit.backend` | 速率限制后端 | enum / env decides | memory/redis | rate_limit | env/system | admin | Redis 不可用时按环境决定 fail-open/fail-closed |
| `cache.memory_max_entries` | Redis fallback LRU 上限 | int / `10000` | 100-1000000 | redis_cache | 系统设置/env | admin | 缺失用 10000 |
| `health.critical_dependencies` | 健康检查关键依赖 | list / `db` | allowlist | monitoring health | 系统设置/env | admin | 缺失只检查 DB，不报告假健康 |

### 2.5 后台管理与审计要求

1. 第一批安全/稳定性配置可先用 env + 集中 settings 类承载，但必须封装读取层和校验函数。
2. 第二批业务策略配置（评分、推荐、徽章、通知、目标、难度）必须优先走数据库规则表/模板表，并预留后台 CRUD：列表、查看、新增、修改、启用/停用、校验、预览、操作记录。
3. 所有配置修改需要 `created_by`、`updated_by`、`enabled`、`version`、`effective_at`、`rollback_to_version` 或等价回退字段。
4. 缺失配置时业务逻辑必须使用安全默认值或关闭非核心功能；配置非法时拒绝保存，运行时遇到非法 active config 必须告警并回退上一个有效版本。

## 3. 验收总标准

本计划完成不是“写完代码”，而是每个条目满足以下条件之一：

1. 已实现并有测试/验证证据；或
2. 已拆成独立 PRD/测试规格并明确前置条件、延期原因、回退策略；或
3. 经验证审计项已不存在，并记录证据。

全局验收：

- 审计覆盖矩阵中 Q-01..Q-30、UX-01..UX-18、G-01..G-10 均有阶段、验收方式和状态。
- 高优安全/稳定性项必须有单元/并发/契约测试。
- 用户可见 UX 改动必须有 Vitest/RTL 测试；关键路径至少一次 Playwright smoke。
- 可配置业务规则不得新增页面/handler 内 magic number 或散落文案。
- 每一阶段 `git diff --check`、targeted lint/type/test 通过；失败必须修复或记录明确阻塞。

## 4. 分阶段落地路线

### Phase 0：基线、冻结与追踪（0.5-1 天）

**目标**：保证后续执行可审计、可回退、不覆盖他人改动。

步骤：
1. 建立执行分支与任务看板：`audit-20260421-remediation`。
2. 记录 `git status --short --branch`、当前 HEAD、依赖版本。
3. 创建 `docs/audit-remediation/20260421-tracker.md` 或 `.omx/state/audit-product-remediation-progress.json`，将本矩阵导入可勾选任务。
4. 跑基线命令：web targeted smoke、`pnpm --dir web exec tsc --noEmit --pretty false`、backend targeted pytest/ruff。
5. 对大文件拆分和架构迁移先写 characterization tests，不直接移动代码。

验收：基线命令结果记录；若失败，标记为“历史失败/本阶段阻塞/需先修复”。

### Phase 1：第一周安全稳定 + 高频 UX 快修（建议 6 个小 PR，不超过 5 文件/PR）

#### PR-1A Backend runtime safety quick wins

覆盖：Q-08、Q-09、Q-10、Q-11、Q-12、Q-13。

- `agent/capabilities/runner.py`：ConnectionError/OSError 等降级为 `CapabilityResult.fail`；`CancelledError` 单独传播或按任务取消语义处理。
- `common/websocket/base_handler.py`：有界队列、QueueFull backpressure、配置读取。
- `sales_bot/websocket/base_sales_handler.py`：移除混合捕获中的 `CancelledError`。
- `sales_bot/websocket/enhanced_handler.py`：`_response_task` 检查/赋值加 `asyncio.Lock`。
- `presentation_coach/websocket/presentation_handler.py`：移除 `next(iter(connections.values()))` 错误回退。
- `sales_bot/websocket/components/tts_component.py`：按 sample_rate/bytes_per_sample/channels 计算时长。

验收：新增/更新单元测试覆盖异常降级、取消传播、QueueFull、并发任务、连接隔离、24kHz TTS 时长。

#### PR-1B Backend correctness/performance quick wins

覆盖：Q-03、Q-04、Q-05、Q-07、Q-29。

- `presentation_coach/services/feedback_service.py`：TTL 清理、max_sessions、disconnect clear 防线。
- `sales_bot/services/bot_service.py`：确认未引用后标记 deprecated/移出 active router；如不能删除，至少 active_sessions 仅存元数据 + TTL cleanup。
- `agent/capabilities/knowledge_retrieval.py`：`search_single` fallback 使用 `asyncio.gather(return_exceptions=True)` 并保持结果排序。
- `evaluation/services/staged_evaluation.py`：用 trigger/start/end turn 或真实 history slice 替代 `stage_number * 2`。
- 4 处 `print()`：替换 logger 或 CLI 明确注释豁免。

验收：内存 TTL 测试、并行 fallback 延迟/错误聚合测试、阶段切分测试、死代码引用扫描、ruff no print。

#### PR-1C Practice live UX

覆盖：UX-01、UX-02、UX-03、UX-06、UX-09。

- `use-practice-recording-hotkeys.ts`：仅在录音热键 scope 内拦截空格；输入框/滚动场景不拦截。
- `practice/[sessionId]/page.tsx`：计时器用绝对开始时间；移除 `isStartingRef` 300ms 死区；自动滚动仅在用户接近底部时触发。
- `use-practice-websocket.ts`：消息去重 Set 跨重连保留窗口/LRU，避免重复欢迎消息。

验收：Vitest 覆盖热键 target、重连计时、快速切换录音、用户上滚不被强制回底、重连去重。

#### PR-1D Report/replay/admin/login UX quick wins

覆盖：UX-05、UX-07、UX-08、UX-10、UX-11、UX-13、UX-14、UX-15、UX-16。

- `replay/page.tsx`：messageRefs Map 替代 `querySelector`。
- `admin/page.tsx`：移除装饰性搜索或实现真实卡片过滤；首选移除。
- `login/page.tsx`：密码可见性切换；“记住我”先接入前端偏好或后端 session TTL 配置，不得伪保存。
- `dashboard/page.tsx`：降级 section label 映射为用户可懂文案。
- 历史删除：二次确认或 undo toast。
- `report/page.tsx`、`replay/page.tsx`：抽取 `validateRetryEntry` / `useRetrySession`；高光 localStorage 添加 schema_version。

验收：RTL/Vitest 覆盖每个用户动作；无非功能 UI；schema mismatch 安全回退。

#### PR-1E KB lock 与 Prompt 安全

覆盖：Q-26、Q-28。

- `sales_bot/websocket/router.py`：连接时重新解析 effective policy，不单信 snapshot。
- `prompt_templates/renderer.py`：模板变量预过滤/转义，保留 LLM prompt 格式；为用户输入变量建立 allowlist/escape helper。

验收：snapshot 被篡改时仍强制 KB lock；恶意 Jinja/HTML payload 不执行模板控制结构。

#### PR-1F 增长低风险首批

覆盖：G-02、G-05，部分 G-03。

- 历史得分趋势：后端复用 `history_service` 返回最近 N 次同场景得分；报告页展示轻量趋势与“相比上次”。
- PPT 进度记忆：新增 `UserPresentationProgress` 或复用 session runtime snapshot，保存 `last_page_number`；Practice 创建/恢复提示继续上次。
- 练后推荐先做规则引擎契约，不做 ML：基于弱项维度生成下一次训练入口。

验收：趋势数据只使用 completed/evaluable；PPT 进度只读当前用户；推荐解释基于真实分数和规则版本。

### Phase 2：架构边界与重复逻辑收敛（第 2-4 周）

覆盖：Q-01、Q-14、Q-15、Q-16、Q-17、Q-18、Q-19、Q-21、Q-22、Q-24、Q-25、UX-04、UX-12、G-01、G-04、G-06、G-07、G-09。

1. **common 反向依赖治理（Q-01）**
   - 先生成 import graph 和防回归测试。
   - 新建 `backend/src/orchestration/practice/` 或顶层 `api/practice_orchestration`，迁移需要调用场景服务的编排逻辑。
   - `common/` 只保留协议、DTO、通用 helpers，不导入场景实现。
   - `kb_lock_guard.py` 中 StepFun 具体知识检索移入 `sales_bot/` 或通过协议注入。

2. **API response helper 增量统一（Q-14）**
   - 先建立 `common.api.response` contract tests。
   - 按 endpoint family 迁移 touched modules，不做一次性全量替换。
   - 对历史前端兼容结构加 adapter tests。

3. **practice helper 去重（Q-15）**
   - 提取 `common/services/practice_helpers.py` 或 orchestration helper。
   - `practice.py` 与 `practice_session_service.py` 只调用同一实现。

4. **类型与异常治理（Q-16、Q-17）**
   - 不全仓一次性 strict；按核心文件分批增加返回类型和具体异常。
   - 先处理无 `noqa` 的用户-facing broad except；保留妥协必须有原因注释。

5. **main.py 拆分（Q-18）**
   - 提取 `app_factory.py`、`routes.py`、`lifespan.py`、`middleware_config.py`、`health_routes.py`。
   - `main.py` 目标 < 200 行；app 创建行为不变。

6. **VoiceRuntimePolicyService 拆分（Q-19）**
   - 提取 `ToolPolicyResolver`、profile/agent/persona merge 子函数。
   - KB lock/network access 判断只保留单一 truth source。

7. **PresentationAIPolicy Result 模式（Q-21）**
   - `ValueError` 转 `Result.fail`；调用方统一处理。

8. **真实健康检查（Q-22）**
   - health payload 区分 liveness/readiness；DB 为首个 critical dependency。
   - Redis/Chroma/ASR/TTS 先作为 optional dependency，不直接引发误判，配置决定 critical。

9. **ASR fallback 与 cache LRU（Q-24、Q-25）**
   - ASR provider chain：Alibaba -> Local Streaming -> Browser handoff 指令。
   - Redis memory fallback 加 LRU + `fnmatch` glob。

10. **报告页拆分与结束过渡（UX-04、UX-12）**
    - 先拆纯展示组件，再并发请求 highlights/knowledge check/replay anchors。
    - Session terminal 显示 5 秒过渡层，可立即查看/留在当前页。

11. **首批增长基础设施（G-01、G-04、G-06、G-07、G-09）**
    - 成就徽章：规则表 + user_achievement + dashboard/report 展示。
    - 高光后端持久化：CRUD + 当前用户权限 + schema version；分享链接另起小切片。
    - 通知基础设施：Notification model/list/read API + dashboard bell。
    - AI 教练触达：复用历史弱项，生成 `ai_coach` notification，不发外部推送。
    - 用户目标：goal presets + current progress；避免与已有固定周目标冲突，先作为可配置目标。

### Phase 3：业务策略配置化与中长期体验（第 4-8 周）

覆盖：Q-20、Q-23、Q-27、Q-30、UX-17、UX-18、G-08、G-10。

1. **PPT 评分算法重构（Q-20）**
   - 先由产品/教研确认评分规则；落入 `scoring.ruleset_version`。
   - logic = 要点覆盖 + 连贯性；accuracy = 唯一禁忌词种类数惩罚；completeness = 已覆盖/总要点。
   - 旧报告保留规则版本，避免历史分数重算混乱。

2. **Redis-backed rate limiter（Q-23）**
   - 内存 limiter 加锁是过渡；Redis limiter 需独立开关和本地 fallback 策略。
   - 多实例部署前必须启用 Redis backend。

3. **实时评分规则迁移（Q-27）**
   - `DEFAULT_DIMENSIONS`、`SCORING_RULES` 迁移为 DB/YAML ruleset。
   - 初始 seed migration 保持旧规则；运行时加载失败回退旧规则并告警。

4. **常量治理（Q-30）**
   - 按模块建 `constants.py`；仅稳定技术常量入代码。
   - 业务阈值迁移至配置表，不进 constants。

5. **录音状态机与时区（UX-17、UX-18）**
   - `useRecordingStateMachine` reducer；状态转换测试。
   - 相对时间改为 server timezone aware 或明确 UTC 解析，不引入重依赖优先。

6. **自适应难度（G-08）**
   - 默认 disabled；规则配置 + explainability。
   - 高风险，必须先离线回放历史分数模拟，不直接影响真实训练。

7. **企业微信分享（G-10）**
   - 独立 ADR：html2canvas/Puppeteer/服务端图片三选一；WeCom JS-SDK 安全域名与 token 策略单独评审。

### Phase 4：大型重构专项（独立授权，贯穿执行）

覆盖：Q-02、UX-04 的进一步深拆，以及大文件长期治理。

1. **StepFunRealtimeHandler 拆分（Q-02）**
   - 禁止一次性“重写”。按 outward contract 逐步拆：
     1. response/function-call 状态对象；
     2. 上游 WS 连接/心跳；
     3. 音频输入输出；
     4. KB lock / grounding 决策；
     5. tool call routing；
     6. feedback arbitration；
     7. recovery/resume。
   - 每拆一块，先写 payload snapshot tests，确保前端协议不变。
   - 目标：主 handler < 1500 行；组件有单测。

2. **报告页后续深拆**
   - 已在 Phase 2 拆展示组件后，再拆 data hooks 和 report view model。
   - 目标：page 容器 < 500 行；每个 section 独立测试。

## 5. 无遗漏覆盖矩阵

### 5.1 代码质量问题 Q-01..Q-30

| ID | 审计范围 | 落地阶段 | 处理方式 | 验收证据 |
| --- | --- | --- | --- | --- |
| Q-01 | `common/` 反向依赖上层场景模块 | Phase 2 | 新增 orchestration/protocol，迁移反向依赖 | import graph 防回归 + route/service contract tests |
| Q-02 | `sales_bot/websocket/stepfun_realtime_handler.py` 4842 行 | Phase 4 | 按状态/连接/音频/KB/tool/feedback/recovery 分块拆 | payload snapshot + websocket integration |
| Q-03 | `presentation_coach/services/feedback_service.py` 内存状态无 TTL | Phase 1B | TTL、max_sessions、disconnect clear、清理任务 | TTL/容量/异常断开单测 |
| Q-04 | `sales_bot/services/bot_service.py` 死代码/active_sessions 泄漏 | Phase 1B | 删除/归档或 TTL 元数据化 | 引用扫描 + session cleanup tests |
| Q-05 | `agent/capabilities/knowledge_retrieval.py` KB fallback 串行 | Phase 1B | `asyncio.gather` 并行 fallback | 延迟/错误聚合测试 |
| Q-06 | `base_sales_handler.py` TTS 全量缓冲 | Phase 2/专项 | chunk 协议设计 + 前端兼容；legacy 分阶段启用 | WS chunk contract + audio playback tests |
| Q-07 | `evaluation/services/staged_evaluation.py` 固定 2 轮切分 | Phase 1B | trigger/history based slice | 多轮/缺 trigger 测试 |
| Q-08 | `agent/capabilities/runner.py` 异常捕获不足 | Phase 1A | ConnectionError/OSError 降级，CancelledError 语义明确 | capability failure tests |
| Q-09 | `common/websocket/base_handler.py` 无界队列 | Phase 1A | maxsize + backpressure | QueueFull/DoS simulation |
| Q-10 | `base_sales_handler.py` CancelledError 捕获不当 | Phase 1A | 单独 `except CancelledError: raise` | cancellation propagation tests |
| Q-11 | `enhanced_handler.py` `_response_task` 竞态 | Phase 1A | async lock 原子检查赋值 | 并发双消息测试 |
| Q-12 | `presentation_handler.py` active websocket 错误回退 | Phase 1A | 找不到 session 返回 None | cross-session isolation tests |
| Q-13 | `tts_component.py` duration 公式错误 | Phase 1A | sample_rate/bit depth/channels 公式 | 16k/24k PCM 测试 |
| Q-14 | 全项目 API response helper 重复 | Phase 2 | endpoint family 增量迁移 | response envelope contract tests |
| Q-15 | `practice.py` 与 service helper 重复 | Phase 2 | 提取共享 helper | helper parity tests |
| Q-16 | 全项目类型提示不足 | Phase 2+ | 核心文件分批补返回类型 | mypy/pyright scoped baseline |
| Q-17 | 全项目 broad `except Exception` | Phase 2+ | 先无 noqa 用户-facing，保留需注释 | ruff BLE001 scoped check |
| Q-18 | `backend/src/main.py` 899 行 | Phase 2 | app/routes/lifespan/middleware 拆分 | `/health` + route registration tests |
| Q-19 | `voice_runtime_policy.py` 750 行方法 | Phase 2 | `ToolPolicyResolver` + 子方法 | policy matrix unit tests |
| Q-20 | PPT 评分算法缺陷 | Phase 3 | 配置化 ruleset + 版本化评分 | scoring rules tests + old report compatibility |
| Q-21 | `presentation_ai_policy_service.py` 抛 ValueError | Phase 2 | 统一 Result.fail | invalid scope/session tests |
| Q-22 | 静态 health payload | Phase 2 | liveness/readiness + dependency checks | DB down returns degraded/503 tests |
| Q-23 | 内存 rate limit 多实例失效 | Phase 3 | Redis backend + lock fallback | redis/memory concurrency tests |
| Q-24 | ASR 无 provider fallback | Phase 2 | Alibaba -> local -> browser handoff | provider failure chain tests |
| Q-25 | Redis memory fallback 无 LRU / pattern 错 | Phase 2 | LRU + fnmatch glob | eviction/pattern tests |
| Q-26 | KB lock 可被 snapshot 绕过 | Phase 1E | 连接时重算 effective policy | tampered snapshot tests |
| Q-27 | realtime scoring 规则硬编码 | Phase 3 | ruleset 配置化 + seed | config load/fallback tests |
| Q-28 | PromptRenderer autoescape=False 注入风险 | Phase 1E | 变量 escape/allowlist | malicious template input tests |
| Q-29 | 4 处 print | Phase 1B | logger 或 CLI 豁免注释 | ruff/rg no print |
| Q-30 | 魔法数字分散 | Phase 3 | 稳定常量集中，业务阈值配置化 | rg + config validation tests |

### 5.2 用户体验问题 UX-01..UX-18

| ID | 场景 | 落地阶段 | 处理方式 | 验收证据 |
| --- | --- | --- | --- | --- |
| UX-01 | 空格键热键阻止页面滚动 | Phase 1C | scope guard / 不在输入与滚动场景拦截 | hotkey tests |
| UX-02 | 重连后计时器重置 | Phase 1C | 绝对开始时间计算 | reconnect timer tests |
| UX-03 | `isStartingRef` 300ms 死区 | Phase 1C | 移除超时守卫，状态驱动 | rapid toggle tests |
| UX-04 | 报告页 2177 行 + 瀑布加载 | Phase 2/4 | 展示组件拆分 + 并发请求 | report loading tests |
| UX-05 | 回放 querySelector 滚动 | Phase 1D | refs Map | jump-to-message tests |
| UX-06 | 自动滚动打断阅读 | Phase 1C | near-bottom 判断 | user scrolled-up tests |
| UX-07 | admin 装饰性搜索 | Phase 1D | 移除或真实过滤 | admin page tests |
| UX-08 | 登录密码可见性/记住我缺失 | Phase 1D | show password + remember preference | login tests |
| UX-09 | 重连重复欢迎消息 | Phase 1C | LRU/time-window 去重 | reconnect dedupe tests |
| UX-10 | Dashboard 降级文案生硬 | Phase 1D | section label map | degraded banner tests |
| UX-11 | 历史删除无确认 | Phase 1D | undo toast/二次确认 | delete confirmation tests |
| UX-12 | 会话结束突兀跳报告 | Phase 2 | 5 秒过渡 + 用户操作 | lifecycle tests |
| UX-13 | 登录密码可见性/记住我重复项 | Phase 1D | 与 UX-08 合并执行 | 同 UX-08 |
| UX-14 | 报告页 retry handler 重复 | Phase 1D | `validateRetryEntry` | retry validation tests |
| UX-15 | 回放页 retry hook 重复 | Phase 1D | `useRetrySession` | report/replay parity tests |
| UX-16 | 高光 localStorage 无 schema | Phase 1D | schema_version + safe migration | schema mismatch tests |
| UX-17 | 录音状态机复杂 | Phase 3 | `useRecordingStateMachine` reducer | state transition tests |
| UX-18 | 相对时间时区偏差 | Phase 3 | UTC/timezone-aware formatting | timezone tests |

### 5.3 用户粘性建议 G-01..G-10

| ID | 功能 | 落地阶段 | 处理方式 | 验收证据 |
| --- | --- | --- | --- | --- |
| G-01 | 成就徽章系统 | Phase 2 | Achievement/user_achievement + 规则配置 + dashboard/report | unlock/idempotency/display tests |
| G-02 | 历史得分趋势对比 | Phase 1F | 最近 N 次同场景趋势接口 + report chart | evaluable-only trend tests |
| G-03 | 练后智能推荐 | Phase 1F/2 | rules engine + report/dashboard CTA | recommendation explainability tests |
| G-04 | 高光后端持久化与教练分享 | Phase 2 | CRUD + current-user + share token 二期 | permission/share TTL tests |
| G-05 | PPT 演练进度记忆 | Phase 1F | progress model + continue prompt | own progress tests |
| G-06 | 应用内通知 | Phase 2 | Notification model/API + dashboard bell | unread/read tests |
| G-07 | AI 教练主动触达 | Phase 2 | 基于真实训练数据生成 ai_coach notification | trigger/template tests |
| G-08 | 个性化难度自适应 | Phase 3 | 默认 disabled + rules + simulation | offline simulation + opt-in tests |
| G-09 | 练习目标设定与追踪 | Phase 2 | user_goals + presets + dashboard progress | progress/update tests |
| G-10 | 企业微信分享 | Phase 3/4 | 独立 ADR + WeCom JS-SDK/图片方案 | token/domain/share tests |

## 6. 关键依赖与执行顺序

1. **先稳定，再增长**：Q-03/Q-08/Q-09/Q-10/Q-11/Q-12/Q-13 必须先于实时体验新增能力。
2. **先规则版本，再改评分**：Q-20/Q-27 必须先有 ruleset 版本与回退机制，避免历史报告口径混乱。
3. **先通知基础，再 AI 教练**：G-06 是 G-07 的基础；AI 教练不能直接写页面文案绕过模板配置。
4. **先高光 schema，再后端迁移**：UX-16 为 G-04 铺路。
5. **先 characterization tests，再拆大文件**：Q-02/Q-18/UX-04 都必须测试先行。
6. **先 API 契约，再前端消费**：趋势、推荐、通知、目标、成就、PPT 进度都需 contract tests。

## 7. 风险与缓解

| 风险 | 影响 | 缓解 |
| --- | --- | --- |
| common 迁移破坏 import 路径 | 后端启动失败 | import graph + incremental shim + contract tests |
| StepFun handler 拆分破坏 WS 协议 | 销售对练不可用 | payload snapshot + replayed fixture + feature branch |
| TTS chunk 协议前端不兼容 | legacy 模式音频失败 | 先支持双协议，旧 `tts_audio` 保留一个版本 |
| 评分算法改变历史分数 | 用户报告不一致 | ruleset_version，旧报告按旧版本展示 |
| 通知/AI 教练文案骚扰用户 | 留存反降 | 默认频控、退订/关闭、模板审核、触达上限配置 |
| Redis/rate limiter 引入环境依赖 | 本地测试失败 | memory fallback + feature flag + fake redis tests |
| 登录“记住我”涉及安全策略 | session 过长风险 | 默认关闭长时持久；最大 TTL 配置；共享设备提示 |
| 分享链接泄露训练内容 | PII/企业数据风险 | 短期 token、最小字段、访问审计、可撤销 |

## 8. 交付说明模板（后续每个 PR 必填）

每次实现后必须在 PR/最终报告附：

1. 本次新增或修改的业务功能。
2. 本次涉及的可配置项清单、默认值、读取位置、管理入口、校验规则、权限、兜底策略。
3. 保留在代码中的固定规则及原因。
4. 未做配置化的内容及原因。
5. 后续管理限制与需补充后台能力。
6. 测试覆盖：正常、缺配置、非法配置、默认值、权限、回退。
7. 运行命令与结果。
8. 回退方案。

## 9. 后续执行建议

- 如果目标是最快落地：按 Phase 1 的 6 个 PR 顺序执行，先修后端 runtime safety，再修 practice UX，再上低风险增长。
- 如果目标是并行交付：用 `$team`，按 Backend safety、Frontend practice UX、Frontend report/replay/admin/login、Growth/API、Architecture characterization 五条 lane 并行。
- 如果目标是质量优先：用 `$ralph`，每次只执行一个 PR tranche，完成测试/审查后再推进下一 tranche。


---

## 附：执行交接文件

- OMX context：`.omx/context/audit-product-remediation-20260421T024145Z.md`
- OMX PRD：`.omx/plans/prd-audit-product-remediation-20260421.md`
- OMX Test Spec：`.omx/plans/test-spec-audit-product-remediation-20260421.md`
- OMX RALPLAN：`.omx/plans/ralplan-audit-product-remediation-20260421.md`
- 版本控制副本测试规格：`docs/plans/2026-04-21-audit-product-remediation-test-spec.md`

---

## 10. RALPLAN-DR 共识审查补丁：覆盖、配置治理与延期风险承诺

本节为 `$ralplan docs/plans/2026-04-21-audit-product-remediation-plan.md` 的共识规划补丁。补丁遵循 Planner 与 Architect 推荐的 **append-only hardening patch**：不重写既有计划，不实施业务源码，只补齐计划可追踪性、配置治理、阶段偏移解释、后台管理、权限、审计、回退与验收边界。

### 10.1 审计源映射规则

为避免后续执行时发生编号漂移，所有任务 ID 均按审计原文顺序固定映射：

- `Q-01..Q-30`：对应 `项目代码审计与产品迭代建议.md` 第二章“代码质量问题与优化建议”第 1..30 条。
- `UX-01..UX-18`：对应第三章“用户体验问题与优化建议”第 1..18 条。
- `G-01..G-10`：对应第四章“用户粘性提升的迭代建议”第 1..10 条。

执行期间不得重排这些 ID 的含义；如发现审计原文描述与当前代码事实不一致，应在 tracker 中标记 `verified-not-present` 或 `changed-by-prior-work`，但不能删除对应 ID。

### 10.2 Q-01 / Q-02 / Q-06 阶段偏移说明

审计优先级将 Q-01、Q-02、Q-06 列为高优紧急，但本计划未把它们全部放入第一批直接实现，原因如下。

#### Q-01 common 反向依赖：Phase 2，而非 PR-1A

- **延期原因**：迁移 `common/api/practice.py`、`practice_session_service.py`、`kb_lock_guard.py`、`session_evidence.py` 等涉及 API 路由、会话生命周期、知识检索和评分证据链，属于跨模块架构边界迁移。若无 import graph、contract tests 与兼容 shim，容易造成启动失败或接口路径漂移。
- **Phase 1 临时防线**：禁止在 `common/` 新增对 `sales_bot/`、`presentation_coach/`、`evaluation/` 的直接运行时导入；任何新增依赖必须通过协议、DTO、service factory 或 orchestration 层承载。
- **提前触发条件**：若出现循环导入、启动失败、打包失败，或新增需求必须继续扩大 common 反向依赖，则 Q-01 提前为 Phase 1 hotfix。
- **回退策略**：迁移时必须保留旧 import path shim 一个版本；若新 orchestration 层失败，可切回旧 router/service path，并保留 import-boundary 测试防止继续恶化。

#### Q-02 StepFunRealtimeHandler 拆分：Phase 4 专项，而非第一周

- **延期原因**：`stepfun_realtime_handler.py` 是实时销售对练核心路径，承担上游 WS、音频、tool call、KB lock、feedback、resume 等职责。直接拆分 4842 行主文件的风险高于收益，必须先冻结 WebSocket payload contract、event replay fixture、function-call state snapshot。
- **Phase 1 临时防线**：第一周只允许新增 characterization tests、payload snapshot、竞态/资源防线和小型纯函数提取；不得改 StepFun 外部协议。
- **提前触发条件**：若后续功能必须改动同一区域超过 3 个职责边界，或出现协议回归/竞态生产事故，则单独开启 Q-02 RALPLAN 专项。
- **回退策略**：每次只拆一个 outward contract；保留旧 handler 调用入口；新组件可通过 feature flag 或 adapter 回切。

#### Q-06 TTS chunk 协议：Phase 2 / 专项，而非直接替换

- **延期原因**：`tts_audio_chunk` 属于 WebSocket 协议变化，后端 chunk 化必须与前端播放队列、音频证据留痕、报告/回放 duration 口径一起验证。直接替换 `tts_audio` 可能破坏 legacy 模式。
- **Phase 1 临时防线**：先修 duration 公式、取消传播、队列 backpressure；设计双协议兼容，不移除旧 `tts_audio`。
- **提前触发条件**：若 legacy TTS 首包延迟成为阻塞核心训练体验的 P0，或内存峰值导致 OOM，可提前做双协议 chunk 发送。
- **回退策略**：chunk 协议必须保留 `tts_audio` fallback；前端无法播放 chunk 时自动降级到完整音频或 browser TTS。

### 10.3 配置治理通用标准

后续任何配置项，不论来自 env、数据库配置表、规则表、模板表、前端集中配置还是后台管理页面，必须定义以下字段：

| 字段 | 要求 |
| --- | --- |
| key / name | 全局唯一，禁止 magic string 分散在业务函数中 |
| 用途 | 说明影响的业务流程、页面或安全边界 |
| 类型 | string / int / float / bool / enum / JSON schema / template |
| 默认值 | 必须有安全默认值；若默认 disabled，需说明启用条件 |
| 是否必填 | 缺失时是 fallback、禁用、拒绝启动还是拒绝保存 |
| 校验规则 | 范围、枚举、schema、模板变量、跨字段约束 |
| 生效范围 | 全局、租户、用户、场景、Agent、Persona、Presentation、Session |
| 生效时机 | 立即、下次会话、下次发布、灰度窗口、需重启 |
| 读取位置 | service/hook/module 路径，必须集中读取，不得多处复制 |
| 修改入口 | 后台页面、API、迁移 seed、env、前端设置 |
| 权限要求 | admin、教研、运营、manager、普通用户；最小权限原则 |
| 操作记录 | actor、action、before、after、version、reason、timestamp、trace_id |
| 回退机制 | 回退到上一 active version、默认值、禁用非核心能力或 fail-closed |
| 缺失兜底 | 缺配置时如何继续核心流程，如何告警 |
| 非法处理 | 保存前拒绝；运行时发现非法 active config 时回退并记录告警 |
| 停用行为 | 停用后业务逻辑如何识别，是否继续读取历史版本 |

### 10.4 后台管理、权限、审计与回退要求

所有业务可调规则（评分、推荐、徽章、通知、AI 教练触达、目标、分享、难度、自定义文案）必须优先复用现有配置/后台体系；无法复用时新增统一规则模块，不得为单功能散落新配置逻辑。

后台管理最小能力：

1. 配置列表、详情、创建、修改、启用、停用、复制版本、回滚版本。
2. 保存前 schema 校验、模板变量校验、dry-run 预览。
3. 权限分层：
   - `admin`：全量配置、启停、回滚、权限分配。
   - `教研/内容管理员`：评分 ruleset、PPT 规则、推荐规则草稿。
   - `运营`：通知模板、徽章展示、目标 preset、触达频控。
   - `manager`：只能创建/查看自己权限范围内的干预或提醒，不得改全局规则。
   - `普通用户`：只能修改个人偏好，不得影响他人。
4. 操作审计：任何配置变更必须写入 audit log，至少包含 actor、role、action、before/after、version、reason、timestamp、trace_id。
5. 回退要求：active 配置必须可回滚到上一有效版本；非法 active config 不得导致核心训练不可用。

### 10.5 安全敏感 UX 与增长功能边界

- **登录“记住我”（UX-08/UX-13）**：默认关闭长期持久；TTL 有上限；登出必须清理；管理员可禁用；共享设备提示必须用户可见；不得只保存前端 checkbox 状态形成假持久。
- **通知中心（G-06）**：必须支持 read/unread、频控、过期、退订/关闭同类提醒；模板缺失或变量缺失时不发送，不展示空壳通知。
- **AI 教练触达（G-07）**：只能基于真实 completed/evaluable 训练证据；不得编造“连续低分”等事实；需要频控、退订、解释来源和 CTA。
- **高光分享 / 企业微信分享（G-04/G-10）**：分享 token 默认短期有效、可撤销、可审计；默认不包含完整训练原文，除非用户明确选择；访问者权限和企业数据边界必须明确。
- **推荐与趋势（G-02/G-03）**：无足够样本时必须解释“证据不足”，不得用 0 分或假趋势替代。

### 10.6 评分与推荐规则版本化

Q-20、Q-27、G-03、G-08 涉及评分、推荐和难度策略，必须使用版本化 ruleset：

1. 每次报告保存 `ruleset_version`、规则来源和关键配置摘要。
2. 历史报告按生成时 ruleset 展示，不被新规则静默重算。
3. 新 ruleset 发布前必须 dry-run 最近样本，输出差异报告。
4. 非法 ruleset 不可发布；运行时发现非法 active ruleset 时回退上一有效版本并告警。
5. 推荐结果必须带 `rule_version`、`source_session_id`、`evidence_summary` 和用户可理解解释。

### 10.7 RALPLAN-DR 决策记录

- **Decision**：采用 append-only hardening patch 完善现有计划，而不是重写计划或立即实施代码。
- **Drivers**：覆盖完整性、配置治理合规、阶段风险透明。
- **Alternatives considered**：
  - 全面重排阶段：更贴近审计高优顺序，但会提高 Q-01/Q-02/Q-06 同时变更风险。
  - 拆成多份 PRD：边界更清晰，但会削弱当前“无遗漏总计划”的单一入口价值。
- **Why chosen**：现有计划已覆盖全部 ID，append-only 补丁能最小化文档 churn，同时补齐 Critic 指出的硬缺口。
- **Consequences**：正式进入实施前必须同时满足主计划与测试规格的补丁验收；任何执行模式不得跳过配置治理、权限审计和回退测试。
- **Follow-ups**：如后续要执行，应从 Phase 0 tracker 开始；Q-02、G-10、G-08 必须独立 ADR/RALPLAN 后才能进入代码。

