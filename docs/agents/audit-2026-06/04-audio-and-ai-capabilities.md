# 音频与 AI 能力 (ASR·TTS·LLM·RAG) 审查 (2026-06)

> 范围: `backend/src/common/audio/`、`backend/src/common/ai/`、`backend/src/common/knowledge/`、`backend/src/common/knowledge_engine/`、`backend/src/common/resilience/`、`backend/src/common/rate_limit/`、`backend/src/common/monitoring/`、`backend/src/common/jobs/audio_archival.py`、以及 sales_bot / presentation_coach / sales_trainer 中与语音/AI 相关的入口
> 角色: 严苛架构师
> 触发: 用户要求审查 ASR·TTS·LLM·RAG 链路完整性与宪法原则 II/IV/V/VI/VII 合规
> 数据快照: 2026-06-03

---

## 0. 概览 (TL;DR)

| 维度 | 数值 | 评级 |
|------|------|------|
| ASR Provider 实现 | 4 个 (alibaba, local qwen3-asr-flash, local_streaming paraformer, asr_with_fallback) | A |
| ASR 服务链路实际装配 | **1 个** (ConfigManager → 单 provider); `ASRServiceWithFallback` 在生产代码 0 引用 | F |
| TTS 降级链声明 | 3 级 (aliyun → edge → browser) 完整 (factory.py:194) | A |
| TTS 降级链实际调用 | 0 处 (无生产 caller) | F |
| 阿里云 TTS streaming 降级路径 | `Result.fail("[USE_BROWSER_TTS]")` 6 处, 浏览器无实测集成 | B |
| ASR 失败 → 浏览器接管 | 16 处 `[USE_BROWSER_ASR]`, 但前端无统一语音接管层契约 | C |
| StepFun 双轨模式 (realtime / legacy) | 实现完整 (`DEFAULT_VOICE_MODE=stepfun_realtime`) | A |
| StepFun API Key 加密 | **未加密** (env 直读 `os.getenv("STEPFUN_API_KEY")`) | F |
| LLM 链路 | OpenAI / Azure / Anthropic, ConfigManager + Fernet 加密 ✓ | A |
| LLM 成本埋点 | `CostTrackingHandler` 内存级; `track_llm_request` 死代码; 无 per-call 持久化 | D |
| ChromaDB 检索降级 | `kb_lock_guard` 4 状态码齐 (`blocked_no_kb/not_ready/search_failed/empty`) | A |
| `common/knowledge/` vs `common/knowledge_engine/` | 双轨并存, 互不 import, 角色混叠 | D |
| 熔断器 | 实现完整 (CLOSED/OPEN/HALF_OPEN, 阈值 5/3/60s); 仅 ASR 主 + voice_policy_monitor 真用 | C |
| 熔断覆盖矩阵 | ASR ✓ / TTS ✗ / LLM ✗ / StepFun ✗ / ChromaDB ✗ / OSS/COS ✗ | F |
| 限流 | `api_limiter` 装饰器 ✓; 进程内单例, **未挂中间件**; 仅登录接口用 | D |
| Prometheus 指标 | 9 个 ASR/TTS/LLM 指标定义, **0 个生产调用** | F |
| 音频保留 (retention) | `AUDIO_RETENTION_DAYS=30` + `AUDIO_ARCHIVAL_RETENTION_DAYS=365`; 调度器存在 | B |
| 销售训练音频 (SalesTrainer) | **零** 显式删除函数; 仅靠 retention 周期清理 | C |
| 错误码规范 | 主干 `[SCREAMING_SNAKE]` 合规; LLM fallback 路径有 pl/sql 化字符串 | B |
| 单次演练成本 < ¥1 | `MAX_COST_PER_SESSION=1.0` + warning 0.8; 阿里云 ASR ¥0.00033/s 隐含预算可控 | B |
| 宪法原则 VI (数据隐私) | 音频保留周期声明 ✓; ACL (user/admin only) 落实度需复核 | B |

**严苛总评: C-** — 骨架与降级声明完整, 但生产代码实际只走 "single provider + 浏览器" 路径, 中间链路被 `ASRServiceWithFallback` / `TTSServiceWithFallback` 单例缓存 + 无 caller 双重架空。

---

## 1. ASR 链路

### 1.1 实现拓扑

```text
common/audio/
├── asr_base.py            # ASRProvider 抽象 (stream_transcribe / transcribe_file / health_check)
├── asr_service.py         # ASRService 工厂 (ConfigManager 驱动)
├── asr_alibaba.py         # AlibabaASRProvider  (qwen3-asr-flash-realtime, ¥0.00033/s)
├── asr_local.py           # LocalASRProvider   (qwen3-asr-flash, CUDA/CPU)
├── asr_streaming.py       # LocalStreamingASRProvider (paraformer-zh-streaming, ~220MB)
├── asr_with_fallback.py   # ASRServiceWithFallback (Circuit Breaker + 重试 + 显式 fallback factories)
└── pcm_duration.py        # 工具
```

| 类 | 文件 | 行 | 行为 |
|----|------|----|------|
| `ASRProvider` | asr_base.py:13 | 61 | ABC, 三个抽象方法 |
| `AlibabaASRProvider` | asr_alibaba.py:43 | 403 | WebSocket, Manual 模式 turn_detection=null |
| `LocalASRProvider` | asr_local.py:51 | 201 | FunASR AutoModel, 200ms chunk 伪流式 |
| `LocalStreamingASRProvider` | asr_streaming.py:55 | 399 | 真正流式, cache 复用, latency tracker 埋点 |
| `ASRService` | asr_service.py:30 | 263 | ConfigManager → provider 工厂 |
| `ASRServiceWithFallback` | asr_with_fallback.py:76 | 414 | 主链 + 显式 fallback + Circuit Breaker |

### 1.2 降级链完整性矩阵

