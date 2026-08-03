# 新人录音评测运行手册

## 适用范围

本手册覆盖首发的两类完整文件录音：`audio_assessment`（录音讲解）和 `assignment`（固定 discovery / objection / commitment 三段异步客户场景）。两类活动共用 `audio_assessment.pipeline.process` 持久任务，不包含实时音频流、实时转写或 AI 客户实时对练。

PostgreSQL 是 UploadSession、Submission、TranscriptRevision、ScoreOutcomeVersion、DurableTask 和审计的事实源。对象存储保存不可变原始/标准化音频；浏览器 IndexedDB 只保存尚未被服务端确认的本地草稿，不是正式提交。

## 发布前检查

1. 先执行 Alembic migration，再启动 API 和独立 Worker；应用启动不创建表。
2. Worker 节点必须安装可执行的 `ffmpeg` 与 `ffprobe`，并允许临时目录容纳单个最大 100MB 原始录音及标准化副本。
3. 对象存储、LLM 和 ASR 凭据必须由部署 Secret 提供，不能写入命令、日志或前端。
4. 已发布资源必须包含当前 PathRevision 引用的材料/场景与 ScorecardRevision。
5. 正式评分引用的 PromptRevision、ModelRoutingRevision、输入/输出 Schema 必须存在且已发布。标准包只冻结引用，不替部署环境创建 Provider/model。
6. 使用 Fake Provider 的 contract/integration 测试和目标环境 Gold Set/校准必须通过；未校准路由只能 shadow，不能生成正式结果。

建议的发布顺序：

```bash
cd backend
alembic upgrade head

PYTHONPATH=src python -m uvicorn src.main:app --host 0.0.0.0 --port 3444

TASK_WORKER_TASK_TYPES=audio_assessment.pipeline.process \
PYTHONPATH=src python -m task_runtime.worker_main
```

Worker 的通用 Lease、probe、扩缩容和停机合同见 [`durable-task-worker-runbook.md`](durable-task-worker-runbook.md)。API 与 Worker 必须使用同一数据库和同一对象存储 backend；否则会出现对象校验/物化失败，但不会伪造完成。

## 配置

### 首发开关已退役

开发期的 `NEWCOMER_AUDIO_ASSESSMENT_ENABLED`、`NEWCOMER_ASYNC_ASSIGNMENT_ENABLED` 环境开关已在首发 Clean Cut 中删除。它们没有组织范围、审计、过期时间或一致的多实例传播，不能作为正式运营权威。录音讲解和异步客户场景现在只由冻结 PathRevision、ReleasePlan、Cohort/Enrollment 状态和组织范围 TaskTypeControl 决定。

需要停止新范围时，回滚当前 ReleasePlan 并暂停对应 Cohort/新分配；需要停止后台处理时，通过受保护的 Task Runtime Operator 命令暂停 `audio_assessment.pipeline.process`，填写原因并保留审计。不要重新引入环境变量开关，也不要恢复旧同步 writer。

### 文件、上传与质量规则

首发标准包冻结以下默认值；后端快照是权威，前端只用于提前提示和拦截：

- 单段最长 30 分钟、最大 100MB；
- 分片目标 5MB；上传会话 24 小时过期；
- 浏览器本地草稿 7 天过期，退出登录清理；
- ASR 置信度、语音/静音、削波和平均音量阈值来自冻结 ScorecardRevision；
- 超限、损坏和不支持格式属于确定性失败；音质不足属于“无法评分/需人工处理”，不能记零分。

不要直接改数据库中的冻结快照。规则调整必须创建并发布新修订；已开始 Attempt 继续使用原快照。

### 媒体工具

| 变量 | 默认 | 说明 |
|---|---|---|
| `AUDIO_FFMPEG_BINARY` | `ffmpeg` | 标准化和静音/音量分析可执行文件 |
| `AUDIO_FFPROBE_BINARY` | `ffprobe` | 媒体头、时长、采样率和声道探测 |

Worker 将录音标准化为 16kHz、单声道 PCM WAV，并在 Artifact 中记录实际工具版本。工具缺失进入可恢复失败并保留原始音频；损坏、空音频或确定性不支持格式进入终态并提示重新上传。

### 对象存储

