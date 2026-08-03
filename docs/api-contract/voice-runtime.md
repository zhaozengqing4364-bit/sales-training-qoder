# 语音运行时契约（`voice-runtime`）

> 状态：✅ 已实现（2026-02-16 更新）  
> 前缀：`/api/v1/admin/voice-runtime`

> 首发基线说明（2026-07-15）：下文 `088`、`089` 是首发前历史 revision 的行为证据，现已归档到 `backend/alembic/archive/prelaunch_20260715/`；它们的最终 schema 与默认值已吸收到活动基线 `20260715_0000_001`，新数据库不会逐条执行这些归档 revision。首发后的任何变更必须从当前唯一 head 新增线性 revision，不能修改或重新激活归档历史。

## Authority boundary（M021/S02 contract sync）

- **live compiled prompt authority**：`VoiceRuntimePolicyService` + `VoiceInstructionCompiler` 会把 `persona_policy`、customer pressure、runtime profile 的 `tool_policy` 编译进 `voice_policy_snapshot.instructions` 与 `instruction_contract_hash`；这条 compiled artifact 才是新的 StepFun / presentation 会话真正执行的实时指令合同。
- **runtime guardrail authority**：`network_access_mode`、`require_kb_grounding`、`allow_web_search_without_kb`、`retrieval_priority` 等字段不只是配置展示，它们会同时改变 compiled instruction 文本与 StepFun tool surface。
- **frozen snapshot rule**：这些调整默认影响“下一次会话创建 / effective policy preview”；已经落库的 `voice_policy_snapshot` 不会被 prompt admin 页面回写覆盖。
- **not the legacy template authority**：如果目标是修改 legacy evaluation/report 的 compiled prompt，入口在 `prompt-templates` / `scenario-prompts`；如果 diagnostics 指向 `base_url` 缺失，则修复入口在 `model-configs`，而不是继续改 runtime profile。

## 1) Runtime Profile（`VoiceRuntimeProfile`）

### 数据结构（核心字段）

```ts
interface VoiceRuntimeProfile {
  id: string;
  name: string;
  description?: string | null;
  is_default: boolean;
  is_active: boolean;
  voice_mode: 'legacy' | 'stepfun_realtime';
  model_name: string;
  voice_name: string;
  temperature: number;
  input_audio_format: string;
  output_audio_format: string;
  output_sample_rate: number;
  turn_detection?: string | null;
  tool_policy: Record<string, unknown>;
}
```

`tool_policy` 关键字段（新增）：

```ts
interface ToolPolicy {
  enable_web_search: boolean;
  enable_internal_retrieval: boolean;
  retrieval_priority: 'kb_only' | 'kb_first' | 'web_first' | 'balanced';
  network_access_mode: 'off' | 'controlled'; // 默认 off，强制禁网
  enforcement_level: 'strict' | 'best_effort'; // 默认 strict
  allow_web_search_without_kb: boolean; // 默认 false
  require_kb_grounding: boolean; // 默认 false，开启后每轮必须命中知识库才允许生成
}
```

约束规则：
- `voice_mode` 仅允许 `legacy | stepfun_realtime`，非法值会触发请求校验失败（`422`）
- `network_access_mode=off` 时必须禁用 `web_search`（与是否绑定知识库无关）
- 绑定知识库时，系统会强制 `retrieval_priority=kb_only`
- 未绑定知识库且 `allow_web_search_without_kb=false` 时，同样禁用 `web_search`
- `require_kb_grounding=true` 时进入知识库硬锁模式：
  - 每轮必须先检索内部知识并命中可引用片段，才允许生成回答
  - 未绑定知识库 / 文档未就绪 / 检索失败 / 未命中都会触发阻断回复
- `system_instruction_template` 已收敛到角色中心，不允许继续通过 Runtime Profile 写入。

### StepFun Realtime upstream contract

销售实时对练使用共享 `StepFunTransport` 连接 StepFun 上游，运行时契约如下：