| 触发场景 | 实际降级路径 | 是否合规 (CLAUDE.md §2 ≥ 2 备选) | 证据 |
|----------|--------------|--------------------------------|------|
| `ASRService` 启动 (default `local_streaming`) | 阿里云 alibaba → 不存在 → LocalStreaming → FunASR CPU | ⚠ **单链路** (1 备选) | asr_service.py:115-128 |
| `ASRServiceWithFallback` 主降级 | 主 provider 失败 → `_try_fallback_provider_chain` → 浏览器接管 | ✗ **fallback 链空** (0 备选) | asr_with_fallback.py:118, 311-354 |
| `AlibabaASRProvider` 自身错误 | `Result.fail("[USE_BROWSER_ASR]")` 9 处 | ⚠ **无服务器备选** | asr_alibaba.py:108,158,240,244,248,378,402 |
| `LocalStreamingASRProvider` 错误 | `Result.fail("[USE_BROWSER_ASR]")` 6 处 | 同上 | asr_streaming.py:256,356,370,374,388 |
| `LocalASRProvider` 错误 | `Result.fail("[USE_BROWSER_ASR]")` 5 处 | 同上 | asr_local.py:122,172,182,186,200 |
| `ASRServiceWithFallback` Circuit Open | `Result.fail("[ASR_CIRCUIT_OPEN]")` | ✓ 有提示, 无备选 | asr_with_fallback.py:174 |

**结论**: 工厂层声明 "阿里云 → FunASR 本地" 1 条备用; 包装层 `ASRServiceWithFallback` 接受 `fallback_provider_factories` 但生产代码 (sales_bot/presentation_coach/sales_trainer) **完全不传**。CLAUDE.md §2 要求关键服务至少 2 个备选, 当前**仅 1 个真实备选** (本地 vs 阿里云互斥), 不满足"主服务 → 备用 → 客户端"三级。

### 1.3 `ASRServiceWithFallback` 空跑证据

```python
# asr_with_fallback.py:107-118
fallback_provider_factories: Sequence[tuple[str, ASRProviderFactory]] | None = None,
...
self._fallback_provider_factories = tuple(fallback_provider_factories or ())
```

`tuple(... or ())` 默认空, 任何 `ASRServiceWithFallback()` 无参构造 → `_try_fallback_provider_chain` 立即 `Result.fail(ASR_FALLBACK_PROVIDER_UNAVAILABLE_CODE)` (asr_with_fallback.py:311-312) → 浏览器接管。

**生产 0 引用** (除 `app_lifespan.py:115` 调的是 `get_asr_service()` 而非 `get_asr_with_fallback()`):

```text
src/common/audio/asr_with_fallback.py    7 处 (全在自身)
src/app_lifespan.py                      0 处 (用 get_asr_service)
src/sales_bot/...                        0 处
src/presentation_coach/...               0 处
src/sales_trainer/...                    0 处
tests/                                   5 处 (test_p0_fixes / test_asr_provider_chain / test_nfr_metrics)
```

### 1.4 失败指令统一性 (Scream Snake)

| 指令 | 来源 | 出现次数 | 规范 |
|------|------|----------|------|
| `[USE_BROWSER_ASR]` | 全部 4 个 ASR provider | 20+ | ✓ |
| `[ASR_CIRCUIT_OPEN]` | asr_with_fallback.py:174 | 1 | ✓ |
| `[ASR_BROWSER_HANDOFF_REQUIRED]` | 常量 L27, 用作 `Result.fail(ASR_BROWSER_HANDOFF_CODE)` L272 | 2 | ✓ |
| `[ASR_FALLBACK_PROVIDER_UNAVAILABLE]` | 常量 L28, L312, L354 | 3 | ✓ |
| `[ASR_NO_RESULT]` | L299, L374 | 2 | ✓ |
| `[ASR_STREAMING_ERROR]` | L303 | 1 | ✓ |
| `[ASR_TIMEOUT]` | L327 | 1 | ✓ |
| `[ASR_HEALTH_CHECK_FAILED]` | L394 | 1 | ✓ |
| `[ASR_API_KEY_REQUIRED]` | sales_trainer/paraformer_file_asr.py:63 | 1 | ✓ |
| `[ASR_FILE_URL_REQUIRED]` | 同上 L65 | 1 | ✓ |
| `[ASR_DASHSCOPE_SDK_REQUIRED]` | L69 | 1 | ✓ |
| `[ASR_PROVIDER_FAILED]` | L71 | 1 | ✓ |
| `[ASR_SUBTASK_FAILED]` | L76 | 1 | ✓ |
| `[ASR_TRANSCRIPTION_URL_MISSING]` | L79 | 1 | ✓ |
| `[ASR_RESULT_DOWNLOAD_FAILED]` | L84 | 1 | ✓ |
| `[TRANSCRIPT_EMPTY]` | L88 | 1 | ✓ |
| `[ASR_TASK_SUBMIT_FAILED]` / `[ASR_TASK_WAIT_FAILED]` / `[ASR_TASK_FAILED]` | L110/116/119 (抛异常) | 3 | ✓ |

**ASR 错误码统一性: A** — 全部 SCREAMING_SNAKE, 无口语化。

### 1.5 ASR 容量与延迟 (Constitution II 端到端 < 300ms)

- `AlibabaASRProvider.stream_transcribe`: 10s connect timeout, 5s session wait, 10s final wait (asr_alibaba.py:125,152,217)
- `LocalStreamingASRProvider`: first token 200ms, display 600ms (asr_streaming.py:62-65, 实测依据文档)
- 缺少 **`stream_transcribe` 端到端 P95 监控**; `latency_tracker` 在 asr_streaming.py:166 有埋点, 但 `track_asr_request` 全代码库 0 调用 (metrics.py:213 定义)

---

## 2. TTS 链路

### 2.1 实现拓扑

```text
common/audio/
├── tts_service.py          # TTSService (Edge-TTS 包装), ConfigManager 集成
├── aliyun_streaming_tts.py # AliyunStreamingTTS (CosyVoice, 首包 50ms, MP3@16kHz)
├── tts_factory.py          # TTSServiceFactory + TTSServiceWithFallback (降级编排)
└── pcm_duration.py         # 工具
```

