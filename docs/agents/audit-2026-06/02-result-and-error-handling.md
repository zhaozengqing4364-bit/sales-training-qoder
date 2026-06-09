# 错误处理与 Result 范式合规审查 (2026-06)

> 范围: `backend/src/` 全量
> 角色: 严苛架构师
> 触发: 用户要求审查宪法原则 I (用户体验永不中断) + L1/L2 错误处理规则
> 数据快照: 2026-06-03

---

## 0. 概览 (TL;DR)

| 维度 | 数值 | 评级 |
|------|------|------|
| `Result.ok / Result.fail` 总调用 | **814** 处 | — |
| 使用 `Result` 的文件 | 151 / 423 (36%) | C |
| `raise HTTPException(...)` 总数 | **112** 处 | D |
| 5xx `HTTPException` (违宪) | **3** 处 | F |
| `raise XxxError(...)` 服务层异常 | **51+** 处 (excl. schemas) | D |
| `except Exception: pass` 空吞错 | **0** 处 (已收敛) | A |
| `except Exception: # noqa: BLE001` | **23+** 处 | C |
| `print(` 真实调用 (非子串) | **0** 处 | A |
| `Result` 工具方法覆盖 | unwrap / unwrap_or / map ✓ | A |
| TTS 降级链 | aliyun → edge → browser ✓ | A |
| ASR 降级链 | aliyun(local) → provider_factories → browser handoff ⚠ 弱 | B |
| 关键外部依赖熔断 | 仅 ASR (1 处) + voice policy 监控 | D |
| 错误码规范 (`[SCREAMING_SNAKE]`) | 主干合规，**3 处**违反 (口语化) | B |
| Result 缺失但承担用户面的关键文件 | 33+ 处 (admin/, supervisor/, support/) | D |

**严苛总评: C-** — 骨架已就位，但"用户体验永不中断"的边界仍可被穿透。

---

## 1. Result 覆盖率热力图

### 1.1 全局统计

```text
已 grep 的 Result.ok: 276 处
已 grep 的 Result.fail: 507 处
出现 Result. 的非测试文件: 151 / 423
未使用 Result 的非测试文件: 272 / 423
```

### 1.2 目录维度 ASCII 可视化 (按 Result 引用文件占比)

```text
common/audio              ####################  90% ( 9/10)
prompt_templates/         ###########.........  56% ( 5/9)
presentation_coach/       ###########.........  56% (10/18)
agent/                    ##########..........  52% (13/25)
evaluation/               ##########..........  50% (10/20)
common/                   #######.............  39% (62/159)
curriculum_practice/      #######.............  38% (17/45)
curriculum_analytics/     ######..............  33% ( 1/3)
sales_bot/                ######..............  33% (17/51)
sales_trainer/            #####...............  28% ( 9/32)
training_runtime/         ####................  20% ( 1/5)
admin/                    ###.................  15% ( 6/40)
support/                  ....................   0% ( 0/6)
supervisor/               ....................   0% ( 0/4)
```

> 1 格 ≈ 5%。`common/audio` 受益于 L0/L1 强制。`admin/`, `support/`, `supervisor/` 几乎裸奔。

### 1.3 Top-15 文件 (按 `Result.` 出现次数)

| # | 文件 | 次数 | 角色 |
|---|------|------|------|
| 1 | `common/knowledge/service.py` | 49 | 向量检索/知识库 |
| 2 | `curriculum_practice/services/test_bank.py` | 43 | 题库服务 |
| 3 | `curriculum_practice/services/learning_contents.py` | 43 | 学习内容 |
| 4 | `common/knowledge/vector_store.py` | 32 | ChromaDB 适配 |
| 5 | `curriculum_practice/services/learning_progress_service.py` | 31 | 进度服务 |
| 6 | `common/conversation/highlight_review_service.py` | 29 | 复盘/亮点 |
| 7 | `agent/services/agent_service.py` | 28 | Agent CRUD |
| 8 | `evaluation/services/comprehensive_report.py` | 25 | 报告生成 |
| 9 | `common/growth/growth_service.py` | 22 | 成长值 |
| 10 | `common/analytics/history_service.py` | 20 | 历史分析 |
| 11 | `curriculum_practice/services/question_generation.py` | 18 | 题目生成 |
| 12 | `curriculum_practice/services/examiner_agents.py` | 17 | 考官 Agent |
| 13 | `common/conversation/storage.py` | 17 | 会话存储 |
| 14 | `common/analytics/release_verification_service.py` | 17 | 发布验证 |
| 15 | `agent/services/agent_persona_service.py` | 17 | Persona 关系 |

### 1.4 应当使用但未使用 Result 的关键文件 (用户面/服务层)

