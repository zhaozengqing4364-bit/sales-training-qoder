# 模型配置契约（`model-configs`）

> 状态：✅ 已实现  
> 前缀：`/api/v1/admin/model-configs`

## Prompt/runtime dependency routing

- `provider` / `base_url` / `model_name` 是 legacy evaluation/report compiled prompt contract 的运行时前提；`PromptTemplateService.compile_runtime_prompt_contract(...)` 会读取当前 LLM model config 并生成对应的 `base_url` policy diagnostics。
- 如果 provider 要求 `base_url` 但当前配置缺失，运行时会 fail-closed 并显式返回 `[PROMPT_CONTRACT_BASE_URL_REQUIRED]`，修复入口是 `/admin/model-configs`，不是继续修改 prompt template 文本或 persona policy。
- 这个 surface 决定的是 compiled prompt contract 能否执行，不负责选择 prompt source，也不会单独生成新的 StepFun `instruction_contract_hash`。

## 1) 数据模型（`ModelConfig`）

```ts
interface ModelConfig {
  id: string;
  name: string;
  model_type: 'llm' | 'embedding' | 'asr' | 'tts';
  provider: 'openai' | 'azure' | 'alibaba' | 'anthropic' | 'local' | 'local_streaming';
  base_url: string;
  api_key_masked: string;
  model_name: string;
  extra_config: Record<string, unknown>;
  is_default: boolean;
  is_active: boolean;
  last_tested_at?: string | null;
  last_test_status?: string | null;
  created_at: string;
  updated_at: string;
}
```

## 2) 接口

- `POST /`：创建配置
- `GET /`：分页列表
  - query: `model_type?`, `provider?`, `is_active?`, `page`, `page_size`
- `GET /{config_id}`：详情
- `PUT /{config_id}` / `PATCH /{config_id}`：更新
- `DELETE /{config_id}`：删除
- `POST /{config_id}/test`：测试指定配置
- `POST /test`：使用临时参数执行内联测试
- `POST /tts/preview`：生成 TTS 预览音频

## 3) 响应格式

成功：

```json
{
  "success": true,
  "data": {},
  "trace_id": "..."
}
```

失败：

```json
{
  "success": false,
  "error": "...",
  "error_code": "[MODEL_CONFIG_...]",
  "trace_id": "..."
}
```

## 4) 常见错误码

- `[MODEL_CONFIG_NOT_FOUND]`
- `[MODEL_CONFIG_PROVIDER_NOT_SUPPORTED]`
- `[MODEL_CONFIG_BASE_URL_REQUIRED]`
- `[MODEL_CONFIG_API_KEY_REQUIRED]`
- `[MODEL_CONFIG_CREATE_FAILED]`
- `[MODEL_CONFIG_UPDATE_FAILED]`
- `[MODEL_CONFIG_DELETE_FAILED]`