| 类 | 文件 | 行 | 备注 |
|----|------|----|------|
| `TTSService` | tts_service.py:69 | 374 | Edge-TTS (Microsoft 免费), voice="zh-CN-XiaoxiaoNeural" |
| `AliyunStreamingTTS` | aliyun_streaming_tts.py:39 | 326 | DashScope CosyVoice, voices=longxiaochun 等 5 个 |
| `TTSServiceFactory` | tts_factory.py:144 | 191 | `create(provider=None)` 自动解析 runtime config |
| `TTSServiceWithFallback` | tts_factory.py:194 | 466 | 3 级降级编排 |
| `TTSProvider` enum | tts_factory.py:88 | EDGE/ALIYUN/BROWSER | ✓ |

### 2.2 三级降级链验证 (CLAUDE.md §2 强制)

```text
第 1 级 (primary):  AliyunStreamingTTS (DashScope CosyVoice)
  └ 失败/不可用 → 第 2 级
第 2 级 (fallback): TTSService (Edge-TTS, free)
  └ 失败/不可用 → 第 3 级
第 3 级 (final):    Result.fail("[USE_BROWSER_TTS]") 客户端 Web Speech API
```

代码证据 (`tts_factory.py:296-350`):

```python
# 1. 尝试阿里云TTS
if self.primary_available and self.primary_service:
    result = await self.primary_service.synthesize_streaming(...)
    if result.is_success: return result
# 2. 降级到 Edge-TTS
if self.fallback_available and self.fallback_service:
    result = await self.fallback_service.synthesize_streaming(...)
    if result.is_success: return result
# 3. 最终降级到浏览器TTS
self.metrics["browser_fallbacks"] += 1
return Result.fail("[USE_BROWSER_TTS]")
```

**三级降级声明完整: A**

### 2.3 TTS 降级链实际装配

| 调用点 | 实际走的链路 | 证据 |
|--------|--------------|------|
| `TTSServiceWithFallback.synthesize_streaming` | aliyun → edge → browser ✓ | tts_factory.py:296-350 |
| `TTSServiceFactory.create("aliyun")` | 单 aliyun (无降级) | tts_factory.py:169-177 |
| `TTSServiceFactory.create("edge")` | 单 edge (无降级) | tts_factory.py:178-183 |
| `TTSServiceFactory.create("browser")` | **抛 `ValueError`** (L186) | tts_factory.py:184-189 |
| `AliyunStreamingTTS` 内部 `synthesize_streaming` 失败 | `Result.fail("[USE_BROWSER_TTS]")` 单点返回 | aliyun_streaming_tts.py:148 |
| `TTSService` `synthesize`/`synthesize_streaming`/`synthesize_to_file` 失败 | `[USE_BROWSER_TTS]` | tts_service.py:198,283,315 |

**TTS 实际降级触发: 0 次生产调用** (grep `TTSServiceWithFallback|get_tts_service_with_fallback` 在 `src/` 唯一命中是 `tts_factory.py` 自身 + `admin/api/model_configs.py:225` 调 `reset_tts_service_with_fallback()` 仅用于管理后台热重置)。

销售对练 StepFun 走的是**原生 WebSocket 音频流** (`stepfun_realtime_handler._connect_upstream` 直连 `wss://api.stepfun.com/v1/realtime`, 1106-1115 行), 完全跳过 `TTSServiceWithFallback`; PPT 演练 `presentation_coach` 走的是 `tts_service.synthesize_to_file` 简单路径 (无降级编排)。

### 2.4 TTS 配置加载 (CLAUDE.md §7 优先级: runtime DB > env > default)

| Env 变量 | 来源 | 实际生效处 |
|----------|------|------------|
| `TTS_PROVIDER` | env, factory.py:166 fallback | ✓ `aliyun` 默认 |
| `TTS_VOICE` | env (config.py:112), ConfigManager `model_name` (config_manager.get_effective_config L320-328) | ⚠ **env 与 DB 优先级倒置**: config.py:112 用 `os.getenv` 直接读 env, 跳过 ConfigManager |
| `TTS_SAMPLE_RATE` | **未读取**; `tts_service.py:82` 硬编 `self.default_sample_rate` 仅在 `aliyun_streaming_tts.py:83` (16kHz 硬编) | ✗ |
| `TTS_TIMEOUT` | **未读取**; Edge-TTS 与 Aliyun SDK 各自内部 timeout | ✗ |
| `TTS_CONNECTION_POOL_SIZE` | **未读取**; 进程内单例, 无连接池 | ✗ |
| `TTS_ENABLE_WARMUP` | **未读取**; `app_lifespan.py` 0 处调 `preload_asr_service` 之外的 TTS 预热 | ✗ |
| `TTS_FALLBACK_CHAIN` | **未读取** | ✗ |

**配置覆盖矩阵 (CLAUDE.md §7 要求)**: **4/7 关键 env 实际未消费**, `tts_factory.py:_resolve_tts_runtime_config` (L31-59) 走的仅是 `ConfigManager.get_default_config(ModelType.TTS)`, 没有 fallback 到 env 链。

### 2.5 TTS 降级指令出现位置

```text
tts_factory.py:350   synthesize_streaming 终态
tts_factory.py:417   synthesize_to_file 终态
aliyun_streaming_tts.py:148   streaming exception
aliyun_streaming_tts.py:183   synthesize_to_file 异常 → [TTS_FILE_ERROR]  (非降级指令)
tts_service.py:198   synthesize 异常
tts_service.py:283   synthesize_streaming 异常
tts_service.py:315   synthesize_to_file 异常
```

**统计**: `[USE_BROWSER_TTS]` 6 处 (5 真实降级 + 1 重复), `[TTS_FILE_ERROR]` 1 处 (语义独立)。

---

## 3. StepFun Realtime (双轨语音)

### 3.1 模式路由

`voice_runtime_profile.py` 维护两种模式:
- `legacy` — 走 `presentation_handler` / `simple_handler` ASR+TTS 编排
- `stepfun_realtime` — 直连 `wss://api.stepfun.com/v1/realtime` (LLM+ASR+TTS 端到端)

**`DEFAULT_VOICE_MODE=stepfun_realtime`** (voice_runtime_policy.py:1070) → 默认全走 StepFun。

### 3.2 配置实际加载 (agent/models.py:265-296)