| 路径 | 命中风险 | 现状 |
|------|----------|------|
| `admin/api/users.py` | 21 处 `raise HTTPException` | 仅在 detail 字符串中夹带 `[CODE]`，**未返回 Result** |
| `common/knowledge/api.py` | 27 处 `raise HTTPException` | 同上 |
| `admin/api/admin.py` | 10 处 `raise HTTPException` | 多为非标 404 文案 |
| `admin/api/rag_profiles.py` | 8 处 `raise HTTPException` | 同上 |
| `agent/api/agent_personas.py` | 10 处 `raise HTTPException` | 4 处用 `result.fallback` 透传，但**先 raise** |
| `common/validation/file_validator.py` | 7 处 `raise HTTPException` | 校验层抛 400/413 |
| `common/api/training_tasks.py` | 5 处 `raise HTTPException` | — |
| `agent/api/personas.py` | 5 处 `raise HTTPException` | — |
| `support/api/runtime_status.py` | 1 处 `raise HTTPException` | — |
| `sales_bot/api/scenarios.py` | 1 处 `raise HTTPException` | — |
| `common/auth/service.py` | 3 处 `raise HTTPException` | 鉴权短路 (可豁免，但应统一错误体) |
| `supervisor/api.py`, `supervisor/service.py` | 18/0 Result | **整个模块零 Result 引用** |
| `support/` (6 文件) | 0 Result | **整个目录零 Result 引用** |
| `sales_trainer/services/material_service.py` | 31 raise | 31 处自定义异常，**未走 Result** |
| `sales_trainer/services/audio_submission_service.py` | 31 raise | 同上 |
| `sales_trainer/services/question_service.py` | 18 raise | `SalesTrainerQuestionServiceError` 全量抛 |
| `common/business_rules/validators.py` | **80 raise** | 头号抛异常大户 |
| `common/services/practice_session_service.py` | 32 raise | 练会话服务 |

---

## 2. 违规点扫描

### 2.1 `HTTPException` 状态码分布

```text
status_code=404  → 51 处
status_code=400  → 25 处
status_code=500  →  3 处  ⚠ 违宪 (HTTPException 500)
status_code=403  →  3 处
status_code=401  →  1 处
```

> 5xx 出现在 `admin/api/users.py` (2 处) + 历史 `presentation_coach/api/presentations.py.backup` (1 处，应清理)。

### 2.2 P0 违宪清单 (5xx HTTPException)

| file:line | 详情 |
|-----------|------|
| `admin/api/users.py:487` | `raise HTTPException(status_code=500, detail="[ADMIN_USER_STATS_FAILED]")` |
| `admin/api/users.py:809` | `raise HTTPException(status_code=500, detail="[ADMIN_USER_PROGRESS_FAILED]")` |
| `presentation_coach/api/presentations.py.backup:100` | `raise HTTPException(status_code=500, detail="Upload failed")` ← 已弃用备份文件，应删除 |

### 2.3 P1 错误码格式违例 (HTTPException detail 非标)

| file:line | detail | 备注 |
|-----------|--------|------|
| `sales_bot/api/scenarios.py:179` | `"Scenario not found"` | 应为 `[SCENARIO_NOT_FOUND]` |
| `admin/api/admin.py:53` | `"Filename is required"` | 应为 `[FILENAME_REQUIRED]` |
| `admin/api/admin.py:302,334` | `"Presentation not found"` | 应为 `[PRESENTATION_NOT_FOUND]` |
| `admin/api/admin.py:402` | `"Page not found"` | 应为 `[PAGE_NOT_FOUND]` |
| `admin/api/admin.py:519` | `"Talking point not found"` | 应为 `[TALKING_POINT_NOT_FOUND]` |
| `admin/api/admin.py:549` | `"Forbidden phrase is required"` | 应为 `[FORBIDDEN_PHRASE_REQUIRED]` |
| `admin/api/admin.py:617` | `"Forbidden word not found"` | 应为 `[FORBIDDEN_WORD_NOT_FOUND]` |
| `admin/api/rag_profiles.py:290,311,344,382,413` | `"RAG profile not found"` | 应为 `[RAG_PROFILE_NOT_FOUND]` |
| `common/knowledge/api.py:587` | `"Knowledge base not found"` | 应为 `[KNOWLEDGE_BASE_NOT_FOUND]` (服务层已有) |
| `agent/api/agent_personas.py:81,85,147,149,151` | `"Agent/Persona/Link not found"` | 仍以口语文案穿透 |
| `common/auth/service.py:735` | `"Development mode only"` | 仅 dev 短路 (可豁免，但建议 `[DEV_MODE_ONLY]`) |

> 112 处 `raise HTTPException` 中，**75 处 detail 不带 `[CODE]` 包裹** (74 即 raw 文案 + 1 状态码动态)。覆盖率仅 33%。

### 2.4 服务层显式 `raise` (违宪 I — 应返回 Result)

