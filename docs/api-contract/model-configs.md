# 模型配置契约（`model-configs`）

> 状态：✅ 已实现  
> 前缀：`/api/v1/admin/model-configs`

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