```python
class VoiceRuntimeProfile(Base):
    voice_mode = Column(String(32), default="stepfun_realtime")
    model_name = Column(String(100), default="step-audio-2")
    voice_name = Column(String(100), default="qingchunshaonv")
    ...
    # ⚠ 没有任何 api_key_encrypted 列
```

**StepFun API Key 完全未入库加密**: `stepfun_realtime_handler.py:291` `self._stepfun_api_key = os.getenv("STEPFUN_API_KEY", "")` 直接从环境变量读, 落到 `common.db.models.ModelConfig` (`common/ai/models.py`) 的 `api_key_encrypted` 字段**只服务于 LLM/ASR/TTS/Embedding, 不服务于 StepFun**。

合规对比:
- LLM/ASR/TTS/Embedding → ConfigManager + Fernet (`MODEL_CONFIG_ENCRYPTION_KEY`) ✓
- StepFun → env 直读 ✗

**评级 F** (与 LLM/TTS 不对称, 违背"敏感配置必须加密"宪法原则 VII 子要求)。

### 3.3 StepFun 自身降级

```text
StepFun WebSocket 断开
  └ stepfun_realtime_connection.py 抛 [SESSION_LIFECYCLE_FAILED] / STEPFUN_API_KEY missing
  └ 无自动回退到 legacy ASR + tts_factory.TTSServiceWithFallback
```

`stepfun_asr_fallback.py` (sales_bot/websocket/components/) 提供 `ASR_FALLBACK_REQUIRED_ERROR_CODE`, 但 grep 显示在 `stepfun_realtime_handler` 主流程中**没有调用 `tts_factory` 的回退链**, 也就是 StepFun 自身断流后, 客户端只收到 status="disconnected" 事件, 没有 server-side 把会话切到 legacy 模式的代码。

### 3.4 模型白名单与默认

| Env 变量 | 默认 | 实际加载 | 校验 |
|----------|------|----------|------|
| `STEPFUN_REALTIME_URL` | `wss://api.stepfun.com/v1/realtime` | stepfun_realtime_handler.py:292 ✓ | — |
| `STEPFUN_REALTIME_MODEL` | `step-audio-2` (env) / `step-audio-2` (DB default) | handler.py:295, voice_runtime_policy.py:1076 | 仅 string, 无 enum 校验 |
| `STEPFUN_REALTIME_VOICE` | `qingchunshaonv` | handler.py:296, voice_runtime_policy.py:1077 | 仅 string |
| `STEPFUN_REALTIME_TEMPERATURE` | `0.7` (env) | handler.py:297 | _to_float 限幅 [0, 2] |
| `STEPFUN_REALTIME_OUTPUT_SAMPLE_RATE` | `24000` (env) / `24000` (DB) | handler.py:306 | _to_int min=8000 |
| `STEPFUN_REALTIME_INPUT_AUDIO_FORMAT` | `pcm16` | handler.py:300 | 无校验 |
| `STEPFUN_REALTIME_OUTPUT_AUDIO_FORMAT` | `pcm16` | handler.py:303 | 无校验 |
| `STEPFUN_REALTIME_INPUT_AUDIO_FORMAT` | `pcm16` | profile 默认值 | — |
| `STEPFUN_REALTIME_TEMPERATURE` 默认 | `0.7` | profile 默认值 | 上下界 0-2 ✓ |

**StepFun 配置加载: A (除加密缺失)**

---

## 4. LLM 链路

### 4.1 目录与实现

```text
common/ai/
├── __init__.py
├── config_manager.py        # ConfigManager 单例, db+env 双层, 优先级: DB > env
├── encryption.py            # KeyEncryption (Fernet), encrypt_api_key/decrypt_api_key
├── models.py                # ModelConfig SQLAlchemy 模型, ModelType/ModelProvider 枚举
├── endpoint_policy.py       # base_url 必需性策略
├── llm_service.py           # LLMService (LangChain, OpenAI/Azure/Anthropic)
├── embedding_service.py     # EmbeddingService (OpenAI/DashScope)
└── schemas.py               # Pydantic schemas
```

### 4.2 LLM Service 装载链

```text
1. 显式 config (LLMService(config=...))
2. ConfigManager.get_effective_config(ModelType.LLM)
   ├ DB default ModelConfig → decrypt_api_key (Fernet) → 解密
   └ 失败/缺失 → ConfigManager.get_env_fallback(LLM)
       ├ LLM_API_KEY / OPENAI_API_KEY
       ├ LLM_BASE_URL / OPENAI_BASE_URL
       ├ LLM_MODEL / OPENAI_MODEL
       └ extra_config.temperature/timeout
3. 装载 LangChain 客户端
   ├ provider=azure       → AzureChatOpenAI
   ├ provider=anthropic   → ChatAnthropic (fallback to ChatOpenAI 兼容)
   └ provider=openai/其他 → ChatOpenAI (OpenAI 兼容, 含 DeepSeek/Qwen 等)
```

**配置加载链: A** (CLAUDE.md §7 三级优先级完整, DB > env > 代码默认)

### 4.3 加密链路

```text
MODEL_CONFIG_ENCRYPTION_KEY (env, Fernet base64 32B key)
  └ KeyEncryption._fernet = Fernet(key.encode())
      ├ encrypt(plain) → Result[bytes]  (encryption.py:58)
      └ decrypt(cipher) → Result[str]  (encryption.py:78)
  └ ConfigManager.get_decrypted_api_key(config) → Result[str]
  └ 失败: warn + fallback to env_fallback
```

`MODEL_CONFIG_ENCRYPTION_KEY` 缺失时 `KeyEncryption.__init__` 抛 `ValueError("MODEL_CONFIG_ENCRYPTION_KEY is required")` (encryption.py:50) → **启动即硬失败**, 不会静默放过。✓

**LLM 加密链: A** (除 STEPFUN_KEY 之外, 见 §3.2)

### 4.4 LLM 错误码

| 指令 | 来源 | 计数 |
|------|------|------|
| `[LLM_NOT_CONFIGURED]` | llm_service.py:435 | 1 |
| `[LLM_GENERATION_ERROR:{ExcType}]` | llm_service.py:555 | 1 (动态前缀) |
| `[LLM_EVALUATION_FAILED]` | llm_service.py:656 (fallback or) | 1 |
| `[REPORT_GENERATION_FAILED]` | llm_service.py:778 | 1 |