| file:line | 抛出 | 性质 |
|-----------|------|------|
| `sales_bot/services/voice_runtime_policy.py:319` | `RuntimeError("Voice policy monitor not available")` | 内部状态断言 (可豁免) |
| `sales_bot/services/voice_runtime_policy.py:606,628,1280,1289,1296` | `ValueError("Agent/Runtime profile not found")` | **用户面缺 Result** |
| `presentation_coach/services/presentation_ai_policy_service.py:108` | `ValueError(scope_result.fallback or "[INVALID_SCOPE]")` | **错误码埋在异常里** |
| `presentation_coach/services/presentation_ai_policy_service.py:557` | `ValueError(policy_result.fallback or "[SESSION_NOT_FOUND]")` | 同上 |
| `agent/capabilities/base.py:182,189,196,214` | `ValueError` (config 校验) | **用户面缺 Result** (能力层) |
| `agent/capabilities/registry.py:104,114` | `ValueError` | 能力注册校验 (可豁免) |
| `common/auth/service.py:242,245,628,632,645,657,687` | `ValueError` (WeCom SSO) | 鉴权层 (可豁免) |
| `common/knowledge_engine/evaluation.py:63,65,70` | `ValueError` | 评估用例 (可豁免) |
| `sales_trainer/schemas.py` (10 处) | `ValueError` (Pydantic validator) | **可豁免** — Pydantic 自定义校验 |
| `sales_trainer/services/question_service.py` (≥18 处) | `SalesTrainerQuestionServiceError` | **应改 Result** |
| `sales_trainer/services/exam_paper_serializers.py:20,49` | `ExamPaperSerializationError` | 同上 |
| `common/business_rules/validators.py` (80 处) | 自定义业务异常 | **宪法原则 I 红线** |
| `common/services/practice_session_service.py` (32 处) | 多种异常 | 同上 |
| `sales_trainer/services/material_service.py` (31 处) | 多种异常 | 同上 |
| `sales_trainer/services/audio_submission_service.py` (31 处) | 多种异常 | 同上 |

### 2.5 `except Exception` 大伞 (BLE001) — 23+ 处

| 文件 | 数量 | 性质 |
|------|------|------|
| `sales_bot/websocket/stepfun_realtime_upstream.py` | 11 | 上游路由器裸吞 |
| `sales_bot/websocket/components/score_processor.py` | 3 | 评分组件 |
| `sales_bot/websocket/router.py` | 2 | WS 路由 |
| `sales_bot/websocket/stepfun_realtime_policy.py` | 2 | 策略 (含 `raise` 重新抛出) |
| `sales_bot/websocket/stepfun_realtime_feedback.py` | 2 | 反馈 |
| `sales_bot/websocket/stepfun_realtime_handler.py` | 2 | handler |
| `sales_bot/websocket/stepfun_realtime_connection.py` | 1 | 连接 |
| `sales_bot/websocket/grounding_decision_pipeline.py` | 1 | KB 决策 |
| `sales_bot/websocket/session_control_adapter.py` | 1 | 会话适配 |
| `sales_bot/websocket/components/capability_processor.py` | 1 | 能力 |
| `sales_bot/services/voice_policy_monitor.py` | 2 | 策略监控 |
| `curriculum_practice/websocket/examiner_runtime.py` | 3 | 考官 runtime |
| `curriculum_practice/websocket/router.py` | 2 | WS 路由 |
| `websocket_routes.py` | 2 | 总入口 |
| `curriculum_practice/services/voice_clone.py` | 1 | 声音克隆 |
| `admin/api/knowledge_answer_config.py` | 1 | 配置 |
| `admin/api/model_configs.py` | 5 | 模型配置 |
| `admin/config_assets/import_service.py` | 1 | 资产导入 |
| `admin/config_assets/publish_after_import.py` | 1 | 发布 |
| `admin/config_bundles/lifecycle.py` | 1 | bundle 生命周期 |
| `sales_trainer/services/transcription_service.py` | 2 | 转写 |
| `sales_trainer/services/audio_submission_service.py` | 2 | 提交 |
| `agent/capabilities/knowledge_retrieval.py` | 2 | 知识检索 |
| `common/websocket/session_manager.py` | 1 | session |

> 全部以 `# noqa: BLE001` 显式豁免 ruff 规则。多数在 WS handler 边界做"快速失败 + 状态帧"，**可豁免但应记录在 trace**。
> 当前豁免**没有**统一的 `trace_id + 错误码` 注入约定。建议在 `BaseWebSocketHandler` 收口。

### 2.6 `print(` 真实调用

```text
0 处 (已完全收敛到 logger)
```

> 抽查: 旧的 `fingerprint=` 参数子串被 grep 误报，已交叉验证为 0 真调用。L0 规则彻底落地。

---

## 3. 降级链完整性

### 3.1 ASR 降级链 (`common/audio/asr_with_fallback.py`)