- URL：默认 `wss://api.stepfun.com/v1/realtime`，可通过 `STEPFUN_REALTIME_URL` 覆盖；如果使用 Step Plan 订阅凭证，应先在控制台或官方支持确认 Realtime 专用路径，再显式配置对应 `wss://api.stepfun.com/step_plan/v1/realtime` 形态的 URL。
- 模型：作为 query 参数传递，形态为 `?model=<model_name>`；当前按本任务要求默认模型为 `stepaudio-2.5-realtime`。`StepFunTransport` 必须结构化追加或替换 `model` query，禁止用字符串拼接产生重复 `?` 或把 key 写入 URL。
- 鉴权：只通过 WebSocket handshake header `Authorization: Bearer <STEPFUN_API_KEY>` 传递，不允许把 key 写入 URL、query、日志、trace 或前端 payload。
- 密钥来源：`STEPFUN_API_KEY` 只允许来自环境变量/密钥管理，不属于 `VoiceRuntimeProfile`、`sales_trainer.realtime_provider.registry`、migration seed、审计日志或运行时 snapshot 字段。后台配置只能保存 `provider`、`model_name`、URL、readiness 和 masked/configured 状态；任何 API 响应和日志只能显示 `<configured>` / `<missing>` 或 hash/trace 元数据。
- 上游 401：统一分类为 `[STEPFUN_UPSTREAM_REJECTED]`，operator-facing reason 是 `upstream_auth_rejected`，表示本地 learner auth、seed、path/start/WS 链路已经到达上游，但 StepFun 拒绝握手；处理动作是检查 `STEPFUN_API_KEY` 是否有效、是否开通 realtime 权限，以及是否授权对应 `model_name`。
- 上游 402/403/429：同样属于真实 provider executed failure，不得降级为 local provider 通过；门禁 evidence 必须保留失败分类。

### StepAudio 2.5 首发前 migration 历史契约

- 历史 apply 行为：归档 revision `20260702_1100_088_stepfun_default_model_stepaudio25` 当时只把 `voice_runtime_profiles.model_name` 的服务端默认值切到 `stepaudio-2.5-realtime`，并仅更新 `is_default=true AND voice_mode='stepfun_realtime' AND model_name='step-audio-2.3'` 的默认 profile；它不得写入、复制或打印 `STEPFUN_API_KEY`。当前空库直接由首发 baseline 建立最终状态。
- 历史 rollback 行为：该归档 revision 的 downgrade 当时只把同一条件下的默认 profile 从 `stepaudio-2.5-realtime` 回退到 `step-audio-2.3`，并恢复 server default；已经显式配置为其他模型的 profile 不应被覆盖。它不再是首发后的发布回滚入口。
- Apply/rollback 前后都必须运行 `scripts/check_stepfun_realtime_prereqs.py --env-file backend/.env` 或等价环境预检；预检报告必须只包含 redacted key 状态和 `endpoint_without_secret`。
- 如果 StepFun 控制台未授权 `stepaudio-2.5-realtime`，这是 provider readiness failure，返回 `[STEPFUN_UPSTREAM_REJECTED]` 或 registry readiness diagnostic；不得把模型自动降级为 legacy/local provider 作为成功。

### StepFun Realtime roleplay observation sidecar

`roleplay_observation_v1` 是 StepFun realtime 的后台复盘旁路，不是实时守门路径：

- StepFun roleplay compliance 的全局运行模式固定为 `record_only`。`roleplay_observation_policy` 只能选择观测器、采样和后台评估方式，不能把当前 turn 改成阻断、重生成、修复或关闭连接模式。
- `main_chain_effect="none"`，任何 capture sink、heuristic evaluator、可选 LLM evaluator、DB 写入或 admin 读取失败都不得改变 WebSocket 主链路状态。
- current turn 的角色一致性检查只做 record-only 记录；不得在 learner 实时对练中弹窗、阻断、取消当前上游响应、关闭 WebSocket、同步重生成、repair/re-synthesize audio 或无限重试。
- next-turn soft steering 只允许作为非阻断、可审计的下一轮提示建议：必须记录 `session_id`、`turn_index`、`source`、`signal_key`、建议内容摘要、`trace_id` 和是否被下一轮编译消费；生成、写库或消费失败都不得阻断当前或下一轮主链路。
- 旧同步 `cancel_current_turn` / `regenerate_current_turn` / `repair_audio` 类动作正式退役；不得通过隐藏环境变量、未登记 feature flag 或 policy 私有字段重新开启。若未来要恢复任何阻断/中断/同步修复能力，必须新增 ADR 明确状态机、UX、错误码、审计、回滚和测试矩阵；当前 record-only 决策记录在 `docs/adr/2026-07-03-roleplay-realtime-record-only.md`。
- observation policy 优先读取冻结的 `voice_policy_snapshot.roleplay_observation_policy`；缺失或非法时回退到 bundled default：同步 `heuristic.enabled=true`、后台 `llm.enabled=false`。
- 若 policy 开启 `llm.enabled=true`，sink 仍先同步写 `source="heuristic"`，再后台执行 `evaluate_background()` 并写入独立 `source="llm_evaluator"` observation；LLM timeout/失败只允许写 `failed` observation / diagnostic，不得阻断 WS。
- capture metadata 只能包含 `session_id`、`turn_index`、`source_event_type`、`response_id`、`turn_id`、`instruction_contract_hash`、安全 grounding 摘要和 `trace_id`；不得保存 thinking、secret、Authorization、Cookie、API key、JWT、LLM provider key、StepFun handshake headers 或完整上游 payload。
- observation 历史 migration：归档 revision `20260702_1530_089_sales_trainer_roleplay_observations` 当时只创建 append-only 观测表和索引；首发 baseline 已直接包含该最终结构。该归档 revision 的 apply 不回填历史 turn，rollback 只删除 sidecar 表且不得修改 `practice_sessions`、训练记录或 runtime snapshot。首发后不得通过重新执行归档 downgrade 删除数据；业务回滚优先停止注入 sink/隐藏读取入口，若未来确需 schema 变更必须新增受审查 revision。
- 读取入口在 `GET /api/v1/admin/sales-trainer/training-records/realtime-roleplay/{session_id}/observations`，权限和对象级范围由 sales trainer training records contract 约束。