**LLM 错误指令: A** (全部 SCREAMING_SNAKE)

### 4.5 LLM 成本埋点 (宪法原则 V < ¥1/次)

| 埋点 | 位置 | 状态 |
|------|------|------|
| `MAX_COST_PER_SESSION=1.0` (env) | common/config.py:134 | ✓ |
| `COST_WARNING_THRESHOLD=0.8` | common/config.py:135 | ✓ |
| `CostTrackingHandler` (LangChain callback) | llm_service.py:81-105 | ✓ 内存累加 |
| `self.session_costs[session_id]` 累加 | llm_service.py:466-468 | ✓ |
| Budget warning at ¥0.8 (logger.warning) | llm_service.py:494-498 | ✓ |
| `_record_runtime_event` "llm_session_cost_budget_warning" | llm_service.py:499-517 | ✓ 事件 |
| `track_llm_request(...)` Prometheus 导出 | common/monitoring/metrics.py:201-210 | ✗ **0 生产调用** (grep 全代码库, 仅 metrics.py 定义处) |
| `cost_per_1k_tokens` 默认 `0.00005` (¥0.00005) | llm_service.py:138 | ✓ 但**单位语义模糊** (注释 "¥0.05/1K tokens" 矛盾, 实际 0.00005) |

**成本埋点缺口**:
1. `track_llm_request` 死代码, Prometheus 拿不到 LLM 调用次数/token/延迟
2. `session_costs` 仅在内存 (`LLMService.session_costs: dict[str, float]`), 服务重启即清零, 无法跨 session 累计
3. 没有 per-call 持久化事件 (`llm_cost_tracking_coarse_session_total` 仅是 summary, LLM_RUNTIME_EVENT_INVENTORY 自承)
4. StepFun 双轨的 LLM 调用完全不走 `LLMService`, 0 token 记录
5. `cost_per_1k_tokens` 单位混乱: 代码 `0.00005` 注释写 `¥0.05/1K tokens`, 测试断言可能与 prod 不一致

### 4.6 LLM 调用覆盖矩阵

| 入口 | provider | 成本埋点 | Prometheus |
|------|----------|----------|------------|
| `LLMService.generate` (sales_bot 评价/报告) | OpenAI/Azure/Anthropic | ✓ in-memory | ✗ |
| `LLMService.evaluate` | 同上 | ✗ (只解析返回) | ✗ |
| `LLMService.generate_report` | 同上 | ✗ | ✗ |
| StepFun upstream (`stepfun_realtime_handler._send_upstream`) | StepFun 端点 | ✗ (无 client-side token) | ✗ |
| PPT coach (`presentation_coach/services`) | ? | ? | ? |

---

## 5. RAG / ChromaDB

### 5.1 双轨目录分析

```text
common/knowledge/         17 个文件    # 知识库 CRUD / 检索 / 字典 / ingestion
common/knowledge_engine/  19 个文件    # 引擎抽象 / 评分 / 检索 / 兼容性
```

**职责对比** (高粒度):

| 维度 | `common/knowledge/` | `common/knowledge_engine/` |
|------|---------------------|---------------------------|
| 角色 | 知识库数据平面 (CRUD/文档/索引) | 检索策略平面 (重排/引擎抽象/Schema) |
| ChromaDB 直接调用 | `vector_store.py` 22k 行, `processor.py` 64k 行 | 通过 `haystack_adapter.py` |
| 内部检索函数 | `internal_searcher.py` (主) | `engine.py` 抽象入口 |
| 关键决策 | `kb_lock_guard.py` 29k 行 (grounding 决策) | `compat.py` 16k 行 (rollout mode) |
| 评分 | `retrieval_helpers.py` | `cross_encoder_reranker.py`, `reranker.py` |
| Schema | `schemas.py` 13k 行 | `schemas.py` 3k 行 |

**重叠与冲突**:
- 两侧均定义 `schemas.py` (无 import 关联)
- 两侧均定义 `reranker.py` (`common/knowledge_engine/reranker.py:8` 引用 `common.knowledge_engine.config_repo`, 完全自闭)
- 实际业务调用 grep:
  ```text
  common/knowledge.kb_lock_guard:   sales_bot/ 4 个 handler 引用
  common/knowledge.service:          knowledge/api.py / sales_bot
  common/knowledge.internal_searcher:  sales_bot 4 个 handler 引用
  common/knowledge_engine.engine:    admin/api/knowledge_answer_config.py:1552
  common/knowledge_engine.compat:     admin 唯一消费者
  common/knowledge_engine.reranker:   自闭, 0 外部引用
  common/knowledge_engine.assembler:  自闭, 0 外部引用
  common/knowledge_engine.intent_classifier:  自闭
  common/knowledge_engine.entity_resolver:    自闭
  common/knowledge_engine.retrieval_planner:  自闭
  common/knowledge_engine.evaluation:         自闭
  ```

**结论**: `common/knowledge_engine/` 内 6+ 模块**实际是孤儿代码**, 仅 `engine` / `compat` / `config_repo` / `answerability` 4 个被使用; `common/knowledge/` 是事实唯一数据平面。两个目录并存造成新成员无法快速判断 "该用哪个"。

### 5.2 KB Lock 决策流合规 (CLAUDE.md §3)

| 状态码 | 来源 | 触发条件 | 用户提示 (CLAUDE.md §3) | 实际提示 |
|--------|------|----------|------------------------|----------|
| `blocked_no_kb` | kb_lock_guard.py:613 | 锁启用 + 无 KB 绑定 | "请先完成知识库绑定" | kb_lock_guard.py:615 `_build_blocked_user_message("blocked_no_kb")` ✓ |
| `blocked_not_ready` | kb_lock_guard.py:718 | 文档未处理 | "请稍后重试" | L720 ✓ |
| `blocked_search_failed` | kb_lock_guard.py:665, 708 | 检索异常 | "请稍后重试或联系管理员" | L667 ✓ |
| `blocked_empty` | kb_lock_guard.py:479,506,627,710,720,730,754 | 检索空 | "请提供更具体的产品关键词" | L629 ✓ |
| `blocked_search_timeout` | kb_lock_guard.py:60, 711 | 检索超时 | (未在 CLAUDE.md 表) | L713 ⚠ 提示文案有但未列入"官方表" |
| `blocked_answerability` | kb_lock_guard.py:538, 548 | 答案性不足 (新) | (未在 CLAUDE.md 表) | L540 ⚠ 业务新增但未同步 CLAUDE.md |
| `coach_no_kb` / `coach_not_ready` / `coach_search_failed` / `coach_search_timeout` | kb_lock_guard.py:61-64 | coach_mode 分支 | — | — |