```text
主: AlibabaASRProvider (WebSocket qwen3-asr-flash-realtime)
  └─ retry x3 (exponential backoff 2s/4s/8s, timeout 5s)
  └─ 失败 → fallback_provider_factories (Sequence[tuple[name, factory]])
     └─ 全部失败 → browser_web_speech handoff
        Result.fail("[ASR_BROWSER_HANDOFF_REQUIRED]")  ← ASR_BROWSER_HANDOFF_CODE
```

| 槽位 | 状态 | 评价 |
|------|------|------|
| 阿里云 ASR | ✓ 接入 | 200ms 实时流 |
| 本地 ASR (funasr) | ✗ **未挂入 fallback_provider_factories** | `asr_service.py` 中 `LocalASRProvider` 仅在 dev 路径硬切换，未在工厂链注册 |
| 浏览器 ASR (web speech) | ✓ 终态降级 | `browser_fallback_provider` 注入 |
| 降级指令统一性 | ✓ 全部走 `ASR_BROWSER_HANDOFF_CODE` 常量 | 良好 |

> **降级链只有 2 段 (server → browser)**。L2 规则要求 ≥3 备选，**asr_with_fallback 不达标**。
> 关键失败码: `[ASR_CIRCUIT_OPEN]`、`[ASR_TIMEOUT]`、`[ASR_BROWSER_HANDOFF_REQUIRED]`、`[ASR_FALLBACK_PROVIDER_UNAVAILABLE]`
> 错误码 `Result.fail("[ASR_NO_RESULT]")`、`[ASR_STREAMING_ERROR]` 等 13 种 ASR_* 错误码定义在多个文件，**没有错误码中心表**。

### 3.2 TTS 降级链 (`common/audio/tts_factory.py`)

```text
主: AliyunStreamingTTS (synthesize_streaming / synthesize_to_file)
  └─ 失败 → Edge-TTS (TTSService)
     └─ 失败 → Browser TTS (客户端)
        Result.fail("[USE_BROWSER_TTS]")  ← 终态
```

| 槽位 | 状态 | 评价 |
|------|------|------|
| 阿里云流式 TTS | ✓ 主路径 | protocol 定义清晰 |
| Edge-TTS (免费) | ✓ 备用 | `tts_service.TTSService` |
| 浏览器 TTS | ✓ 终态 | `Result.fail("[USE_BROWSER_TTS]")` (6 处命中) |
| 降级指令 | ✓ 统一 | `USE_BROWSER_TTS` |
| Metrics | ✓ `_TTSMetrics` TypedDict | primary_success / fallback_success / browser_fallbacks |
| Circuit breaker | ✗ **TTS 全链无熔断** | 单点服务故障将直接打穿到 browser |

> TTS 降级链 3 段合格，但**未挂熔断器**。

### 3.3 降级指令统一性

| 指令 | 出现次数 | 用途 | 评价 |
|------|----------|------|------|
| `[USE_BROWSER_TTS]` | 6 | TTS 终态 | ✓ 统一 |
| `[USE_BROWSER_ASR]` | 17 | ASR 浏览器接管 | ✓ 统一 (注: `ASR_BROWSER_HANDOFF_CODE` 常量值与本指令不同) |
| `[USE_KEYWORD_SEARCH]` | 10 | 知识库降级 | ✓ 统一 |
| `[USE_FALLBACK_RESPONSE]` | 0 (仅 1 旧 commit 引用) | 兜底回复 | ⚠ 文档/规则列示但几乎不用 |

> `asr_with_fallback.py` 内部用 `[ASR_BROWSER_HANDOFF_REQUIRED]`，而其他服务用 `[USE_BROWSER_ASR]` — **降级指令名不统一**。前端文档需明确两者映射。

---

## 4. 错误码字典

### 4.1 唯一错误码集合 (按前缀聚合)

```text
ASR_*          : 13 个  (ASR_API_KEY_REQUIRED, ASR_CIRCUIT_OPEN, ASR_BROWSER_HANDOFF_REQUIRED, ...)
TTS_*          :  1 个  (TTS_FILE_ERROR)  ⚠ 偏少
EMBEDDING_*    :  7 个  (EMBEDDING_TIMEOUT, EMBEDDING_INIT_FAILED, ...)
LLM_*          :  9 个  (LLM_NOT_CONFIGURED, LLM_PARSE_ERROR, LLM_VALIDATION_FAILED, ...)
KNOWLEDGE_*    :  5 个
EXAMINER_*     :  8 个
HIGHLIGHT_*    :  6 个
LEARNING_*     :  4 个
QUESTION_*     :  5 个
AGENT_*        :  9 个
PERSONA_*      :  4 个
PROMPT_*       :  4 个
STEPFUN_*      :  0 个  ⚠ 完全缺失 (熔断或降级)
CHROMADB_*     :  0 个  ⚠ 完全缺失 (vector_store 抛裸异常)
USE_*          :  4 个  (USE_BROWSER_TTS, USE_BROWSER_ASR, USE_KEYWORD_SEARCH, USE_FALLBACK_RESPONSE)
[其他]         : ~40 个
```