### 接口

- `GET /profiles`：获取运行时配置列表
  - query: `only_active?: boolean`
- `POST /profiles`：创建运行时配置
- `PUT /profiles/{profile_id}`：更新运行时配置（部分字段可选）
- `DELETE /profiles/{profile_id}`：删除运行时配置

统一响应：

```json
{
  "success": true,
  "data": {"items": [], "total": 0},
  "trace_id": "..."
}
```

失败响应同样使用统一 envelope：

```json
{
  "success": false,
  "error": "[VOICE_RUNTIME_PROFILE_NOT_FOUND]",
  "message": "运行时配置不存在。",
  "trace_id": "trace-xxx"
}
```

## 2) Agent Voice Policy（`AgentVoicePolicy`）

### 数据结构（核心字段）

```ts
interface AgentVoicePolicy {
  enabled: boolean;
  runtime_profile_id?: string | null;
  voice_mode_override?: 'legacy' | 'stepfun_realtime' | null;
  model_override?: string | null;
  voice_override?: string | null;
  temperature_override?: number | null;
  tool_policy_override: Record<string, unknown>;
}
```

`tool_policy_override` 仅允许技术运行时相关键，以下键位于 Persona 侧并被禁止在 Agent 侧覆盖：
- `enable_web_search`
- `enable_internal_retrieval`
- `retrieval_priority`
- `strict_instruction_following`
- `require_grounding`
- `network_access_mode`
- `enforcement_level`
- `allow_web_search_without_kb`
- `require_kb_grounding`

### 接口

- `GET /agents/{agent_id}/policy`：查询 Agent 语音策略
- `PUT /agents/{agent_id}/policy`：创建/更新 Agent 语音策略
- `GET /agents/{agent_id}/effective`：预览生效后的合并策略
  - query: `persona_id?`, `voice_mode_override?`, `runtime_profile_id?`

生效策略新增审计字段：
- `instruction_contract_hash`：系统角色契约哈希，用于验证每轮是否沿用同一角色约束
- `network_access_mode`：当前会话网络访问模式（`off` / `controlled`）
- `persona_policy`：当前会话生效的角色中心策略（提示词/知识库/工具策略）
- `knowledge_base_ids`：从角色策略解析后的知识库绑定列表

## 3) 错误码（常见）

- `[VOICE_RUNTIME_PROFILE_NOT_FOUND]`
- `[VOICE_RUNTIME_PROFILE_CREATE_FAILED]`
- `[VOICE_RUNTIME_PROFILE_UPDATE_FAILED]`
- `[VOICE_RUNTIME_PROFILE_DELETE_FAILED]`
- `[AGENT_VOICE_POLICY_UPSERT_FAILED]`
- `[AGENT_NOT_FOUND]`（更新 Agent voice policy 时目标 Agent 不存在）
- `[FIELD_DEPRECATED_PERSONA_CENTERED]`（尝试覆盖 Persona 所有权工具策略键）

兼容收敛说明：
- `system_instruction_template` 与 `instructions_override` 已从 API 写入契约移除。
- 请求体若继续携带上述旧字段，会触发 FastAPI 请求校验失败（`422`，`extra_forbidden`）。