**KB Lock 决策流: B+** — 主路径完整, 但 `blocked_search_timeout` / `blocked_answerability` / `coach_*` 4 个状态码 CLAUDE.md §3 表未收录, 文档与代码不同步。

### 5.3 检索降级 (CLAUDE.md §3 决策流)

```text
用户发言
  └ require_kb_grounding=true?
     ├ 否 → 正常 LLM 回答 (kb_lock_guard.py 不阻塞)
     └ 是 → evaluate_kb_lock_decision()
        ├ 无 KB 绑定 → blocked_no_kb
        ├ 文档未就绪 → blocked_not_ready
        ├ 检索异常 → blocked_search_failed
        ├ 检索超时 → blocked_search_timeout
        ├ 结果空   → blocked_empty
        └ 全部通过 → 返回 grounding_context 给 LLM
```

`evaluate_kb_lock_decision` (`kb_lock_guard.py:200+`) 是唯一入口, 与 CLAUDE.md §3 完全对齐; `apply_runtime_enforcement` (`voice_runtime_policy.py:132-177`) 在会话启动时把 `require_kb_grounding=true` 时强制 `retrieval_priority=kb_only` + `enable_web_search=false` + `enable_internal_retrieval=true`, 决策链一致。

### 5.4 ChromaDB 熔断

`common/resilience/circuit_breaker.py` 提供 CircuitBreaker, 但 grep 显示:

```text
common/audio/asr_with_fallback.py  → get_circuit_registry  (ASR)
sales_bot/voice_policy_monitor.py  → 4 处  (ASR + TTS 监控用, 仅状态)
```

`common/knowledge/` / `common/knowledge_engine/` 0 处熔断器使用。

**ChromaDB / Vector Store 熔断: ✗ 缺失** — 单次向量检索阻塞或 ChromaDB OOM 会直接拖垮 stepfun upstream, 无防级联措施。

---

## 6. 熔断器 / 限流覆盖矩阵

### 6.1 CircuitBreaker 行为 (`common/resilience/circuit_breaker.py`)

| 配置项 | 默认值 | 来源 | 文件 |
|--------|--------|------|------|
| `failure_threshold` | 5 | CircuitBreakerConfig L36 | circuit_breaker.py:36 |
| `success_threshold` | 3 | L37 | circuit_breaker.py:37 |
| `timeout_seconds` | 60 (ASR 包装层) | 60 (默认) | asr_with_fallback.py:135 |
| `half_open_max_calls` | 3 | L39 | circuit_breaker.py:39 |
| 状态机 | CLOSED/OPEN/HALF_OPEN | L24-29 | circuit_breaker.py:24-29 |
| 回调 `on_state_change` | optional | L72 | circuit_breaker.py:72 |
| Registry | `get_circuit_registry()` | L295 | circuit_breaker.py:295 |

**与宪法 §IV "failure_threshold=5 / recovery_timeout=30s / half_open=3" 对比**:
- 阈值 5 ✓
- recovery 60s ⚠ (CLAUDE.md §9 说 30s)
- half_open 3 ✓

CLAUDE.md §9 的"30s 恢复间隔"与代码"60s 超时"**不一致**, 文档与代码偏差。

### 6.2 熔断覆盖矩阵 (实际启用)