唯一静态错误码 (严格 `[SCREAMING_SNAKE]`): **99 个** (含 f-string 模板 4 个)。

### 4.2 违例错误码 (非标 / 口语化)

| file:line | 内容 | 评价 |
|-----------|------|------|
| `presentation_coach/services/coach_service.py` | `Result.fail("Presentation not found or not ready")` | **必须改为 `[PRESENTATION_NOT_READY]`** |
| `evaluation/services/comprehensive_report.py:398` | `Result.fail("[REPORT_PROMPT_COMPILE_FAILED:EMPTY_CONTRACT]")` | 冒号分隔子码可接受，但**不严格符合 `[A-Z_]+`** |
| `evaluation/services/comprehensive_report.py:425` | `Result.fail("[LLM_ERROR:EMPTY_RESPONSE]")` | 同上 |
| `evaluation/services/comprehensive_report.py` (2) | `[LLM_VALIDATION_FAILED:EMPTY_RESPONSE]` | 同上 |
| `evaluation/services/staged_evaluation.py` (3) | `[PROMPT_CONTRACT_COMPILE_FAILED:EMPTY_CONTRACT]`、`[LLM_EVALUATION_FAILED:EMPTY_RESPONSE]`、`[LLM_VALIDATION_FAILED:EMPTY_RESPONSE]` | 同上 |
| `common/ai/llm_service.py` | `Result.fail(f"[LLM_GENERATION_ERROR:{type(e).__name__}]")` | 动态类型入码，**L2 规则不允许** |
| `evaluation/schemas.py` | `Result.fail(f"[LLM_PARSE_ERROR: {schema_class.__name__} - {str(e)}]")` | 含空格 + 短横线，**L2 违规** |
| `presentation_coach/services/presentation_report_service.py` (2) | `Result.fail(f"[PRESENTATION_REPORT_BUILD_FAILED:{exc}]")` 等 | 含原始异常文本 |
| `prompt_templates/service.py` | `Result.fail(f"[PROMPT_CONTRACT_MISSING_VARIABLES:{missing}]")` | 动态变量入码 |

> 共 **≥13 处**违反 L2 `[SCREAMING_SNAKE]` 严格规范。
> 注: 大部分属"主码:子码"复合错误，方向可接受，但**应当用结构化 `code + sub_code` 字段**而不是塞进 fallback 字符串。

### 4.3 完全缺失的错误码域

| 域 | 缺失后果 | 建议 |
|----|----------|------|
| `STEPFUN_*` | StepFun Realtime 失败无统一降级指令 (各 handler 内部处理) | 建议 `[STEPFUN_CIRCUIT_OPEN]`、`[STEPFUN_HANDOFF]` |
| `CHROMADB_*` | 向量库错误无降级链 → LLM 强行 grounding 失败 | 建议 `[VECTOR_STORE_UNAVAILABLE]` (已有) 但无 `CHROMADB_TIMEOUT` 等 |
| `REALTIME_*` | ASR/TTS 实时流降级指令 | `[REALTIME_STREAM_DROPPED]` |
| `WEBHOOK_*` | (未审计) | — |
| `RATE_LIMIT_*` | 限流触发后无 Result 降级码 | 建议 `[RATE_LIMITED]` 配合 429 |

---

## 5. 熔断器与限流

### 5.1 熔断器实现 (`common/resilience/circuit_breaker.py`)

```text
✓ CircuitBreaker (CLOSED / OPEN / HALF_OPEN) — 250 行
✓ CircuitBreakerRegistry (singleton)
✓ 失败阈值 5 / 恢复阈值 3 / 60s 超时 / half_open 探测 3
✓ on_state_change 回调
```

### 5.2 熔断器接入情况 (全仓 3 处)

| 文件 | 保护对象 | 评价 |
|------|----------|------|
| `common/audio/asr_with_fallback.py` | ASR 主链 | ✓ 标准接入 (`circuit_name="asr_service"`) |
| `sales_bot/services/voice_policy_monitor.py` | 语音策略 (内部监控) | ⚠ 监控器用，**不直接保护下游** |
| `common/resilience/circuit_breaker.py` | 定义本身 | — |

**未接入熔断器的关键外部依赖 (违宪 IV)**:

| 外部依赖 | 现状 | 风险 |
|----------|------|------|
| TTS (Aliyun / Edge) | 无熔断 | 阿里云抖动直接打穿到 browser |
| LLM (DashScope / OpenAI) | 无熔断 | LLM 限流/超时将堆到上游 |
| StepFun Realtime | 无熔断 | 实时语音双轨断流 → 静默失败 |
| ChromaDB | 无熔断 | 向量检索挂掉时 LLM 强行 grounding |
| 阿里云 Embedding | 无熔断 | 与 ChromaDB 联动放大 |
| Redis (session state) | 内部 `raise RuntimeError` | 启动期断言可豁免 |
| WeCom SSO | 无熔断 | 鉴权服务抖动会 500 |