| 变量 | 默认 | 说明 |
|---|---|---|
| `AUDIO_ASSESSMENT_STORAGE_BACKEND` | `local` | `local`、`oss` 或 `cos`；旧 `SALES_TRAINER_AUDIO_STORAGE_BACKEND` 仅作为部署配置 fallback |
| `AUDIO_ASSESSMENT_LOCAL_STORAGE_PATH` | `./data/audio_assessment` | 仅本地开发 backend 使用 |

`local` 通过受权限保护的 API 流式写单个 part；`oss/cos` 返回签名 URL 让浏览器直传。服务端在登记 part 和 Worker 物化前重新验证对象大小、SHA-256 和受控 key。业务 key 由后端按组织/Run/UploadSession 生成，不能由用户提供。

云存储必须支持签名 PUT/GET、metadata HEAD、下载、上传标准化文件和删除未完成 part；签名 GET 默认只用于短时试听。API 不返回底层 storage key。

### ASR 与评分

完整文件 ASR 当前受治理适配器使用 `DASHSCOPE_API_KEY` 和 `SALES_TRAINER_ASR_*` 文件转写配置；`AUDIO_ASR_LANGUAGE` 默认 `zh-CN`。评分 LLM 连接、endpoint、模型和成本配置沿用 [`durable-task-worker-runbook.md`](durable-task-worker-runbook.md) 的受治理 AI Worker 配置。

正式合同必须与 [`../api-contract/newcomer-training-v2.md`](../api-contract/newcomer-training-v2.md) §3.3 一致：ASR 不携带 Prompt lineage；评分严格编译精确 PromptRevision，并为每次真实动态输入计算 `sha256:` contract hash。缺 Prompt、路由、Schema、Provider 或校准条件时 fail closed。

## 流水线与恢复位置

正常顺序为：

`uploading → uploaded → validating → normalizing → transcribing → transcript_ready → scoring → reconciling → completed`

每次 `audio_assessment.pipeline.process` 只在短事务中读取/写入状态；对象存储、ffmpeg/ffprobe、ASR 和 LLM IO 均在数据库事务外执行。相同业务幂等键、AI invocation 和 reconcile 重放不会产生重复 Transcript、ScoreOutcomeVersion、通用 Outcome 或 Outbox 事件。

| 分类 | 典型原因 | 结果与操作 |
|---|---|---|
| 上传完整性 | part 缺失、大小/hash 不一致、对象不可读 | 原草稿/已上传 part 保留；恢复对象存储后续传或从 `validation` 精确重试 |
| 媒体确定性失败 | 空文件、损坏、超时长、不支持格式 | `failed_terminal`；要求重新录制/上传，不重跑 Provider |
| 媒体暂时失败 | 工具缺失、标准化产物暂时无法保存 | `failed_recoverable`；修复工具/存储后从 `normalization` 重试 |
| ASR 暂时失败 | timeout、429、网络、空/invalid schema | 保留标准化音频，从 `transcription` 重试；不写空 Transcript |
| 质量不足 | 低置信度、语音不足、语言不符、静音/削波超阈值 | `needs_review/not_scorable`；重录或人工处理，不写零分/未通过证据 |
| 评分暂时失败 | Prompt 编译、路由、Provider 或 Schema 失败 | 保留音频与 Transcript，从 `scoring` 重试；不写固定分 |
| 结果对账 | Outcome 写入/Outbox 失败 | `reconciling`；修复后安全重放，不把任务成功当业务完成 |

学员可从 Activity Workspace 对当前失败阶段执行 `retry_stage`。管理员可在录音队列确认失败分类后调用：

```text
GET  /api/v1/admin/newcomer-training/audio-assessments/queue
POST /api/v1/admin/newcomer-training/audio-submissions/{id}/commands/repair
```

`repair` 只接受可恢复失败或对账状态，必须携带 capability、组织/对象 scope、原因和 `Idempotency-Key`，并保留审计。禁止手工更新 Submission/DurableTask 状态。

Transcript 更正、重转写/重评和失效必须先 preview，再以相同未过期 token + impact hash + reason confirm；只追加新版本，不覆盖历史。统一管理工作台 UI 由切片 6 接入，本切片的 API/队列是后端运营权威。

## 未完成上传自动清理

