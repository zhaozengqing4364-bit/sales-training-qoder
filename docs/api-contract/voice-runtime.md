# 语音运行时契约（`voice-runtime`）

> 状态：✅ 已实现（2026-02-16 更新）  
> 前缀：`/api/v1/admin/voice-runtime`

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
- `[FIELD_DEPRECATED_PERSONA_CENTERED]`（尝试覆盖 Persona 所有权工具策略键）

兼容收敛说明：
- `system_instruction_template` 与 `instructions_override` 已从 API 写入契约移除。
- 请求体若继续携带上述旧字段，会触发 FastAPI 请求校验失败（`422`，`extra_forbidden`）。