### 5.3 限流器 (`common/rate_limit/`)

```text
✓ api_limiter.py — APIRateLimiter (per-IP / per-user, in-memory, 100/60s 默认)
✓ session_limiter.py — SessionRateLimiter (per-session, 含 cleanup task)
✓ @rate_limit 装饰器 (fastapi 集成)
```

**接入点**: 仅 `common/auth/api.py:558` 一处 (`@rate_limit(...)`)，**全栈仅 1 处接入**。
**缺失**: 几乎所有 FastAPI 路由都未挂限流 (admin / sales_trainer / agent / curriculum_practice / websocket)。

### 5.4 严重度矩阵

```text
                     circuit_breaker  rate_limit
ASR                   ✓                ✗
TTS                   ✗                ✗
LLM                   ✗                ✗
StepFun Realtime      ✗                ✗
ChromaDB              ✗                ✗
WeCom SSO             ✗                ✗
Auth (login)          ✗                ✓ (1处)
```

---

## 6. 宪法原则 I 合规检查 (用户面不得 raise)

### 6.1 范围审计

| 目录 | 严格违例 | 可豁免 (内部断言/Pydantic) | 备注 |
|------|----------|---------------------------|------|
| `sales_bot/services/` | 7 (voice_runtime_policy) | 1 (RuntimeError 启动期) | **需改造** |
| `sales_bot/websocket/` | 23+ BLE001 + 7 re-raise | 几乎全部为 WS 边界 | **可豁免但应注入 trace_id + 错误码** |
| `presentation_coach/services/` | 2 (presentation_ai_policy) | — | **需改造** |
| `presentation_coach/websocket/` | — | — | (无 raise) |
| `agent/services/` | 0 | 4 (capabilities/config) | ✓ |
| `agent/api/` | 0 (全走 HTTPException) | — | HTTPException 视为"用户面契约"，不算内部 raise |
| `common/websocket/` | 3 (session_state_service 启动断言) | 3 | ✓ 可豁免 |
| `common/auth/` | 0 raise RuntimeError, 7 ValueError, 3 HTTPException | WeCom SSO + dev 短路 | ✓ 鉴权层可豁免 |
| `common/knowledge/` | 27 HTTPException | — | 应改 Result |
| `common/business_rules/` | **80 raise** | 0 | ❌ **头号违例** |
| `common/services/practice_session_service.py` | 32 raise | — | ❌ |
| `sales_trainer/services/` (5 文件) | 31+31+18+17+13 = 110 raise | 0 | ❌ |
| `admin/api/` | 0 raise (全 HTTPException) | — | HTTPException 算契约 |
| `support/`, `supervisor/` | 0 Result, 18 raise (supervisor) | — | ❌ 完全无防护 |

### 6.2 严苛判定

> **宪法原则 I 在以下链路中可被穿透**:
> 1. `common/business_rules/validators.py` (80 raise) — 任何业务校验异常将冒泡到 500
> 2. `sales_trainer/services/*` (110+ raise) — 销售训练/考试服务大面积穿透
> 3. `support/` + `supervisor/` (0 Result) — 整个子系统无降级防线
> 4. `common/services/practice_session_service.py` (32 raise) — 核心练会话

> **可豁免的 raise**:
> - Pydantic `@field_validator` / `@model_validator` 内部 `ValueError` (schemas.py 10 处)
> - 启动期 / 配置校验 `RuntimeError` (session_state_service, voice_runtime_policy:319)
> - 鉴权 / 同步短路 `HTTPException` (auth/service.py, dev mode only)

---

## 7. `common/error_handling/result.py` 完整性

### 7.1 类结构

```text
@dataclass class Result(Generic[T])
  value: T | None = None
  fallback: str | None = None
  is_success: bool = True

  ok(value) -> Result[T]          ✓
  fail(fallback) -> Result[T]     ✓
  unwrap() -> T                   ✓  (失败时 raise ValueError)
  unwrap_or(default) -> T         ✓
  map(fn) -> Result[U]            ✓  (仅捕获 RuntimeError, ValueError)
```

### 7.2 评估

| 项 | 状态 | 备注 |
|----|------|------|
| `unwrap` 方法 | ✓ | 失败时抛 `ValueError` (非 Result.fail 码) |
| `unwrap_or` 方法 | ✓ | 标准 |
| `map` 方法 | ✓ | 但**只捕获 RuntimeError + ValueError**，漏 `KeyError/TypeError/IOError` 等 |
| `and_then` (monadic bind) | ✗ | 缺失，链式调用需嵌套 |
| `is_success` 字段 | ✓ | 显式 |
| `error_code` 字段 | ✗ | 当前 `fallback` 兼做错误码 + 用户文案，**职责混合** |
| `trace_id` / `context` 字段 | ✗ | **L0 规则 §VII 要求"所有日志含 trace_id"，但 Result 不携带** |
| missing-context 警告 | ✗ | 无任何 warning — `fail()` 接受任意 string 也不校验 |
| 文档/Docstring | ✓ | 头部含宪法引用 |