| 外部依赖 | 是否熔断 | 熔断器名称 | 失败阈值 | 证据 |
|----------|----------|------------|----------|------|
| ASR 阿里云 | ✓ | `asr_service` | 5/60s/3 | asr_with_fallback.py:132-137 |
| ASR 本地 FunASR | ✗ (直接 `run_in_executor`) | — | — | asr_local.py:139, asr_streaming.py:287 |
| TTS 阿里云 | ✗ | — | — | tts_factory.py:299-316, 仅 metrics |
| TTS Edge-TTS | ✗ | — | — | tts_service.py 直接 await |
| LLM (OpenAI/Azure/Anthropic) | ✗ | — | — | llm_service.py 用 tenacity retry, 无 CB |
| StepFun Realtime | ✗ | — | — | stepfun_realtime_handler.py 上游断流靠 keepalive/auto_recover 常量 |
| ChromaDB | ✗ | — | — | vector_store.py 直接 await |
| OSS / COS | ✗ | — | — | common/oss/* 直接 aiohttp |
| Redis | ✗ | — | — | 取决于 redis 客户端 |
| Embedding (DashScope) | ✗ | — | — | embedding_service.py 直接 httpx |

**熔断覆盖: D** — 6/9 关键外部依赖无熔断, 任何单点故障将级联。

### 6.3 限流覆盖

| 限流器 | 文件 | 实现 | 部署形态 |
|--------|------|------|----------|
| `APIRateLimiter` | common/rate_limit/api_limiter.py | 装饰器 + 内存 dict | **未挂中间件** (Agent 1 已发现) |
| `SessionRateLimiter` | common/rate_limit/session_limiter.py | 装饰器 + 内存 | 同上 |

| 粒度 | 是否覆盖 | 证据 |
|------|----------|------|
| 全局 QPS | ✗ | 无全局中间件 |
| 用户级 | `scope="user"` 参数支持 | api_limiter.py:158-162 |
| IP 级 | `scope="ip"` 默认 | api_limiter.py:158 |
| 端点级 | 通过装饰器 per-endpoint | common/auth/api.py:558 (login 装饰器) |

**实际使用**: grep `rate_limit(` 在 `src/`:
- `common/auth/api.py:558` (登录端点) — 唯一生产应用

**限流覆盖: D** — 装饰器已实现但仅登录 1 个端点; 语音 WebSocket、admin API、API key 设置接口均无任何限流。

---

## 7. 监控 / 可观测

### 7.1 Prometheus 指标定义 (common/monitoring/metrics.py)

| 指标 | 类型 | 标签 | 状态 |
|------|------|------|------|
| `http_requests_total` | Counter | method/endpoint/status | ✓ 通过 MetricsMiddleware L136 |
| `http_request_duration_seconds` | Histogram | method/endpoint | ✓ 同上 |
| `websocket_connections_active` | Gauge | scenario_type | ✗ 0 调用 (track_websocket_connection metrics.py:225) |
| `websocket_messages_total` | Counter | scenario_type/direction | ✗ 0 调用 |
| `websocket_message_duration_seconds` | Histogram | scenario_type/message_type | ✗ 0 调用 |
| `practice_sessions_total` | Counter | scenario_type/status | ✗ 0 调用 (track_practice_session metrics.py:180) |
| `practice_session_duration_seconds` | Histogram | scenario_type | ✗ 0 调用 |
| `practice_scores` | Histogram | scenario_type/score_type | ✗ 0 调用 |
| `llm_requests_total` | Counter | service/status | ✗ **0 调用** (track_llm_request L201) |
| `llm_request_duration_seconds` | Histogram | service | ✗ **0 调用** |
| `llm_tokens_total` | Counter | service/token_type | ✗ **0 调用** |
| `asr_requests_total` | Counter | status | ✗ **0 调用** (track_asr_request L213) |
| `asr_request_duration_seconds` | Histogram | — | ✗ **0 调用** |
| `tts_requests_total` | Counter | status | ✗ **0 调用** (track_tts_request L219) |
| `tts_request_duration_seconds` | Histogram | provider | ✗ **0 调用** |
| `voice_policy_rollbacks_total` | Counter | service_type/from/to | ✓ voice_policy_monitor 内部记录 |
| `voice_policy_state_changes_total` | Counter | service_type/from/to | ✓ 同上 |
| `errors_total` | Counter | service/error_type | ✗ 0 调用 (track_error L243) |
| `frontend_analytics_events_total` | Counter | event_type/status | ✗ 0 调用 |
| `situation_pack_dual_read_mismatch` | Counter | code/scope | ✗ 0 调用 |
| `application_info` | Info | version/environment | ✓ initialize_metrics L308 |

**统计**: 21 个指标定义, **13 个 AI/LLM/ASR/TTS/WS 指标 0 生产调用**; 监控骨架完整, 实际数据采集率 ~38%。

### 7.2 关键缺失指标 (CLAUDE.md §VII)

| 指标 | CLAUDE.md §VII | 实际 | 评级 |
|------|----------------|------|------|
| TTS 成功率 | "TTS 成功率" | 仅 `tts_factory.py:206-213` 内存 metrics (`primary_success`/`browser_fallbacks`), **不导出 Prometheus** | D |
| 降级次数 | (隐含) | 同上 | D |
| LLM 延迟 | "LLM 延迟" | `track_llm_request` 死代码 | F |
| KB 命中率 | "KB 命中率" | 无此指标 | F |
| Circuit Breaker 状态变更 | — | 内部 log, 不导出 | D |
| Cost 累计 | "成本 <¥1/次" | 仅内存 dict, 不导出 | D |
| ASR 端到端 P95 | "端到端 <300ms" | `latency_tracker` 内部 (asr_streaming.py:166) 不导出 | D |

### 7.3 结构化日志

- 所有 logger 调用 `get_logger(__name__)` (common/monitoring/logger.py) ✓
- `trace_id` 通过 `trace_context.normalize_trace_id` (common/monitoring/trace_context.py) 注入 ✓
- 脱敏: `log_safety_inventory.py` 提供 inventory 工具, **无统一 sanitize 调用** (grep 不到调用点)
- structlog 风格 logger 自实现, 未引入 structlog 库

**结构化日志: B** (trace_id ✓, 脱敏工具存在但未挂入 pipeline)

---

## 8. 数据隐私 / 音频生命周期

### 8.1 音频保留 (宪法原则 VI)

| 存储 | 保留期 | 清理机制 | 证据 |
|------|--------|----------|------|
| 通用练习音频 (PracticeSession.audio_url) | `AUDIO_ARCHIVAL_RETENTION_DAYS=365` 默认 | `common/jobs/audio_archival.py:AudioArchivalJob.archive_old_audio` | audio_archival.py:40-100 |
| 本地音频文件 | `AUDIO_RETENTION_DAYS=30` 默认 | `common/storage/audio.py:cleanup_old_files` | audio.py:241-281 |
| 销售训练音频 (SalesTrainerAudioSubmission) | **未声明** | **无删除函数**, 仅 transcription_service.py 通过 `transcription_service.delete_submission` ... ❌ 实际无该函数 | audio_submission_service.py 函数列表 (0 个 `def delete`) |
| 销售训练文件 URL 有效期 | `SALES_TRAINER_AUDIO_FILE_URL_EXPIRES_SECONDS=3600` | Presigned URL 短期 | audio_submission_service.py:978-997 |

**音频生命周期缺口**:
1. `audio_submission_service.py` 1036 行无 `delete_*` 方法 — 一旦用户提交, 永久保留 (除非手工调 OSS/COS)
2. `SALES_TRAINER_AUDIO_FILE_URL_EXPIRES_SECONDS=3600` 仅控制**访问 URL**, 不影响对象存储
3. OSS/COS 后端**无 lifecycle policy 同步**, 依赖应用层 `archive_old_audio` 周期
4. `AUDIO_ARCHIVAL_RETENTION_DAYS=365` 长达 1 年, 对个人语音数据偏长 (中国个保法对生物特征类建议 ≤ 必要期间)

### 8.2 访问控制 (宪法原则 VI "只能被本人和管理员访问")

| 资源 | 检查点 | 证据 |
|------|--------|------|
| `AudioSubmission` | `_submission_in_department` + `AudioSubmissionServiceError("[ACCESS_DENIED]", ..., 403)` | audio_submission_service.py:773, 352 |
| `KnowledgeBase` ACL | (待 Agent 2 复核) | — |
| WebSocket 会话 | `_submission_in_department` 校验 + JWT | — |
| StepFun session | `JWTError` / `resolve_websocket_token` | stepfun_realtime_handler.py:34-40 |

**ACL: B** (有显式 403 路径, 但需全文审计确保无遗漏)

### 8.3 合规缺口

- **生物特征 (声纹) 标签**: 系统不存储声纹特征 (仅音频字节 + 转写文本), ✓
- **审计日志**: `OperationLogService` 存在 (audio_submission_service.py:83), 但**无独立的音频访问审计**, 管理员"查看" vs "下载"未区分
- **删除权利 (GDPR/个保法)**: `AudioSubmissionService` 无 `delete_for_user` 入口, 用户无法自主删除历史演练

---

## 9. 严苛发现汇总

### 9.1 阻断性 (F 级) — 必修复

| ID | 描述 | 位置 |
|----|------|------|
| F-ASR-1 | `ASRServiceWithFallback` 生产 0 引用, 实际只走单 provider + 浏览器 | asr_with_fallback.py:118 (默认空 fallback) + 无 caller |
| F-TTS-1 | `TTSServiceWithFallback` 生产 0 引用, 降级链声明是 dead code | tts_factory.py:194-466 + 无 caller |
| F-SEC-1 | `STEPFUN_API_KEY` 未走 Fernet 加密, 违反"敏感配置加密"对称性 | stepfun_realtime_handler.py:291 + agent/models.py:VoiceRuntimeProfile |
| F-OBS-1 | `track_asr_request` / `track_tts_request` / `track_llm_request` 13 个 Prometheus 指标全代码库 0 调用 | common/monitoring/metrics.py:201-222 + 全 grep |
| F-CFG-1 | 5 个 CLAUDE.md §2 必备 TTS env (TTS_TIMEOUT / TTS_SAMPLE_RATE / TTS_CONNECTION_POOL_SIZE / TTS_ENABLE_WARMUP / TTS_FALLBACK_CHAIN) 实际未读取 | common/audio/tts_factory.py 全文 |

### 9.2 严重 (D 级) — 需修复

| ID | 描述 |
|----|------|
| D-CB-1 | ChromaDB / OSS / COS / StepFun / Embedding / LLM 6 个外部依赖无熔断, 单点故障级联 |
| D-CFG-2 | CLAUDE.md §9 写 "recovery_timeout=30s" 代码用 60s, 文档与代码偏差 |
| D-COST-1 | LLM cost 仅内存, 服务重启即清零; Prometheus 不导出 |
| D-LIMIT-1 | 限流仅登录 1 端点装饰, 全站无全局 QPS/用户级/IP 级中间件 |
| D-KNOW-1 | `common/knowledge` 与 `common/knowledge_engine` 双轨并存, 6+ 模块自闭 |
| D-SEC-2 | `audio_submission_service` 0 个删除函数, 销售训练音频无 lifecycle |

### 9.3 中等 (C 级) — 改进

| ID | 描述 |
|----|------|
| C-ASR-1 | CLAUDE.md §2 要求 ≥ 2 备选, 实际 1 备选 (本地 vs 阿里云互斥) |
| C-KB-1 | 4 个 KB Lock 状态码 (blocked_search_timeout / blocked_answerability / coach_*) 文档未同步 |
| C-SEC-3 | `log_safety_inventory` 脱敏工具存在, 无统一 sanitize 调用点 |
| C-COST-2 | `cost_per_1k_tokens=0.00005` 注释写 "¥0.05/1K tokens" 单位语义混乱 |
| C-STEP-1 | StepFun upstream 断流无 server-side 自动回退到 legacy ASR + tts_factory |

### 9.4 良好 (A/B 级) — 可作模式

| 维度 | 评级 |
|------|------|
| LLM 错误码统一性 | A |
| ASR 错误码统一性 | A |
| TTS 3 级降级声明完整 | A |
| KB Lock 主决策流 | A |
| ModelConfig 加密链路 (LLM/ASR/TTS) | A |
| StepFun 配置加载 (除加密) | A |
| TTS Edge-TTS voice 默认 | A |
| audio 访问控制 (ACL 403) | B |

---

## 10. 修复优先级建议

1. **Sprint-1 (阻断)**: F-SEC-1 (StepFun 加密) + F-OBS-1 (Prometheus 调用接入) + F-CFG-1 (TTS env 读取) — 可独立交付
2. **Sprint-2 (严重)**: F-ASR-1 + F-TTS-1 (要么接入降级链, 要么删除死代码) + D-CB-1 (熔断补全 Chroma/StepFun/LLM)
3. **Sprint-3 (改进)**: D-KNOW-1 双轨合并 + D-COST-1 Prometheus cost 导出 + D-LIMIT-1 中间件化
4. **后续**: D-SEC-2 销售训练音频 lifecycle; C-ASR-1 ≥ 2 备选; C-KB-1 文档同步

---

## 11. 与 Agent 1/2/3 的交叉对齐

| 项 | 涉及 Agent | 现状 |
|----|------------|------|
| voice_mode 工具函数重复 (main.py:33/36/47, sales_bot/websocket/router.py:340/347/417) | Agent 1 | **本审计无关**, 跳过 |
| `common/` 17/30 子目录无 `__init__.py` (PEP 420 混用) | Agent 1 | **本审计无关**, 跳过 |
| 限流未挂中间件 (仅装饰器) | Agent 1 | **本审计 §6.3 已交叉确认** — 与 Agent 1 结论一致 |
| Result 错误码规范 | Agent 2 | **本审计 §1.4/§2.5/§4.4 交叉确认** — AI 链路全合规, 无新增违规 |
| KB Lock 决策流 | Agent 2 | **本审计 §5.2/§5.3 已复核** — 4 主状态码 + 3 衍生码与 CLAUDE.md §3 一致, 仅文档未列 coach_* |
| StepFun vs legacy 切换路径 | Agent 3 | **本审计 §3 已交叉** — `_stepfun_url/model/voice` 全 env 装载, 仅加密缺失 |

---

> 审计者: 严苛架构师
> 报告版本: 2026-06-03
> 待与 Agent 5/6/7 交叉确认