部署级 Cron/CronJob 必须周期运行有界清理命令；建议每 15 分钟执行一次：

```bash
cd backend
PYTHONPATH=src ./.venv/bin/python scripts/cleanup_foundation_audio_uploads.py --limit 100
```

命令输出 `claimed_count`、`expired_count`、`cleaned_count`、`failed_count`。部分对象删除失败时退出码为 `2`，应告警并在下一周期重试。

清理服务只领取 `expired/cancelled` 或已超过 TTL 的 `uploading` 会话。领取使用行锁、claim token 和 15 分钟 stale-claim 恢复；数据库 claim 提交后才在事务外删除对象，完成写入由 token fencing 保护。它不会删除 `finalized` 会话、正式原始 Artifact、标准化 Artifact、Transcript 或评分历史。

多实例可以并发运行，但单次 `--limit` 必须在 1～1000；不要用无界循环替代部署调度，也不要直接删除数据库行来“清理”。

## 数据保留、访问与删除

- 浏览器未完成草稿：默认 7 天；过期或退出登录由客户端删除。服务端尚未确认前不得因上传失败自动删草稿。
- 服务端未完成 part：UploadSession 默认 24 小时；过期/取消后由上述 fenced cleanup 删除对象，数据库会话和尝试次数保留作审计。
- 已 finalized 的原始/标准化音频、TranscriptRevision、QualityReport、ScoreOutcomeVersion、审核/失效历史：首发采用 fail-safe 保留，不由未完成上传清理器删除。组织级法定保留/删除仍必须通过独立批准的 retention/erasure 工作流和有租约任务实施；在该治理能力明确发布前，禁止临时脚本、单表删除或对象存储生命周期规则批量清除正式证据。
- 试听/下载、跨组织拒绝、管理员更正、重评、失效和人工处理都必须做对象级权限校验并审计。日志和任务 payload 不得含音频 bytes、完整 Transcript、Prompt 正文、raw Provider payload、Secret 或签名 URL。
- 合法删除请求在正式 retention/erasure 工作流上线前必须进入安全/隐私人工流程；只能在确认组织范围、证据/申诉保留义务和审计后执行补偿，不能手工删单表造成悬空 lineage。

## 监控与告警

至少按 `domain=audio_assessment, workload=full_file_pipeline` 观察：

- queued/running/retry_wait/dead_letter 数、最老任务等待时间和 Lease 过期；
- 从 finalize 到 completed 的 p50/p95（目标 p95 ≤ 90 秒）以及各阶段耗时；
- 上传确认耗时（目标 ≤ 2 秒）、对象 HEAD/hash/下载/写入失败率；
- `failed_recoverable`、`failed_terminal`、`needs_review` 和 `reconciling` 的数量/停留时间；
- ASR/评分 timeout、429、schema invalid、Prompt/route 缺失、fallback/degradation、成本；
- cleanup `failed_count`、最老未清理 expired session 和 stale claim 数；
- 跨组织/越权试听与高风险命令拒绝量。

告警中只使用 task/submission/artifact opaque ID 和安全错误分类。需要查看内容时必须从授权业务页面进入，不从日志复制音频或 Transcript。

## 回滚与降级

1. 回滚当前 ReleasePlan 到已知稳定修订，并暂停受影响 Cohort 的新分配；既有 Enrollment 继续冻结，不做隐式迁移。
2. 使用组织范围、受审计的 Task Runtime Operator 命令暂停 `audio_assessment.pipeline.process`；让在途任务完成，或通过协作式取消请求在安全 checkpoint 停止。不要直接改任务状态。
3. Provider 故障时保持 Worker/队列和用户输入，修复路由后从精确阶段重试；不能切回固定分、同步请求处理或未治理 Provider。
4. 如需回退应用，先保留当前数据库、对象存储和任务表，部署兼容的上一应用版本并保持新写关闭。旧录音写 API/BackgroundTask 已退役，不能作为回滚写权威重新开启。
5. Alembic downgrade 只允许无业务数据的开发环境；生产恢复使用前向修复/新迁移，不能删除正式录音和版本历史。

回滚完成后验证：学员无法开始新录音、历史授权试听仍可用、已有任务/失败位置仍可查询、无新旧双写、未完成上传清理仍按策略运行。