### 7.3 严苛结论

> `Result` 类**满足最小可用**，但**远未达到 L0/L1 要求**:
> 1. **错误码与用户文案混在一个字段** (`fallback`)，前端难以 i18n。
> 2. **无 trace_id 透传**，违反宪法原则 VII。
> 3. `map` 捕获异常过窄，会吞掉 `KeyError` 等。
> 4. **缺 `and_then`**，导致 4+ 层 Result 嵌套时可读性下降。
> 5. `fail()` 无验证，`""` 空串、`None` 文案均可传入。

---

## 8. 降级指令格式一致性 (L2 规则 §1.3)

### 8.1 L2 规则要求

> 降级指令必须 `[SCREAMING_SNAKE]`，且语义集中表。

### 8.2 实际使用分布

| 形式 | 数量 | 评价 |
|------|------|------|
| `Result.fail("[USE_BROWSER_TTS]")` 标准方括号 | 95%+ | ✓ |
| `Result.fail(f"[X_{type(e).__name__}]")` 动态注入类型 | 6+ | ⚠ 破坏 `[A-Z_]+` 严格匹配 |
| `Result.fail("[X:sub]")` 冒号子码 | 13+ | ⚠ 偏离 L2 |
| `Result.fail("[X] 中文文案")` 中英混排 | 1+ (`[DECRYPTION_ERROR] Empty input`) | ❌ 违例 |
| `Result.fail("[FIELD_DEPRECATED_PERSONA_CENTERED] system_prompt")` | 1 | ⚠ 应为 `[FIELD_DEPRECATED]` + 字段名上下文 |
| `Result.fail(SERVER_ERROR)` 间接常量 (值是 `[XXX_FAILED]`) | 41 | ✓ 间接合规 |
| `Result.fail("Presentation not found or not ready")` 口语化 | 1 | ❌ **直接违例** |

### 8.3 严苛结论

> 整体一致性 **B**，但 **3 类硬违例** (口语化 / 混排 / 冒号子码) 应在下一个迭代清理。

---

## 9. 严苛分级

### 9.1 P0 — 必须立即修复 (合规红线)

| 序号 | 位置 | 问题 | 行动 |
|------|------|------|------|
| P0-1 | `admin/api/users.py:487,809` | `HTTPException(500)` 违宪 | 改为 `Result.fail("[CODE]")` + 4xx 映射 |
| P0-2 | `presentation_coach/api/presentations.py.backup:100` | 备份文件含 5xx | 删除 `.backup` 文件 |
| P0-3 | `presentation_coach/services/coach_service.py` | `Result.fail("Presentation not found or not ready")` 口语化 | 改 `[PRESENTATION_NOT_READY]` |
| P0-4 | `common/business_rules/validators.py` | **80 处 raise** 直接违宪 I | 重构为 Result 或在调用层 try→Result.fail |
| P0-5 | `support/`, `supervisor/` | **0 Result 引用** | 至少关键路径 (status, lifecycle) 包 Result |
| P0-6 | `sales_trainer/services/{question,material,audio_submission,exam_paper}_service.py` | 110+ raise 业务异常 | 全部走 Result |

### 9.2 P1 — 下迭代修复 (规范层)

| 序号 | 位置 | 问题 | 行动 |
|------|------|------|------|
| P1-1 | `result.py` | 缺 `error_code` / `trace_id` 字段；`map` 异常捕获过窄 | 升级 dataclass |
| P1-2 | `evaluation/services/comprehensive_report.py` (5+) | 冒号子码 `[X:Y]` | 拆 `code + sub_code` 字段 |
| P1-3 | TTS / LLM / StepFun / ChromaDB / WeCom | 缺熔断 | 接入 `get_circuit_registry()` |
| P1-4 | 全栈 API 路由 | 限流仅 1 处 | `@rate_limit` 装饰器补齐 |
| P1-5 | ASR 降级链 | 只 2 段，缺本地 funasr | 注册 `LocalASRProvider` 进 `fallback_provider_factories` |
| P1-6 | STEPFUN_* / CHROMADB_* | 错误码缺失 | 补齐错误码字典 |
| P1-7 | `agent/api/agent_personas.py` (10 raise) | 5 处口语化 detail | 改 `[CODE]` |
| P1-8 | `admin/api/*` (10+ raise) | 大量口语化 | 同上 |

### 9.3 P2 — 中期改进 (质量层)

| 序号 | 位置 | 问题 | 行动 |
|------|------|------|------|
| P2-1 | `result.py` | 缺 `and_then` 链式 | 添加 monadic bind |
| P2-2 | 23+ `except Exception: # noqa: BLE001` | WS 边界裸吞 | 在 `BaseWebSocketHandler` 统一注入 `trace_id + 错误码` |
| P2-3 | `Result.fail` 静默接受空串 | 无校验 | fail() 增加最小长度 / 模式校验 |
| P2-4 | 错误码集中表 | 没有 `docs/error-codes.md` | 维护 registry |
| P2-5 | `Result` 文档示例 | 头注释但缺 LLM/TTS 用例 | 增补场景化示例 |

---

## 10. 关键发现 (What / Where / Risks / Next / Open)

### What
- Result 范式**已被广泛接受** (814 调用, 36% 文件覆盖)，但**关键用户面仍大量 raise** (admin/supervisor/support 几乎裸奔)。
- TTS 降级链 3 段合格；ASR 降级链只 2 段 (缺本地 funasr)。
- 错误码主干合规 (99 个 `[SCREAMING_SNAKE]`)，但**口语化违例 13+ 处**且**没有错误码中心表**。
- 熔断器**仅 ASR 接入**，TTS/LLM/StepFun/ChromaDB/WeCom 全部裸奔。
- 限流器**仅 1 处接入** (auth)，全栈 0 防护。
- `result.py` **缺 `error_code` / `trace_id` 字段**，违反宪法 VII。

### Where
- P0 修复入口: `docs/agents/audit-2026-06/02-result-and-error-handling.md` (本文件) §9.1
- 关键违例文件: `admin/api/users.py`, `common/business_rules/validators.py`, `sales_trainer/services/*`, `support/`, `supervisor/`

### Risks
1. `common/business_rules/validators.py` 80 raise 在生产异常路径会**直接 500**。
2. ChromaDB 不可用时 LLM grounding 失败 → 当前仅 1 处 `Result.fail("[VECTOR_STORE_UNAVAILABLE]")` 且无熔断。
3. StepFun Realtime 抖动无降级指令 → 销售对练静默中断。
4. `Result.fallback` 字段同时承担**错误码** + **用户文案**两职，前端 i18n 困难。
5. WS 边界 23+ BLE001 裸吞在长会话中**无法事后追溯**。

### Next
1. 建立错误码中心表 `docs/error-codes.md`，强制 lint。
2. 升级 `result.py`：拆分 `code / user_message / trace_id` 字段。
3. 接入 TTS / LLM / StepFun / ChromaDB 熔断器。
4. `admin/api/users.py` 5xx 立即下线。
5. `common/business_rules/validators.py` 逐函数改 Result。

### Open
- 是否允许"主码:子码"复合错误码 (`[LLM_ERROR:EMPTY_RESPONSE]`)？建议迁移到 `code + sub_code` 双字段。
- `Result` 是否需要引入 `Severity` 枚举 (`info / warn / error / fatal`)？影响前端展示。
- `support/`, `supervisor/` 是否属于"内部运维面"，可豁免 Result？需产品确认。
- 是否要在 FastAPI 异常处理器中**强制拒绝 5xx**？作为发布门禁。

---

## 附录 A: 抽样证据 (file:line)

| 类别 | 证据 |
|------|------|
| 814 Result.ok/fail | `grep -rn "Result\.\(ok\\|fail\)" backend/src/ \| wc -l` = 814 |
| 112 raise HTTPException | `grep -rn "raise HTTPException(" backend/src/ \| wc -l` = 112 |
| 51 状态码=404 | `grep -rE "status_code=404" backend/src/ \| wc -l` |
| 3 状态码=500 | `grep -rE "status_code=500" backend/src/ \| wc -l` |
| 0 print | `grep -rE "(^\|[^a-zA-Z_])print\(" backend/src/ \| wc -l` = 0 |
| 0 空 except | `grep -rE "except.*: *pass" backend/src/ \| wc -l` = 0 |
| 23+ BLE001 | `grep -rEn "noqa.*BLE001" backend/src/ \| wc -l` |
| 3 处熔断接入 | `grep -rln "get_circuit_registry\|circuit_breaker" backend/src/` = 3 files |
| 1 处 @rate_limit | `grep -rn "@rate_limit" backend/src/` (common/auth/api.py:558) |

## 附录 B: 严苛评分卡

```text
[Coverage]         36%  C   (151/423 文件使用 Result)
[Convention]       75%  B   (主干合规, 13+ 违例)
[Fallback Chain]   60%  C+  (TTS 3 段合格, ASR 2 段不足)
[Circuit Breaker]  10%  F   (仅 1 个外部依赖)
[Rate Limit]        5%  F   (仅 1 处接入)
[Traceability]     40%  C   (Result 无 trace_id, BLE001 裸吞)
[Result API]       65%  B-  (unwrap/unwrap_or/map 齐, and_then 缺, error_code 缺)
[Constitution I]   55%  C   (业务校验层 raise 重灾区)
─────────────────────────────────────
[Total]            43%  D+  严苛结论: 骨架可, 防线未完
```
